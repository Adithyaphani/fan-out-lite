# Fan-Out Lite

> **One product brief in, a finished localized video ad for every market out — in a single chained GenMedia run.**

**Track:** Multimodal Creative Pipelines with GenMedia

---

## Short description

A localized ad engine. Upload a product and a brief once; a chained pipeline
(**Nano Banana 2 Lite → Omni → Lyria → ffmpeg**) generates a finished,
culturally-localized video ad for each of many markets — all locked to one
shared scene bible so the product, palette, and beat stay identical everywhere.

## Overview

Marketers need one campaign rebuilt for many markets — different cities,
languages, signage, and music — while the product identity stays constant.
Today that is weeks of agency work. Fan-Out Lite compresses it into one loop.

Upload a product and a brief, and five generative stages chain together:

1. **Concept** — `gemini-3.8-flash` writes an editable creative concept
   (tagline, concept, hero moment, "why it travels"). Refine it by **chat or voice**
   before anything expensive runs.
2. **Timed shot list** — the concept becomes six contiguous timed scenes across
   the full ad timeline, each with a shootable description for its slot.
3. **Images (Nano Banana 2 Lite, `gemini-3.1-flash-lite-image`)** — a brand sheet,
   a 6-shot master storyboard, then a localized board per market, fanned out in parallel.
4. **Video (Omni, `gemini-omni-1.1-flash`) + Music (Lyria, `lyria-3.5`)** — a hero
   clip and a regional score per market, generated in parallel; **ffmpeg** muxes them.
5. **Master edit** — one conversational instruction is replayed across **every**
   market's clip at once.

Continuity is **guaranteed, not hoped for**: a single JSON **scene bible** is the
source of truth that every model reads its inputs from and writes its outputs back to.

## Highlights

- 🎬 **Chained pipeline, not a prompt box** — each model's output is the next one's input
- 🌍 **36 cities across 18 markets** — one master concept, fanned out in parallel
- 🗣️ **Concept & storyboard editing by chat or voice**, before expensive stages run
- ⏱️ **Timed shot list** — scenes planned across a 3s–120s timeline, feeding the prompts
- 🔁 **Master-edit propagation** — one instruction updates every market's clip at once
- 🧠 **Scene bible as source of truth** — cross-market continuity of product, palette, and beat
- ⚡ **Speed is load-bearing** — ~24 localized boards in ~24s; live pipeline timer
- 🛟 **Offline demo fallback** — a pre-rendered run loads in one click

## Architecture

Backend and frontend are fully isolated:

- **Backend** — Python · FastAPI · async orchestrator with per-model concurrency
  limits, timeouts, and retries · isolated model adapters · `ffmpeg` muxing.
- **Frontend** — React + TypeScript (Vite) SPA; a read-only view that polls the
  scene bible and is a pure function of that state.

**Models:** Nano Banana 2 Lite · Omni (via the Interactions API) · Lyria 3.5 ·
`gemini-3.8-flash` (concept + voice transcription).

**Stack:** Python · FastAPI · React · TypeScript · Vite · `google-genai` ·
Pydantic v2 · tenacity · ffmpeg.

## Links

- **Repository:** https://github.com/Adithyaphani/fan-out-lite
- **Technical write-up:** [KAGGLE_WRITEUP.md](KAGGLE_WRITEUP.md)
