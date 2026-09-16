from decimal import Decimal, InvalidOperation


LENGTH_FACTORS = {'mm': Decimal('0.001'), 'cm': Decimal('0.01'), 'm': Decimal('1'), 'km': Decimal('1000'), 'in': Decimal('0.0254'), 'ft': Decimal('0.3048'), 'yd': Decimal('0.9144'), 'mi': Decimal('1609.344')}
MASS_FACTORS = {'mg': Decimal('0.000001'), 'g': Decimal('0.001'), 'kg': Decimal('1'), 'oz': Decimal('0.028349523125'), 'lb': Decimal('0.45359237')}


def _number(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError('A numeric value is required.') from exc


def convert_temperature(value, from_unit, to_unit):
    value = _number(value)
    source, target = from_unit.upper(), to_unit.upper()
    if source == target:
        return float(value)
    if source == 'C':
        celsius = value
    elif source == 'F':
        celsius = (value - 32) * Decimal(5) / Decimal(9)
    elif source == 'K':
        celsius = value - Decimal('273.15')
    else:
        raise ValueError(f'Unsupported temperature unit: {from_unit}')
    if target == 'C':
        result = celsius
    elif target == 'F':
        result = celsius * Decimal(9) / Decimal(5) + 32
    elif target == 'K':
        result = celsius + Decimal('273.15')
    else:
        raise ValueError(f'Unsupported temperature unit: {to_unit}')
    return float(result)


def convert_unit(value, from_unit, to_unit):
    if from_unit.upper() in {'C', 'F', 'K'} or to_unit.upper() in {'C', 'F', 'K'}:
        return convert_temperature(value, from_unit, to_unit)
    for factors in (LENGTH_FACTORS, MASS_FACTORS):
        if from_unit.lower() in factors and to_unit.lower() in factors:
            return float(_number(value) * factors[from_unit.lower()] / factors[to_unit.lower()])
    raise ValueError(f'Unsupported conversion: {from_unit} to {to_unit}')