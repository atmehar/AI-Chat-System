DEFAULT_PROVIDERS = ('openai', 'claude', 'gemini')
FALLBACK_ORDER = {
    'openai': ('openai', 'claude', 'gemini'),
    'claude': ('claude', 'openai', 'gemini'),
    'gemini': ('gemini', 'openai', 'claude'),
}


def provider_order(provider, fallback_order=None):
    requested = (provider or 'openai').lower()
    allowed = set(DEFAULT_PROVIDERS)
    if fallback_order:
        providers = [name for name in fallback_order if name in allowed]
    else:
        providers = list(FALLBACK_ORDER.get(requested, DEFAULT_PROVIDERS))
    if requested not in providers:
        providers.insert(0, requested)
    return providers