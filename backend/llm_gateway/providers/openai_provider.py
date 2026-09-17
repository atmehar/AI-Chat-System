import os

from .common import extract_text, prepare_messages, request_with_retries


def call_openai(messages, response_format=None):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError('OpenAI API key is not configured. Please add it to your .env file.')
    payload = {'model': 'gpt-4o-mini', 'messages': prepare_messages(messages)}
    if response_format and response_format.get('type') == 'json':
        payload['response_format'] = {'type': 'json_object'}
    response = request_with_retries(
        'https://api.openai.com/v1/chat/completions',
        {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        payload,
        'OpenAI',
    )
    content = extract_text(response.json(), 'openai')
    if content is None:
        raise RuntimeError(f'OpenAI response structure mismatch: {response.json()}')
    return {'role': 'assistant', 'content': content}