import re
from .exceptions import GuardrailViolation

MAX_MESSAGE_LENGTH = 12000
INJECTION_PATTERNS = (
    r'ignore (all|any|the) previous instructions',
    r'reveal (your|the) system prompt',
    r'bypass (your|the) safety',
    r'developer message',
)


def validate_messages(messages):
    if not messages:
        raise GuardrailViolation('At least one message is required.', 'empty_input')
    for message in messages:
        content = message.get('content', '') if isinstance(message, dict) else ''
        if not isinstance(content, str):
            raise GuardrailViolation('Message content must be text.', 'invalid_input')
        if len(content) > MAX_MESSAGE_LENGTH:
            raise GuardrailViolation('Message is too long.', 'input_too_long')
        if message.get('role') == 'user' and any(re.search(pattern, content, re.IGNORECASE) for pattern in INJECTION_PATTERNS):
            raise GuardrailViolation('This request cannot be processed.', 'prompt_injection')
    return messages