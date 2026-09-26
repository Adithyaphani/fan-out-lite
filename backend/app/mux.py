"""ffmpeg helpers: merge Omni video with a Lyria track and hard-cap the
duration so every market clip stays aligned even if a model overshoots.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from .config import settings


async def _run(*args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        tail = stderr.decode(errors="replace")[-800:]
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {tail}")


async def mux(video_path: str, track_path: str, out_path: str, duration_s: float | None = None) -> str:
    """Replace the clip's audio with the regional track, trimmed to duration.

    -t caps output length; -af apad pads a short track with silence so the
    stream never ends before the video. The Omni clip's own audio is dropped.
    """
    dur = duration_s if duration_s is not None else settings.AD_DURATION_S
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # If the hero clip is shorter than the target (Omni caps clips at ~10s),
    # loop it to fill the full ad timeline. -stream_loop repeats the input; -t
    # hard-caps the output; -af apad pads the track so it never ends early.
    vlen = await probe_duration(video_path)
    loop_video = vlen and vlen + 0.05 < dur
    pre_input = ["-stream_loop", "-1"] if loop_video else []
    # A looped stream can't be stream-copied cleanly, so re-encode when looping.
    vcodec = ["-c:v", "libx264", "-pix_fmt", "yuv420p"] if loop_video else ["-c:v", "copy"]

    await _run(
        *pre_input,
        "-i", video_path,
        "-i", track_path,
        "-map", "0:v:0", "-map", "1:a:0",
        *vcodec, "-c:a", "aac", "-b:a", "192k",
        "-af", "apad",
        "-t", f"{dur:.3f}",
        "-shortest",
        out_path,
    )
    return out_path


async def audio_to_wav(data: bytes) -> bytes:
    """Transcode arbitrary browser audio (webm/opus, ogg, m4a…) to 16 kHz mono
    PCM WAV — the most reliably transcribed format. Returns the wav bytes."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "in.bin"
        dst = Path(d) / "out.wav"
        src.write_bytes(data)
        await _run("-i", str(src), "-ac", "1", "-ar", "16000", "-f", "wav", str(dst))
        return dst.read_bytes()


async def probe_duration(path: str) -> float:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0
