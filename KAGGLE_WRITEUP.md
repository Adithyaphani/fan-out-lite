# Fan-Out Lite

### One brief in, a finished, narrated, localized video ad for every market out — in a single chained run.

**Track:** Multimodal Creative Pipelines with GenMedia

---

## The problem

A marketer with one product and one idea needs that idea rebuilt for many markets — different cities, languages, signage, music, voiceover, and cultural setting — while the product, palette, and beat stay identical everywhere. Today that is weeks of agency work. Fan-Out Lite compresses it into one loop: upload a product and a brief once, and the system produces a finished, localized, narrated video ad for each of up to 36 cities across 18 countries, all locked to a single shared source of truth.

This is deliberately a **chained pipeline, not a prompt box**. Six generative stages feed one another, and the throughput (20+ images, N video clips, N tracks, N voiceovers per run) is the whole point — the product only exists because of fan-out.

## What it does

The flow is **Upload → Concept → Storyboard → Manage**:

1. **Concept.** From the product photos, brief, palette, and selected markets, `gemini-3.8-flash` writes an editable creative concept (tagline, concept, hero moment, "why it travels"). The user refines it by **chat or voice** before anything expensive runs.
2. **Timed shot list.** The approved concept is broken into contiguous timed scenes covering `0 → duration`. Scene count scales with the chosen duration (3–120s) — a 60s ad gets the classic 6-beat arc; a 6s ad gets 2.
3. **Images (NB2 Lite, `gemini-3.1-flash-lite-image`).** A brand sheet, then an N-shot master storyboard, then a localized board for every market — fanned out in parallel.
4. **Video, music and voice, per market, in parallel.** Each scene is animated as its own Omni clip and stitched with `ffmpeg` into the full ad; Lyria scores a regional track; a **localized voiceover** is written (in the market's own language) and synthesized, then ducked under the music.
5. **Master edit or location edit.** One instruction replays across **every** market's ad — or, in location mode, only the market you click.

## Architecture

The backend and frontend are fully isolated: an **async FastAPI** service and a **React + TypeScript (Vite)** SPA that talk over a small REST API.

The keystone is the **scene bible** — a single Pydantic-typed JSON document (`runs/<id>/bible.json`) that is the source of truth for the entire run. Every model call reads its inputs from the bible and writes its outputs back. That is *why* continuity holds: the palette, product refs, BPM, duration, and timed scene plan all live in one place that every stage consults.

```
Upload ─▶ Concept ─▶ NB2 Lite ─▶ Omni×N (stitched) + Lyria + TTS ─▶ ffmpeg mux ─▶ Manage
(brief)   (editable    (boards)   (per-scene clips, music, voice — per market)   (master / location edit)
           idea)
```

Three design rules make it robust:

- **The bible is the API between people.** Only the orchestrator and edit engine write it, always through `BibleStore.update()` — an `asyncio.Lock` + atomic `os.replace`, so a reader never sees a half-written file. The UI is read-only; it polls the bible ~once a second and is a *pure function* of that state.
- **Every stage is idempotent, resumable, and market-independent.** A stage skips any asset already marked `done`; one failed market never blocks another; and each market renders, scores, narrates and muxes on its own timeline, so a fast market's ad becomes playable the moment it's ready, without waiting on the slowest one.
- **Adapters isolate API uncertainty.** Each model lives behind one thin file. Every call is wrapped by `guarded(kind)` — a per-model `asyncio.Semaphore`, a timeout, and `tenacity` exponential backoff. Fan-out width is a tunable, not a hardcode.

## The engineering that backs the demo

The model IDs came from the brief, but the **exact SDK surfaces and limits did not** — verifying them against the real endpoint was the real work, surfacing hard constraints the brief never mentioned.

**Omni is not a `generate_content` model.** Calling it the obvious way returns `400: "This model only supports Interactions API."` I reverse-engineered the SDK's next-gen **Interactions API**: create a *background* interaction with an image + text input and a `video` response format, poll `interactions.get(id)` until `status == "completed"`, and read inline mp4 off `output_video`.

**Omni has both a floor and a ceiling — 3s to 10s per clip, not just a cap.** A 2s request is rejected as firmly as a 30s one. Missing the floor meant *every* ad under 9 seconds silently failed, because the scene planner forced 3 scenes regardless of duration, producing invalid sub-3s clips. The fix picks a scene count keeping every window in `[3s, 10s]`, falling back to one continuous "hero" shot for very short ads.

**Long ads are stitched from real scenes, not a looped clip.** Rather than looping one hero clip to fill a 60–120s timeline, each storyboard scene becomes its own Omni clip and `ffmpeg` concatenates them in order — real cuts and pacing, not repetition. Verified: a 30s ad produced three distinct 10.0s scene clips and a **30.000s** stitched final.

**Rendering was barrier-locked; it isn't anymore.** The render stage originally waited for *every* market's video and music before muxing *any* of them, so a market that finished early still had no preview until the slowest one caught up. Each market now renders and muxes independently, the moment its own assets are ready.

**Lyria ignores the requested duration** (it returned ~80s audio for an 8s request), so `ffmpeg -t` hard-caps every output and `-af apad` pads a short track with silence.

**TTS doesn't translate — it just speaks what it's given.** Adding a real voiceover (not just background music) meant a text-generation step first: a short script is written *in the market's own language and script* from the concept's tagline, then `gemini-3.8-flash-tts` synthesizes it, and `ffmpeg` ducks the music (`volume=0.25`) and mixes them via `amix`. Verified live in English, Hindi and Korean; a full Hindi-market render transcribed back to coherent Hindi correctly naming the product.

**The utility model was silently retired mid-build.** `gemini-2.5-flash` began returning `404: "no longer available… use gemini-3.8-flash,"` quietly breaking voice edits and concept generation until traced and swapped.

**Voice edits are made reliable by not trusting the browser.** Recorded WebM/Opus transcribes poorly, so it's transcoded to 16 kHz mono WAV with `ffmpeg` before the model ever sees it.

**Continuity is enforced by construction, not by hope.** Product references and the brand sheet are attached to every image call; the localized-board prompt re-stages the *master* frame per market, changing only setting and signage. Edit propagation (master **or** location scope) regenerates the affected market's scenes with the instruction folded in and re-stitches — a multi-clip ad can't be edited as one Omni call, so this is scene-by-scene by design, not a shortcut.

## Why these choices were right

- **Stitch scenes, don't loop a clip.** A real ad has distinct beats; Omni's 10s ceiling makes multiple clips unavoidable anyway, so the storyboard and the render both build around per-scene clips instead of fighting the limit with repetition.
- **A single typed bible over ad-hoc state.** Free JSON (de)serialization, resumability, a live-polling UI with no websockets, and a clean FE/BE contract.
- **Per-market independence at every layer.** Fan-out isn't just parallel calls; it's parallel *pipelines* that don't block each other, through to the final playable mp4.
- **`ffmpeg` as the normalization layer.** Models are non-deterministic about duration and can't translate on demand; deterministic tooling (trim, pad, duck, mix, concat) absorbs both.

## Verified results

Measured live through the running system on the challenge endpoint:

| Stage | Result |
|---|---|
| Single image | ~4.2 s |
| 8 parallel images (fan-out) | ~5.9 s |
| Video clip (Omni, per scene) | ~40 s — **under the 60 s go/no-go** |
| Full image pipeline (brand sheet + storyboard + 12 localized boards) | **24 s** |
| 30 s ad: 3 scene clips stitched | final mp4 **exactly 30.000 s** |
| 8 s ad with Hindi voiceover, muxed | final mp4 **exactly 8.000 s**, transcribed back to correct Hindi |
| Location edit (one market only) | other markets untouched, re-stitched in ~45 s |

A pre-rendered fallback run loads offline in one click, so the demo survives a venue-network or model outage.

## What it proves

Fan-Out Lite is a working, chained, multi-model creative pipeline where each model's output is the next one's input, throughput and speed are load-bearing, and cross-modal continuity — including a narrated, correctly localized soundtrack — is guaranteed by a shared scene bible, not hoped for. The hardest parts were never in the brief: an undocumented video API, an unstated minimum clip length, a rendering barrier hiding finished work, a model that speaks but doesn't translate. Each was found only by testing the real endpoint and fixed with focused, isolated engineering. It is a foundational asset: swap markets, models, durations or voices by editing config, and the pipeline scales with it.
