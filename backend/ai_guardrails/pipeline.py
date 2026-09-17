from .input_checks import validate_messages
from .output_checks import validate_output
from .tool_checks import validate_tool_call


def check_input(messages):
    return validate_messages(messages)


def check_tool(tool_name, arguments):
    return validate_tool_call(tool_name, arguments)


def check_output(response):
    if isinstance(response, dict):
        response = dict(response)
        response['content'] = validate_output(response.get('content', ''))
        return response
    return validate_output(response)