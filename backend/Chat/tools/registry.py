from .calculator import calculate
from .conversation import create_conversation, rename_conversation
from .currency import convert_currency
from .date_time import execute_date_time
from .language import detect_language
from .unit_conversion import convert_unit
from .weather import get_forecast, get_weather


def execute_tool_call(tool_name, arguments):
    if tool_name == 'calculate':
        return calculate(arguments.get('expression', ''))
    if tool_name == 'get_weather':
        return get_weather(arguments.get('location', ''))
    if tool_name == 'get_forecast':
        return get_forecast(arguments.get('location', ''), arguments.get('units', 'metric'), arguments.get('days', 5))
    if tool_name in {'date_time', 'current_datetime'}:
        return execute_date_time(arguments)
    if tool_name == 'convert_unit':
        return convert_unit(arguments.get('value'), arguments.get('from_unit', ''), arguments.get('to_unit', ''))
    if tool_name == 'convert_currency':
        return convert_currency(arguments.get('amount'), arguments.get('from_currency', ''), arguments.get('to_currency', ''))
    if tool_name == 'detect_language':
        return detect_language(arguments.get('text', ''))
    if tool_name == 'create_conversation':
        return create_conversation(arguments.get('user_id'), arguments.get('title', 'New Chat'), arguments.get('provider', 'openai'), arguments.get('system_prompt', 'You are a helpful assistant.'))
    if tool_name == 'rename_conversation':
        return rename_conversation(arguments.get('conversation_id'), arguments.get('user_id'), arguments.get('title'))
    raise ValueError(f'Unsupported tool: {tool_name}')