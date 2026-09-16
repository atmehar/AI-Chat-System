import requests


def convert_currency(amount, from_currency, to_currency):
    source = from_currency.upper()
    target = to_currency.upper()
    if source == target:
        return {'amount': float(amount), 'from': source, 'to': target, 'rate': 1.0, 'converted_amount': float(amount)}
    response = requests.get(f'https://open.er-api.com/v6/latest/{source}', timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f'Currency API Error ({response.status_code}): {response.text}')
    data = response.json()
    rate = data.get('rates', {}).get(target)
    if rate is None:
        raise ValueError(f'Unsupported currency: {target}')
    amount = float(amount)
    return {'amount': amount, 'from': source, 'to': target, 'rate': rate, 'converted_amount': amount * rate, 'updated_at': data.get('time_last_update_utc')}