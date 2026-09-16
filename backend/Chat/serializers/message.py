from rest_framework import serializers

from ..models import Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'conversation', 'role', 'content', 'tool_name', 'tool_response', 'created_at']
        read_only_fields = ['id', 'created_at']