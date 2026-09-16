from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _timezone(name):
    try:
        return ZoneInfo(name or 'UTC')
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f'Unknown timezone: {name}') from exc


def current_datetime(timezone='UTC'):
    value = datetime.now(_timezone(timezone))
    return {'timezone': timezone or 'UTC', 'datetime': value.isoformat(), 'date': value.date().isoformat(), 'time': value.time().isoformat(timespec='seconds')}


def time_difference(first_timezone, second_timezone):
    first = datetime.now(_timezone(first_timezone))
    second = datetime.now(_timezone(second_timezone))
    difference_hours = (first.utcoffset() - second.utcoffset()).total_seconds() / 3600
    return {'from': first_timezone, 'to': second_timezone, 'hours': difference_hours}


def execute_date_time(arguments):
    operation = arguments.get('operation', 'current').lower()
    if operation in {'current', 'now'}:
        return current_datetime(arguments.get('timezone', 'UTC'))
    if operation in {'difference', 'diff'}:
        return time_difference(arguments.get('from_timezone'), arguments.get('to_timezone'))
    raise ValueError(f'Unsupported date/time operation: {operation}')