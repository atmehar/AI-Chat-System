import os
from unittest.mock import Mock, patch

from django.test import TestCase, SimpleTestCase

from ..models import Conversation
from ..tools import calculate, convert_currency, convert_temperature, convert_unit, current_datetime, detect_language, execute_tool_call, time_difference


class DeterministicToolTests(SimpleTestCase):
    def test_date_time_supports_timezone_and_difference(self):
        result = current_datetime('Asia/Muscat')
        self.assertEqual(result['timezone'], 'Asia/Muscat')
        self.assertEqual(time_difference('UTC', 'Asia/Muscat')['hours'], -4.0)

    def test_unit_and_temperature_conversion(self):
        self.assertEqual(convert_unit(1, 'km', 'm'), 1000.0)
        self.assertEqual(convert_temperature(32, 'F', 'C'), 0.0)

    def test_language_detection_and_dispatch(self):
        self.assertEqual(detect_language('مرحبا')['language_code'], 'ar')
        self.assertEqual(execute_tool_call('calculate', {'expression': '2 + 2'}), '4')


class ExternalToolTests(SimpleTestCase):
    @patch('Chat.tools.weather.requests.get')
    def test_weather_returns_current_conditions(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: {'name': 'Muscat', 'main': {'temp': 30, 'feels_like': 32}, 'weather': [{'description': 'clear sky'}]})
        from ..tools import get_weather

        with patch.dict(os.environ, {'OPENWEATHER_API_KEY': 'test-key'}):
            result = get_weather('Muscat')
        self.assertEqual(result['temperature'], 30)
        mock_get.assert_called_once()

    @patch('Chat.tools.currency.requests.get')
    def test_currency_conversion_uses_live_rate(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: {'rates': {'EUR': 0.9}, 'time_last_update_utc': 'today'})

        result = convert_currency(10, 'USD', 'EUR')
        self.assertEqual(result['converted_amount'], 9.0)
        mock_get.assert_called_once()


class ConversationToolTests(TestCase):
    def test_create_and_rename_conversation(self):
        created = execute_tool_call('create_conversation', {'user_id': 'alice', 'title': 'First Chat'})
        renamed = execute_tool_call('rename_conversation', {'user_id': 'alice', 'conversation_id': created['id'], 'title': 'Renamed Chat'})

        self.assertEqual(renamed['title'], 'Renamed Chat')
        self.assertEqual(Conversation.objects.get(id=created['id']).title, 'Renamed Chat')