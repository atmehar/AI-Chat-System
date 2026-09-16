from django.db import models
from .conversationmodel import Conversation
class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('tool', 'Tool'),
    ]

    conversation = models.ForeignKey(Conversation, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='user')
    content = models.TextField(blank=True, default='')
    tool_name = models.CharField(max_length=255, blank=True, default='')
    tool_response = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:30] if self.content else ''}"
