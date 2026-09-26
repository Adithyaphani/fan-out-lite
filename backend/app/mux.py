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


async def mux(
    video_path: str,
    track_path: str,
    out_path: str,
    duration_s: float | None = None,
    voice_path: str | None = None,
) -> str:
    """Merge the clip's video with the regional music track, trimmed to
    duration. When `voice_path` is given, a spoken voiceover is mixed in over
    the (ducked) background music — otherwise the final has music only, no
    narration. -t caps output length so the stream never overshoots; the
    Omni clip's own audio is always dropped in favour of the generated track(s).
    """
    dur = duration_s if duration_s is not None else settings.AD_DURATION_S
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # If the hero clip is shorter than the target (Omni caps clips at ~10s),
    # loop it to fill the full ad timeline. -stream_loop repeats the input; -t
    # hard-caps the output.
    vlen = await probe_duration(video_path)
    loop_video = vlen and vlen + 0.05 < dur
    pre_input = ["-stream_loop", "-1"] if loop_video else []
    # A looped stream can't be stream-copied cleanly, so re-encode when looping.
    vcodec = ["-c:v", "libx264", "-pix_fmt", "yuv420p"] if loop_video else ["-c:v", "copy"]

    if voice_path:
        # Ducks the background music under the narration and mixes them into
        # one audio stream. `apad` on each keeps the stream alive past its own
        # natural length so `-t` (not a short input) decides where audio ends.
        filt = (
            "[1:a]volume=0.25,apad[bg];"
            "[2:a]apad[vo];"
            "[bg][vo]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        await _run(
            *pre_input,
            "-i", video_path,
            "-i", track_path,
            "-i", voice_path,
            "-filter_complex", filt,
            "-map", "0:v:0", "-map", "[aout]",
            *vcodec, "-c:a", "aac", "-b:a", "192k",
            "-t", f"{dur:.3f}",
            out_path,
        )
    else:
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


async def concat(video_paths: list[str], out_path: str) -> str:
    """Concatenate per-scene clips into one video (no audio).

    Each input is normalised to a common 1280x720 frame before concat so clips
    of slightly different sizes stitch cleanly; the result is re-encoded h264.
    """
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    n = len(video_paths)
    if n == 0:
        raise RuntimeError("concat: no clips")

    inputs: list[str] = []
    for p in video_paths:
        inputs += ["-i", p]
    norm = "".join(
        f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
        f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v{i}];"
        for i in range(n)
    )
    joins = "".join(f"[v{i}]" for i in range(n))
    filt = f"{norm}{joins}concat=n={n}:v=1:a=0[v]"
    await _run(
        *inputs,
        "-filter_complex", filt,
        "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
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
