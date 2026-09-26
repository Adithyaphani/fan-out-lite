# AGENTS.md: Fan-Out Lite

These are the project instructions for AI coding agents: OpenAI Codex, Google Antigravity, and any tool that reads `AGENTS.md`.

> **Google Antigravity note:** the Antigravity CLI (`agy`) reads `AGENTS.md` from the directory it is launched in. The Antigravity 2.0 IDE loads workspace rules from `.agents/rules/`, so copy this file to `.agents/rules/fan-out.md` as well. If a `GEMINI.md` exists, it takes precedence over this file, so keep the two consistent.

The full design is in `docs/implementation-plan.md`. Read the relevant section before starting any task.

## Project overview

Fan-Out Lite is a localized ad engine built for a **3-hour hackathon** (DeepMind, GenMedia track). The user supplies one product brief. The system then produces a finished video ad for each of 4 markets (Delhi, São Paulo, Seoul, Lagos):

- **Images:** NB2 Lite generates a brand sheet, a 6-shot master storyboard, and a localized storyboard per market.
- **Edits:** the user edits the storyboard by chat or voice.
- **Video:** Omni animates one hero clip per market.
- **Audio:** Lyria scores each market in a regional style, all at a shared BPM and duration.
- **Merge:** ffmpeg combines video and audio.
- **Master edit:** one instruction is replayed across every market clip.

Two things carry the demo: **speed** and **cross-modal continuity**. Protect both.

## Setup commands

```bash
pip install -r requirements.txt      # ffmpeg must also be installed and on PATH
cp .env.example .env                 # add GEMINI_API_KEY
```

## Run, test and lint

```bash
python scripts/smoke_test.py         # model latency + go/no-go
streamlit run app/Home.py            # run the app
python scripts/prerender.py          # build fallback/ (only in the 2:15–2:35 window)
pytest -q                            # tests
ruff format . && ruff check . --fix  # format + lint
ffprobe -v error -show_entries format=duration -of csv=p=0 runs/<id>/final/IN_v1.mp4
```

## Repository map

| Path | Purpose |
|---|---|
| `fanout/bible.py` | `SceneBible` pydantic models + `BibleStore` (atomic, locked writes) |
| `fanout/config.py` | Model IDs, concurrency limits, timeouts (from `.env`) |
| `fanout/markets.py` | Market presets: language, script, cultural cues, music style |
| `fanout/prompts.py` | **All** prompt templates |
| `fanout/adapters/` | **All** model calls: `image.py`, `video.py`, `music.py`, `judge.py` |
| `fanout/orchestrator.py` | Pipeline stages, fan-out, retries, timings |
| `fanout/edits.py` | Storyboard edits + master-edit propagation |
| `fanout/mux.py` | ffmpeg helpers |
| `fanout/demo.py` | Fallback loader |
| `app/` | Streamlit UI: `Home.py`, `pages/1_Upload.py`, `2_Storyboard.py`, `3_Manage.py` |
| `fixtures/bible_sample.json` | Fake bible for UI development |
| `runs/` | Live run outputs (gitignored) |
| `fallback/` | Pre-rendered demo run (**do not modify by hand**) |

## Hard constraints

1. **Scope is locked** to `docs/implementation-plan.md`. Don't add features, pages, models, frameworks or dependencies unless the user explicitly asks.
2. **Prefer the simplest working solution.** This is a 3-hour build, and the demo matters more than elegance.
3. **Cut order.** When behind schedule, cut in this order, and state it:
   1. Brand-consistency checker.
   2. Drop to 3 markets.
   3. Skip music re-generation after edits.
4. **Go/no-go.** If Omni takes more than ~60s per clip in the smoke test, stop and report it. The plan pivots to Concept Arena.
5. **`fallback/` is read-only** except through `scripts/prerender.py`. Demo mode must always work offline.
6. **Code freeze at 2:35.** After that, bug fixes only.

## Architecture rules

- **The scene bible is the single source of truth.** Every model call reads its inputs from it, and every result is written back.
- **Only `orchestrator.py` and `edits.py` write the bible**, always through `BibleStore.update()`. The UI is read-only and calls orchestrator functions.
- **Model SDK imports (`google.genai`) are allowed only in `fanout/adapters/`.**
- **Prompts are allowed only in `fanout/prompts.py`**, built from bible fields.
- **Continuity:** attach the product reference images and the brand sheet to every image and video generation call.
- **Idempotent, resumable stages.** Skip assets with status `done`. One failed market must never block the others.
- **Concurrency:** use `asyncio.gather` with the per-model semaphores and timeouts from `config.py`. No unbounded parallelism.
- **Media:** cap every final mp4 to `bible.duration_s` (ffmpeg `-t`). All tracks use `bible.bpm`.
- **Asset paths** are relative to `runs/<run_id>/`.

## Model and SDK rules

- Model IDs come only from config:
  - `gemini-3.1-flash-lite-image` (images)
  - `gemini-omni-1.1-flash` (video)
  - `lyria-3.5` (music)
- **Do not invent SDK methods or parameters.** Verify them against the installed `google-genai` package (version, `help()`, `inspect`) or the smoke-test output before coding.
- If a capability is unconfirmed, implement the plan's fallback and mark it with `# VERIFY:`:
  - Omni clip edit: regenerate from the boards with the instruction appended to the prompt.
  - Lyria BPM/duration: put them in the prompt, then trim or pad with ffmpeg.
- Wrap every model call in `guarded(kind)` (semaphore + timeout + retry).
- Record the latency of every call in `bible.timings`.

## Code style

- Python 3.11+, type hints on public functions, `async` adapters and stages.
- Pydantic v2 for structured data. No loose dicts across modules.
- Small functions and early returns.
- Run `ruff format` and `ruff check`.
- Keep Streamlit pages thin: layout plus calls into `fanout/` only.
- Comment only what is non-obvious, and every `# VERIFY:`.

## Security

- Never commit `.env`, keys, `runs/`, or generated media.
- Never print or log `GEMINI_API_KEY`.
- Don't run destructive commands (`rm -rf`, `git reset --hard`, force push) without explicit approval.
- Market cues describe settings, props, light and music, never people's ethnicity or stereotypes. Flag any cue that does.

## Workflow

1. Name the plan section you are implementing.
2. For changes touching more than 2 files, outline the plan before editing.
3. Keep diffs minimal. Don't refactor unrelated code.
4. When the backend isn't ready, build UI against `fixtures/bible_sample.json`.
5. If an API blocks you for more than ~10 minutes, use the documented fallback and report it.
6. Before finishing, run the checks below and report the commands and results.

## Definition of done

- [ ] `ruff check .` and `pytest -q` pass.
- [ ] `fixtures/bible_sample.json` still validates against `SceneBible`.
- [ ] Pipeline changes: one real market ran end to end, or you explain why it couldn't run.
- [ ] Media changes: `ffprobe` confirms an audio stream and the correct duration.
- [ ] Demo mode still loads `fallback/` offline.
- [ ] Any new `# VERIFY:` items are listed in your summary.

## Commits and PRs

- Use the format `type(scope): summary`, for example `feat(stage): parallel market boards` or `fix(mux): pad short tracks`.
- One logical change per commit, and one commit per working stage.
- PR or task summary: what changed, the checks you ran, `# VERIFY:` items, and any cut-order items applied.

## Stop and ask when

- A change needs a new dependency, model, page or feature outside the plan.
- The go/no-go threshold is breached or a timeline checkpoint is missed.
- A change would touch `fallback/`, delete files, or rewrite git history.
- The user's request conflicts with these rules.
