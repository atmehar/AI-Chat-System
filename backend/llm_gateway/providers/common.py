import json
import re
import time

import requests


def request_with_retries(url, headers, payload, provider):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response
            last_error = RuntimeError(f'{provider} API Error ({response.status_code}): {response.text}')
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
        raise RuntimeError(f'{provider} request failed without a captured error')
    raise last_error


def prepare_messages(messages, max_messages=20):
    if not messages:
        return []
    system_messages = [message for message in messages if message.get('role') == 'system']
    other_messages = [message for message in messages if message.get('role') != 'system']
    if len(other_messages) > max_messages:
        other_messages = other_messages[-max_messages:]
    return [
        {'role': message.get('role', 'user'), 'content': message.get('content') or ''}
        for message in system_messages + other_messages
    ]


def extract_text(response_data, provider):
    try:
        if provider == 'gemini':
            return response_data['candidates'][0]['content']['parts'][0]['text']
        if provider == 'claude':
            return response_data['content'][0]['text']
        return response_data['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        if provider == 'claude':
            try:
                return response_data['choices'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                pass
        return None