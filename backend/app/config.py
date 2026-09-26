"""Central configuration: environment, model IDs, concurrency and timeouts.

Every tunable lives here so the rest of the codebase never reads os.environ
directly. Values are validated once at import time.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the backend root (one level up from this file's package).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_ROOT / ".env")


class Settings:
    """Runtime settings, read from the environment with sane defaults."""

    def __init__(self) -> None:
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()

        # Model IDs — confirmed live on the hackathon endpoint in the smoke test.
        self.IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "gemini-3.1-flash-lite-image")
        self.VIDEO_MODEL: str = os.getenv("VIDEO_MODEL", "gemini-omni-1.1-flash")
        self.MUSIC_MODEL: str = os.getenv("MUSIC_MODEL", "lyria-3.5")
        # A multimodal model for voice transcription + the brand judge.
        # (gemini-2.5-flash is retired on this endpoint; 3.8-flash is current.)
        self.UTILITY_MODEL: str = os.getenv("UTILITY_MODEL", "gemini-3.8-flash")

        # Per-model concurrency limits (fan-out width). Tuned from smoke test.
        self.IMAGE_CONCURRENCY: int = int(os.getenv("IMAGE_CONCURRENCY", "8"))
        self.VIDEO_CONCURRENCY: int = int(os.getenv("VIDEO_CONCURRENCY", "4"))
        self.MUSIC_CONCURRENCY: int = int(os.getenv("MUSIC_CONCURRENCY", "4"))

        # Per-call timeouts (seconds).
        self.IMAGE_TIMEOUT_S: int = int(os.getenv("IMAGE_TIMEOUT_S", "60"))
        self.VIDEO_TIMEOUT_S: int = int(os.getenv("VIDEO_TIMEOUT_S", "600"))
        self.MUSIC_TIMEOUT_S: int = int(os.getenv("MUSIC_TIMEOUT_S", "120"))

        # Ad defaults (the scene-bible source of truth for cross-market lock).
        self.AD_DURATION_S: float = float(os.getenv("AD_DURATION_S", "6"))
        # Omni's per-clip bounds (confirmed against the endpoint): a request
        # below VIDEO_MIN_S or above VIDEO_MAX_S is rejected outright (400).
        self.VIDEO_MIN_S: float = float(os.getenv("VIDEO_MIN_S", "3"))
        self.VIDEO_MAX_S: float = float(os.getenv("VIDEO_MAX_S", "10"))
        self.AD_BPM: int = int(os.getenv("AD_BPM", "128"))
        self.AD_ASPECT: str = os.getenv("AD_ASPECT", "16:9")

        # Voiceover / narration TTS model (same API key, a Gemini TTS model).
        # Confirmed live: returns ready-to-mux audio/wav directly.
        self.VOICE_MODEL: str = os.getenv("VOICE_MODEL", "gemini-3.8-flash-tts")
        self.VOICE_NAME: str = os.getenv("VOICE_NAME", "Kore")
        self.ENABLE_VOICEOVER: bool = os.getenv("ENABLE_VOICEOVER", "true").lower() == "true"
        self.VOICE_TIMEOUT_S: int = int(os.getenv("VOICE_TIMEOUT_S", "60"))

        # Where runs and the demo fallback live.
        self.RUNS_DIR: Path = Path(os.getenv("RUNS_DIR", str(BACKEND_ROOT / "runs")))
        self.FALLBACK_DIR: Path = Path(os.getenv("FALLBACK_DIR", str(BACKEND_ROOT / "fallback")))

        # Enable the optional Gemini-vision brand-consistency judge.
        self.ENABLE_BRAND_JUDGE: bool = os.getenv("ENABLE_BRAND_JUDGE", "false").lower() == "true"

        self.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        self.FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def has_api_key(self) -> bool:
        return bool(self.GEMINI_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
