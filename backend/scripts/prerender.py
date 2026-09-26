"""Produce a pre-rendered complete run in fallback/ for the demo safety net.

Generates a synthetic product reference (so it needs no external assets),
runs the full pipeline end to end, then copies the finished run folder into
fallback/. Run from the backend dir:  python -m scripts.prerender
"""
from __future__ import annotations

import asyncio
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402

from app import edits, orchestrator  # noqa: E402
from app.config import settings  # noqa: E402
from app.runs import create_run, run_dir  # noqa: E402


def _make_ref(path: Path) -> None:
    img = Image.new("RGB", (1024, 1024), (18, 20, 24))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([412, 280, 612, 780], radius=40, fill=(30, 32, 38), outline=(255, 107, 53), width=6)
    d.ellipse([452, 250, 572, 310], fill=(255, 107, 53))
    d.text((470, 520), "AURA", fill=(240, 240, 240))
    img.save(path)


async def main() -> None:
    if not settings.has_api_key:
        print("No GEMINI_API_KEY set — aborting.")
        return

    tmp_ref = run_dir("_prerender_ref")
    tmp_ref.mkdir(parents=True, exist_ok=True)
    ref_path = tmp_ref / "ref.png"
    _make_ref(ref_path)

    run_id, store = create_run(
        product_name="Aura Cold Brew",
        category="premium canned coffee",
        brief="One hero campaign, localized to four markets.",
        market_ids=["IN", "BR", "KR", "NG"],
        palette=["#0B0D10", "#FF6B35", "#F4E9DD"],
        style="warm cinematic product macro",
        ref_files=[("ref.png", ref_path.read_bytes())],
    )
    print("run:", run_id)

    print("image pipeline...")
    await orchestrator.run_image_pipeline(store)
    print("render (video + music + mux)...")
    await orchestrator.run_render(store)
    print("master edit propagation...")
    await edits.propagate_master_edit(store, "add gentle rising steam and slow the hero moment")

    src = run_dir(run_id)
    dst = settings.FALLBACK_DIR
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("fallback written to", dst)


if __name__ == "__main__":
    asyncio.run(main())
