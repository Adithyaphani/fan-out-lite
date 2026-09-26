"""The scene bible: the single source of truth for a campaign run.

Every model call reads from and writes to this document, which is how the
product, palette, beat and cut points stay identical across all markets.
The bible is a Pydantic model persisted atomically to runs/<id>/bible.json.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Status(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    needs_review = "needs_review"
    approved = "approved"


class Market(BaseModel):
    id: str  # "IN", "BR", "KR", "NG"
    city: str
    country: str
    language: str  # for on-screen text / signage
    script: str  # "Devanagari", "Latin", "Hangul"
    cultural_cues: list[str]  # props, setting, wardrobe, weather
    music_style: str  # "filmi-pop", "bossa groove", ...


class Brand(BaseModel):
    product_name: str
    category: str
    palette: list[str] = []  # hex colours
    style: str = "warm cinematic product macro"
    product_refs: list[str] = []  # relative paths to uploaded photos
    spec_notes: str = ""
    brand_sheet: str | None = None  # generated brand-sheet image path


class Shot(BaseModel):
    id: str  # "s1".."s6"
    role: str  # establishing | product | hero | lifestyle | macro | cta
    description: str
    start_s: float = 0.0  # time window within the ad timeline
    end_s: float = 0.0
    master_image: str | None = None
    status: Status = Status.queued


class MarketBoard(BaseModel):
    market_id: str
    shot_id: str
    image: str | None = None
    brand_score: float | None = None
    status: Status = Status.queued


class Clip(BaseModel):
    market_id: str
    version: int = 0
    raw_video: str | None = None
    track: str | None = None
    final: str | None = None  # muxed mp4
    approved: bool = False
    status: Status = Status.queued


class EditOp(BaseModel):
    id: str
    scope: str  # "storyboard_shot" | "master_clip"
    target: str | None = None  # shot id for storyboard edits
    instruction: str
    source: str = "text"  # "text" | "voice"
    created_at: datetime = Field(default_factory=_utcnow)
    applied: dict[str, str] = {}  # market_id -> status string


class Timing(BaseModel):
    stage: str
    started: datetime = Field(default_factory=_utcnow)
    ended: datetime | None = None


class SceneBible(BaseModel):
    run_id: str
    brief: str = ""
    brand: Brand
    markets: list[Market] = []
    bpm: int = 128
    duration_s: float = 6.0
    aspect: str = "16:9"
    # Creative concept: generated from the brief/images/palette/markets, edited
    # conversationally, then approved before storyboards are produced.
    concept: str = ""
    concept_approved: bool = False
    shots: list[Shot] = []
    boards: list[MarketBoard] = []
    clips: list[Clip] = []
    edits: list[EditOp] = []
    timings: list[Timing] = []
    # Coarse pipeline phase for the UI: created|concepting|concept_ready|imaging|
    # boards_ready|rendering|rendered|propagating|done|failed
    phase: str = "created"
    error: str | None = None
    version: int = 0
    created_at: datetime = Field(default_factory=_utcnow)

    # -- convenience lookups (never persisted logic, just helpers) --
    def market(self, market_id: str) -> Market | None:
        return next((m for m in self.markets if m.id == market_id), None)

    def shot(self, shot_id: str) -> Shot | None:
        return next((s for s in self.shots if s.id == shot_id), None)

    def board(self, market_id: str, shot_id: str) -> MarketBoard | None:
        return next(
            (b for b in self.boards if b.market_id == market_id and b.shot_id == shot_id),
            None,
        )

    def clip(self, market_id: str) -> Clip | None:
        return next((c for c in self.clips if c.market_id == market_id), None)

    def boards_for(self, market_id: str) -> list[MarketBoard]:
        order = {s.id: i for i, s in enumerate(self.shots)}
        boards = [b for b in self.boards if b.market_id == market_id]
        return sorted(boards, key=lambda b: order.get(b.shot_id, 99))


class BibleStore:
    """Loads and saves one run's bible behind an asyncio lock, atomically.

    Only the orchestrator and edit engine call `update`; the API layer reads
    with `load`. Atomic os.replace guarantees a reader never sees a half file.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = asyncio.Lock()

    def load(self) -> SceneBible:
        return SceneBible.model_validate_json(self.path.read_text())

    def _write(self, bible: SceneBible) -> None:
        d = str(self.path.parent)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(bible.model_dump_json(indent=2))
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    def save_sync(self, bible: SceneBible) -> None:
        """Initial write when a run is created (no concurrent writers yet)."""
        bible.version += 1
        self._write(bible)

    async def update(self, fn) -> SceneBible:
        """Atomic read-modify-write. `fn(bible)` mutates the bible in place."""
        async with self._lock:
            bible = self.load()
            fn(bible)
            bible.version += 1
            self._write(bible)
            return bible

    # -- timing helpers --
    async def start_stage(self, stage: str) -> None:
        await self.update(lambda b: b.timings.append(Timing(stage=stage)))

    async def end_stage(self, stage: str) -> None:
        def _end(b: SceneBible) -> None:
            for t in reversed(b.timings):
                if t.stage == stage and t.ended is None:
                    t.ended = _utcnow()
                    break

        await self.update(_end)
