"""Aplikasi Recens: perakitan API dan ruang kerja web."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, db
from .api import analysis, billing, library, projects, review, writing
from .config import get_settings
from .core.citations.sources import OFFICIAL_SOURCES
from .core.llm.providers import get_provider

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_dirs()
    db.init_db()
    yield
    db.close_all()


app = FastAPI(
    title="Recens",
    version=__version__,
    summary="AI writing tool untuk seluruh karya tulis ilmiah.",
    description=(
        "Satu ruang kerja untuk makalah, laporan, karya tulis ilmiah, proposal, skripsi, "
        "tesis, disertasi, sampai artikel jurnal — mulai dari mengumpulkan referensi, "
        "menulis, mengolah data, memeriksa naskah, hingga mengekspor dokumen yang "
        "formatnya sudah benar."
    ),
    lifespan=lifespan,
)

for router in (
    projects.router,
    library.router,
    writing.router,
    analysis.router,
    review.router,
    billing.router,
):
    app.include_router(router, prefix="/api")


@app.get("/api/health", tags=["sistem"])
def health() -> dict:
    """Keadaan sistem, termasuk layanan mana yang aktif dan mana yang belum."""
    settings = get_settings()
    provider = get_provider()
    return {
        "status": "ok",
        "version": __version__,
        "language_model": {
            "available": provider.available,
            "provider": provider.name,
            "long_context_model": settings.long_context_model if provider.available else None,
            "fast_model": settings.fast_model if provider.available else None,
            "note": (
                "Tanpa kunci API, fitur penyusunan kalimat memakai jalur deterministik. "
                "Perhitungan statistik, pemeriksaan naskah, perenderan sitasi, dan "
                "perakitan format tetap berjalan penuh."
            ),
        },
        "network": settings.network_enabled,
        "citation_sources": {
            "official": list(OFFICIAL_SOURCES),
            "garuda_configured": bool(settings.garuda_base_url),
        },
        "data_dir": str(settings.data_dir),
    }


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def workspace() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")
