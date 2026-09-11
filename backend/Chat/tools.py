import math
import re


def calculate(expression):
    cleaned = re.sub(r"[^0-9.+\-*/() ]", "", expression)
    if not cleaned:
        raise ValueError("Invalid expression")
    return str(eval(cleaned, {"__builtins__": {}}, {"math": math}))


def get_weather(location):
    return f"The weather in {location} is sunny and 24°C"


def execute_tool_call(tool_name, arguments):
    if tool_name == "calculate":
        return calculate(arguments.get("expression", ""))
    if tool_name == "get_weather":
        return get_weather(arguments.get("location", ""))
    raise ValueError(f"Unsupported tool: {tool_name}")
