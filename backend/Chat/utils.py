import json
import logging
import os
import re
import time
import requests
from ai_guardrails import check_tool
from .tools import execute_tool_call

logger = logging.getLogger(__name__)


def _request_with_retries(url, headers, payload, provider):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f"{provider} API Error ({response.status_code}): {response.text}")
            if response.status_code in {429, 408, 500, 502, 503, 504} and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            break
        except requests.Timeout as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
    if last_error is None:
        raise RuntimeError(f"{provider} request failed without a captured error")
    raise last_error


def _prepare_messages(messages, max_messages=20):
    if not messages:
        return []

    system_messages = [message for message in messages if message.get("role") == "system"]
    other_messages = [message for message in messages if message.get("role") != "system"]
    if len(other_messages) > max_messages:
        other_messages = other_messages[-max_messages:]

    prepared = list(system_messages) + other_messages
    return [{
        "role": message.get("role", "user"),
        "content": message.get("content") or "",
    } for message in prepared]


def _parse_json_response(content):
    if not content:
        return None
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None


def _validate_against_schema(data, schema):
    if not schema:
        return True

    schema_type = schema.get("type")
    if schema_type == "object":
        if not isinstance(data, dict):
            raise ValueError("Structured output failed schema validation: expected object")
        properties = schema.get("properties", {})
        for required_key in schema.get("required", []):
            if required_key not in data:
                raise ValueError(f"Structured output failed schema validation: missing '{required_key}'")
        for key, value in data.items():
            prop_schema = properties.get(key)
            if prop_schema:
                _validate_against_schema(value, prop_schema)
        return True

    if schema_type == "array":
        if not isinstance(data, list):
            raise ValueError("Structured output failed schema validation: expected array")
        item_schema = schema.get("items")
        for item in data:
            _validate_against_schema(item, item_schema)
        return True

    if schema_type == "string":
        if not isinstance(data, str):
            raise ValueError("Structured output failed schema validation: expected string")
        return True

    if schema_type == "integer":
        if not isinstance(data, int) or isinstance(data, bool):
            raise ValueError("Structured output failed schema validation: expected integer")
        return True

    if schema_type == "number":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            raise ValueError("Structured output failed schema validation: expected number")
        return True

    if schema_type == "boolean":
        if not isinstance(data, bool):
            raise ValueError("Structured output failed schema validation: expected boolean")
        return True

    return True


def _extract_text_from_response(res_data, provider):
    if provider == "gemini":
        try:
            return res_data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return None
    if provider == "claude":
        try:
            return res_data["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            pass
        try:
            return res_data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None
    try:
        return res_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def _clean_response_text(text, response_format=None):
    if not text or (response_format and response_format.get("type") == "json"):
        return text

    clean = text
    clean = re.sub(r"```.*?```", "", clean, flags=re.S)
    clean = re.sub(r"`([^`]+)`", r"\1", clean)
    clean = re.sub(r"^#{1,6}\s*", "", clean, flags=re.M)
    clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
    clean = re.sub(r"__(.*?)__", r"\1", clean)
    clean = re.sub(r"\*(.*?)\*", r"\1", clean)
    clean = re.sub(r"_(.*?)_", r"\1", clean)
    clean = re.sub(r"^[-*+]\s*", "", clean, flags=re.M)
    clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", clean)
    clean = re.sub(r"^>\s*", "", clean, flags=re.M)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    return clean.strip()


def _extract_tool_call(content):
    if not content:
        return None

    try:
        parsed = json.loads(content.strip())
        if isinstance(parsed, dict):
            tool_name = parsed.get("tool_name") or parsed.get("toolCall", {}).get("name") or parsed.get("tool_call", {}).get("name")
            if tool_name:
                arguments = parsed.get("arguments") or parsed.get("toolCall", {}).get("arguments") or parsed.get("tool_call", {}).get("arguments") or {}
                return {"name": str(tool_name).lower(), "arguments": arguments}
    except (TypeError, json.JSONDecodeError):
        pass

    match = re.search(r"tool\s+call[:\s]*([a-zA-Z0-9_]+)\s*\((.*)\)", content, re.IGNORECASE)
    if match:
        tool_name = match.group(1).strip().lower()
        raw_args = match.group(2).strip()
        if tool_name == "calculate":
            return {"name": "calculate", "arguments": {"expression": raw_args}}
        if tool_name == "weather":
            return {"name": "get_weather", "arguments": {"location": raw_args}}
        return {"name": tool_name, "arguments": {}}

    if "calculate" in content.lower() and "(" in content:
        match = re.search(r"calculate\s*\((.+)\)", content, re.IGNORECASE)
        if match:
            return {"name": "calculate", "arguments": {"expression": match.group(1).strip()}}

    if "weather" in content.lower() and "in" in content.lower():
        match = re.search(r"weather\s+in\s+(.+)", content, re.IGNORECASE)
        if match:
            return {"name": "get_weather", "arguments": {"location": match.group(1).strip()}}

    return None


def call_openai(messages, response_format=None):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key is not configured. Please add it to your .env file.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    formatted = []
    for message in _prepare_messages(messages):
        formatted.append({
            "role": message["role"],
            "content": message["content"]
        })

    payload = {
        "model": "gpt-4o-mini",
        "messages": formatted,
    }
    if response_format and response_format.get("type") == "json":
        payload["response_format"] = {"type": "json_object"}

    response = _request_with_retries(url, headers, payload, "OpenAI")
    res_data = response.json()
    content = _extract_text_from_response(res_data, "openai")
    if content is None:
        raise RuntimeError(f"OpenAI response structure mismatch: {res_data}")
    return {"role": "assistant", "content": content}


def call_claude(messages, response_format=None):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Anthropic API key is not configured. Please add it to your .env file.")

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    formatted = []
    for message in _prepare_messages(messages):
        role = message["role"]
        if role not in ["user", "assistant", "system"]:
            role = "user"
        formatted.append({
            "role": role,
            "content": message["content"]
        })

    payload = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 1024,
        "messages": formatted,
    }
    if response_format and response_format.get("type") == "json":
        payload["system"] = "Return a valid JSON object."

    response = _request_with_retries(url, headers, payload, "Claude")
    res_data = response.json()
    content = _extract_text_from_response(res_data, "claude")
    if content is None:
        raise RuntimeError(f"Claude response structure mismatch: {res_data}")
    return {"role": "assistant", "content": content}


def call_gemini(messages, response_format=None):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API key is not configured. Please add it to your .env file.")

    model_name = "gemini-3.6-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    contents = []
    for message in _prepare_messages(messages):
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({
            "role": role,
            "parts": [{"text": message["content"]}]
        })

    payload = {"contents": contents}
    if response_format and response_format.get("type") == "json":
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    response = _request_with_retries(url, headers, payload, "Gemini")
    res_data = response.json()
    content = _extract_text_from_response(res_data, "gemini")
    if content is None:
        raise RuntimeError(f"Gemini response structure mismatch: {res_data}")
    return {"role": "assistant", "content": content}


def _call_provider(current_provider, messages, response_format=None):
    if current_provider == "openai":
        return call_openai(messages, response_format=response_format)
    if current_provider == "claude":
        return call_claude(messages, response_format=response_format)
    return call_gemini(messages, response_format=response_format)


def generate_chat_response(messages, provider="openai", response_format=None, fallback_order=None):
    allowed_providers = ["openai", "claude", "gemini"]
    if fallback_order:
        providers = [p for p in fallback_order if p in allowed_providers]
    else:
        fallback_priority = {
            "openai": ["openai", "claude", "gemini"],
            "claude": ["claude", "openai", "gemini"],
            "gemini": ["gemini", "openai", "claude"],
        }
        providers = fallback_priority.get(provider, [provider, "claude", "openai", "gemini"])

    providers = [p for p in providers if p in allowed_providers]
    if provider not in providers:
        providers.insert(0, provider)

    last_error = None
    tool_result = None
    fallback_details = []
    user_message = next((message for message in reversed(messages) if message.get("role") == "user"), None)
    if user_message:
        content = (user_message.get("content") or "").lower()
        if "calculate" in content:
            match = re.search(r"calculate\s+(.+)", content)
            if match:
                tool_result = execute_tool_call("calculate", {"expression": match.group(1).strip()})
        elif "weather" in content:
            match = re.search(r"weather\s+in\s+(.+)", content)
            if match:
                tool_result = execute_tool_call("get_weather", {"location": match.group(1).strip()})

    if tool_result is not None:
        return {
            "role": "assistant",
            "content": f"Tool result: {tool_result}",
            "provider": provider,
            "tool_result": tool_result,
        }

    for current_provider in providers:
        try:
            response_payload = _call_provider(current_provider, messages, response_format=response_format)
            tool_call = _extract_tool_call(response_payload.get("content", ""))
            if tool_call:
                tool_name = tool_call.get("name")
                tool_arguments = tool_call.get("arguments", {}) or {}
                check_tool(tool_name, tool_arguments)
                tool_result = execute_tool_call(tool_name, tool_arguments)
                messages_with_tool = list(messages)
                messages_with_tool.append({"role": "assistant", "content": response_payload.get("content", "")})
                messages_with_tool.append({
                    "role": "tool",
                    "content": str(tool_result),
                    "tool_name": tool_name,
                    "tool_response": str(tool_result),
                })
                follow_up_payload = _call_provider(current_provider, messages_with_tool, response_format=response_format)
                follow_up_payload["provider"] = current_provider
                follow_up_payload["tool_name"] = tool_name
                follow_up_payload["tool_response"] = str(tool_result)
                if current_provider != provider:
                    follow_up_payload["fallback_reason"] = " | ".join(fallback_details) if fallback_details else f"{provider} was unavailable, response served by {current_provider}."
                if response_format and response_format.get("type") == "json":
                    parsed = _parse_json_response(follow_up_payload.get("content", ""))
                    if parsed is None:
                        raise ValueError("Structured output could not be parsed as JSON.")
                    _validate_against_schema(parsed, response_format.get("schema"))
                    follow_up_payload["parsed"] = parsed
                return follow_up_payload

            if response_format and response_format.get("type") == "json":
                parsed = _parse_json_response(response_payload.get("content", ""))
                if parsed is None:
                    raise ValueError("Structured output could not be parsed as JSON.")
                _validate_against_schema(parsed, response_format.get("schema"))
                response_payload["parsed"] = parsed

            response_payload["provider"] = current_provider
            if current_provider != provider:
                response_payload["fallback_reason"] = " | ".join(fallback_details) if fallback_details else f"{provider} was unavailable, response served by {current_provider}."
            response_payload["content"] = _clean_response_text(response_payload.get("content", ""), response_format)
            return response_payload
        except Exception as exc:
            if response_format and response_format.get("type") == "json" and isinstance(exc, ValueError):
                raise
            reason = str(exc) if str(exc) else f"{current_provider} provider failed"
            fallback_details.append(f"{current_provider} failed: {reason}")
            last_error = exc
            logger.warning("Provider %s failed: %s", current_provider, exc)
            continue

    if last_error is None:
        raise RuntimeError("AI provider failed without a captured error")
    raise RuntimeError(f"AI provider failed: {last_error}")


def stream_chat_response(messages, provider="openai", response_format=None, fallback_order=None):
    response_payload = generate_chat_response(messages, provider=provider, response_format=response_format, fallback_order=fallback_order)
    text = response_payload.get("content", "") or ""
    chunk_size = max(1, len(text) // 12) if text else 1
    for index in range(0, len(text), chunk_size):
        chunk = text[index:index + chunk_size]
        yield chunk
        time.sleep(0.02)
    if not text:
        yield ""

