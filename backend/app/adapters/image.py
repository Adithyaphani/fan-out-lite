"""Image adapter — NB2 Lite (gemini-3.1-flash-lite-image).

Verified call shape (smoke test): models.generate_content with
response_modalities=["IMAGE"]; product refs are passed as inline image Parts.
The model returns inline JPEG bytes. ~5s per call.
"""
from __future__ import annotations

from pathlib import Path

from google.genai import types

from ..config import settings
from .client import get_client


def _extract_image(resp) -> bytes:
    candidates = getattr(resp, "candidates", None) or []
    for cand in candidates:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            inline = getattr(part, "inline_data", None)
            if inline and inline.data:
                return inline.data
    # No image came back — surface any text the model returned as the error.
    texts = []
    for cand in candidates:
        content = getattr(cand, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                texts.append(part.text)
    raise RuntimeError(
        "Image model returned no image. " + (" ".join(texts)[:300] if texts else "")
    )


async def generate_image(prompt: str, refs: list[bytes] | None = None, out_path: str = "") -> str:
    """Generate one image from a prompt plus optional reference photos."""
    client = get_client()
    parts: list[types.Part] = []
    for r in refs or []:
        parts.append(types.Part.from_bytes(data=r, mime_type="image/png"))
    parts.append(types.Part.from_text(text=prompt))

    resp = await client.aio.models.generate_content(
        model=settings.IMAGE_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    data = _extract_image(resp)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(data)
    return out_path


async def edit_image(image: bytes, instruction: str, out_path: str) -> str:
    """Conversational edit = the source image plus an instruction in one call."""
    return await generate_image(instruction, refs=[image], out_path=out_path)
