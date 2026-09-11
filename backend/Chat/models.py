from django.db import models


class Conversation(models.Model):
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('claude', 'Claude'),
        ('gemini', 'Gemini'),
    ]

    user_id = models.CharField(max_length=255, default="default_user")
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='openai')
    title = models.CharField(max_length=255, default="New Chat")
    system_prompt = models.TextField(blank=True, default="You are a helpful assistant.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.provider})"


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
