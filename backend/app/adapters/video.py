"""Video adapter — Omni (gemini-omni-1.1-flash).

Verified call shape (smoke test): Omni is served through the next-gen
Interactions API, NOT models.generate_content (that returns
"This model only supports Interactions API"). We create a background
interaction with an image + text input and a video response_format, then
poll interactions.get until status == "completed". Output is inline mp4
(h264/aac, 1280x720). ~40s per 6s clip.
"""
from __future__ import annotations

import asyncio
import base64
from pathlib import Path

from ..config import settings
from .client import get_client

_POLL_INTERVAL_S = 4
_TERMINAL = {"completed", "succeeded", "failed", "cancelled", "canceled", "error"}


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _as_bytes(data) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return base64.b64decode(data)
    raise RuntimeError("Unexpected video data type from Omni")


async def _run_interaction(inputs: list[dict], out_path: str, duration_s: float | None = None) -> str:
    client = get_client()
    dur = duration_s if duration_s is not None else settings.AD_DURATION_S
    # Omni rejects durations above its per-clip maximum (10s); clamp here and let
    # the muxer loop the clip to fill a longer ad timeline.
    dur = max(1.0, min(float(settings.VIDEO_MAX_S), float(dur)))
    duration = f"{int(round(dur))}s"
    interaction = await client.aio.interactions.create(
        model=settings.VIDEO_MODEL,
        input=inputs,
        response_format={
            "type": "video",
            "aspect_ratio": settings.AD_ASPECT,
            "duration": duration,
            "delivery": "inline",
        },
        background=True,
    )

    interaction_id = interaction.id
    status = str(interaction.status).lower()
    while status not in _TERMINAL:
        await asyncio.sleep(_POLL_INTERVAL_S)
        interaction = await client.aio.interactions.get(interaction_id)
        status = str(interaction.status).lower()

    if status not in ("completed", "succeeded"):
        errs = getattr(interaction, "errors", None)
        raise RuntimeError(f"Omni interaction {status}: {errs}")

    video = getattr(interaction, "output_video", None)
    if not video or not getattr(video, "data", None):
        raise RuntimeError("Omni completed but returned no inline video")

    raw = _as_bytes(video.data)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(raw)
    return out_path


async def generate_clip(prompt: str, keyframe: bytes, out_path: str, duration_s: float | None = None) -> str:
    """Animate a clip from one storyboard keyframe plus a prompt."""
    inputs = [
        {"type": "image", "mime_type": "image/png", "data": _b64(keyframe)},
        {"type": "text", "text": prompt},
    ]
    return await _run_interaction(inputs, out_path, duration_s)


async def edit_clip(clip_bytes: bytes, keyframe: bytes, instruction: str, out_path: str, duration_s: float | None = None) -> str:
    """Multi-turn edit: feed the existing clip plus the instruction back to Omni.

    If Omni rejects a video input for editing, the orchestrator falls back to
    regenerating from the keyframe with the instruction folded into the prompt.
    """
    inputs = [
        {"type": "video", "mime_type": "video/mp4", "data": _b64(clip_bytes)},
        {"type": "image", "mime_type": "image/png", "data": _b64(keyframe)},
        {"type": "text", "text": instruction},
    ]
    return await _run_interaction(inputs, out_path, duration_s)
