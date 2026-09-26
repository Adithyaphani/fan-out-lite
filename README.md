# Fan-Out Lite

![Fan-Out Lite — one product, fanned out to many markets](assets/thumbnail.png)

A localized ad engine. Upload a product and a brief once; the system produces a
finished, localized video ad for **each of up to 4 markets** in a single chained
run — storyboards, animation, regional scoring and muxing, all locked to one
shared scene bible.

Built for the DeepMind *Multimodal Creative Pipelines with GenMedia* track.

```
Upload ─▶ Concept ─▶ NB2 Lite ─▶ Omni ─▶ Lyria ─▶ ffmpeg ─▶ Manage / Master-edit
(brief)  (editable    (boards)    (video) (music)  (mux)      (propagate to all clips)
          idea, chat/voice)
```

The flow: **Upload** (product photos, brief, palette, markets, category, visual
style, duration slider) → **Concept** (a creative concept is generated from those
inputs; refine it by chat or voice, then finalize) → **Storyboard** → **Manage**.

## Architecture — backend and frontend fully isolated

| Layer | Stack | Location |
|---|---|---|
| **Backend** | FastAPI + `google-genai`, async orchestrator, ffmpeg | [backend/](backend/) |
| **Frontend** | React + Vite + TypeScript (4-page flow) | [frontend/](frontend/) |

The two talk over a small REST API. The **scene bible** (`runs/<id>/bible.json`)
is the single source of truth: every model call reads from and writes to it,
which is why the product, palette, beat and cut points stay identical across
markets. The frontend never writes the bible — it POSTs actions and polls the
bible ~once a second.

### The chained pipeline (each model's output feeds the next)

1. **NB2 Lite** (`gemini-3.1-flash-lite-image`) → brand sheet → 6-shot master
   storyboard → localized boards for every market, fanned out in parallel.
2. Conversational **storyboard edits** (text or voice) re-localize a shot across
   all markets in seconds.
3. **Omni** (`gemini-omni-1.1-flash`, via the Interactions API) animates one
   hero clip per market.
4. **Lyria** (`lyria-3.5`) scores each market in a regional style at the shared
   BPM/duration.
5. **ffmpeg** muxes video + audio and hard-caps duration so markets stay aligned.
6. One conversational **master edit** replays across all market clips at once.

## Verified model latencies (this endpoint, smoke test)

| Model | Call shape | Latency |
|---|---|---|
| Image · `gemini-3.1-flash-lite-image` | `models.generate_content`, `IMAGE` modality → JPEG | ~4s |
| Music · `lyria-3.5` | `models.generate_content`, `AUDIO` modality → mp3 (trimmed by ffmpeg) | ~40s |
| Video · `gemini-omni-1.1-flash` | **Interactions API**, `background` + poll → mp4 (1280×720) | ~41s ✅ |
| Fan-out | 8 parallel images | ~6s |

End-to-end measured through the running app: **19 images in 24s**;
2-market render (video + music + mux) in **~45s**; master-edit propagation to
2 clips in **~75s**.

## Quick start

Requires Python 3.11+, Node 18+, and `ffmpeg` on PATH.

```bash
# 1. Backend
cd backend
cp .env.example .env        # then paste your GEMINI_API_KEY
pip install -r requirements.txt
python -m scripts.smoke_test        # optional 0:20 go/no-go
python -m scripts.prerender         # optional: build the demo fallback
uvicorn app.main:app --reload --port 8100

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                 # http://localhost:5173  (proxies /api to :8100)
```

Or run everything on one origin: `npm run build` in `frontend/`, then just start
the backend — it serves the built SPA.

`./run.sh` starts both together for local dev.

## Demo flow

Home → **Start a new campaign** → Upload photos + pick markets → Storyboard
(watch 6×N boards appear, speak an edit) → **Render** → Manage (play markets
side by side) → **Master edit** → one instruction propagates to every clip.
If anything fails live, **See it in action** on Home loads the pre-rendered
fallback with no network.

See [backend/README.md](backend/README.md) for the API reference and internals.
