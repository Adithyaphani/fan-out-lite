"""Music adapter — Lyria (lyria-3.5).

Verified call shape (smoke test): models.generate_content with
response_modalities=["AUDIO"]; returns inline audio/mpeg (mp3). Lyria does
not honour an exact duration (it returned ~80s for an 8s request), so the
muxer trims/pads every track to the bible duration with ffmpeg -t.
"""
from __future__ import annotations

from pathlib import Path

from google.genai import types

from ..config import settings
from .client import get_client


def _extract_audio(resp) -> bytes:
    for cand in getattr(resp, "candidates", None) or []:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
    raise RuntimeError("Lyria returned no audio")


async def generate_track(prompt: str, out_path: str) -> str:
    """Generate one instrumental track. Duration is normalised downstream."""
    client = get_client()
    resp = await client.aio.models.generate_content(
        model=settings.MUSIC_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(response_modalities=["AUDIO"]),
    )
    data = _extract_audio(resp)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(data)
    return out_path
