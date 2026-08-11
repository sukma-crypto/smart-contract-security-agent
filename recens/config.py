"""Konfigurasi aplikasi Recens, dibaca dari environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _default_data_dir() -> Path:
    return Path(os.environ.get("RECENS_DATA_DIR", Path.cwd() / "recens_data"))


@dataclass
class Settings:
    """Pengaturan runtime.

    Recens dirancang agar tetap berjalan penuh tanpa satu pun kunci API:
    seluruh perhitungan statistik, pemeriksaan naskah, perakitan format, dan
    perenderan sitasi berjalan lokal. Kunci API hanya menambah kualitas
    kalimat yang disusun model dan akses ke basis data literatur daring.
    """

    data_dir: Path = field(default_factory=_default_data_dir)

    # --- Model AI (Bagian 7.1) ---------------------------------------------
    # Model konteks panjang: menalar atas naskah utuh.
    anthropic_api_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    long_context_model: str = field(
        default_factory=lambda: os.environ.get("RECENS_LONG_CONTEXT_MODEL", "claude-opus-5")
    )
    # Model cepat: tugas bervolume tinggi dengan tuntutan latensi rendah.
    fast_model: str = field(
        default_factory=lambda: os.environ.get("RECENS_FAST_MODEL", "claude-sonnet-5")
    )

    # --- Literatur & sitasi (Bagian 7.1) -----------------------------------
    crossref_mailto: str = field(
        default_factory=lambda: os.environ.get("RECENS_CROSSREF_MAILTO", "")
    )
    openalex_enabled: bool = field(default_factory=lambda: _env_bool("RECENS_OPENALEX", True))
    semantic_scholar_key: str = field(
        default_factory=lambda: os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    )
    garuda_base_url: str = field(
        default_factory=lambda: os.environ.get("RECENS_GARUDA_BASE_URL", "")
    )
    network_enabled: bool = field(default_factory=lambda: _env_bool("RECENS_NETWORK", True))
    http_timeout: float = field(
        default_factory=lambda: float(os.environ.get("RECENS_HTTP_TIMEOUT", "20"))
    )

    # --- Platform -----------------------------------------------------------
    host: str = field(default_factory=lambda: os.environ.get("RECENS_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("RECENS_PORT", "8000")))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "recens.sqlite3"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def has_llm(self) -> bool:
        return bool(self.anthropic_api_key)

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.uploads_dir, self.exports_dir):
            path.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_dirs()
    return _settings


def reset_settings() -> None:
    """Dipakai pengujian untuk memuat ulang pengaturan."""
    global _settings
    _settings = None
