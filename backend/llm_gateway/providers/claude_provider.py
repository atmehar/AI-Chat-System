import os

from .common import extract_text, prepare_messages, request_with_retries


def call_claude(messages, response_format=None):
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError('Anthropic API key is not configured. Please add it to your .env file.')
    formatted = []
    for message in prepare_messages(messages):
        role = message['role'] if message['role'] in {'user', 'assistant', 'system'} else 'user'
        formatted.append({'role': role, 'content': message['content']})
    payload = {'model': 'claude-3-5-sonnet-20241022', 'max_tokens': 1024, 'messages': formatted}
    if response_format and response_format.get('type') == 'json':
        payload['system'] = 'Return a valid JSON object.'
    response = request_with_retries(
        'https://api.anthropic.com/v1/messages',
        {'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'},
        payload,
        'Claude',
    )
    content = extract_text(response.json(), 'claude')
    if content is None:
        raise RuntimeError(f'Claude response structure mismatch: {response.json()}')
    return {'role': 'assistant', 'content': content}