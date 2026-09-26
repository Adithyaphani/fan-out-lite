"""Concept adapter — a multimodal text model turns the product photos + brief
+ palette + markets into an editable creative concept, and revises it on
instruction. Uses the utility model (gemini-3.8-flash).
"""
from __future__ import annotations

from google.genai import types

from ..config import settings
from .client import get_client


async def generate_concept(prompt: str, refs: list[bytes] | None = None) -> str:
    """Generate the initial creative concept from a prompt + product photos."""
    client = get_client()
    parts: list[types.Part] = [types.Part.from_text(text=prompt)]
    for r in refs or []:
        parts.append(types.Part.from_bytes(data=r, mime_type="image/png"))
    resp = await client.aio.models.generate_content(
        model=settings.UTILITY_MODEL,
        contents=parts,
    )
    return (resp.text or "").strip()


async def revise_concept(prompt: str) -> str:
    """Revise an existing concept per an instruction (text-only)."""
    client = get_client()
    resp = await client.aio.models.generate_content(
        model=settings.UTILITY_MODEL,
        contents=[types.Part.from_text(text=prompt)],
    )
    return (resp.text or "").strip()


async def generate_text(prompt: str) -> str:
    """Generic plain-text completion (used for the localized voiceover script)."""
    client = get_client()
    resp = await client.aio.models.generate_content(
        model=settings.UTILITY_MODEL,
        contents=[types.Part.from_text(text=prompt)],
    )
    return (resp.text or "").strip()


async def plan_json(prompt: str) -> str:
    """Return a strict-JSON completion (used for the timed shot list)."""
    client = get_client()
    resp = await client.aio.models.generate_content(
        model=settings.UTILITY_MODEL,
        contents=[types.Part.from_text(text=prompt)],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return (resp.text or "").strip()
