"""Brand judge (optional) — a Gemini multimodal model scores a generated
board against the product references and returns strict JSON. First feature
to cut under time pressure; gated behind ENABLE_BRAND_JUDGE.
"""
from __future__ import annotations

import json
import re

from google.genai import types

from ..config import settings
from ..prompts import brand_judge_prompt
from .client import get_client


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"score": None, "issues": ["judge returned no JSON"]}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"score": None, "issues": ["judge returned invalid JSON"]}


async def score_board(board_image: bytes, refs: list[bytes], brand) -> dict:
    """Return {"score": 0-100 | None, "issues": [...]}. Never raises."""
    client = get_client()
    parts: list[types.Part] = [types.Part.from_text(text=brand_judge_prompt(brand))]
    for r in refs:
        parts.append(types.Part.from_bytes(data=r, mime_type="image/png"))
    parts.append(types.Part.from_bytes(data=board_image, mime_type="image/png"))
    try:
        resp = await client.aio.models.generate_content(
            model=settings.UTILITY_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return _parse_json(resp.text or "")
    except Exception as exc:  # judge is best-effort
        return {"score": None, "issues": [f"judge error: {exc}"]}


async def transcribe(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe a spoken storyboard edit to text (voice path)."""
    client = get_client()
    resp = await client.aio.models.generate_content(
        model=settings.UTILITY_MODEL,
        contents=[
            types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
            types.Part.from_text(
                text="Transcribe this spoken instruction verbatim. Return only the text."
            ),
        ],
    )
    return (resp.text or "").strip()
