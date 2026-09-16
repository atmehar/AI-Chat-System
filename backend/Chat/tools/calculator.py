import math
import re


def calculate(expression):
    cleaned = re.sub(r'[^0-9.+\-*/() ]', '', expression)
    if not cleaned:
        raise ValueError('Invalid expression')
    return str(eval(cleaned, {'__builtins__': {}}, {'math': math}))