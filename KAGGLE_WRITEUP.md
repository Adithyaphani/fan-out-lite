# Fan-Out Lite

### One brief in, a finished localized video ad for every market out — in a single chained run.

**Track:** Multimodal Creative Pipelines with GenMedia

---

## The problem

A marketer with one product and one idea needs that idea rebuilt for many markets — different cities, languages, signage, music, and cultural setting — while the product, palette, and beat stay identical everywhere. Today that is weeks of agency work. Fan-Out Lite compresses it into one loop: upload a product and a brief once, and the system produces a finished, localized video ad for each of up to 36 cities, all locked to a single shared source of truth.

This is deliberately a **chained pipeline, not a prompt box**. Five generative stages feed one another, and the throughput (20+ images, N videos, N tracks per run) is the whole point — the product only exists because of fan-out.

## What it does

The flow is **Upload → Concept → Storyboard → Manage**:

1. **Concept.** From the product photos, brief, palette, and selected markets, `gemini-3.8-flash` writes an editable creative concept (tagline, concept, hero moment, "why it travels"). The user refines it by **chat or voice** before anything expensive runs.
2. **Timed shot list.** The approved concept is broken into six contiguous timed scenes covering `0 → duration` (e.g. hero = 2.5–4.2s of an 8s ad), each with a shootable description for its slot.
3. **Images (NB2 Lite, `gemini-3.1-flash-lite-image`).** A brand sheet, then a 6-shot master storyboard, then a localized board for every market — fanned out in parallel.
4. **Video (Omni, `gemini-omni-1.1-flash`) + Music (Lyria, `lyria-3.5`)** run in parallel per market. `ffmpeg` muxes them.
5. **Master edit.** One conversational instruction ("slow the pour, add rising steam") is replayed across **every** market clip at once.

## Architecture

The backend and frontend are fully isolated: an **async FastAPI** service and a **React + TypeScript (Vite)** SPA that talk over a small REST API.

The keystone is the **scene bible** — a single Pydantic-typed JSON document (`runs/<id>/bible.json`) that is the source of truth for the entire run. Every model call reads its inputs from the bible and writes its outputs back. That is *why* continuity holds: the palette, product refs, BPM, duration, and timed scene plan all live in one place that every stage consults.

```
Upload ─▶ Concept ─▶ NB2 Lite ─▶ Omni ─▶ Lyria ─▶ ffmpeg ─▶ Manage / Master-edit
(brief)   (editable    (boards)   (video) (music)  (mux)     (propagate to all clips)
           idea)
```

Three design rules make it robust:

- **The bible is the API between people.** Only the orchestrator and edit engine write it, always through `BibleStore.update()` — an `asyncio.Lock` + atomic `os.replace`, so a reader never sees a half-written file. The UI is read-only; it polls the bible ~once a second and is a *pure function* of that state. This decoupling is what let the frontend and pipeline be built and tested independently.
- **Every stage is idempotent and resumable.** A stage skips any asset already marked `done`, so a crash mid-run costs only the failed calls, and one failed market never blocks the others (`asyncio.gather(..., return_exceptions=True)`).
- **Adapters isolate API uncertainty.** Each model lives behind one thin file. Every call is wrapped by `guarded(kind)` — a per-model `asyncio.Semaphore` (images 8-wide, video/music 4-wide), a timeout, and `tenacity` exponential backoff. Fan-out width is a tunable, not a hardcode.

## The engineering that backs the demo

The model IDs came from the brief, but the **exact SDK surfaces did not** — the plan explicitly flagged them as "best-guess, verify in a smoke test." Verifying them was the real work.

**Omni is not a `generate_content` model.** Calling it the obvious way returns `400: "This model only supports Interactions API."` I reverse-engineered the SDK's next-gen **Interactions API** (a Responses-style surface): create a *background* interaction with an image + text input and a `video` response format, poll `interactions.get(id)` until `status == "completed"`, and read inline mp4 off `output_video`. Because this lives in one adapter file, that surprise touched nothing else.

**Omni caps a single clip at 10 seconds.** A 30s request returns `400: "exceeds the maximum allowed 10s."` To honor a duration slider that goes up to **120 seconds**, the adapter clamps what it sends to Omni, and the muxer **loops the hero clip** (`ffmpeg -stream_loop`) to fill the full timeline while the music and storyboard span the whole ad. Verified end-to-end: a 24s request produces a 10.0s raw clip and a **24.000s** final mp4 with audio.

**Lyria ignores the requested duration** (it returned ~80s audio for an 8s request). So `ffmpeg` is the reliability layer: `-t` hard-caps every output to the bible's duration and `-af apad` pads a short track with silence. Because BPM and duration are locked in the bible, music can start *in parallel with* video and still cut-align across markets.

**The utility model was silently retired.** `gemini-2.5-flash` now returns `404: "no longer available… use gemini-3.8-flash"` on this endpoint — which was quietly breaking voice edits and the brand judge until I traced it and switched models.

**Voice edits are made reliable by not trusting the browser.** The browser records WebM/Opus, which transcribes poorly; the endpoint transcodes it to 16 kHz mono WAV with `ffmpeg` before sending it to the model. Verified: spoken *"make the packaging pop more"* → exact text → live storyboard edit.

**Continuity is enforced by construction.** Product references and the brand sheet are attached to every image call; the localized-board prompt re-stages the *master* frame per market ("keep camera, composition, product placement identical; change only setting and signage to {cues}"). The timed shot list feeds both the storyboard prompts ("this scene runs 2.5–4.2s") and Omni's **timed beat sheet**, so pacing is planned, not accidental.

**Master-edit propagation** replays one instruction across all clips via Omni's video-edit path, with a documented fallback (regenerate from the keyframe with the instruction folded in) if a direct clip edit is unsupported — then re-muxes against the existing tracks.

## Why these choices were right

- **Go wide on images, narrow on video.** Images are ~4s and cheap, so we fan out 20+; video is ~40s and capped, so we generate one hero clip per market and loop it. This matches the models' real economics instead of fighting them.
- **A single typed bible over ad-hoc state.** It gives free JSON (de)serialization, resumability, a live-polling UI with no websockets, and a clean FE/BE contract — the simplest thing that is also robust for a live demo.
- **`ffmpeg` as a normalization layer.** Generative models are non-deterministic about duration; deterministic tooling absorbs that so markets stay frame-aligned.
- **Isolated adapters + guarded calls.** The two biggest surprises (Interactions API, 10s cap) each changed exactly one file, and rate-limit/latency behavior is tuned by config, not code.

## Verified results

Measured live through the running system on the challenge endpoint:

| Stage | Result |
|---|---|
| Single image | ~4.2 s |
| 8 parallel images (fan-out) | ~5.9 s |
| Music track (Lyria) | ~40 s |
| Video clip (Omni, ≤10 s) | ~41 s — **under the 60 s go/no-go** |
| Full image pipeline (brand sheet + 6 masters + 12 boards) | **24 s** |
| 2-market render (video + music + mux) | ~45 s |
| Master-edit propagation to all clips | ~75 s |
| 24 s ad, end-to-end | final mp4 **exactly 24.000 s**, video + audio |

A pre-rendered fallback run loads offline in one click, so the demo survives a venue-network or model outage.

## What it proves

Fan-Out Lite is a working, chained, multi-model creative pipeline where each model's output is the next one's input, throughput and speed are load-bearing, and cross-modal continuity is guaranteed by a shared scene bible rather than hoped for. The hard parts — an undocumented video API, a hard clip-length cap, non-deterministic audio, a retired model — were each found by verification and solved with focused engineering. It is a foundational asset: swap markets, models, or duration by editing config, and the pipeline scales with it.
