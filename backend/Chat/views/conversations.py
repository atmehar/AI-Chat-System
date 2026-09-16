from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import Conversation
from ..serializers import ConversationDetailSerializer, ConversationSerializer, MessageSerializer


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
        return Response(serializer.data, status=201)