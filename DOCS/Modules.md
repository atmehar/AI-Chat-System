# Development Roadmap — Stepwise Modules
## AI Multi-Provider Chat System

> **Architecture note:** This roadmap uses a **traditional Django app architecture** — one `chat` app with standard `models.py`, `views.py`, `serializers.py`, `urls.py`, plus `utils.py` for provider-calling functions and `tools.py` for tool/function-calling logic. Provider selection is handled with simple conditional logic directly in the view, not a separate abstraction/factory layer.

This roadmap breaks the project into sequential, buildable modules. Each module has a clear goal, steps, and a "done when" checkpoint so you always know what to build next and when to move on.

---

## Module 0: Project Setup & Environment

**Goal:** Get a working skeleton with frontend, backend, and database talking to each other.

1. Initialize the backend: Django project + Django REST Framework, PostgreSQL connection configured via environment variables.
2. Initialize the frontend: Next.js + Javascript + Tailwind CSS.
3. Set up `.env` files for both frontend and backend (never commit real keys).
4. Create the base folder structure (traditional Django app architecture — no separate provider/service layers):
   - Backend: a single `chat` Django app containing `models.py`, `views.py`, `serializers.py`, `urls.py`, `admin.py`, `utils.py` (for provider-calling helper functions), and `tools.py` (for tool/function-calling logic).
   - Frontend: `app/`, `components/`, `hooks/`, `services/`, `lib/`, `types/`
5. Set up CORS between Next.js and Django.
6. Run both servers locally and confirm a basic "ping" API call from frontend to backend works.

**Done when:** Frontend can hit a `/health` endpoint on the backend and display the response.

---

## Module 1: Database Design & Models

**Goal:** Persistent storage ready before any AI logic is built.

1. Create the `Conversation` model: `id`, `user_id`, `provider`, `title`, `created_at`, `updated_at`.
2. Create the `Message` model: `id`, `conversation_id` (FK), `role`, `content`, `tool_name`, `tool_response`, `created_at`.
3. Write and run migrations.
4. Add basic serializers (DRF) for both models.
5. Build simple CRUD API endpoints: create conversation, list conversations, get conversation with messages.
6. Test via Postman/curl — no AI involved yet.

**Done when:** You can create a conversation and add messages to it purely through the API, and see them persisted in PostgreSQL.

---

## Module 2: Single-Provider Integration (Start with One — e.g., OpenAI)

**Goal:** Prove the core chat loop works end-to-end with one provider, built directly into the app.

1. In `chat/utils.py`, write a simple function `call_openai(messages)` that calls OpenAI's Chat Completions API and returns the response — no abstraction, just a direct function.
2. In `chat/views.py`, create the `/api/chat/` view: user sends a message → view loads conversation history from the DB → appends new message → calls `call_openai()` → saves both user and assistant messages → returns response.
3. Keep it simple and linear at this stage — all logic in the view and one utility function is fine.
4. Test full round-trip from the frontend: type a message, see a reply, refresh the page, see history persisted.

**Done when:** A full non-streaming chat conversation with OpenAI works and is saved to the database.

---

## Module 3: Add Claude and Gemini (Direct, Conditional Integration)

**Goal:** Full multi-provider support, using straightforward conditional logic instead of an abstraction layer.

1. In `chat/utils.py`, add two more simple functions: `call_claude(messages)` using Anthropic's Messages API, and `call_gemini(messages)` using Google's Gemini API.
2. In the `/api/chat/` view, add a simple conditional based on the conversation's `provider` field:
   ```python
   if conversation.provider == "openai":
       response = call_openai(messages)
   elif conversation.provider == "claude":
       response = call_claude(messages)
   elif conversation.provider == "gemini":
       response = call_gemini(messages)
   ```
3. Normalize each function's return value to the same simple shape (e.g., `{"content": ..., "role": "assistant"}`) so the rest of the view logic doesn't need to know which provider was used.
4. Add a provider selector in the frontend UI.
5. Test each provider independently with the same conversation flow from Module 2.

**Done when:** You can start a new conversation with any of the three providers and get consistent behavior from the frontend's perspective, with all logic visible directly in `views.py` and `utils.py`.

---

## Module 4: System Prompts

**Goal:** Let conversations have configurable AI behavior/personas.

1. Add a `system_prompt` field to the `Conversation` model (or a linked `SystemPromptTemplate` model if you want reusable presets like "AI Teacher," "Coding Assistant," etc.).
2. Ensure the system prompt is always injected as the first message when building the messages array for any provider.
3. Add a simple frontend selector or input for choosing/editing the system prompt when starting a new conversation.

**Done when:** Two conversations with different system prompts produce noticeably different AI behavior for the same user question.

---

## Module 5: Streaming Responses (SSE)

**Goal:** Real-time token streaming instead of waiting for the full response.

1. Update each provider module to support a streaming mode (most provider SDKs expose a streaming API).
2. Implement an SSE endpoint in Django (e.g., using `StreamingHttpResponse`) that yields tokens as they arrive from the provider.
3. On the frontend, use the native `EventSource` API (or a small SSE client) to consume the stream and render tokens incrementally.
4. Handle stream errors and client disconnects gracefully on both ends.
5. Once streaming completes, save the full assembled message to the database (same as non-streaming flow).

**Done when:** Messages visibly "type out" in the UI in real time for all three providers.

---

## Module 6: Function / Tool Calling

**Goal:** Let the AI call external tools mid-conversation.

1. In `chat/tools.py`, define simple tool functions (e.g., `get_weather(location)`, `calculate(expression)`) with a consistent input/output schema.
2. Extend the `call_openai`/`call_claude`/`call_gemini` functions in `chat/utils.py` to accept tool definitions and to detect when a provider response requests a tool call.
3. Implement the tool-execution loop:
   - Provider requests a tool → backend executes the matching function → tool result is appended to the messages array with `role: tool` → request is sent back to the provider for a final answer.
4. Add validation/sanitization for all tool inputs before execution.
5. Test with a simple tool (e.g., a calculator or mock weather API) across at least two providers, since tool-calling formats differ.

**Done when:** Asking "What's 245 * 12?" or "What's the weather in X?" correctly triggers a tool call and returns a grounded answer.

---

## Module 7: Structured Outputs (JSON Mode / Schema)

**Goal:** Get reliable, machine-readable responses for automation use cases.

1. Add a way to request structured output on the `/api/chat/` endpoint (e.g., a `response_format` parameter with an optional JSON Schema).
2. Implement provider-specific handling: JSON mode for providers that support it natively, prompt-engineered fallback for those that don't.
3. Validate the returned JSON against the provided schema before returning it to the frontend; retry once on validation failure if needed.
4. Test with a sample schema (e.g., extracting `{name, email, intent}` from a user message).

**Done when:** A structured request reliably returns valid JSON matching the schema, across providers.

---

## Module 8: Error Handling & Retry Logic

**Goal:** Make the system resilient to real-world API failures.

1. Wrap all provider calls in a consistent error-handling layer that classifies errors: rate limit, timeout, invalid request, server error.
2. Implement exponential backoff retry (e.g., 3 attempts with increasing delay) for transient errors (rate limits, timeouts, 5xx).
3. Implement token/context-length checks before sending a request; truncate history or return a clear error if it would exceed the model's limit.
4. Return clean, user-safe error messages to the frontend (no raw provider stack traces).
5. Add structured logging for all failures (without logging API keys or full sensitive payloads).

**Done when:** Simulated failures (e.g., invalid API key, oversized request) are handled gracefully with clear errors instead of crashing the request.

---

## Module 9: Provider Fallback

**Goal:** Automatic failover when a provider is down.

1. Define a fallback order (e.g., OpenAI → Claude → Gemini), configurable per deployment or per conversation.
2. In the provider-calling logic, catch unrecoverable errors (after retries are exhausted) and automatically retry the same request with the next provider in the fallback chain.
3. Log every fallback event with the reason for failover.
4. Return to the frontend which provider actually served the response, so the UI can reflect it if desired.
5. Test by temporarily using an invalid API key for the primary provider and confirming the system falls back correctly.

**Done when:** A conversation configured for "OpenAI" still gets a valid response (via fallback) even when the OpenAI key is deliberately broken.

---

## Module 10: Conversation Management UI

**Goal:** Polish the user-facing experience around history.

1. Build a conversation list/sidebar (fetch from the `Conversation` list endpoint).
2. Add "new conversation," "rename," and "delete" actions.
3. Add basic search/filter over conversation titles.
4. Add loading and error states throughout the chat UI.

**Done when:** A user can manage multiple ongoing conversations naturally, similar to ChatGPT's sidebar.

---

## Module 11: Security Hardening

**Goal:** Production-readiness from a security standpoint.

1. Add authentication (e.g., session or JWT-based) and scope all conversation/message queries to the authenticated user.
2. Confirm API keys are never sent to or readable from the frontend (audit network requests).
3. Add request validation on all endpoints (DRF serializers/validators).
4. Add rate limiting on the chat endpoint (e.g., per-user throttling in DRF).
5. Review logs to ensure no sensitive data (keys, full user PII) is being written.

**Done when:** A security review checklist (auth, key exposure, input validation, rate limiting, log hygiene) passes cleanly.

---

## Module 12: Performance & Scalability Pass

**Goal:** Make sure the system holds up under real load.

1. Add database indexes on frequently queried fields (`conversation_id`, `user_id`, `created_at`).
2. Add connection pooling for PostgreSQL.
3. Load-test the streaming endpoint with concurrent connections.
4. Review and optimize any N+1 query patterns in conversation/message retrieval.

**Done when:** The system handles your target concurrent user load without significant latency degradation.

---

## Module 13: Deployment

**Goal:** Ship it.

1. Containerize backend and frontend (Docker) or prepare deployment configs for your chosen platform.
2. Set up environment-specific `.env` configuration (dev/staging/production) with all provider keys stored securely (secrets manager or platform env vars).
3. Set up a managed PostgreSQL instance for production.
4. Configure HTTPS end-to-end.
5. Set up basic monitoring/alerting for provider errors and fallback frequency.

**Done when:** The app is live, reachable over HTTPS, and a real conversation across all three providers works in production.

---

## Suggested Build Order (Summary)

```
0. Setup  →  1. DB Models  →  2. Single Provider (OpenAI)  →  3. Add Claude + Gemini
   →  4. System Prompts  →  5. Streaming (SSE)  →  6. Tool Calling
   →  7. Structured Outputs  →  8. Error Handling & Retry  →  9. Provider Fallback
   →  10. Conversation UI  →  11. Security  →  12. Performance  →  13. Deployment
```

This order intentionally gets you to a *working, end-to-end demo* (Modules 0–2) as fast as possible, then layers in multi-provider support, real-time behavior, resilience, and polish — rather than trying to build every feature across all three providers simultaneously. Since we're using a traditional Django app architecture, provider logic stays directly inside `chat/views.py` and `chat/utils.py` throughout — there's no separate abstraction/factory step to build.

---

*This roadmap complements the SRS document — refer back to the relevant SRS section (e.g., "3.6 Streaming Responses") when implementing each module for the exact requirements to satisfy.*