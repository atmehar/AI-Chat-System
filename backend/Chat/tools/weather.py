import os

import requests


def _request(endpoint, location, units='metric', days=None):
    api_key = os.getenv('OPENWEATHER_API_KEY') or os.getenv('WEATHER_API_KEY')
    if not api_key:
        raise ValueError('OpenWeather API key is not configured.')
    params = {'q': location, 'appid': api_key, 'units': units}
    if days is not None:
        params['cnt'] = days * 8
    response = requests.get(endpoint, params=params, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f'Weather API Error ({response.status_code}): {response.text}')
    return response.json()


def get_weather(location, units='metric'):
    if not location or not location.strip():
        raise ValueError('Location is required.')
    data = _request('https://api.openweathermap.org/data/2.5/weather', location.strip(), units)
    return {
        'location': data.get('name', location),
        'temperature': data['main']['temp'],
        'feels_like': data['main'].get('feels_like'),
        'description': data['weather'][0]['description'],
        'units': units,
    }


def get_forecast(location, units='metric', days=5):
    if not location or not location.strip():
        raise ValueError('Location is required.')
    days = max(1, min(int(days), 5))
    data = _request('https://api.openweathermap.org/data/2.5/forecast', location.strip(), units, days)
    return {
        'location': location,
        'units': units,
        'forecast': [
            {'datetime': item['dt_txt'], 'temperature': item['main']['temp'], 'description': item['weather'][0]['description']}
            for item in data.get('list', [])
        ],
    }