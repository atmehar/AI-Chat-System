from django.urls import path

from .views import (
    ChatView,
    ConversationDetailView,
    ConversationListCreateView,
    ConversationMessageView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    StreamChatView,
    health_check,
)

urlpatterns = [
    path('health', health_check, name='health-check'),
    path('health/', health_check, name='health-check-slash'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('conversations/', ConversationListCreateView.as_view(), name='conversation-list-create'),
    path('conversations/<int:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<int:conversation_id>/messages/', ConversationMessageView.as_view(), name='conversation-messages'),
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/stream/', StreamChatView.as_view(), name='chat-stream'),
]
