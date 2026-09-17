import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ..utils import call_gemini, generate_chat_response


class GeminiApiTests(SimpleTestCase):
    @patch('llm_gateway.providers.common.requests.post')
    def test_call_gemini_uses_current_model_name(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {'error': {'message': 'quota exceeded'}}
        mock_response.text = '{"error": {"message": "quota exceeded"}}'
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {'GEMINI_API_KEY': 'test-key'}, clear=False):
            with self.assertRaisesRegex(RuntimeError, 'Gemini API Error'):
                call_gemini([{'role': 'user', 'content': 'hi'}])

        called_url = mock_post.call_args.args[0]
        self.assertIn('gemini-3.6-flash', called_url)

    @patch('llm_gateway.providers.common.requests.post')
    def test_generate_chat_response_parses_structured_json(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'choices': [{'message': {'content': '{"name": "Ada", "intent": "help"}'}}]}
        mock_response.text = '{"choices": [{"message": {"content": "{\"name\": \"Ada\", \"intent\": \"help\"}"}}]}'
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}, clear=False):
            result = generate_chat_response([{'role': 'user', 'content': 'Extract the JSON'}], provider='openai', response_format={'type': 'json'})

        self.assertEqual(result['content'], '{"name": "Ada", "intent": "help"}')
        self.assertEqual(result['provider'], 'openai')

    @patch('llm_gateway.providers.common.requests.post')
    def test_generate_chat_response_falls_back_to_next_provider(self, mock_post):
        first_response = Mock(status_code=500, text='server over capacity')
        first_response.json.return_value = {'error': {'message': 'server over capacity'}}
        second_response = Mock(status_code=200, text='fallback reply')
        second_response.json.return_value = {'choices': [{'message': {'content': 'fallback reply'}}]}
        mock_post.side_effect = [first_response, first_response, first_response, second_response]

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'ANTHROPIC_API_KEY': 'test-key'}, clear=False):
            result = generate_chat_response([{'role': 'user', 'content': 'hello'}], provider='openai')

        self.assertEqual(result['content'], 'fallback reply')
        self.assertEqual(result['provider'], 'claude')

    @patch('llm_gateway.providers.common.requests.post')
    def test_generate_chat_response_falls_back_from_gemini(self, mock_post):
        gemini_error = Mock(status_code=429, text='quota exceeded')
        gemini_error.json.return_value = {'error': {'message': 'quota exceeded'}}
        openai_success = Mock(status_code=200, text='recovered reply')
        openai_success.json.return_value = {'choices': [{'message': {'content': 'recovered reply'}}]}
        mock_post.side_effect = [gemini_error, gemini_error, gemini_error, openai_success]

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'GEMINI_API_KEY': 'test-key'}, clear=False):
            result = generate_chat_response([{'role': 'user', 'content': 'hello'}], provider='gemini')

        self.assertEqual(result['content'], 'recovered reply')
        self.assertEqual(result['provider'], 'openai')

    @patch('llm_gateway.providers.common.requests.post')
    def test_generate_chat_response_executes_tool_call_and_returns_result(self, mock_post):
        first_response = Mock(status_code=200, text='Tool call: calculate(2+2)')
        first_response.json.return_value = {'choices': [{'message': {'content': 'Tool call: calculate(2+2)'}}]}
        second_response = Mock(status_code=200, text='The result is 4.')
        second_response.json.return_value = {'choices': [{'message': {'content': 'The result is 4.'}}]}
        mock_post.side_effect = [first_response, second_response]

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}, clear=False):
            result = generate_chat_response([{'role': 'user', 'content': 'Calculate 2+2'}], provider='openai')

        self.assertIn('4', result['content'])
        self.assertEqual(result['provider'], 'openai')

    @patch('llm_gateway.providers.common.requests.post')
    def test_generate_chat_response_cleans_markdown_formatting(self, mock_post):
        response = Mock(status_code=200, text='**Bold** text and `code` with [link](https://example.com).')
        response.json.return_value = {'choices': [{'message': {'content': response.text}}]}
        mock_post.return_value = response

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}, clear=False):
            result = generate_chat_response([{'role': 'user', 'content': 'Clean markdown'}], provider='openai')

        self.assertEqual(result['content'], 'Bold text and code with link.')
        self.assertEqual(result['provider'], 'openai')

    @patch('llm_gateway.providers.common.requests.post')
    def test_generate_chat_response_validates_schema(self, mock_post):
        response = Mock(status_code=200, text='{"name": "Ada"}')
        response.json.return_value = {'choices': [{'message': {'content': '{"name": "Ada"}'}}]}
        mock_post.return_value = response

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key', 'ANTHROPIC_API_KEY': 'test-key', 'GEMINI_API_KEY': 'test-key'}, clear=False):
            with self.assertRaisesRegex(ValueError, 'schema'):
                generate_chat_response(
                    [{'role': 'user', 'content': 'Extract info'}], provider='openai',
                    response_format={'type': 'json', 'schema': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name', 'email']}},
                )