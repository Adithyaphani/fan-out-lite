"""0:00-0:20 go/no-go smoke test.

Confirms all three models return output and records latency. Run from the
backend dir:  python -m scripts.smoke_test
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters import image, music, video  # noqa: E402
from app.config import settings  # noqa: E402

SP = Path(__file__).resolve().parent.parent / "runs" / "_smoke"
SP.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    if not settings.has_api_key:
        print("No GEMINI_API_KEY set — aborting.")
        return

    t = time.perf_counter()
    await image.generate_image(
        "a matte black coffee bottle on a wooden table, warm cinematic light, 16:9",
        out_path=str(SP / "img.png"),
    )
    print(f"image:            {time.perf_counter() - t:6.1f}s")

    keyframe = (SP / "img.png").read_bytes()

    t = time.perf_counter()
    await music.generate_track("bossa groove, 128 BPM, premium, instrumental", str(SP / "trk.mp3"))
    print(f"music:            {time.perf_counter() - t:6.1f}s")

    t = time.perf_counter()
    await video.generate_clip(
        "slow cinematic push-in on the bottle, gentle steam, warm light",
        keyframe, str(SP / "vid.mp4"),
    )
    dt = time.perf_counter() - t
    print(f"video:            {dt:6.1f}s   {'GO' if dt < 60 else 'NO-GO (pivot)'}")

    t = time.perf_counter()
    await asyncio.gather(*(
        image.generate_image(f"test product shot {i}", out_path=str(SP / f"p{i}.png"))
        for i in range(8)
    ))
    print(f"8 parallel images:{time.perf_counter() - t:6.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
