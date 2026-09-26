"""Voice adapter — narration/voiceover TTS (gemini-3.8-flash-tts).

Verified call shape: models.generate_content with response_modalities=["AUDIO"]
and a speech_config.voice_config.prebuilt_voice_config; this model returns
ready-to-mux inline audio/wav (unlike some sibling TTS models that return raw
PCM and need manual WAV wrapping).
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
    raise RuntimeError("TTS model returned no audio")


async def generate_voiceover(text: str, out_path: str, voice_name: str | None = None) -> str:
    """Synthesize a spoken line to a wav file and return its path."""
    client = get_client()
    resp = await client.aio.models.generate_content(
        model=settings.VOICE_MODEL,
        contents=[text],
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice_name or settings.VOICE_NAME
                    )
                )
            ),
        ),
    )
    data = _extract_audio(resp)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(data)
    return out_path
