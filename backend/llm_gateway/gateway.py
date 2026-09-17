import json
import logging
import re

from ai_guardrails import GuardrailViolation, check_input, check_output, check_tool
from .exceptions import AllProvidersFailed
from .providers import call_claude, call_gemini, call_openai
from .routing import provider_order
from .telemetry import RequestTimer, record_request, request_id
from Chat.tools import execute_tool_call

logger = logging.getLogger(__name__)


class LLMGateway:
    def generate(self, messages, provider='openai', response_format=None, fallback_order=None):
        check_input(messages)
        providers = provider_order(provider, fallback_order)
        call_id = request_id()
        failures = []

        direct_tool = self._direct_tool_call(messages)
        if direct_tool:
            tool_name, arguments = direct_tool
            check_tool(tool_name, arguments)
            tool_result = execute_tool_call(tool_name, arguments)
            result = {'role': 'assistant', 'content': f'Tool result: {tool_result}', 'provider': provider, 'tool_name': tool_name, 'tool_response': str(tool_result)}
            check_output(result)
            record_request({'request_id': call_id, 'provider': provider, 'tool_name': tool_name, 'fallback_used': False, 'success': True})
            return result

        for current_provider in providers:
            try:
                with RequestTimer() as timer:
                    response = self._call_provider(current_provider, messages, response_format)
                    response = self._handle_model_tool(response, messages, current_provider, response_format)
                    response['provider'] = current_provider
                    response['content'] = self._clean_response(response.get('content', ''), response_format)
                    check_output(response)
                if current_provider != provider:
                    response['fallback_reason'] = ' | '.join(failures) or f'{provider} was unavailable, response served by {current_provider}.'
                record_request({'request_id': call_id, 'provider': current_provider, 'latency_ms': timer.latency_ms, 'fallback_used': current_provider != provider, 'success': True})
                return response
            except GuardrailViolation:
                raise
            except ValueError:
                if response_format and response_format.get('type') == 'json':
                    raise
                raise
            except Exception as exc:
                failures.append(f'{current_provider} failed: {exc}')
                logger.warning('Gateway provider %s failed: %s', current_provider, exc)

        record_request({'request_id': call_id, 'provider': provider, 'fallback_used': bool(failures), 'success': False})
        raise AllProvidersFailed(f'AI provider failed: {failures[-1] if failures else "no providers configured"}')

    def _call_provider(self, provider, messages, response_format):
        providers = {'openai': call_openai, 'claude': call_claude, 'gemini': call_gemini}
        return providers[provider](messages, response_format=response_format)

    def _handle_model_tool(self, response, messages, provider, response_format):
        tool_call = self._extract_tool_call(response.get('content', ''))
        if not tool_call:
            if response_format and response_format.get('type') == 'json':
                parsed = self._parse_json(response.get('content', ''))
                if parsed is None:
                    raise ValueError('Structured output could not be parsed as JSON.')
                self._validate_schema(parsed, response_format.get('schema'))
                response['parsed'] = parsed
            return response

        tool_name = tool_call['name']
        arguments = tool_call.get('arguments', {}) or {}
        check_tool(tool_name, arguments)
        tool_result = execute_tool_call(tool_name, arguments)
        messages_with_tool = list(messages) + [
            {'role': 'assistant', 'content': response.get('content', '')},
            {'role': 'tool', 'content': str(tool_result), 'tool_name': tool_name, 'tool_response': str(tool_result)},
        ]
        follow_up = self._call_provider(provider, messages_with_tool, response_format)
        follow_up['tool_name'] = tool_name
        follow_up['tool_response'] = str(tool_result)
        if response_format and response_format.get('type') == 'json':
            parsed = self._parse_json(follow_up.get('content', ''))
            if parsed is None:
                raise ValueError('Structured output could not be parsed as JSON.')
            self._validate_schema(parsed, response_format.get('schema'))
            follow_up['parsed'] = parsed
        return follow_up

    @staticmethod
    def _direct_tool_call(messages):
        user_message = next((message for message in reversed(messages) if message.get('role') == 'user'), None)
        content = (user_message.get('content') or '') if user_message else ''
        match = re.search(r'calculate\s+(.+)', content, re.IGNORECASE)
        if match:
            return 'calculate', {'expression': match.group(1).strip()}
        match = re.search(r'weather\s+in\s+(.+)', content, re.IGNORECASE)
        if match:
            return 'get_weather', {'location': match.group(1).strip()}
        return None

    @staticmethod
    def _extract_tool_call(content):
        if not content:
            return None
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, dict):
                nested_call = parsed.get('toolCall') or parsed.get('tool_call')
                name = parsed.get('tool_name')
                call = nested_call if isinstance(nested_call, dict) else {}
                name = name or call.get('name')
                if name:
                    return {'name': str(name).lower(), 'arguments': parsed.get('arguments') or call.get('arguments') or {}}
        except (TypeError, json.JSONDecodeError):
            pass
        match = re.search(r'tool\s+call[:\s]*([a-zA-Z0-9_]+)\s*\((.*)\)', content, re.IGNORECASE)
        if match:
            name, arguments = match.group(1).lower(), match.group(2).strip()
            if name == 'calculate':
                return {'name': name, 'arguments': {'expression': arguments}}
            if name == 'weather':
                return {'name': 'get_weather', 'arguments': {'location': arguments}}
            return {'name': name, 'arguments': {}}
        return None

    @staticmethod
    def _parse_json(content):
        try:
            return json.loads(content)
        except (TypeError, json.JSONDecodeError):
            match = re.search(r'\{.*\}', content or '', re.DOTALL)
            try:
                return json.loads(match.group(0)) if match else None
            except json.JSONDecodeError:
                return None

    @staticmethod
    def _validate_schema(data, schema):
        if not schema:
            return
        schema_type = schema.get('type')
        if schema_type == 'object':
            if not isinstance(data, dict):
                raise ValueError('Structured output failed schema validation: expected object')
            for key in schema.get('required', []):
                if key not in data:
                    raise ValueError(f"Structured output failed schema validation: missing '{key}'")
            for key, value in data.items():
                if key in schema.get('properties', {}):
                    LLMGateway._validate_schema(value, schema['properties'][key])
        elif schema_type == 'array':
            if not isinstance(data, list):
                raise ValueError('Structured output failed schema validation: expected array')
            for item in data:
                LLMGateway._validate_schema(item, schema.get('items'))
        elif schema_type == 'string' and not isinstance(data, str):
            raise ValueError('Structured output failed schema validation: expected string')
        elif schema_type == 'integer' and (not isinstance(data, int) or isinstance(data, bool)):
            raise ValueError('Structured output failed schema validation: expected integer')
        elif schema_type == 'number' and (not isinstance(data, (int, float)) or isinstance(data, bool)):
            raise ValueError('Structured output failed schema validation: expected number')
        elif schema_type == 'boolean' and not isinstance(data, bool):
            raise ValueError('Structured output failed schema validation: expected boolean')

    @staticmethod
    def _clean_response(text, response_format=None):
        if not text or (response_format and response_format.get('type') == 'json'):
            return text
        text = re.sub(r'```.*?```', '', text, flags=re.S)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.M)
        text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', lambda match: match.group(1) or match.group(2), text)
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        return text.strip()


gateway = LLMGateway()