"""EditEngine: conversational storyboard edits and the headline feature —
one master-edit instruction replayed across every market clip at once.

Edits are recorded as structured EditOps on the bible, so the chat transcript
and the per-market propagation status render straight from bible.edits.
"""
from __future__ import annotations

import secrets
import traceback

from .adapters import concept as concept_adapter
from .bible import EditOp, SceneBible, Status
from .config import settings
from .mux import mux
from .orchestrator import (
    _abs,
    _set_phase,
    edit_image,
    gen_image,
)
from .prompts import concept_edit_prompt, localized_board_prompt
from .runs import read_bytes, run_dir


def _new_id() -> str:
    return secrets.token_hex(4)


# --------------------------------------------------------- concept edit ------
async def edit_concept(store, instruction: str, source: str = "text") -> None:
    """Revise the creative concept conversationally (text or voice), before
    storyboards exist. Recorded as an EditOp(scope="concept")."""
    import asyncio

    bible = store.load()
    op = EditOp(id=_new_id(), scope="concept", instruction=instruction, source=source)
    await store.update(lambda b: b.edits.append(op))
    try:
        revised = await asyncio.wait_for(
            concept_adapter.revise_concept(concept_edit_prompt(bible.concept, instruction)),
            settings.IMAGE_TIMEOUT_S,
        )
        await store.update(lambda b: setattr(b, "concept", revised))
        await _mark_edit(store, op.id, {"concept": Status.done.value})
    except Exception:
        traceback.print_exc()
        await _mark_edit(store, op.id, {"concept": Status.failed.value})


# ------------------------------------------------------ storyboard edit ------
async def edit_storyboard_shot(store, shot_id: str, instruction: str, source: str = "text") -> None:
    """Edit one master shot, then re-localize that shot across all markets.

    Because NB2 Lite is fast, this round-trips all markets in seconds — the
    second visible "speed is load-bearing" moment.
    """
    bible = store.load()
    shot = bible.shot(shot_id)
    if not shot or not shot.master_image:
        raise ValueError(f"shot {shot_id} has no master image to edit")

    op = EditOp(id=_new_id(), scope="storyboard_shot", target=shot_id,
                instruction=instruction, source=source)
    await store.update(lambda b: b.edits.append(op))
    await _set_phase(store, "imaging")

    # 1. New master frame for this shot.
    master_bytes = read_bytes(bible.run_id, shot.master_image)
    master_rel = shot.master_image  # overwrite in place; version tracked via edits
    try:
        await edit_image(master_bytes, instruction, _abs(bible.run_id, master_rel))
    except Exception as exc:  # noqa: BLE001
        await _mark_edit(store, op.id, {"master": Status.failed.value})
        raise

    sheet = [read_bytes(bible.run_id, bible.brand.brand_sheet)] if bible.brand.brand_sheet else []
    new_master = read_bytes(bible.run_id, master_rel)

    # 2. Re-localize the shot for every market in parallel.
    import asyncio

    async def relocalize(market_id: str):
        market = bible.market(market_id)
        rel = f"images/board_{market_id}_{shot_id}.png"
        try:
            await gen_image(
                localized_board_prompt(bible, shot, market),
                refs=[new_master] + sheet,
                out_path=_abs(bible.run_id, rel),
            )
            await store.update(lambda b: _set_board(b, market_id, shot_id, rel))
            return market_id, Status.done.value
        except Exception:
            traceback.print_exc()
            return market_id, Status.failed.value

    results = await asyncio.gather(*(relocalize(m.id) for m in bible.markets))
    await _mark_edit(store, op.id, dict(results))
    await _set_phase(store, "boards_ready")


# ------------------------------------------------ master-edit propagation ----
async def propagate_master_edit(store, instruction: str, source: str = "text") -> None:
    """Replay one instruction across every non-failed market ad, then re-mux.

    Ads are stitched from per-scene clips (each within Omni's 10s cap), so a
    single long clip can't be edited in one call. Instead we regenerate every
    scene with the instruction folded into its prompt and re-stitch — preserving
    each market's localization. Music is reused (edits keep BPM/duration fixed).
    """
    import asyncio

    from .orchestrator import render_market_video

    bible = store.load()
    op = EditOp(id=_new_id(), scope="master_clip", instruction=instruction, source=source)
    await store.update(lambda b: b.edits.append(op))
    await _set_phase(store, "propagating")

    async def apply(market_id: str):
        bib = store.load()
        clip = bib.clip(market_id)
        if not clip or clip.status == Status.failed or not clip.raw_video:
            return market_id, Status.failed.value
        version = clip.version + 1
        try:
            raw = await render_market_video(bible, market_id, version=version,
                                            extra_instruction=instruction)
            if not raw:
                return market_id, Status.failed.value
            await store.update(lambda b: _bump_clip(b, market_id, raw))
            return market_id, Status.done.value
        except Exception:
            traceback.print_exc()
            return market_id, Status.failed.value

    results = await asyncio.gather(*(apply(m.id) for m in bible.markets))
    await _mark_edit(store, op.id, dict(results))

    # Re-mux updated clips against their existing tracks.
    bible = store.load()

    async def remux(market_id: str):
        bib = store.load()
        c = bib.clip(market_id)
        if not c or not c.raw_video or not c.track:
            return
        rel = f"final/{market_id}_v{c.version}.mp4"
        await mux(_abs(bible.run_id, c.raw_video), _abs(bible.run_id, c.track),
                  _abs(bible.run_id, rel), duration_s=bible.duration_s)
        await store.update(lambda b: _finalize(b, market_id, rel))

    await asyncio.gather(*(remux(m.id) for m in bible.markets), return_exceptions=True)
    await _set_phase(store, "rendered")


# -------------------------------------------------- per-location clip edit ----
async def edit_market_clip(store, market_id: str, instruction: str, source: str = "text") -> None:
    """Apply an edit to ONE market's ad only (location-wise edit).

    Regenerates just that market's scenes with the instruction folded in,
    re-stitches, and re-muxes against its existing track. The other markets
    are untouched.
    """
    from .orchestrator import render_market_video

    bible = store.load()
    op = EditOp(id=_new_id(), scope="market_clip", target=market_id,
                instruction=instruction, source=source)
    await store.update(lambda b: b.edits.append(op))
    await _set_phase(store, "propagating")

    clip = bible.clip(market_id)
    if not clip or not clip.raw_video:
        await _mark_edit(store, op.id, {market_id: Status.failed.value})
        await _set_phase(store, "rendered")
        return

    version = clip.version + 1
    try:
        raw = await render_market_video(bible, market_id, version=version,
                                        extra_instruction=instruction)
        if not raw:
            raise RuntimeError("no video produced")
        await store.update(lambda b: _bump_clip(b, market_id, raw))
        # Re-mux this market only.
        bib = store.load()
        c = bib.clip(market_id)
        if c and c.raw_video and c.track:
            rel = f"final/{market_id}_v{c.version}.mp4"
            await mux(_abs(bible.run_id, c.raw_video), _abs(bible.run_id, c.track),
                      _abs(bible.run_id, rel), duration_s=bible.duration_s)
            await store.update(lambda b: _finalize(b, market_id, rel))
        await _mark_edit(store, op.id, {market_id: Status.done.value})
    except Exception:
        traceback.print_exc()
        await _mark_edit(store, op.id, {market_id: Status.failed.value})
    await _set_phase(store, "rendered")


# ---------------------------------------------------------- mutators ----------
async def _mark_edit(store, op_id: str, applied: dict[str, str]) -> None:
    def _apply(b: SceneBible):
        for e in b.edits:
            if e.id == op_id:
                e.applied.update(applied)

    await store.update(_apply)


def _set_board(b: SceneBible, market_id: str, shot_id: str, image_rel: str) -> None:
    bd = b.board(market_id, shot_id)
    if bd:
        bd.image = image_rel
        bd.status = Status.done


def _bump_clip(b: SceneBible, market_id: str, raw_rel: str) -> None:
    c = b.clip(market_id)
    if c:
        c.raw_video = raw_rel
        c.version += 1
        c.status = Status.done


def _finalize(b: SceneBible, market_id: str, final_rel: str) -> None:
    c = b.clip(market_id)
    if c:
        c.final = final_rel
