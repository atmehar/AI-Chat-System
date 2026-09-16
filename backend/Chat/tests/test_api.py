from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..models import Conversation


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
        login_response = self.client.post('/api/auth/login/', {'username': 'alice', 'password': 'secret123'}, content_type='application/json')
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()['token']
        self.assertTrue(token)
        me_response = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()['username'], 'alice')
        self.assertEqual(me_response.json()['name'], 'Alice')

    def test_register_endpoint(self):
        self.client.logout()
        response = self.client.post('/api/auth/register/', {'username': 'carol', 'password': 'secret123', 'name': 'Carol'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Carol')
        self.assertTrue(response.json()['token'])

    def test_create_conversation_is_scoped_to_user(self):
        response = self.client.post('/api/conversations/', {'title': 'New Chat', 'provider': 'openai'}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['user_id'], 'alice')
        list_response = self.client.get('/api/conversations/')
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)

    @patch('Chat.views.chat.generate_chat_response')
    def test_chat_accepts_message_field_and_returns_response(self, mock_generate):
        mock_generate.return_value = {'role': 'assistant', 'content': 'Hello from the model', 'provider': 'openai'}
        conversation = Conversation.objects.create(title='New Chat', provider='openai', user_id='alice')
        response = self.client.post('/api/chat/', {'conversation_id': conversation.id, 'message': 'Hi', 'provider': 'openai'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['response'], 'Hello from the model')
        messages = self.client.get(f'/api/conversations/{conversation.id}/messages/')
        self.assertEqual(messages.status_code, 200)
        roles = [item['role'] for item in messages.json()]
        self.assertIn('user', roles)
        self.assertIn('assistant', roles)