import os
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .utils import call_gemini, generate_chat_response


class GeminiApiTests(SimpleTestCase):
    @patch("Chat.utils.requests.post")
    def test_call_gemini_uses_current_model_name(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": {"message": "quota exceeded"}}
        mock_response.text = '{"error": {"message": "quota exceeded"}}'
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Gemini API Error"):
                call_gemini([{"role": "user", "content": "hi"}])

        called_url = mock_post.call_args.args[0]
        self.assertIn("gemini-3.6-flash", called_url)

    @patch("Chat.utils.requests.post")
    def test_generate_chat_response_parses_structured_json(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Ada", "intent": "help"}'}}]
        }
        mock_response.text = '{"choices": [{"message": {"content": "{\"name\": \"Ada\", \"intent\": \"help\"}"}}]}'
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            result = generate_chat_response(
                [{"role": "user", "content": "Extract the JSON"}],
                provider="openai",
                response_format={"type": "json"},
            )

        self.assertEqual(result["content"], '{"name": "Ada", "intent": "help"}')
        self.assertEqual(result["provider"], "openai")

    @patch("Chat.utils.requests.post")
    def test_generate_chat_response_falls_back_to_next_provider(self, mock_post):
        first_response = Mock()
        first_response.status_code = 500
        first_response.json.return_value = {"error": {"message": "server over capacity"}}
        first_response.text = "server over capacity"

        second_response = Mock()
        second_response.status_code = 200
        second_response.json.return_value = {
            "choices": [{"message": {"content": "fallback reply"}}]
        }
        second_response.text = "fallback reply"

        mock_post.side_effect = [first_response, first_response, first_response, second_response]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key"}, clear=False):
            result = generate_chat_response(
                [{"role": "user", "content": "hello"}],
                provider="openai",
            )

        self.assertEqual(result["content"], "fallback reply")
        self.assertEqual(result["provider"], "claude")

    @patch("Chat.utils.requests.post")
    def test_generate_chat_response_falls_back_from_gemini(self, mock_post):
        gemini_error = Mock()
        gemini_error.status_code = 429
        gemini_error.json.return_value = {"error": {"message": "quota exceeded"}}
        gemini_error.text = "quota exceeded"

        openai_success = Mock()
        openai_success.status_code = 200
        openai_success.json.return_value = {
            "choices": [{"message": {"content": "recovered reply"}}]
        }
        openai_success.text = "recovered reply"

        mock_post.side_effect = [gemini_error, gemini_error, gemini_error, openai_success]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "GEMINI_API_KEY": "test-key"}, clear=False):
            result = generate_chat_response(
                [{"role": "user", "content": "hello"}],
                provider="gemini",
            )

        self.assertEqual(result["content"], "recovered reply")
        self.assertEqual(result["provider"], "openai")

    @patch("Chat.utils.requests.post")
    def test_generate_chat_response_executes_tool_call_and_returns_result(self, mock_post):
        first_response = Mock()
        first_response.status_code = 200
        first_response.json.return_value = {
            "choices": [{"message": {"content": "Tool call: calculate(2+2)"}}]
        }
        first_response.text = "Tool call: calculate(2+2)"

        second_response = Mock()
        second_response.status_code = 200
        second_response.json.return_value = {
            "choices": [{"message": {"content": "The result is 4."}}]
        }
        second_response.text = "The result is 4."

        mock_post.side_effect = [first_response, second_response]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            result = generate_chat_response(
                [{"role": "user", "content": "Calculate 2+2"}],
                provider="openai",
            )

        self.assertIn("4", result["content"])
        self.assertEqual(result["provider"], "openai")

    @patch("Chat.utils.requests.post")
    def test_generate_chat_response_cleans_markdown_formatting(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": "**Bold** text and `code` with [link](https://example.com)."}}]
        }
        response.text = "**Bold** text and `code` with [link](https://example.com)."
        mock_post.return_value = response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False):
            result = generate_chat_response(
                [{"role": "user", "content": "Clean markdown"}],
                provider="openai",
            )

        self.assertEqual(result["content"], "Bold text and code with link.")
        self.assertEqual(result["provider"], "openai")

    @patch("Chat.utils.requests.post")
    def test_generate_chat_response_validates_schema(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [{"message": {"content": '{"name": "Ada"}'}}]
        }
        response.text = '{"name": "Ada"}'
        mock_post.return_value = response

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "ANTHROPIC_API_KEY": "test-key", "GEMINI_API_KEY": "test-key"}, clear=False):
            with self.assertRaisesRegex(ValueError, "schema"):
                generate_chat_response(
                    [{"role": "user", "content": "Extract info"}],
                    provider="openai",
                    response_format={
                        "type": "json",
                        "schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name", "email"]},
                    },
                )


from unittest.mock import patch as mock_patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Conversation


class ChatApiIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='alice', password='secret123', first_name='Alice')
        self.client.force_login(self.user)

    def test_health_endpoint_accepts_trailing_slash(self):
        for path in ('/api/health', '/api/health/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'ok')

    def test_login_and_me_endpoints(self):
        self.client.logout()
        login_response = self.client.post(
            '/api/auth/login/',
            {'username': 'alice', 'password': 'secret123'},
            content_type='application/json',
        )
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()['token']
        self.assertTrue(token)

        me_response = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()['username'], 'alice')
        self.assertEqual(me_response.json()['name'], 'Alice')

    def test_register_endpoint(self):
        self.client.logout()
        response = self.client.post(
            '/api/auth/register/',
            {'username': 'carol', 'password': 'secret123', 'name': 'Carol'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Carol')
        self.assertTrue(response.json()['token'])

    def test_create_conversation_is_scoped_to_user(self):
        response = self.client.post(
            '/api/conversations/',
            {'title': 'New Chat', 'provider': 'openai'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['user_id'], 'alice')

        list_response = self.client.get('/api/conversations/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

    @mock_patch('Chat.views.generate_chat_response')
    def test_chat_accepts_message_field_and_returns_response(self, mock_generate):
        mock_generate.return_value = {
            'role': 'assistant',
            'content': 'Hello from the model',
            'provider': 'openai',
        }
        conversation = Conversation.objects.create(title='New Chat', provider='openai', user_id='alice')
        response = self.client.post(
            '/api/chat/',
            {'conversation_id': conversation.id, 'message': 'Hi', 'provider': 'openai'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['response'], 'Hello from the model')

        messages = self.client.get(f'/api/conversations/{conversation.id}/messages/')
        self.assertEqual(messages.status_code, 200)
        roles = [item['role'] for item in messages.json()]
        self.assertIn('user', roles)
        self.assertIn('assistant', roles)


