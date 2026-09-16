from ..models import Conversation


def create_conversation(user_id, title='New Chat', provider='openai', system_prompt='You are a helpful assistant.'):
    if not user_id:
        raise ValueError('user_id is required.')
    conversation = Conversation.objects.create(user_id=user_id, title=title or 'New Chat', provider=provider, system_prompt=system_prompt)
    return {'id': conversation.id, 'user_id': conversation.user_id, 'title': conversation.title, 'provider': conversation.provider}


def rename_conversation(conversation_id, user_id, title):
    if not title or not title.strip():
        raise ValueError('title is required.')
    conversation = Conversation.objects.filter(id=conversation_id, user_id=user_id).first()
    if conversation is None:
        raise ValueError('Conversation not found.')
    conversation.title = title.strip()
    conversation.save(update_fields=['title', 'updated_at'])
    return {'id': conversation.id, 'title': conversation.title}