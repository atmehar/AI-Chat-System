import re

from .exceptions import GuardrailViolation

MAX_OUTPUT_LENGTH = 30000
SECRET_PATTERNS = (
    r'(?i)sk-[a-z0-9]{20,}',
    r'(?i)api[_-]?key\s*[:=]\s*[\w-]{12,}',
    r'(?i)bearer\s+[a-z0-9._-]{20,}',
)


def validate_output(text):
    if not isinstance(text, str) or not text.strip():
        raise GuardrailViolation('The model returned an empty response.', 'empty_output')
    if len(text) > MAX_OUTPUT_LENGTH:
        raise GuardrailViolation('The model response is too long.', 'output_too_long')
    if any(re.search(pattern, text) for pattern in SECRET_PATTERNS):
        raise GuardrailViolation('The response contained sensitive data.', 'sensitive_data')
    if re.search(r'(?i)(system prompt|developer message)\s*[:=]', text):
        raise GuardrailViolation('The response exposed internal instructions.', 'prompt_leak')
    return text