import time

from llm_gateway import gateway
from llm_gateway.providers import call_claude, call_gemini, call_openai


def generate_chat_response(messages, provider='openai', response_format=None, fallback_order=None):
    return gateway.generate(
        messages,
        provider=provider,
        response_format=response_format,
        fallback_order=fallback_order,
    )


def stream_chat_response(messages, provider='openai', response_format=None, fallback_order=None):
    response_payload = generate_chat_response(
        messages,
        provider=provider,
        response_format=response_format,
        fallback_order=fallback_order,
    )
    text = response_payload.get('content', '') or ''
    chunk_size = max(1, len(text) // 12) if text else 1
    for index in range(0, len(text), chunk_size):
        yield text[index:index + chunk_size]
        time.sleep(0.02)
    if not text:
        yield ''


__all__ = [
    'call_claude',
    'call_gemini',
    'call_openai',
    'generate_chat_response',
    'stream_chat_response',
]
