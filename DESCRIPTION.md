# Fan-Out Lite

> **One product brief in, a finished, narrated, localized video ad for every market out — in a single chained GenMedia run.**

**Track:** Multimodal Creative Pipelines with GenMedia

---

## Short description

A localized ad engine. Upload a product and a brief once; a chained pipeline
(**Nano Banana 2 Lite → Omni (stitched per scene) → Lyria → TTS voiceover →
ffmpeg**) generates a finished, culturally-localized, *narrated* video ad for
each of up to 36 cities across 18 countries — all locked to one shared scene
bible so the product, palette, and beat stay identical everywhere.

## Overview

Marketers need one campaign rebuilt for many markets — different cities,
languages, signage, music, and voiceover — while the product identity stays
constant. Today that is weeks of agency work. Fan-Out Lite compresses it into
one loop.

Upload a product and a brief, and six generative stages chain together:

1. **Concept** — `gemini-3.8-flash` writes an editable creative concept
   (tagline, concept, hero moment, "why it travels"). Refine it by **chat or voice**
   before anything expensive runs.
2. **Timed shot list** — the concept becomes contiguous timed scenes across
   the full ad timeline. Scene count scales with the chosen duration (3–120s),
   each with a shootable description for its slot.
3. **Images (Nano Banana 2 Lite, `gemini-3.1-flash-lite-image`)** — a brand sheet,
   an N-shot master storyboard, then a localized board per market, fanned out in parallel.
4. **Video, music and voice, per market, in parallel** — each storyboard scene
   is animated as its own Omni clip (`gemini-omni-1.1-flash`, 3–10s per clip)
   and `ffmpeg` stitches them into the full ad; **Lyria** (`lyria-3.5`) scores
   a regional track; a **localized voiceover** is written *in the market's own
   language* and synthesized (`gemini-3.8-flash-tts`), then ducked under the music.
5. Each market renders and muxes **independently** — a fast market's ad is
   playable the moment it's ready.
6. **Master edit or location edit** — one instruction is replayed across
   **every** market's ad, or, in location mode, only the market you pick.

Continuity is **guaranteed, not hoped for**: a single JSON **scene bible** is the
source of truth that every model reads its inputs from and writes its outputs back to.

## Highlights

- 🎬 **Chained pipeline, not a prompt box** — each model's output is the next one's input
- 🌍 **36 cities across 18 countries** — one master concept, fanned out in parallel
- 🗣️ **Concept & storyboard editing by chat or voice**, before expensive stages run
- ⏱️ **Duration-scaled timeline (3–120s)** — scene count and pacing adapt to the length you pick
- 🎞️ **Real per-scene footage, not a looped clip** — each scene is its own Omni clip, stitched
- 🔊 **Localized voiceover** — a script written and spoken in each market's own language, mixed under the music
- 🔁 **Master edit or location edit** — update every market at once, or just one
- 🧠 **Scene bible as source of truth** — cross-market continuity of product, palette, and beat
- ⚡ **Speed is load-bearing, per market** — each market previews the moment it's ready, not all-or-nothing
- 🛟 **Offline demo fallback** — a pre-rendered run loads in one click

## Architecture

Backend and frontend are fully isolated:

- **Backend** — Python · FastAPI · async orchestrator with per-model concurrency
  limits, timeouts, and retries · isolated model adapters · per-market
  independent render+mux · `ffmpeg` scene stitching and audio mixing.
- **Frontend** — React + TypeScript (Vite) SPA; a read-only view that polls the
  scene bible and is a pure function of that state.

**Models:** Nano Banana 2 Lite · Omni (via the Interactions API, 3–10s per clip) ·
Lyria 3.5 · `gemini-3.8-flash` (concept, shot planning, voice-script localization,
transcription) · `gemini-3.8-flash-tts` (voiceover synthesis).

**Stack:** Python · FastAPI · React · TypeScript · Vite · `google-genai` ·
Pydantic v2 · tenacity · ffmpeg.

## Links

- **Repository:** https://github.com/Adithyaphani/fan-out-lite
- **Technical write-up:** [KAGGLE_WRITEUP.md](KAGGLE_WRITEUP.md)
