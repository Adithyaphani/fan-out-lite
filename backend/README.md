# Fan-Out Lite — Backend

FastAPI service that runs the chained GenMedia pipeline and owns the scene bible.

## Layout

```
backend/
├── app/
│   ├── config.py         # env, model IDs, concurrency, timeouts, Omni's 3-10s bounds
│   ├── bible.py          # SceneBible pydantic models + BibleStore (atomic writes)
│   ├── markets.py        # market presets (36 cities/18 countries) + duration-scaled shot planning
│   ├── prompts.py        # prompt templates built from the bible
│   ├── adapters/
│   │   ├── client.py     # shared google-genai client
│   │   ├── concept.py    # gemini-3.8-flash — concept, edits, shot-list JSON, voiceover script text
│   │   ├── image.py      # NB2 Lite  — models.generate_content, IMAGE modality
│   │   ├── video.py      # Omni      — Interactions API (create+poll), inline mp4
│   │   ├── music.py      # Lyria     — models.generate_content, AUDIO modality
│   │   ├── voice.py      # TTS       — gemini-3.8-flash-tts, localized voiceover synthesis
│   │   └── judge.py      # optional brand judge + voice-edit transcription
│   ├── orchestrator.py   # stage runners, fan-out, per-market render+mux, semaphores, retries, timings
│   ├── edits.py          # concept edit, storyboard edit, master-edit + location-edit propagation
│   ├── mux.py            # ffmpeg mux (video+music[+voice]), scene concat, duration normalization
│   ├── runs.py           # run lifecycle, filesystem layout, store registry
│   ├── demo.py           # pre-rendered fallback loader
│   └── main.py           # FastAPI app (REST + asset serving + SPA fallback)
├── scripts/
│   ├── smoke_test.py     # go/no-go latency check
│   └── prerender.py      # build fallback/ for the demo
└── runs/<id>/{bible.json, refs/, images/, clips/, clips/scenes/, tracks/, final/}
```

## Design principles

- **The bible is the API between people.** The UI builds against it; only the
  orchestrator and edit engine write to it, behind an `asyncio.Lock` with atomic
  `os.replace`.
- **Every stage is idempotent, resumable, and market-independent.** A stage
  skips any asset already marked `done`; one failed market never blocks
  another; each market renders, scores, narrates and muxes on its own
  timeline, so a fast market's ad becomes playable the moment it's ready
  rather than waiting on the slowest one.
- **Adapters isolate API uncertainty.** Each model lives behind one thin file;
  if an SDK shape or a limit changes, one file changes. `guarded(kind)` wraps
  every model call with a per-model semaphore, a timeout and tenacity backoff
  on failure.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | key/model/fallback status |
| `GET` | `/api/markets` | available market presets (36 cities) |
| `POST` | `/api/runs` | multipart: `product_name, category, brief, style, markets, palette, duration_s, images[]` → `{run_id}`; kicks off concept generation |
| `GET` | `/api/runs/{id}/bible` | full scene bible (poll this ~1/s) |
| `GET` | `/api/runs/{id}/assets/{path}` | serve any run asset (images/clips/tracks/final) |
| `POST` | `/api/runs/{id}/concept/edit` | `{instruction, source}` — revise the concept by chat/voice |
| `POST` | `/api/runs/{id}/concept/regenerate` | regenerate the concept from scratch |
| `POST` | `/api/runs/{id}/concept/finalize` | approve the concept, plan the timed shot list, start the image pipeline |
| `POST` | `/api/runs/{id}/render` | render + mux every market (video, music, voice, per market, independently) |
| `POST` | `/api/runs/{id}/storyboard/edit` | `{shot_id, instruction, source}` — edit + re-localize a shot |
| `POST` | `/api/runs/{id}/master-edit` | `{instruction}` — propagate an edit to every market's ad |
| `POST` | `/api/runs/{id}/market-edit` | `{market_id, instruction}` — apply an edit to one market only |
| `POST` | `/api/runs/{id}/approve` | `{market_id, approved}` |
| `POST` | `/api/runs/{id}/transcribe` | audio upload → text (voice edits) |
| `POST` | `/api/demo` | load the pre-rendered fallback → `{run_id}` |

## Notes learned by verifying against the real endpoint

- **Omni is served only through the Interactions API** (`models.generate_content`
  returns *"This model only supports Interactions API"*). We create a background
  interaction with an image + text input and a `video` response format, then poll
  `interactions.get(id)` until `status == "completed"`; the mp4 comes back inline.
- **Omni has both a floor and a ceiling — 3s to 10s per clip, not just a cap.**
  A request outside that range is rejected outright (400). `markets.plan_shot_count`
  picks a scene count so every window fits `[VIDEO_MIN_S, VIDEO_MAX_S]`; missing
  the floor originally meant every ad under 9s silently failed on every market.
- **Long ads are stitched from distinct per-scene clips, not a looped hero
  clip.** Each storyboard scene is animated from its own localized board and
  `mux.concat` joins them in order — real cuts and pacing, matching the
  storyboard. `mux.mux` still has a loop-and-pad fallback for a stray short
  raw clip, but the primary render path is per-scene stitching.
- **Rendering is per-market-independent.** `orchestrator.render_and_mux_one_market`
  runs one market's video + music + voice in parallel and muxes it as soon as
  all three are ready — it does not wait for other markets, so a fast market's
  final mp4 appears in the UI immediately.
- **Lyria ignores exact duration** (it returned ~80s for an 8s request), so the
  muxer trims/pads every track to the bible duration with `ffmpeg -t … -af apad`.
- **TTS speaks exactly what it's given — it does not translate.** Localizing
  the voiceover requires a text-generation step first: `prompts.voiceover_script_prompt`
  asks the utility model to write a short script *in the market's own language
  and script* from the concept's tagline, then `adapters/voice.py` synthesizes
  it. `mux.mux`'s `voice_path` argument then ducks the music (`volume=0.25`)
  and mixes both via ffmpeg `amix`.
- **The utility model was silently retired mid-build**: `gemini-2.5-flash` now
  returns 404 on this endpoint (*"use gemini-3.8-flash"*), which had quietly
  broken voice transcription and concept generation until traced.
- Image output is JPEG bytes even though we save `.png`; the browser reads the
  content, not the extension.

## Config

All tunables live in `.env` (see `.env.example`): model IDs, per-model
concurrency and timeouts, ad duration/BPM/aspect, Omni's `VIDEO_MIN_S`/`VIDEO_MAX_S`
bounds, `ENABLE_VOICEOVER` + `VOICE_MODEL`/`VOICE_NAME`, and `ENABLE_BRAND_JUDGE`.
