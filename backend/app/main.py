"""FastAPI application: the backend API for Fan-Out Lite.

The UI never writes the bible directly — it POSTs actions here, and the
orchestrator/edit-engine run as asyncio background tasks on the app's event
loop. The UI polls GET /api/runs/{id}/bible ~once a second for state.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import demo, edits, orchestrator
from .adapters import judge
from .config import settings
from .markets import MARKETS
from .runs import create_run, get_store, run_dir

app = FastAPI(title="Fan-Out Lite API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------- helpers -----
def _store_or_404(run_id: str):
    try:
        return get_store(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")


# ---------------------------------------------------------------- meta -------
@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "has_api_key": settings.has_api_key,
        "has_fallback": demo.has_fallback(),
        "models": {
            "image": settings.IMAGE_MODEL,
            "video": settings.VIDEO_MODEL,
            "music": settings.MUSIC_MODEL,
        },
        "duration_s": settings.AD_DURATION_S,
        "bpm": settings.AD_BPM,
    }


@app.get("/api/markets")
async def list_markets() -> dict:
    return {
        "markets": [
            {"id": m.id, "city": m.city, "country": m.country,
             "language": m.language, "script": m.script,
             "music_style": m.music_style, "cultural_cues": m.cultural_cues}
            for m in MARKETS.values()
        ]
    }


# ------------------------------------------------------------ run create -----
@app.post("/api/runs")
async def create(
    product_name: str = Form(...),
    category: str = Form(""),
    brief: str = Form(""),
    style: str = Form("warm cinematic product macro"),
    markets: str = Form("IN,BR,KR,NG"),
    palette: str = Form(""),
    spec_notes: str = Form(""),
    duration_s: float = Form(6.0),
    images: list[UploadFile] = File(default=[]),
):
    market_ids = [m.strip() for m in markets.split(",") if m.strip()]
    palette_list = [c.strip() for c in palette.split(",") if c.strip()]
    ref_files: list[tuple[str, bytes]] = []
    for up in images:
        ref_files.append((up.filename or "ref.png", await up.read()))

    run_id, store = create_run(
        product_name=product_name,
        category=category,
        brief=brief,
        market_ids=market_ids,
        palette=palette_list,
        style=style,
        ref_files=ref_files,
        spec_notes=spec_notes,
        duration_s=max(3.0, min(120.0, duration_s)),  # up to 2 minutes
    )

    # Kick off concept generation first; storyboards follow on approval.
    import asyncio

    asyncio.create_task(orchestrator.run_concept(store))
    return {"run_id": run_id}


class ConceptEditBody(BaseModel):
    instruction: str
    source: str = "text"


@app.post("/api/runs/{run_id}/concept/edit")
async def concept_edit(run_id: str, body: ConceptEditBody):
    import asyncio

    store = _store_or_404(run_id)
    asyncio.create_task(edits.edit_concept(store, body.instruction, body.source))
    return {"ok": True}


@app.post("/api/runs/{run_id}/concept/regenerate")
async def concept_regenerate(run_id: str):
    import asyncio

    store = _store_or_404(run_id)
    asyncio.create_task(orchestrator.run_concept(store))
    return {"ok": True}


@app.post("/api/runs/{run_id}/concept/finalize")
async def concept_finalize(run_id: str):
    """Approve the concept and start the storyboard image pipeline."""
    import asyncio

    store = _store_or_404(run_id)
    await store.update(lambda b: setattr(b, "concept_approved", True))
    asyncio.create_task(orchestrator.run_image_pipeline(store))
    return {"ok": True}


# --------------------------------------------------------------- read --------
@app.get("/api/runs/{run_id}/bible")
async def get_bible(run_id: str):
    store = _store_or_404(run_id)
    return JSONResponse(content=store.load().model_dump(mode="json"))


@app.get("/api/runs/{run_id}/assets/{asset_path:path}")
async def get_asset(run_id: str, asset_path: str):
    base = run_dir(run_id).resolve()
    target = (base / asset_path).resolve()
    if not str(target).startswith(str(base)) or not target.exists():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(target)


# --------------------------------------------------------------- actions -----
class InstructionBody(BaseModel):
    instruction: str
    source: str = "text"


class ShotEditBody(BaseModel):
    shot_id: str
    instruction: str
    source: str = "text"


@app.post("/api/runs/{run_id}/render")
async def render(run_id: str):
    import asyncio

    store = _store_or_404(run_id)
    asyncio.create_task(orchestrator.run_render(store))
    return {"ok": True}


@app.post("/api/runs/{run_id}/storyboard/edit")
async def storyboard_edit(run_id: str, body: ShotEditBody):
    import asyncio

    store = _store_or_404(run_id)
    asyncio.create_task(
        edits.edit_storyboard_shot(store, body.shot_id, body.instruction, body.source)
    )
    return {"ok": True}


@app.post("/api/runs/{run_id}/master-edit")
async def master_edit(run_id: str, body: InstructionBody):
    import asyncio

    store = _store_or_404(run_id)
    asyncio.create_task(
        edits.propagate_master_edit(store, body.instruction, body.source)
    )
    return {"ok": True}


class ApproveBody(BaseModel):
    market_id: str
    approved: bool = True


@app.post("/api/runs/{run_id}/approve")
async def approve(run_id: str, body: ApproveBody):
    store = _store_or_404(run_id)

    def _apply(b):
        c = b.clip(body.market_id)
        if c:
            c.approved = body.approved

    await store.update(_apply)
    return {"ok": True}


@app.post("/api/runs/{run_id}/transcribe")
async def transcribe(run_id: str, audio: UploadFile = File(...)):
    _store_or_404(run_id)
    from .mux import audio_to_wav

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty audio")
    try:
        # Normalise whatever the browser recorded to 16kHz mono wav first.
        wav = await audio_to_wav(data)
        text = await judge.transcribe(wav, "audio/wav")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"transcription failed: {exc}")
    return {"text": text}


# ------------------------------------------------------------ demo mode ------
@app.post("/api/demo")
async def start_demo():
    try:
        run_id = demo.load_fallback()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"run_id": run_id}


# Serve the built frontend if present (single-origin deploy convenience).
# API routes are declared above, so they take precedence; anything else falls
# back to index.html so client-side routes (/manage, /storyboard) survive a
# refresh. In dev the Vite server on :5173 proxies /api and /assets here.
_STATIC = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _STATIC.exists():

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        candidate = (_STATIC / full_path).resolve()
        if full_path and str(candidate).startswith(str(_STATIC.resolve())) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC / "index.html")
