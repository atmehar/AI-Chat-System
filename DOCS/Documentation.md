# AI Multi-Provider Chat System — Project Documentation (Updated)

> **Update note:** This version replaces the original modular/plugin-based backend architecture (separate `providers/`, `services/`, `tools/` layers with an abstraction/factory pattern) with a **traditional Django app architecture** — a single, self-contained `chat` app using Django's standard conventions. All other project goals, features, and technology choices remain the same.

---

## Project Overview

The **AI Multi-Provider Chat System** is a production-ready AI chat application that enables users to interact with multiple Large Language Models (LLMs) through a single, unified interface.

Instead of integrating only one AI provider, the application supports multiple providers such as **OpenAI**, **Anthropic Claude**, and **Google Gemini**. Provider selection and provider-specific request handling are implemented directly within the backend's chat view and a small set of utility functions — following a traditional, straightforward Django app structure rather than a modular plugin/abstraction framework.

---

## Technology Stack

**Frontend:** Next.js, React, JavaScript, Tailwind CSS, Server-Sent Events (SSE)

**Backend:** Django, Django REST Framework, PostgreSQL, Python

**AI Providers:** OpenAI, Anthropic Claude, Google Gemini

---

## System Architecture (Traditional)

```
                User
                  │
                  ▼
        Next.js Chat Interface
                  │
                  ▼
          Django Backend (chat app)
                  │
        views.py — /api/chat/ endpoint
                  │
     if/elif provider selection (in-view)
      ┌─────────┼──────────┐
      │         │          │
      ▼         ▼          ▼
   OpenAI    Claude     Gemini
  (utils.py functions)
      │         │          │
      └─────────┼──────────┘
                │
                ▼
         AI Generated Response
                │
                ▼
     Save Conversation History (models.py)
                │
                ▼
     Stream Response to Frontend (SSE)
```

Unlike a modular/plugin architecture, there is no separate provider abstraction layer, base class, or factory. Each provider is called via a plain function (`call_openai`, `call_claude`, `call_gemini`), and the view chooses which one to call based on the conversation's `provider` field.

---

## Folder Structure (Traditional Django App)

```
Frontend
├── app/
├── components/
├── hooks/
├── services/
├── lib/
└── types/

Backend (Django project: Backend/)
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
└── chat/                  # single Django app
    ├── models.py           # Conversation, Message
    ├── views.py            # /api/chat/ endpoint, streaming, provider selection
    ├── serializers.py      # DRF serializers
    ├── urls.py             # app-level routes
    ├── admin.py
    ├── utils.py            # call_openai(), call_claude(), call_gemini(), retry/backoff logic
    └── tools.py            # tool/function-calling implementations
```

**Why this approach:** For a project of this scope, a single well-organized Django app keeps related logic (models, views, provider calls, tools) easy to find and reason about, without the overhead of maintaining abstract interfaces, factories, and multiple provider packages. It's faster to build, easier to onboard into, and still fully supports all the same features — multi-provider support, streaming, tool calling, structured outputs, retries, and fallback — just implemented with direct functions and conditionals instead of an abstraction layer.

---

## Core Features (Unchanged)

All ten core features from the original documentation remain part of the system and are unaffected by the architecture change:

1. Multi-Provider AI Support
2. Chat Completions
3. Conversation History
4. System Prompts
5. Function Calling (Tool Calling)
6. Streaming Responses
7. Structured Outputs
8. Error Handling
9. Provider Fallback
10. Conversation Persistence

Only *how* provider logic is organized in the codebase has changed — not what the system does.

---

## Database Design (Unchanged)

**Conversation Table:** `id`, `user_id`, `provider`, `title`, `created_at`, `updated_at`

**Message Table:** `id`, `conversation_id`, `role`, `content`, `tool_name`, `tool_response`, `created_at`

---

## Security Considerations (Unchanged)

- Store API keys in environment variables.
- Never expose provider keys to the frontend.
- Validate all incoming requests.
- Implement authentication.
- Apply rate limiting.
- Sanitize tool inputs.
- Log errors without exposing sensitive information.

---
