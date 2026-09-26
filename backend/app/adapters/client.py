"""Shared google-genai client. One process-wide async-capable client.

Isolating client construction here means an SDK/auth change touches one file.
"""
from __future__ import annotations

from functools import lru_cache

from google import genai

from ..config import settings


@lru_cache
def get_client() -> genai.Client:
    if not settings.has_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy backend/.env.example to backend/.env "
            "and add your key."
        )
    return genai.Client(api_key=settings.GEMINI_API_KEY)
