"""Aplikasi Recens: perakitan API dan ruang kerja web."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, db
from .api import analysis, auth, billing, library, projects, publication, review, writing
from .config import get_settings
from .core.citations.sources import OFFICIAL_SOURCES
from .core.llm.catalog import TASKS, Tier
from .core.llm.providers import get_provider
from .core.llm.router import candidates_for

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
    auth.router,
    projects.router,
    library.router,
    writing.router,
    analysis.router,
    review.router,
    publication.router,
    billing.router,
):
    app.include_router(router, prefix="/api")


#: Satu tugas mewakili tiap jenjang, dipakai memperlihatkan hasil perutean.
_CONTOH_TUGAS = {
    Tier.RINGAN: TASKS["lanjutan_kalimat"],
    Tier.SEDANG: TASKS["outline"],
    Tier.BERAT: TASKS["mode_sidang"],
}


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
            "providers": settings.llm_keys,
            # Jenjang beserta model yang benar-benar akan dipakai hari ini,
            # supaya keputusan perutean bisa diperiksa tanpa membaca kode.
            "tiers": {
                tier.value: [m.key for m in candidates_for(task)]
                for tier, task in _CONTOH_TUGAS.items()
            },
            "budget": {
                "harian_usd": round(settings.budget_daily_cents / 100, 2),
                "bulanan_usd": round(settings.budget_monthly_cents / 100, 2),
            },
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

    def _index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    # Halaman depan, halaman masuk, dan ruang kerja dilayani berkas yang sama;
    # pemilihannya terjadi di sisi klien. Rute ditulis eksplisit agar alamat
    # yang tidak dikenal tetap menghasilkan 404 yang jujur.
    app.get("/", include_in_schema=False)(_index)
    app.get("/masuk", include_in_schema=False)(_index)
    app.get("/daftar", include_in_schema=False)(_index)
    app.get("/app", include_in_schema=False)(_index)
    app.get("/app/{path:path}", include_in_schema=False)(lambda path: _index())
