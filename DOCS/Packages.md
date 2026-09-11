These are the packages that i have already installed.

# Core framework
pip install django djangorestframework

# Database
pip install psycopg2-binary          # PostgreSQL adapter

# Environment variables
pip install python-dotenv

# CORS (needed for Next.js frontend to call Django backend)
pip install django-cors-headers

# AI Provider SDKs
pip install openai                   # OpenAI
pip install anthropic                # Claude
pip install google-generativeai      # Gemini

# Retry logic with exponential backoff (Module 8: Error Handling & Retry)
pip install tenacity

# JSON Schema validation (Module 7: Structured Outputs)
pip install jsonschema

# Token counting / context length checks (Module 8)
pip install tiktoken

# Production server (Module 13: Deployment)
pip install gunicorn