"""Jalankan Recens: python -m recens"""

from __future__ import annotations

import uvicorn

from .config import get_settings


def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    print(f"Recens berjalan di http://{settings.host}:{settings.port}")
    if not settings.has_llm:
        print(
            "Catatan: ANTHROPIC_API_KEY belum disetel. Fitur penyusunan kalimat memakai "
            "jalur deterministik; analisis data, pemeriksaan naskah, sitasi, dan ekspor "
            "tetap berjalan penuh."
        )
    uvicorn.run("recens.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
