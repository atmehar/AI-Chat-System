import json
import logging

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Conversation, Message
from ..utils import generate_chat_response

logger = logging.getLogger(__name__)


def _message_text(request):
    return (request.data.get('message') or request.data.get('content') or '').strip()


def _formatted_messages(conversation):
    formatted_messages = []
    if conversation.system_prompt:
        formatted_messages.append({'role': 'system', 'content': conversation.system_prompt})
    for message in conversation.messages.all().order_by('created_at'):
        if message.role != 'system':
            formatted_messages.append({'role': message.role, 'content': message.content or ''})
    return formatted_messages


def _update_conversation(conversation, content, provider):
    if conversation.title in {'New Chat', 'New Conversation'} and content:
        conversation.title = content[:40]
    conversation.provider = provider
    conversation.save(update_fields=['title', 'provider', 'updated_at'])


class ChatView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get('conversation_id')
        content = _message_text(request)
        provider = (request.data.get('provider') or '').lower()
        response_format = request.data.get('response_format')
        if not conversation_id:
            return Response({'error': 'conversation_id is required'}, status=400)
        if not content:
            return Response({'error': 'message is required'}, status=400)

        conversation = get_object_or_404(Conversation, id=conversation_id, user_id=request.user.username)
        if provider in {'openai', 'claude', 'gemini'}:
            conversation.provider = provider
            conversation.save(update_fields=['provider', 'updated_at'])
        Message.objects.create(conversation=conversation, role='user', content=content, tool_name='', tool_response='')

        try:
            result = generate_chat_response(_formatted_messages(conversation), provider=conversation.provider, response_format=response_format)
            provider_used = result.get('provider') or conversation.provider
            assistant_content = result.get('content') or ''
            assistant_message = Message.objects.create(
                conversation=conversation, role='assistant', content=assistant_content,
                tool_name=result.get('tool_name') or '', tool_response=result.get('tool_response') or '',
            )
            _update_conversation(conversation, content, provider_used)
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
            return Response({'error': 'Provider request failed after retries. Please try again.'}, status=503)


class StreamChatView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        conversation_id = request.data.get('conversation_id')
        content = _message_text(request)
        response_format = request.data.get('response_format')
        provider = (request.data.get('provider') or '').lower()
        if not conversation_id or not content:
            return Response({'error': 'conversation_id and message are required'}, status=400)

        conversation = get_object_or_404(Conversation, id=conversation_id, user_id=request.user.username)
        if provider in {'openai', 'claude', 'gemini'}:
            conversation.provider = provider
            conversation.save(update_fields=['provider', 'updated_at'])
        Message.objects.create(conversation=conversation, role='user', content=content, tool_name='', tool_response='')
        formatted_messages = _formatted_messages(conversation)

        def event_stream():
            try:
                response_payload = generate_chat_response(formatted_messages, provider=conversation.provider, response_format=response_format)
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
                Message.objects.create(conversation=conversation, role='assistant', content=full_text, tool_name='', tool_response='')
                _update_conversation(conversation, content, provider_used)
                yield f"data: {json.dumps({'done': True, 'content': full_text, 'provider': provider_used, 'fallback_reason': fallback_reason})}\n\n"
            except Exception as exc:
                logger.exception('Streaming chat failed: %s', exc)
                yield f"data: {json.dumps({'error': True, 'message': 'Provider request failed after retries. Please try again.'})}\n\n"

        return StreamingHttpResponse(event_stream(), content_type='text/event-stream')