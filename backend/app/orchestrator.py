"""The orchestrator: runs pipeline stages with per-model concurrency limits,
timeouts and retries, records timings, and keeps the scene bible authoritative.

Every stage is idempotent: an asset already marked `done` is skipped, so a
crash mid-run costs only the failed calls. Only this module and edits.py write
to the bible.
"""
from __future__ import annotations

import asyncio
import functools
import traceback

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .adapters import concept as concept_adapter
from .adapters import image, judge, music, video, voice
from .bible import Clip, MarketBoard, SceneBible, Status
from .config import settings
from .mux import concat, mux
from .prompts import (
    brand_sheet_prompt,
    concept_prompt,
    localized_board_prompt,
    master_shot_prompt,
    regional_track_prompt,
    scene_clip_prompt,
    shotlist_prompt,
    voiceover_script_prompt,
)
from .runs import read_bytes, run_dir

# ---- per-model concurrency limits (fan-out width), created lazily on the loop ----
_LIMITS: dict[str, asyncio.Semaphore] = {}
_TIMEOUTS = {
    "image": settings.IMAGE_TIMEOUT_S,
    "video": settings.VIDEO_TIMEOUT_S,
    "music": settings.MUSIC_TIMEOUT_S,
    "voice": settings.VOICE_TIMEOUT_S,
}
_SIZES = {
    "image": settings.IMAGE_CONCURRENCY,
    "video": settings.VIDEO_CONCURRENCY,
    "music": settings.MUSIC_CONCURRENCY,
    "voice": settings.MUSIC_CONCURRENCY,  # narration is cheap; reuse the music lane's width
}


def _limit(kind: str) -> asyncio.Semaphore:
    sem = _LIMITS.get(kind)
    if sem is None:
        sem = asyncio.Semaphore(_SIZES[kind])
        _LIMITS[kind] = sem
    return sem


def guarded(kind: str):
    """Wrap a model coroutine with a semaphore, a timeout and retry/backoff."""

    def deco(fn):
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(min=2, max=20),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        )
        @functools.wraps(fn)
        async def inner(*a, **kw):
            async with _limit(kind):
                return await asyncio.wait_for(fn(*a, **kw), _TIMEOUTS[kind])

        return inner

    return deco


gen_image = guarded("image")(image.generate_image)
edit_image = guarded("image")(image.edit_image)
gen_clip = guarded("video")(video.generate_clip)
edit_clip = guarded("video")(video.edit_clip)
gen_track = guarded("music")(music.generate_track)
gen_voice = guarded("voice")(voice.generate_voiceover)


# ---------------------------------------------------------------- helpers ----
def _refs(bible: SceneBible) -> list[bytes]:
    return [read_bytes(bible.run_id, p) for p in bible.brand.product_refs]


def _abs(run_id: str, rel: str) -> str:
    return str(run_dir(run_id) / rel)


async def _set_phase(store, phase: str) -> None:
    await store.update(lambda b: setattr(b, "phase", phase))


# ------------------------------------------------------- stage 0 (plan) ------
def _normalize_timeline(shots, duration: float) -> None:
    """Split the timeline into equal contiguous windows covering 0..duration.

    Even windows guarantee every scene fits Omni's per-clip cap (the scene count
    is chosen so duration/n <= cap) and that the stitched clips align exactly to
    the full duration — so the model's creative *descriptions* vary per scene
    while the *timing* stays valid for stitching.
    """
    n = len(shots)
    if n == 0:
        return
    step = duration / n
    for i, s in enumerate(shots):
        s.start_s = round(i * step, 2)
        s.end_s = round((i + 1) * step, 2) if i < n - 1 else round(float(duration), 2)


async def stage_plan_shots(store) -> None:
    """Turn the approved concept into a timed shot list: each shot gets a time
    window and a concrete description for that slot. Idempotent."""
    import json

    bible = store.load()
    if any(s.end_s > s.start_s for s in bible.shots):
        return  # already planned
    if not bible.concept:
        return
    await store.start_stage("shotlist")
    try:
        raw = await asyncio.wait_for(
            concept_adapter.plan_json(shotlist_prompt(bible)), settings.IMAGE_TIMEOUT_S
        )
        data = json.loads(raw)
        by_id = {d.get("id"): d for d in data if isinstance(d, dict)}

        def _apply(b: SceneBible):
            for s in b.shots:
                d = by_id.get(s.id)
                if d:
                    s.description = str(d.get("description", s.description))
                    try:
                        s.start_s = float(d.get("start_s", 0))
                        s.end_s = float(d.get("end_s", 0))
                    except (TypeError, ValueError):
                        pass
            _normalize_timeline(b.shots, b.duration_s)

        await store.update(_apply)
    except Exception:
        # Fall back to an even split so downstream prompts still get timings.
        traceback.print_exc()
        await store.update(lambda b: _normalize_timeline(b.shots, b.duration_s))
    await store.end_stage("shotlist")


# --------------------------------------------------------------- stage 1 -----
async def stage_brand_sheet(store) -> None:
    bible = store.load()
    if bible.brand.brand_sheet:
        return
    await store.start_stage("brand_sheet")
    refs = _refs(bible)
    rel = "images/brand_sheet.png"
    await gen_image(brand_sheet_prompt(bible.brand), refs=refs, out_path=_abs(bible.run_id, rel))
    await store.update(lambda b: setattr(b.brand, "brand_sheet", rel))
    await store.end_stage("brand_sheet")


# --------------------------------------------------------------- stage 2 -----
async def stage_master_board(store) -> None:
    bible = store.load()
    await store.start_stage("master_board")
    refs = _refs(bible)
    sheet = [read_bytes(bible.run_id, bible.brand.brand_sheet)] if bible.brand.brand_sheet else []
    attach = refs + sheet

    async def one(shot, index):
        if shot.master_image:
            return
        await store.update(lambda b: _set_shot_status(b, shot.id, Status.running))
        rel = f"images/master_{shot.id}.png"
        try:
            await gen_image(master_shot_prompt(bible, shot, index), refs=attach, out_path=_abs(bible.run_id, rel))
            await store.update(lambda b: _set_shot(b, shot.id, rel, Status.done))
        except Exception:
            await store.update(lambda b: _set_shot_status(b, shot.id, Status.failed))
            raise

    await asyncio.gather(*(one(s, i + 1) for i, s in enumerate(bible.shots)), return_exceptions=True)
    await store.end_stage("master_board")


# --------------------------------------------------------------- stage 3 -----
async def stage_market_boards(store) -> None:
    bible = store.load()
    await store.start_stage("market_boards")
    sheet = [read_bytes(bible.run_id, bible.brand.brand_sheet)] if bible.brand.brand_sheet else []

    # Seed board rows.
    def _seed(b: SceneBible):
        existing = {(x.market_id, x.shot_id) for x in b.boards}
        for m in b.markets:
            for s in b.shots:
                if (m.id, s.id) not in existing:
                    b.boards.append(MarketBoard(market_id=m.id, shot_id=s.id))

    await store.update(_seed)

    async def one(market_id: str, shot):
        bib = store.load()
        board = bib.board(market_id, shot.id)
        if board and board.status == Status.done and board.image:
            return
        if not shot.master_image:
            return
        master = read_bytes(bible.run_id, shot.master_image)
        market = bible.market(market_id)
        rel = f"images/board_{market_id}_{shot.id}.png"
        await store.update(lambda b: _set_board_status(b, market_id, shot.id, Status.running))
        try:
            await gen_image(
                localized_board_prompt(bible, shot, market),
                refs=[master] + sheet,
                out_path=_abs(bible.run_id, rel),
            )
            await store.update(lambda b: _set_board(b, market_id, shot.id, rel, Status.done))
        except Exception:
            await store.update(lambda b: _set_board_status(b, market_id, shot.id, Status.failed))
            raise

    tasks = [one(m.id, s) for m in bible.markets for s in bible.shots]
    await asyncio.gather(*tasks, return_exceptions=True)

    if settings.ENABLE_BRAND_JUDGE:
        await stage_brand_check(store)

    await store.end_stage("market_boards")
    await _set_phase(store, "boards_ready")


# --------------------------------------------------------------- stage 4 -----
def _scene_keyframe(bible: SceneBible, market_id: str, shot) -> bytes | None:
    """The animation keyframe for a scene = that scene's localized board, with
    fallbacks to the shot's master frame or any available board for the market."""
    board = bible.board(market_id, shot.id)
    if board and board.image:
        return read_bytes(bible.run_id, board.image)
    if shot.master_image:
        return read_bytes(bible.run_id, shot.master_image)
    for other in bible.shots:
        b = bible.board(market_id, other.id)
        if b and b.image:
            return read_bytes(bible.run_id, b.image)
    return None


def _scene_len(shot, bible: SceneBible) -> float:
    """Clip length for a scene: its timeline window, clamped to Omni's bounds.

    Omni rejects a request outside [VIDEO_MIN_S, VIDEO_MAX_S] outright (400),
    so both ends must be enforced here, not just the cap — plan_shot_count
    picks a scene count that should already keep every window in range, but
    this is the last line of defense against any per-scene edit or rounding
    pushing a single clip below the floor.
    """
    length = shot.end_s - shot.start_s
    if length <= 0:
        length = bible.duration_s / max(1, len(bible.shots))
    return max(float(settings.VIDEO_MIN_S), min(float(settings.VIDEO_MAX_S), round(length)))


async def render_market_video(bible: SceneBible, market_id: str, version: int,
                              extra_instruction: str = "") -> str | None:
    """Generate one Omni clip per storyboard scene for a market and concatenate
    them into a full-length raw video. Returns the relative path, or None.

    This is the heart of Option 2: distinct footage per beat, each clip within
    Omni's 10s cap, stitched to the full duration. Reused by the master edit,
    which passes an extra instruction folded into every scene prompt.
    """
    market = bible.market(market_id)
    if market is None:
        return None
    run_id = bible.run_id
    scene_dir = f"clips/scenes"

    async def one_scene(shot):
        keyframe = _scene_keyframe(bible, market_id, shot)
        if keyframe is None:
            return None
        rel = f"{scene_dir}/{market_id}_{shot.id}_v{version}.mp4"
        out = _abs(run_id, rel)
        await gen_clip(
            scene_clip_prompt(bible, market, shot, extra_instruction),
            keyframe, out, duration_s=_scene_len(shot, bible),
        )
        return out

    scene_paths = await asyncio.gather(*(one_scene(s) for s in bible.shots),
                                       return_exceptions=True)
    ordered = [p for p in scene_paths if isinstance(p, str)]
    if not ordered:
        return None
    raw_rel = f"clips/{market_id}_v{version}.mp4"
    await concat(ordered, _abs(run_id, raw_rel))
    return raw_rel


def _seed_clips(b: SceneBible) -> None:
    have = {c.market_id for c in b.clips}
    for m in b.markets:
        if m.id not in have:
            b.clips.append(Clip(market_id=m.id))


async def _render_one_video(store, bible: SceneBible, market_id: str) -> str | None:
    """Generate (or reuse) one market's raw video. Returns the relative path."""
    bib = store.load()
    clip = bib.clip(market_id)
    if clip and clip.raw_video and clip.status in (Status.done, Status.approved):
        return clip.raw_video
    await store.update(lambda b: _set_clip_status(b, market_id, Status.running))
    try:
        raw = await render_market_video(bible, market_id, version=1)
        if raw:
            await store.update(lambda b: _set_clip_field(b, market_id, "raw_video", raw, Status.done))
            return raw
        await store.update(lambda b: _set_clip_status(b, market_id, Status.failed))
        return None
    except Exception:
        await store.update(lambda b: _set_clip_status(b, market_id, Status.failed))
        raise


async def _render_one_track(store, bible: SceneBible, market_id: str) -> str | None:
    """Generate (or reuse) one market's music track. Returns the relative path."""
    bib = store.load()
    clip = bib.clip(market_id)
    if clip and clip.track:
        return clip.track
    market = bible.market(market_id)
    rel = f"tracks/{market_id}.mp3"
    try:
        await gen_track(regional_track_prompt(bible, market), _abs(bible.run_id, rel))
        await store.update(lambda b: _set_clip_field(b, market_id, "track", rel))
        return rel
    except Exception:
        traceback.print_exc()
        return None


async def _render_one_voice(store, bible: SceneBible, market_id: str) -> str | None:
    """Generate (or reuse) one market's localized voiceover. Returns the
    relative path, or None if voiceover is disabled or generation fails (the
    ad still gets background music either way — narration is best-effort)."""
    if not settings.ENABLE_VOICEOVER:
        return None
    bib = store.load()
    clip = bib.clip(market_id)
    if clip and clip.voice:
        return clip.voice
    market = bible.market(market_id)
    rel = f"tracks/{market_id}_voice.wav"
    try:
        script = await concept_adapter.generate_text(voiceover_script_prompt(bible, market))
        if not script:
            return None
        await gen_voice(script, _abs(bible.run_id, rel))
        await store.update(lambda b: _set_clip_field(b, market_id, "voice", rel))
        return rel
    except Exception:
        traceback.print_exc()
        return None


async def render_and_mux_one_market(store, bible: SceneBible, market_id: str) -> None:
    """Render one market's video + music + voiceover in parallel, then mux it
    *as soon as all are ready* — independent of every other market. This is
    what lets the UI preview a market's finished ad while slower markets are
    still rendering, instead of waiting for every market to finish before any
    becomes playable.
    """
    raw, track, voice_path = await asyncio.gather(
        _render_one_video(store, bible, market_id),
        _render_one_track(store, bible, market_id),
        _render_one_voice(store, bible, market_id),
    )
    if not raw or not track:
        return  # left in its current (failed / partial) status; other markets unaffected
    bib = store.load()
    c = bib.clip(market_id)
    version = (c.version + 1) if (c and c.final) else 1
    rel = f"final/{market_id}_v{version}.mp4"
    await mux(_abs(bible.run_id, raw), _abs(bible.run_id, track),
              _abs(bible.run_id, rel), duration_s=bible.duration_s,
              voice_path=_abs(bible.run_id, voice_path) if voice_path else None)
    await store.update(lambda b: _finalize_clip(b, market_id, rel, version))


async def stage_video(store) -> None:
    """Kept for the smoke test / scripted use: generate every market's video only."""
    bible = store.load()
    await store.update(_seed_clips)
    await store.start_stage("video")
    await asyncio.gather(*(_render_one_video(store, bible, m.id) for m in bible.markets),
                        return_exceptions=True)
    await store.end_stage("video")


async def stage_music(store) -> None:
    """Kept for the smoke test / scripted use: generate every market's track only."""
    bible = store.load()
    await store.update(_seed_clips)
    await store.start_stage("music")
    await asyncio.gather(*(_render_one_track(store, bible, m.id) for m in bible.markets),
                        return_exceptions=True)
    await store.end_stage("music")


async def stage_mux(store) -> None:
    """Mux every market that already has both a raw video and a track."""
    bible = store.load()
    await store.start_stage("mux")

    async def one(clip: Clip):
        bib = store.load()
        c = bib.clip(clip.market_id)
        if not c or not c.raw_video or not c.track:
            return
        version = c.version + 1 if c.final else 1
        rel = f"final/{clip.market_id}_v{version}.mp4"
        await mux(_abs(bible.run_id, c.raw_video), _abs(bible.run_id, c.track),
                  _abs(bible.run_id, rel), duration_s=bible.duration_s,
                  voice_path=_abs(bible.run_id, c.voice) if c.voice else None)
        await store.update(lambda b: _finalize_clip(b, clip.market_id, rel, version))

    await asyncio.gather(*(one(c) for c in bible.clips), return_exceptions=True)
    await store.end_stage("mux")


# --------------------------------------------------------------- optional ----
async def stage_brand_check(store) -> None:
    bible = store.load()
    refs = _refs(bible)

    async def one(board: MarketBoard):
        if not board.image:
            return
        img = read_bytes(bible.run_id, board.image)
        result = await judge.score_board(img, refs, bible.brand)
        score = result.get("score")

        def _apply(b: SceneBible):
            bd = b.board(board.market_id, board.shot_id)
            if bd:
                bd.brand_score = float(score) if score is not None else None
                if score is not None and score < 85:
                    bd.status = Status.needs_review

        await store.update(_apply)

    await asyncio.gather(*(one(b) for b in bible.boards), return_exceptions=True)


# ------------------------------------------------------------- concept -------
async def run_concept(store) -> None:
    """Generate the initial creative concept from images + brief + palette +
    markets, then wait (phase concept_ready) for the user to edit and approve."""
    try:
        await _set_phase(store, "concepting")
        await store.start_stage("concept")
        bible = store.load()
        refs = _refs(bible)
        text = await asyncio.wait_for(
            concept_adapter.generate_concept(concept_prompt(bible), refs=refs),
            settings.IMAGE_TIMEOUT_S,
        )
        await store.update(lambda b: setattr(b, "concept", text))
        await store.end_stage("concept")
        await _set_phase(store, "concept_ready")
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        await store.update(lambda b: setattr(b, "error", str(exc)))
        await _set_phase(store, "failed")


# ---------------------------------------------------------- top-level runs ---
async def run_image_pipeline(store) -> None:
    """Stages 1-3: everything up to localized boards (triggered on upload)."""
    try:
        await _set_phase(store, "imaging")
        await stage_plan_shots(store)
        await stage_brand_sheet(store)
        await stage_master_board(store)
        await stage_market_boards(store)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        await store.update(lambda b: setattr(b, "error", str(exc)))
        await _set_phase(store, "failed")


async def run_render(store) -> None:
    """Stages 4-6: video + music in parallel per market, muxed as each market
    finishes — so a fast market's ad is playable in the UI immediately, rather
    than every market waiting on the slowest one before any preview appears.
    """
    try:
        await _set_phase(store, "rendering")
        bible = store.load()
        await store.update(_seed_clips)
        await store.start_stage("video")
        await store.start_stage("music")
        if settings.ENABLE_VOICEOVER:
            await store.start_stage("voice")
        await store.start_stage("mux")
        await asyncio.gather(
            *(render_and_mux_one_market(store, bible, m.id) for m in bible.markets),
            return_exceptions=True,
        )
        await store.end_stage("video")
        await store.end_stage("music")
        if settings.ENABLE_VOICEOVER:
            await store.end_stage("voice")
        await store.end_stage("mux")
        await _set_phase(store, "rendered")
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        await store.update(lambda b: setattr(b, "error", str(exc)))
        await _set_phase(store, "failed")


# ------------------------------------------------------- bible mutators -------
# Small pure helpers used inside store.update() so mutations stay in one place.
def _set_shot(b: SceneBible, shot_id: str, image_rel: str, status: Status) -> None:
    s = b.shot(shot_id)
    if s:
        s.master_image = image_rel
        s.status = status


def _set_shot_status(b: SceneBible, shot_id: str, status: Status) -> None:
    s = b.shot(shot_id)
    if s:
        s.status = status


def _set_board(b: SceneBible, market_id: str, shot_id: str, image_rel: str, status: Status) -> None:
    bd = b.board(market_id, shot_id)
    if bd:
        bd.image = image_rel
        bd.status = status


def _set_board_status(b: SceneBible, market_id: str, shot_id: str, status: Status) -> None:
    bd = b.board(market_id, shot_id)
    if bd:
        bd.status = status


def _set_clip_status(b: SceneBible, market_id: str, status: Status) -> None:
    c = b.clip(market_id)
    if c:
        c.status = status


def _set_clip_field(b: SceneBible, market_id: str, field: str, value, status: Status | None = None) -> None:
    c = b.clip(market_id)
    if c:
        setattr(c, field, value)
        if status is not None:
            c.status = status


def _finalize_clip(b: SceneBible, market_id: str, final_rel: str, version: int) -> None:
    c = b.clip(market_id)
    if c:
        c.final = final_rel
        c.version = version
        c.status = Status.done
