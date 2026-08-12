"""Autentikasi dan isolasi antar-akun.

Berkas ini punya satu tugas: membuktikan bahwa akun A tidak dapat menyentuh
apa pun milik akun B. Sebelum ada pengujian ini, ``get_project`` hanya mencari
``WHERE id = ?`` — sehingga ``GET /api/projects/7`` mengembalikan proyek nomor
tujuh milik siapa pun. Kebocoran seperti itu tidak terlihat dari antarmuka dan
gampang kembali diam-diam, jadi ia dijaga di sini per sumber daya, bukan
sekadar sekali di pintu depan.
"""

from __future__ import annotations

import pytest

from recens.core import auth

PASSWORD = "kalimat sandi yang panjang"


@pytest.fixture
def their_project(second_client) -> dict:
    """Proyek berisi milik akun kedua, lengkap dengan bab, blok, dan analisis."""
    project = second_client.post(
        "/api/projects", json={"name": "Naskah Orang Lain", "work_type": "makalah"}
    ).json()
    manuscript = second_client.get(f"/api/projects/{project['id']}/manuscript").json()
    section_id = manuscript["sections"][0]["id"]
    block_id = second_client.post(
        f"/api/sections/{section_id}/blocks",
        json={"kind": "paragraph", "content": "Isi rahasia milik orang lain."},
    ).json()["id"]
    revision_id = second_client.post(
        f"/api/projects/{project['id']}/revisions",
        json={"text": "Perbaiki latar belakang.", "source": "pembimbing"},
    ).json()["id"]
    return {
        "project_id": project["id"],
        "section_id": section_id,
        "block_id": block_id,
        "revision_id": revision_id,
    }


class TestKataSandi:
    def test_hash_tidak_pernah_menyimpan_kata_sandi_asli(self):
        stored = auth.hash_password(PASSWORD)
        assert PASSWORD not in stored
        assert stored.startswith("pbkdf2_sha256$")
        assert auth.verify_password(PASSWORD, stored)
        assert not auth.verify_password(PASSWORD + "x", stored)

    def test_garam_berbeda_tiap_akun(self):
        """Dua orang dengan kata sandi sama tidak boleh punya hash yang sama."""
        assert auth.hash_password(PASSWORD) != auth.hash_password(PASSWORD)

    def test_hash_lama_tetap_terverifikasi(self):
        """Iterasi boleh dinaikkan tanpa membatalkan kata sandi yang sudah ada."""
        lama = auth.hash_password(PASSWORD, iterations=1_000)
        assert auth.verify_password(PASSWORD, lama)
        assert auth.needs_rehash(lama)
        assert not auth.needs_rehash(auth.hash_password(PASSWORD))

    def test_akun_tanpa_kata_sandi_tidak_bisa_dimasuki(self):
        """Akun peninggalan sebelum autentikasi ada tidak boleh terbuka begitu saja."""
        assert not auth.verify_password("", None)
        assert not auth.verify_password(PASSWORD, None)

    def test_kata_sandi_pendek_ditolak_dengan_saran(self):
        problem = auth.password_problem("pendek")
        assert problem and "minimal" in problem

    def test_kata_sandi_yang_memuat_surel_sendiri_ditolak(self):
        problem = auth.password_problem("mahasiswa2024rahasia", email="mahasiswa@kampus.ac.id")
        assert problem and "surel" in problem

    def test_kata_sandi_umum_ditolak(self):
        assert auth.password_problem("password123") is not None


class TestPendaftaranDanMasuk:
    def test_daftar_membuka_sesi_sekaligus(self, anon_client):
        response = anon_client.post(
            "/api/auth/register", json={"email": "baru@kampus.ac.id", "password": PASSWORD}
        )
        assert response.status_code == 201
        assert anon_client.get("/api/auth/me").json()["email"] == "baru@kampus.ac.id"

    def test_surel_disamakan_bentuknya(self, anon_client):
        anon_client.post(
            "/api/auth/register", json={"email": "  Budi@Kampus.AC.ID ", "password": PASSWORD}
        )
        assert anon_client.get("/api/auth/me").json()["email"] == "budi@kampus.ac.id"

    def test_surel_ganda_ditolak(self, anon_client):
        payload = {"email": "kembar@kampus.ac.id", "password": PASSWORD}
        assert anon_client.post("/api/auth/register", json=payload).status_code == 201
        assert anon_client.post("/api/auth/register", json=payload).status_code == 409

    def test_surut_salah_dan_sandi_salah_dijawab_sama(self, anon_client):
        """Halaman masuk tidak boleh dipakai memetakan siapa yang punya akun."""
        anon_client.post(
            "/api/auth/register", json={"email": "ada@kampus.ac.id", "password": PASSWORD}
        )
        anon_client.post("/api/auth/logout")

        sandi_salah = anon_client.post(
            "/api/auth/login", json={"email": "ada@kampus.ac.id", "password": "salah sekali ini"}
        )
        surel_tak_ada = anon_client.post(
            "/api/auth/login", json={"email": "tidak.ada@kampus.ac.id", "password": PASSWORD}
        )
        assert sandi_salah.status_code == surel_tak_ada.status_code == 401
        assert sandi_salah.json()["detail"] == surel_tak_ada.json()["detail"]

    def test_kuki_sesi_tidak_terbaca_javascript(self, anon_client):
        response = anon_client.post(
            "/api/auth/register", json={"email": "kuki@kampus.ac.id", "password": PASSWORD}
        )
        cookie = response.headers["set-cookie"].lower()
        assert "httponly" in cookie
        assert "samesite=lax" in cookie

    def test_token_sesi_tidak_disimpan_apa_adanya(self, anon_client, conn):
        """Salinan basis data yang bocor tidak boleh langsung bisa dipakai masuk."""
        token = anon_client.post(
            "/api/auth/register", json={"email": "token@kampus.ac.id", "password": PASSWORD}
        ).json()["token"]
        rows = conn.execute("SELECT token_hash FROM sessions").fetchall()
        assert rows and all(row["token_hash"] != token for row in rows)

    def test_keluar_mematikan_sesi(self, client):
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/me").status_code == 401

    def test_token_boleh_lewat_header(self, anon_client):
        """Klien non-peramban tidak perlu mengurus kuki."""
        token = anon_client.post(
            "/api/auth/register", json={"email": "skrip@kampus.ac.id", "password": PASSWORD}
        ).json()["token"]
        anon_client.cookies.clear()
        response = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200


class TestPengelolaanAkun:
    def test_ubah_nama_dan_surel(self, client):
        response = client.patch(
            "/api/auth/me", json={"display_name": "Bayu S.", "email": "bayu@kampus.ac.id"}
        )
        assert response.status_code == 200
        assert response.json()["display_name"] == "Bayu S."
        assert response.json()["email"] == "bayu@kampus.ac.id"

    def test_surel_milik_orang_lain_ditolak(self, client, second_client):
        response = client.patch("/api/auth/me", json={"email": "orang.lain@kampus.ac.id"})
        assert response.status_code == 409

    def test_ganti_sandi_menuntut_sandi_lama(self, client):
        response = client.post(
            "/api/auth/me/password",
            json={"current_password": "tebakan keliru", "new_password": "sandi baru yang panjang"},
        )
        assert response.status_code == 403

    def test_ganti_sandi_mengeluarkan_perangkat_lain(self, anon_client):
        from fastapi.testclient import TestClient

        from recens.main import app

        anon_client.post(
            "/api/auth/register", json={"email": "dua.alat@kampus.ac.id", "password": PASSWORD}
        )
        with TestClient(app) as alat_kedua:
            alat_kedua.post(
                "/api/auth/login", json={"email": "dua.alat@kampus.ac.id", "password": PASSWORD}
            )
            assert alat_kedua.get("/api/auth/me").status_code == 200

            hasil = anon_client.post(
                "/api/auth/me/password",
                json={"current_password": PASSWORD, "new_password": "sandi baru yang panjang"},
            )
            assert hasil.status_code == 200
            assert hasil.json()["sessions_revoked"] == 1

            # Perangkat kedua langsung terputus; perangkat pengubah tetap masuk.
            assert alat_kedua.get("/api/auth/me").status_code == 401
            assert anon_client.get("/api/auth/me").status_code == 200

    def test_daftar_sesi_menandai_yang_sedang_dipakai(self, client):
        sessions = client.get("/api/auth/sessions").json()
        assert len(sessions) == 1
        assert sessions[0]["current"] is True
        assert "token" not in sessions[0] and "token_hash" not in sessions[0]

    def test_sesi_orang_lain_tidak_bisa_dicabut(self, client, second_client):
        milik_orang_lain = second_client.get("/api/auth/sessions").json()[0]["id"]
        assert client.delete(f"/api/auth/sessions/{milik_orang_lain}").status_code == 404
        assert second_client.get("/api/auth/me").status_code == 200

    def test_hapus_akun_menuntut_sandi_dan_ketikan_surel(self, client):
        salah_sandi = client.request(
            "DELETE",
            "/api/auth/me",
            json={"password": "keliru sekali ini", "confirm": "penulis@kampus.ac.id"},
        )
        assert salah_sandi.status_code == 403

        tanpa_ketikan = client.request(
            "DELETE", "/api/auth/me", json={"password": PASSWORD, "confirm": ""}
        )
        assert tanpa_ketikan.status_code == 400

    def test_hapus_akun_ikut_menghapus_proyeknya(self, client, conn):
        project = client.post(
            "/api/projects", json={"name": "Akan hilang", "work_type": "makalah"}
        ).json()
        response = client.request(
            "DELETE",
            "/api/auth/me",
            json={"password": PASSWORD, "confirm": "penulis@kampus.ac.id"},
        )
        assert response.status_code == 204
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM projects WHERE id = ?", (project["id"],)
        ).fetchone()["n"] == 0


class TestPintuTertutup:
    """Tanpa sesi, tidak ada satu pun data pengguna yang bisa disentuh."""

    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/projects"),
            ("POST", "/api/projects"),
            ("GET", "/api/projects/1"),
            ("DELETE", "/api/projects/1"),
            ("GET", "/api/projects/1/manuscript"),
            ("GET", "/api/projects/1/dashboard"),
            ("PATCH", "/api/blocks/1"),
            ("PATCH", "/api/sections/1"),
            ("POST", "/api/analyses/1/insert"),
            ("GET", "/api/datasets/1/preview"),
            ("POST", "/api/references/1/verify"),
            ("GET", "/api/references/search?q=motivasi"),
            ("GET", "/api/account"),
            ("POST", "/api/account/topup"),
            ("GET", "/api/account/ledger"),
            ("GET", "/api/auth/me"),
            ("GET", "/api/auth/sessions"),
        ],
    )
    def test_tanpa_sesi_dijawab_401(self, anon_client, method, path):
        response = anon_client.request(method, path, json={})
        assert response.status_code == 401, f"{method} {path} → {response.status_code}"

    @pytest.mark.parametrize(
        "path", ["/api/health", "/api/catalog", "/api/plans", "/api/limits", "/api/journals"]
    )
    def test_katalog_tetap_terbuka(self, anon_client, path):
        """Yang tidak memuat data siapa pun tetap bisa dibaca sebelum masuk."""
        assert anon_client.get(path).status_code == 200


class TestIsolasiAntarAkun:
    """Tiap sumber daya diuji sendiri, karena masing-masing punya jalan masuknya."""

    def test_proyek_orang_lain_tidak_terbaca(self, client, their_project):
        assert client.get(f"/api/projects/{their_project['project_id']}").status_code == 404

    def test_proyek_orang_lain_tidak_terhapus(self, client, second_client, their_project):
        assert client.delete(f"/api/projects/{their_project['project_id']}").status_code == 404
        # Buktikan proyeknya memang masih ada, bukan sekadar tidak terlihat.
        assert second_client.get(f"/api/projects/{their_project['project_id']}").status_code == 200

    def test_proyek_orang_lain_tidak_terubah(self, client, their_project):
        response = client.patch(
            f"/api/projects/{their_project['project_id']}", json={"name": "Dibajak"}
        )
        assert response.status_code == 404

    def test_daftar_proyek_hanya_milik_sendiri(self, client, their_project):
        milik_sendiri = client.post(
            "/api/projects", json={"name": "Punya saya", "work_type": "makalah"}
        ).json()
        daftar = client.get("/api/projects").json()
        assert [p["id"] for p in daftar] == [milik_sendiri["id"]]

    def test_naskah_orang_lain_tidak_terbaca(self, client, their_project):
        assert (
            client.get(f"/api/projects/{their_project['project_id']}/manuscript").status_code == 404
        )

    def test_blok_orang_lain_tidak_terubah(self, client, second_client, their_project):
        response = client.patch(
            f"/api/blocks/{their_project['block_id']}", json={"content": "Disusupi."}
        )
        assert response.status_code == 404

        manuscript = second_client.get(
            f"/api/projects/{their_project['project_id']}/manuscript"
        ).json()
        isi = manuscript["sections"][0]["blocks"][0]["content"]
        assert isi == "Isi rahasia milik orang lain."

    def test_blok_orang_lain_tidak_terhapus(self, client, their_project):
        assert client.delete(f"/api/blocks/{their_project['block_id']}").status_code == 404

    def test_bagian_orang_lain_tidak_terubah(self, client, their_project):
        response = client.patch(
            f"/api/sections/{their_project['section_id']}", json={"title": "Judul baru"}
        )
        assert response.status_code == 404

    def test_blok_tidak_bisa_ditambahkan_ke_bab_orang_lain(self, client, their_project):
        response = client.post(
            f"/api/sections/{their_project['section_id']}/blocks",
            json={"kind": "paragraph", "content": "Titipan."},
        )
        assert response.status_code == 404

    def test_catatan_revisi_orang_lain_tidak_terubah(self, client, their_project):
        response = client.patch(
            f"/api/revisions/{their_project['revision_id']}", json={"status": "selesai"}
        )
        assert response.status_code == 404

    def test_data_penelitian_orang_lain_tidak_terbaca(self, client, second_client, their_project):
        import io

        csv = io.BytesIO(b"Nilai\n80\n85\n90\n")
        dataset = second_client.post(
            f"/api/projects/{their_project['project_id']}/datasets",
            files={"file": ("nilai.csv", csv, "text/csv")},
        ).json()
        assert client.get(f"/api/datasets/{dataset['id']}/preview").status_code == 404

    def test_uji_statistik_tidak_bisa_memakai_data_proyek_lain(
        self, client, second_client, their_project
    ):
        """Celah paling halus: proyek sendiri, tetapi ``dataset_id`` milik orang lain."""
        import io

        csv = io.BytesIO(b"Nilai\n80\n85\n90\n")
        dataset = second_client.post(
            f"/api/projects/{their_project['project_id']}/datasets",
            files={"file": ("nilai.csv", csv, "text/csv")},
        ).json()
        milik_sendiri = client.post(
            "/api/projects", json={"name": "Punya saya", "work_type": "makalah"}
        ).json()

        response = client.post(
            f"/api/projects/{milik_sendiri['id']}/analyses",
            json={
                "method": "descriptive",
                "dataset_id": dataset["id"],
                "params": {"columns": ["Nilai"]},
            },
        )
        assert response.status_code == 404

    def test_hasil_analisis_tidak_bisa_disisipkan_ke_naskah_orang_lain(
        self, client, second_client, their_project
    ):
        import io

        csv = io.BytesIO(b"Nilai\n80\n85\n90\n")
        milik_sendiri = client.post(
            "/api/projects", json={"name": "Punya saya", "work_type": "makalah"}
        ).json()
        dataset = client.post(
            f"/api/projects/{milik_sendiri['id']}/datasets",
            files={"file": ("nilai.csv", csv, "text/csv")},
        ).json()
        analysis = client.post(
            f"/api/projects/{milik_sendiri['id']}/analyses",
            json={
                "method": "descriptive",
                "dataset_id": dataset["id"],
                "params": {"columns": ["Nilai"]},
            },
        ).json()

        response = client.post(
            f"/api/analyses/{analysis['id']}/insert",
            json={"section_id": their_project["section_id"]},
        )
        assert response.status_code == 404

    def test_ekspor_orang_lain_tidak_bisa_diunduh(self, client, second_client, their_project):
        second_client.post(
            f"/api/projects/{their_project['project_id']}/export", json={"format": "docx"}
        )
        response = client.get(
            f"/api/projects/{their_project['project_id']}/export/download?format=docx"
        )
        assert response.status_code == 404

    def test_kredit_akun_lain_tidak_bisa_ditambah(self, client, second_client):
        """Endpoint kredit bekerja pada akun sendiri, tanpa menerima nomor akun."""
        sebelum = second_client.get("/api/account").json()["credits"]
        client.post("/api/account/topup", json={"amount": 5_000})
        assert second_client.get("/api/account").json()["credits"] == sebelum
