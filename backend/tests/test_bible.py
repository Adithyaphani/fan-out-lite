"""Network-free tests for the scene bible and store — the DoD checklist:
the fixture validates, the bible round-trips through JSON, and store updates
are atomic and version-bumping.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.bible import BibleStore, SceneBible, Status
from app.markets import MARKETS

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "bible_sample.json"


def test_fixture_validates():
    bible = SceneBible.model_validate_json(FIXTURE.read_text())
    assert bible.run_id
    assert len(bible.shots) == 6
    assert bible.duration_s > 0


def test_bible_roundtrips():
    bible = SceneBible.model_validate_json(FIXTURE.read_text())
    again = SceneBible.model_validate_json(bible.model_dump_json())
    assert again.model_dump() == bible.model_dump()


def test_market_cues_are_about_settings_not_people():
    banned = {"ethnic", "race", "skin", "caste"}
    for m in MARKETS.values():
        for cue in m.cultural_cues:
            assert not (banned & set(cue.lower().split())), f"suspect cue: {cue}"


def test_store_update_is_atomic_and_bumps_version(tmp_path):
    src = SceneBible.model_validate_json(FIXTURE.read_text())
    path = tmp_path / "bible.json"
    path.write_text(src.model_dump_json())
    store = BibleStore(path)

    async def go():
        before = store.load().version
        await store.update(lambda b: setattr(b, "phase", "rendering"))
        after = store.load()
        assert after.version == before + 1
        assert after.phase == "rendering"
        # File is valid JSON on disk (atomic replace never leaves a partial).
        json.loads(path.read_text())

    asyncio.run(go())


def test_lookup_helpers():
    bible = SceneBible.model_validate_json(FIXTURE.read_text())
    m = bible.markets[0]
    assert bible.market(m.id).id == m.id
    assert bible.shot("s1").id == "s1"
    ordered = bible.boards_for(m.id)
    assert [b.shot_id for b in ordered] == [s.id for s in bible.shots]
