# Fan-Out Lite — Backend

FastAPI service that runs the chained GenMedia pipeline and owns the scene bible.

## Layout

```
backend/
├── app/
│   ├── config.py         # env, model IDs, concurrency, timeouts
│   ├── bible.py          # SceneBible pydantic models + BibleStore (atomic writes)
│   ├── markets.py        # market presets + default 6-shot skeleton
│   ├── prompts.py        # prompt templates built from the bible
│   ├── adapters/
│   │   ├── client.py     # shared google-genai client
│   │   ├── image.py      # NB2 Lite  — models.generate_content, IMAGE modality
│   │   ├── video.py      # Omni      — Interactions API (create+poll), inline mp4
│   │   ├── music.py      # Lyria     — models.generate_content, AUDIO modality
│   │   └── judge.py      # optional brand judge + voice transcription
│   ├── orchestrator.py   # stage runners, fan-out, semaphores, retries, timings
│   ├── edits.py          # storyboard edits + master-edit propagation
│   ├── mux.py            # ffmpeg mux + duration normalization
│   ├── runs.py           # run lifecycle, filesystem layout, store registry
│   ├── demo.py           # pre-rendered fallback loader
│   └── main.py           # FastAPI app (REST + asset serving + SPA fallback)
├── scripts/
│   ├── smoke_test.py     # 0:20 go/no-go latency check
│   └── prerender.py      # build fallback/ for the demo
└── runs/<id>/{bible.json, refs/, images/, clips/, tracks/, final/}
```

## Design principles

- **The bible is the API between people.** The UI builds against it; only the
  orchestrator and edit engine write to it, behind an `asyncio.Lock` with atomic
  `os.replace`.
- **Every stage is idempotent and resumable.** A stage skips any asset already
  marked `done`, so a crash mid-run costs only the failed calls.
- **Adapters isolate API uncertainty.** Each model lives behind one thin file;
  if an SDK shape changes, one file changes. `guarded(kind)` wraps every model
  call with a per-model semaphore, a timeout and tenacity backoff on failure.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | key/model/fallback status |
| `GET` | `/api/markets` | available market presets |
| `POST` | `/api/runs` | multipart: `product_name, category, brief, style, markets, palette, images[]` → `{run_id}`; kicks off the image pipeline |
| `GET` | `/api/runs/{id}/bible` | full scene bible (poll this ~1/s) |
| `GET` | `/api/runs/{id}/assets/{path}` | serve any run asset (images/clips/tracks/final) |
| `POST` | `/api/runs/{id}/render` | run video + music (parallel) then mux |
| `POST` | `/api/runs/{id}/storyboard/edit` | `{shot_id, instruction, source}` — edit + re-localize |
| `POST` | `/api/runs/{id}/master-edit` | `{instruction}` — propagate to every clip |
| `POST` | `/api/runs/{id}/approve` | `{market_id, approved}` |
| `POST` | `/api/runs/{id}/transcribe` | audio upload → text (voice edits) |
| `POST` | `/api/demo` | load the pre-rendered fallback → `{run_id}` |

## Notes learned in the smoke test

- **Omni is served only through the Interactions API** (`models.generate_content`
  returns *"This model only supports Interactions API"*). We create a background
  interaction with an image + text input and a `video` response format, then poll
  `interactions.get(id)` until `status == "completed"`; the mp4 comes back inline.
  Clip edits pass the previous video back as a `video` input; if that is ever
  rejected, `edits.py` falls back to regenerating from the keyframe with the
  instruction folded into the prompt.
- **Lyria ignores exact duration** (it returned ~80s for an 8s request), so the
  muxer trims/pads every track to the bible duration with `ffmpeg -t … -af apad`.
- Image output is JPEG bytes even though we save `.png`; the browser reads the
  content, not the extension.

## Config

All tunables live in `.env` (see `.env.example`): model IDs, per-model
concurrency and timeouts, ad duration/BPM/aspect, and `ENABLE_BRAND_JUDGE`.
