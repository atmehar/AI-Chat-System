import json
import logging

from django.contrib.auth import authenticate, get_user_model, login
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message
from .serializers import ConversationDetailSerializer, ConversationSerializer, MessageSerializer
from .utils import generate_chat_response

logger = logging.getLogger(__name__)


def health_check(request):
    return JsonResponse({'status': 'ok', 'project': 'AI Chat System'})


def _user_payload(user):
    display_name = (user.get_full_name() or '').strip() or user.username
    token, _created = Token.objects.get_or_create(user=user)
    return {
        'id': user.id,
        'username': user.username,
        'name': display_name,
        'token': token.key,
    }


def _message_text(request):
    return (request.data.get('message') or request.data.get('content') or '').strip()


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user is None:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response(_user_payload(user))


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        name = (request.data.get('name') or '').strip()

        if not username or not password:
            return Response({'error': 'Username and password are required'}, status=status.HTTP_400_BAD_REQUEST)
        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters'}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password, first_name=name)
        return Response(_user_payload(user), status=status.HTTP_201_CREATED)


class MeView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_user_payload(request.user))


class LogoutView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationListCreateView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user_id=self.request.user.username).order_by('-updated_at', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user_id=self.request.user.username)


class ConversationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ConversationDetailSerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(user_id=self.request.user.username)


class ConversationMessageView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id, user_id=request.user.username)
        messages = conversation.messages.all().order_by('created_at')
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, conversation_id):
        conversation = get_object_or_404(Conversation, id=conversation_id, user_id=request.user.username)
        payload = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        payload['conversation'] = conversation.id
        serializer = MessageSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        conversation.save(update_fields=['updated_at'])
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get('conversation_id')
        content = _message_text(request)
        provider = (request.data.get('provider') or '').lower()
        response_format = request.data.get('response_format')

        if not conversation_id:
            return Response({'error': 'conversation_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not content:
            return Response({'error': 'message is required'}, status=status.HTTP_400_BAD_REQUEST)

        conversation = get_object_or_404(Conversation, id=conversation_id, user_id=request.user.username)
        if provider in {'openai', 'claude', 'gemini'}:
            conversation.provider = provider
            conversation.save(update_fields=['provider', 'updated_at'])

        Message.objects.create(
            conversation=conversation,
            role='user',
            content=content,
            tool_name='',
            tool_response='',
        )

        formatted_messages = []
        if conversation.system_prompt:
            formatted_messages.append({'role': 'system', 'content': conversation.system_prompt})
        for msg in conversation.messages.all().order_by('created_at'):
            if msg.role == 'system':
                continue
            formatted_messages.append({'role': msg.role, 'content': msg.content or ''})

        try:
            result = generate_chat_response(
                formatted_messages,
                provider=conversation.provider,
                response_format=response_format,
            )
            provider_used = result.get('provider') or conversation.provider
            assistant_content = result.get('content') or ''
            assistant_message = Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=assistant_content,
                tool_name=result.get('tool_name') or '',
                tool_response=result.get('tool_response') or '',
            )

            if conversation.title in {'New Chat', 'New Conversation'} and content:
                conversation.title = content[:40]
            conversation.provider = provider_used
            conversation.save(update_fields=['title', 'provider', 'updated_at'])

            payload = {
                'response': assistant_content,
                'message_id': assistant_message.id,
                'provider': provider_used,
                'fallback_provider': None if provider_used == (provider or conversation.provider) else provider_used,
            }
            if result.get('parsed') is not None:
                payload['structured_response'] = result['parsed']
            if result.get('fallback_reason'):
                payload['fallback_reason'] = result['fallback_reason']
            return Response(payload)
        except Exception:
            logger.exception('Chat provider request failed')
            return Response(
                {'error': 'Provider request failed after retries. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class StreamChatView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get('conversation_id')
        content = _message_text(request)
        response_format = request.data.get('response_format')
        provider = (request.data.get('provider') or '').lower()

        if not conversation_id or not content:
            return Response({'error': 'conversation_id and message are required'}, status=status.HTTP_400_BAD_REQUEST)

        conversation = get_object_or_404(Conversation, id=conversation_id, user_id=request.user.username)
        if provider in {'openai', 'claude', 'gemini'}:
            conversation.provider = provider
            conversation.save(update_fields=['provider', 'updated_at'])

        Message.objects.create(
            conversation=conversation,
            role='user',
            content=content,
            tool_name='',
            tool_response='',
        )
        formatted_messages = []
        if conversation.system_prompt:
            formatted_messages.append({'role': 'system', 'content': conversation.system_prompt})
        for msg in conversation.messages.all().order_by('created_at'):
            if msg.role == 'system':
                continue
            formatted_messages.append({'role': msg.role, 'content': msg.content or ''})

        def event_stream():
            try:
                response_payload = generate_chat_response(
                    formatted_messages,
                    provider=conversation.provider,
                    response_format=response_format,
                )
                provider_used = response_payload.get('provider', conversation.provider)
                text = response_payload.get('content', '') or ''
                parts = []
                chunk_size = max(1, len(text) // 12) if text else 1
                fallback_reason = response_payload.get('fallback_reason')
                for index in range(0, len(text), chunk_size):
                    chunk = text[index:index + chunk_size]
                    parts.append(chunk)
                    yield f"data: {json.dumps({'chunk': chunk, 'provider': provider_used, 'fallback_reason': fallback_reason})}\n\n"
                full_text = ''.join(parts)
                Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=full_text,
                    tool_name='',
                    tool_response='',
                )
                if conversation.title in {'New Chat', 'New Conversation'} and content:
                    conversation.title = content[:40]
                conversation.provider = provider_used
                conversation.save(update_fields=['title', 'provider', 'updated_at'])
                yield f"data: {json.dumps({'done': True, 'content': full_text, 'provider': provider_used, 'fallback_reason': fallback_reason})}\n\n"
            except Exception as exc:
                error_message = 'Provider request failed after retries. Please try again.'
                logger.exception('Streaming chat failed: %s', exc)
                yield f"data: {json.dumps({'error': True, 'message': error_message})}\n\n"

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
