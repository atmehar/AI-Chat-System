import os

from .common import extract_text, prepare_messages, request_with_retries


def call_gemini(messages, response_format=None):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError('Gemini API key is not configured. Please add it to your .env file.')
    model_name = 'gemini-3.6-flash'
    contents = []
    for message in prepare_messages(messages):
        role = 'model' if message['role'] == 'assistant' else 'user'
        contents.append({'role': role, 'parts': [{'text': message['content']}]})
    payload = {'contents': contents}
    if response_format and response_format.get('type') == 'json':
        payload['generationConfig'] = {'responseMimeType': 'application/json'}
    response = request_with_retries(
        f'https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}',
        {'Content-Type': 'application/json'},
        payload,
        'Gemini',
    )
    content = extract_text(response.json(), 'gemini')
    if content is None:
        raise RuntimeError(f'Gemini response structure mismatch: {response.json()}')
    return {'role': 'assistant', 'content': content}