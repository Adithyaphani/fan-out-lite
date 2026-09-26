"""Demo fallback: load a pre-rendered complete run so the demo survives a
model outage or venue Wi-Fi failure. The fallback is a normal run folder,
copied into runs/ under a fresh id so every asset serves through the same
routes as a live run.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .bible import SceneBible
from .config import settings
from .runs import new_run_id, register_store, run_dir


def _find_fallback() -> Path | None:
    root = settings.FALLBACK_DIR
    if (root / "bible.json").exists():
        return root
    for child in sorted(root.iterdir()) if root.exists() else []:
        if child.is_dir() and (child / "bible.json").exists():
            return child
    return None


def has_fallback() -> bool:
    return _find_fallback() is not None


def load_fallback() -> str:
    """Copy the pre-rendered run into runs/ and return its new run id."""
    src = _find_fallback()
    if src is None:
        raise FileNotFoundError(
            "No fallback run found. Run scripts/prerender.py to create one."
        )
    run_id = new_run_id()
    dst = run_dir(run_id)
    shutil.copytree(src, dst)

    # Rewrite the run_id inside the copied bible so links resolve.
    bible = SceneBible.model_validate_json((dst / "bible.json").read_text())
    bible.run_id = run_id
    (dst / "bible.json").write_text(bible.model_dump_json(indent=2))
    register_store(run_id, dst)
    return run_id
