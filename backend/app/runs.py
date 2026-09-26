"""Run lifecycle: filesystem layout, a per-run BibleStore registry, and the
factory that turns an upload into an initial scene bible on disk.

Asset paths inside the bible are always relative to runs/<id>/, so a whole
run folder can be copied into fallback/ unchanged and replayed offline.
"""
from __future__ import annotations

import secrets
from pathlib import Path

from .bible import Brand, BibleStore, Market, SceneBible, Shot
from .config import settings
from .markets import DEFAULT_MARKET_IDS, MARKETS, build_shots, plan_shot_count

# One BibleStore per run id, kept in memory so the asyncio lock is shared
# across every request and background task touching that run.
_STORES: dict[str, BibleStore] = {}

SUBDIRS = ("refs", "images", "clips", "tracks", "final")


def run_dir(run_id: str) -> Path:
    return settings.RUNS_DIR / run_id


def new_run_id() -> str:
    return secrets.token_hex(4)


def get_store(run_id: str) -> BibleStore:
    """Return the store for a run, creating the wrapper if the run exists on disk."""
    if run_id in _STORES:
        return _STORES[run_id]
    path = run_dir(run_id) / "bible.json"
    if not path.exists():
        raise KeyError(run_id)
    store = BibleStore(path)
    _STORES[run_id] = store
    return store


def register_store(run_id: str, base: Path) -> BibleStore:
    store = BibleStore(base / "bible.json")
    _STORES[run_id] = store
    return store


def create_run(
    *,
    product_name: str,
    category: str,
    brief: str,
    market_ids: list[str],
    palette: list[str],
    style: str,
    ref_files: list[tuple[str, bytes]],
    spec_notes: str = "",
    duration_s: float | None = None,
) -> tuple[str, BibleStore]:
    """Materialise a new run on disk and return (run_id, store).

    Does not call any model — just lays out folders and the initial bible so
    the UI can render immediately while the pipeline runs.
    """
    run_id = new_run_id()
    base = run_dir(run_id)
    for sub in SUBDIRS:
        (base / sub).mkdir(parents=True, exist_ok=True)

    ref_paths: list[str] = []
    for idx, (name, data) in enumerate(ref_files):
        ext = Path(name).suffix or ".png"
        rel = f"refs/ref_{idx}{ext}"
        (base / rel).write_bytes(data)
        ref_paths.append(rel)

    chosen = [MARKETS[m] for m in market_ids if m in MARKETS]
    if not chosen:
        chosen = [MARKETS[m] for m in DEFAULT_MARKET_IDS]

    brand = Brand(
        product_name=product_name,
        category=category,
        palette=palette,
        style=style or "warm cinematic product macro",
        product_refs=ref_paths,
        spec_notes=spec_notes,
    )
    dur = float(duration_s) if duration_s else settings.AD_DURATION_S
    # Scene count scales with duration so each scene fits one Omni clip.
    shots = [Shot(id=s["id"], role=s["role"], description=s["description"])
             for s in build_shots(plan_shot_count(dur))]

    bible = SceneBible(
        run_id=run_id,
        brief=brief,
        brand=brand,
        markets=[Market(**m.model_dump()) for m in chosen],
        bpm=settings.AD_BPM,
        duration_s=dur,
        aspect=settings.AD_ASPECT,
        shots=shots,
        phase="created",
    )

    store = register_store(run_id, base)
    store.save_sync(bible)
    return run_id, store


def read_bytes(run_id: str, rel_path: str) -> bytes:
    return (run_dir(run_id) / rel_path).read_bytes()
