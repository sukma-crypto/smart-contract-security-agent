"""Perkakas bersama untuk pengujian Recens."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from recens import config, db
from recens.core.llm import providers


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Tiap uji memakai basis data dan direktori sendiri, serta tanpa jaringan."""
    monkeypatch.setenv("RECENS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RECENS_NETWORK", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    config.reset_settings()
    providers.reset_provider()
    db.close_all()
    config.get_settings().ensure_dirs()
    db.init_db()
    yield
    db.close_all()
    config.reset_settings()
    providers.reset_provider()


@pytest.fixture
def conn():
    return db.connect()


@pytest.fixture
def anon_client():
    """Klien tanpa sesi — untuk menguji bahwa endpoint memang tertutup."""
    from fastapi.testclient import TestClient

    from recens.main import app

    with TestClient(app) as test_client:
        yield test_client


def register(test_client, email: str, password: str = "kalimat sandi yang panjang") -> dict:
    response = test_client.post(
        "/api/auth/register", json={"email": email, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def client(anon_client):
    """Klien yang sudah masuk.

    Seluruh endpoint proyek kini menuntut sesi, jadi fixture ini mendaftarkan
    satu akun dan menyimpan kukinya. Pengujian yang ingin memeriksa keadaan
    tanpa sesi memakai ``anon_client``.
    """
    register(anon_client, "penulis@kampus.ac.id")
    return anon_client


@pytest.fixture
def second_client():
    """Akun kedua dengan kuki terpisah, untuk menguji isolasi antar-akun."""
    from fastapi.testclient import TestClient

    from recens.main import app

    with TestClient(app) as test_client:
        register(test_client, "orang.lain@kampus.ac.id")
        yield test_client


@pytest.fixture
def survey_frame() -> pd.DataFrame:
    """Data kuesioner sintetis dengan faktor bersama, sehingga instrumennya reliabel."""
    rng = np.random.default_rng(2024)
    n = 90
    latent = rng.normal(0, 1, n)
    items = {
        f"X1.{i}": np.clip(np.round(3.6 + 0.75 * latent + rng.normal(0, 0.45, n)), 1, 5)
        for i in range(1, 6)
    }
    motivasi = np.sum(list(items.values()), axis=0)
    kinerja = 2.5 * motivasi + rng.normal(0, 4, n)
    usia = rng.normal(32, 6, n)
    return pd.DataFrame(
        {
            **items,
            "Motivasi": motivasi,
            "Kinerja": kinerja,
            "Usia": usia,
            "Kelompok": rng.choice(["Kontrol", "Eksperimen"], n),
            "Divisi": rng.choice(["A", "B", "C"], n),
            "Pretest": rng.normal(55, 8, n),
        }
    ).assign(Posttest=lambda d: d["Pretest"] + rng.normal(15, 5, n))


@pytest.fixture
def project(client) -> dict:
    return client.post(
        "/api/projects",
        json={
            "name": "Pengaruh Motivasi Kerja terhadap Kinerja Karyawan",
            "work_type": "tugas_akhir",
            "research_type": "kuantitatif_asosiatif",
        },
    ).json()


CROSSREF_ENTRY = {
    "id": "",
    "type": "article-journal",
    "title": "Motivasi Kerja dan Kinerja Karyawan",
    "author": [{"family": "Sugiyono", "given": "Bambang"}, {"family": "Hasibuan", "given": "Malayu"}],
    "issued": {"date-parts": [[2021]]},
    "container-title": "Jurnal Manajemen Indonesia",
    "volume": "12",
    "issue": "2",
    "page": "101-115",
    "DOI": "10.1234/jmi.2021.12",
}
