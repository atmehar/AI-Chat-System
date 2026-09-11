'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
const AUTH_STORAGE_KEY = 'ai-chat-auth';

function readStoredAuth() {
  if (typeof window === 'undefined') return null;
  try {
    return JSON.parse(window.localStorage.getItem(AUTH_STORAGE_KEY) || 'null');
  } catch {
    return null;
  }
}

function avatarLetter(name) {
  const value = (name || '').trim();
  return value ? value[0].toUpperCase() : '?';
}

export default function Home() {
  const [user, setUser] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [provider, setProvider] = useState('openai');
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState('');
  const [loginOpen, setLoginOpen] = useState(false);
  const [authMode, setAuthMode] = useState('login');
  const [authForm, setAuthForm] = useState({ name: '', username: '', password: '' });
  const [authError, setAuthError] = useState('');
  const [authBusy, setAuthBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const messagesEndRef = useRef(null);
  const menuRef = useRef(null);

  const selectedConversation = conversations.find(
    (conversation) => conversation.id === selectedConversationId
  );

  const chatMessages = useMemo(
    () => messages.filter((message) => message.role === 'user' || message.role === 'assistant'),
    [messages]
  );

  const apiFetch = async (path, options = {}) => {
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };
    if (user?.token) {
      headers.Authorization = `Token ${user.token}`;
    }

    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 204) return null;

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = payload.error || payload.detail;
      const message = Array.isArray(detail) ? detail.join(' ') : (detail || 'Request failed');
      throw new Error(typeof message === 'string' ? message : 'Request failed');
    }
    return payload;
  };

  const persistUser = (nextUser) => {
    setUser(nextUser);
    if (nextUser) {
      window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextUser));
    } else {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  };

  const loadConversations = async (activeUser = user) => {
    if (!activeUser?.token) {
      setConversations([]);
      return [];
    }

    setLoadingHistory(true);
    try {
      const data = await fetch(`${API_URL}/conversations/`, {
        headers: { Authorization: `Token ${activeUser.token}` },
      }).then(async (response) => {
        const payload = await response.json().catch(() => []);
        if (!response.ok) throw new Error(payload.error || 'Failed to fetch conversations');
        return payload;
      });
      setConversations(data);
      return data;
    } catch (loadError) {
      setError(loadError.message);
      return [];
    } finally {
      setLoadingHistory(false);
    }
  };

  const loadMessages = async (conversationId, activeUser = user) => {
    if (!conversationId || !activeUser?.token) {
      setMessages([]);
      return;
    }

    try {
      const data = await fetch(`${API_URL}/conversations/${conversationId}/messages/`, {
        headers: { Authorization: `Token ${activeUser.token}` },
      }).then(async (response) => {
        const payload = await response.json().catch(() => []);
        if (!response.ok) throw new Error(payload.error || 'Failed to load chat');
        return payload;
      });
      setMessages(data);
    } catch (loadError) {
      setError(loadError.message);
    }
  };

  useEffect(() => {
    const stored = readStoredAuth();
    if (!stored?.token) return;

    const restore = async () => {
      try {
        const response = await fetch(`${API_URL}/auth/me/`, {
          headers: { Authorization: `Token ${stored.token}` },
        });
        if (!response.ok) throw new Error('Session expired');
        const payload = await response.json();
        const nextUser = { ...payload, token: stored.token };
        persistUser(nextUser);
        const history = await loadConversations(nextUser);
        if (history[0]) {
          setSelectedConversationId(history[0].id);
          setProvider(history[0].provider || 'openai');
        }
      } catch {
        persistUser(null);
      }
    };

    restore();
  }, []);

  useEffect(() => {
    if (selectedConversationId) {
      loadMessages(selectedConversationId);
    } else {
      setMessages([]);
    }
  }, [selectedConversationId, user?.token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, sending]);

  useEffect(() => {
    const onClick = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const requireLogin = () => {
    setAuthMode('login');
    setAuthError('');
    setLoginOpen(true);
  };

  const handleAuthSubmit = async (event) => {
    event.preventDefault();
    setAuthBusy(true);
    setAuthError('');

    try {
      const path = authMode === 'register' ? '/auth/register/' : '/auth/login/';
      const body = {
        username: authForm.username.trim(),
        password: authForm.password,
      };
      if (authMode === 'register') body.name = authForm.name.trim();

      const payload = await fetch(`${API_URL}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }).then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || 'Authentication failed');
        return data;
      });

      persistUser(payload);
      setLoginOpen(false);
      setAuthForm({ name: '', username: '', password: '' });
      const history = await loadConversations(payload);
      if (history[0] && !selectedConversationId) {
        setSelectedConversationId(history[0].id);
        setProvider(history[0].provider || 'openai');
      }
    } catch (submitError) {
      setAuthError(submitError.message);
    } finally {
      setAuthBusy(false);
    }
  };

  const handleLogout = async () => {
    try {
      if (user?.token) {
        await fetch(`${API_URL}/auth/logout/`, {
          method: 'POST',
          headers: { Authorization: `Token ${user.token}` },
        });
      }
    } finally {
      persistUser(null);
      setConversations([]);
      setSelectedConversationId(null);
      setMessages([]);
      setMenuOpen(false);
    }
  };

  const handleCreateConversation = async () => {
    setError('');
    if (!user) {
      requireLogin();
      return;
    }

    try {
      const created = await apiFetch('/conversations/', {
        method: 'POST',
        body: JSON.stringify({
          title: 'New Chat',
          provider,
        }),
      });
      setConversations((current) => [created, ...current]);
      setSelectedConversationId(created.id);
      setMessages([]);
      setDraft('');
    } catch (createError) {
      setError(createError.message);
    }
  };

  const handleSelectConversation = (conversation) => {
    setSelectedConversationId(conversation.id);
    setProvider(conversation.provider || 'openai');
    setError('');
  };

  const handleSend = async (event) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;

    if (!user) {
      requireLogin();
      return;
    }

    setSending(true);
    setError('');
    setDraft('');

    try {
      let conversationId = selectedConversationId;
      if (!conversationId) {
        const created = await apiFetch('/conversations/', {
          method: 'POST',
          body: JSON.stringify({
            title: text.slice(0, 48),
            provider,
          }),
        });
        conversationId = created.id;
        setConversations((current) => [created, ...current]);
        setSelectedConversationId(created.id);
      }

      setMessages((current) => [
        ...current,
        { id: `local-${Date.now()}`, role: 'user', content: text },
      ]);

      const result = await apiFetch('/chat/', {
        method: 'POST',
        body: JSON.stringify({
          conversation_id: conversationId,
          message: text,
          content: text,
          provider,
        }),
      });

      if (result?.response) {
        setMessages((current) => [
          ...current,
          { id: result.message_id || `assistant-${Date.now()}`, role: 'assistant', content: result.response },
        ]);
      }

      await loadMessages(conversationId);
      await loadConversations();
    } catch (sendError) {
      setError(sendError.message);
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="flex h-screen overflow-hidden bg-slate-950 text-slate-100">
      <aside className="flex w-72 shrink-0 flex-col border-r border-slate-800 bg-slate-900">
        <div className="border-b border-slate-800 p-4">
          <button
            type="button"
            onClick={handleCreateConversation}
            className="w-full rounded-xl bg-cyan-500 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
          >
            Create/Start Conversation
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col p-4">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
            Chat history
          </p>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
            {!user ? (
              <p className="text-sm text-slate-400">Log in to see chats you have started.</p>
            ) : loadingHistory ? (
              <p className="text-sm text-slate-400">Loading history...</p>
            ) : conversations.length === 0 ? (
              <p className="text-sm text-slate-400">No conversations yet. Start one to see it here.</p>
            ) : (
              conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => handleSelectConversation(conversation)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                    selectedConversationId === conversation.id
                      ? 'border-cyan-500 bg-cyan-500/10'
                      : 'border-slate-800 bg-slate-950 hover:border-slate-700'
                  }`}
                >
                  <p className="truncate text-sm font-medium text-slate-100">{conversation.title}</p>
                  <p className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">
                    {conversation.provider}
                  </p>
                </button>
              ))
            )}
          </div>
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-400">AI Chat System</p>
            <h1 className="truncate text-lg font-semibold">
              {selectedConversation ? selectedConversation.title : 'New conversation'}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            <select
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none"
            >
              <option value="openai">OpenAI</option>
              <option value="claude">Claude</option>
              <option value="gemini">Gemini</option>
            </select>

            {user ? (
              <div className="relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setMenuOpen((open) => !open)}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500 text-sm font-bold text-slate-950"
                  aria-label="Account menu"
                >
                  {avatarLetter(user.name || user.username)}
                </button>
                {menuOpen ? (
                  <div className="absolute right-0 z-20 mt-2 w-48 rounded-xl border border-slate-800 bg-slate-900 p-2">
                    <p className="truncate px-2 py-1 text-sm text-slate-300">{user.name}</p>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="mt-1 w-full rounded-lg px-2 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
                    >
                      Log out
                    </button>
                  </div>
                ) : null}
              </div>
            ) : (
              <button
                type="button"
                onClick={requireLogin}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-100 hover:border-cyan-500 hover:text-cyan-400"
              >
                Login
              </button>
            )}
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
          {error ? (
            <p className="mb-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
              {error}
            </p>
          ) : null}

          {chatMessages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <div className="max-w-md text-center">
                <h2 className="text-2xl font-semibold">Start chatting</h2>
                <p className="mt-2 text-sm text-slate-400">
                  {user
                    ? 'Select a conversation from your history or create a new one.'
                    : 'Log in to start a conversation. Your chat history will appear in the sidebar.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {chatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                      message.role === 'user'
                        ? 'bg-cyan-500 text-slate-950'
                        : 'border border-slate-800 bg-slate-900 text-slate-100'
                    }`}
                  >
                    {message.content}
                  </div>
                </div>
              ))}
              {sending ? (
                <div className="flex justify-start">
                  <div className="rounded-2xl border border-slate-800 bg-slate-900 px-4 py-3 text-sm text-slate-400">
                    Thinking...
                  </div>
                </div>
              ) : null}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <form onSubmit={handleSend} className="border-t border-slate-800 px-6 py-4">
          <div className="mx-auto flex max-w-3xl gap-3">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={user ? 'Type a message...' : 'Log in to send a message'}
              className="flex-1 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500"
            />
            <button
              type="submit"
              disabled={sending || !draft.trim()}
              className="rounded-xl bg-cyan-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </form>
      </section>

      {loginOpen ? (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-slate-950/70 px-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xl font-semibold">{authMode === 'login' ? 'Login' : 'Create account'}</h2>
              <button
                type="button"
                onClick={() => setLoginOpen(false)}
                className="text-sm text-slate-400 hover:text-slate-200"
              >
                Close
              </button>
            </div>

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              {authMode === 'register' ? (
                <div>
                  <label className="mb-1 block text-sm text-slate-300">Name</label>
                  <input
                    value={authForm.name}
                    onChange={(event) => setAuthForm((current) => ({ ...current, name: event.target.value }))}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none"
                    placeholder="Your name"
                  />
                </div>
              ) : null}
              <div>
                <label className="mb-1 block text-sm text-slate-300">Username</label>
                <input
                  value={authForm.username}
                  onChange={(event) => setAuthForm((current) => ({ ...current, username: event.target.value }))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none"
                  placeholder="username"
                  required
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-slate-300">Password</label>
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(event) => setAuthForm((current) => ({ ...current, password: event.target.value }))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none"
                  placeholder="At least 8 characters"
                  required
                />
              </div>
              {authError ? <p className="text-sm text-red-300">{authError}</p> : null}
              <button
                type="submit"
                disabled={authBusy}
                className="w-full rounded-xl bg-cyan-500 px-4 py-2 font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
              >
                {authBusy ? 'Please wait...' : authMode === 'login' ? 'Login' : 'Create account'}
              </button>
            </form>

            <p className="mt-4 text-center text-sm text-slate-400">
              {authMode === 'login' ? 'Need an account?' : 'Already have an account?'}{' '}
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === 'login' ? 'register' : 'login');
                  setAuthError('');
                }}
                className="text-cyan-400 hover:text-cyan-300"
              >
                {authMode === 'login' ? 'Create one' : 'Login'}
              </button>
            </p>
          </div>
        </div>
      ) : null}
    </main>
  );
}
