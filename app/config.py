"""Configuración por variables de entorno (12-factor)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PANEL_TOKEN = "demo-abancay"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@dataclass
class Config:
    database_path: str = str(BASE_DIR / "instance" / "kallpa.db")
    upload_dir: Path = BASE_DIR / "uploads"
    data_dir: Path = BASE_DIR / "data"
    ai_provider: str = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ai_timeout_s: float = 20.0
    openai_reasoning_effort: str = ""      # p. ej. "low" para Gemini 3; vacío = valor por defecto del modelo
    ai_price_in: float | None = None       # USD por 1M tokens (sobrescribe la tabla interna)
    ai_price_out: float | None = None
    review_threshold: float = 0.55
    panel_token: str = DEFAULT_PANEL_TOKEN
    rate_limit_per_hour: int = 60
    failed_lookups_per_hour: int = 20     # códigos/tokens equivocados por IP antes de bloquear
    trusted_proxies: int = 0              # nº de proxies delante de la app (Render = 1); 0 = conexión directa
    testing: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv(BASE_DIR / ".env")
        e = os.environ.get
        return cls(
            database_path=e("DATABASE_PATH", str(BASE_DIR / "instance" / "kallpa.db")),
            upload_dir=Path(e("UPLOAD_DIR", str(BASE_DIR / "uploads"))),
            ai_provider=e("AI_PROVIDER", "auto").lower(),
            anthropic_api_key=e("ANTHROPIC_API_KEY", ""),
            anthropic_model=e("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            openai_api_key=e("OPENAI_API_KEY", ""),
            openai_base_url=e("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_model=e("OPENAI_MODEL", "gpt-4o-mini"),
            ai_timeout_s=float(e("AI_TIMEOUT_S", "20")),
            openai_reasoning_effort=e("OPENAI_REASONING_EFFORT", ""),
            ai_price_in=float(e("AI_PRICE_IN")) if e("AI_PRICE_IN") else None,
            ai_price_out=float(e("AI_PRICE_OUT")) if e("AI_PRICE_OUT") else None,
            review_threshold=float(e("REVIEW_THRESHOLD", "0.55")),
            panel_token=e("PANEL_TOKEN", DEFAULT_PANEL_TOKEN) or DEFAULT_PANEL_TOKEN,
            rate_limit_per_hour=int(e("RATE_LIMIT_PER_HOUR", "60")),
            failed_lookups_per_hour=int(e("FAILED_LOOKUPS_PER_HOUR", "20")),
            trusted_proxies=int(e("TRUSTED_PROXIES", "0")),
        )
