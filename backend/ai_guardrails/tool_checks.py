from .exceptions import GuardrailViolation

ALLOWED_TOOLS = {
    'calculate', 'get_weather', 'get_forecast', 'date_time', 'current_datetime',
    'convert_unit', 'convert_currency', 'detect_language', 'create_conversation',
    'rename_conversation',
}


def validate_tool_call(tool_name, arguments):
    if tool_name not in ALLOWED_TOOLS:
        raise GuardrailViolation(f'Unsupported tool: {tool_name}', 'unsupported_tool')
    if not isinstance(arguments, dict):
        raise GuardrailViolation('Tool arguments must be an object.', 'invalid_tool_arguments')
    if tool_name in {'create_conversation', 'rename_conversation'} and not arguments.get('user_id'):
        raise GuardrailViolation('User identity is required for conversation tools.', 'missing_user')
    if tool_name == 'rename_conversation' and not arguments.get('conversation_id'):
        raise GuardrailViolation('Conversation identity is required.', 'missing_conversation')
    if tool_name in {'get_weather', 'get_forecast'} and not arguments.get('location'):
        raise GuardrailViolation('Location is required.', 'missing_location')
    return arguments