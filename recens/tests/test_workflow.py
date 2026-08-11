"""Alur kerja delapan langkah, dari proyek baru sampai naskah siap serah."""

from __future__ import annotations

import zipfile

import pytest

from recens.core.credits import PLANS
from recens.core.worktypes import WORK_TYPES, Family, ResearchType, applicable_steps, get_work_type

from .conftest import CROSSREF_ENTRY


class TestKatalogJenisKarya:
    def test_sembilan_jenis_karya_didukung(self):
        assert len(WORK_TYPES) == 9

    def test_tiap_jenis_karya_punya_struktur_bawaan(self):
        for work_type in WORK_TYPES.values():
            assert work_type.structure, f"{work_type.key} tanpa struktur"
            assert work_type.default_target_words > 0

    @pytest.mark.parametrize(
        "key, family",
        [
            ("makalah", Family.PENDEK),
            ("laporan", Family.PENDEK),
            ("proposal", Family.TUGAS_AKHIR),
            ("tugas_akhir", Family.TUGAS_AKHIR),
            ("artikel_jurnal", Family.PUBLIKASI),
            ("prosiding", Family.PUBLIKASI),
        ],
    )
    def test_kelompok_perlakuan(self, key, family):
        assert get_work_type(key).family is family

    def test_karya_pendek_menjadikan_olah_data_opsional(self):
        steps = applicable_steps(get_work_type("makalah"), ResearchType.NONE)
        olah = next(s for s in steps if s["key"] == "olah_data")
        assert olah["mode"] == "opsional"
        assert olah["active"] is False

    def test_tugas_akhir_kuantitatif_mewajibkan_olah_data(self):
        steps = applicable_steps(get_work_type("tugas_akhir"), ResearchType.KUANTITATIF_ASOSIATIF)
        olah = next(s for s in steps if s["key"] == "olah_data")
        assert olah["active"] is True

    def test_tugas_akhir_tanpa_data_tidak_mewajibkan_langkah_enam(self):
        steps = applicable_steps(get_work_type("tugas_akhir"), ResearchType.NONE)
        assert next(s for s in steps if s["key"] == "olah_data")["active"] is False

    def test_proposal_berhenti_di_metodologi(self):
        titles = [s.title for s in get_work_type("proposal").structure]
        assert any("METODE" in t for t in titles)
        assert not any("HASIL" in t for t in titles)

    def test_artikel_jurnal_memakai_imrad(self):
        titles = [s.title for s in get_work_type("artikel_jurnal").structure]
        assert titles == ["Abstrak", "Pendahuluan", "Metode", "Hasil", "Pembahasan", "Simpulan"]

    def test_prosiding_memakai_ieee_dan_latex(self):
        prosiding = get_work_type("prosiding")
        assert prosiding.citation_style == "ieee"
        assert "latex" in prosiding.export_formats


class TestLangkahSatuSampaiEmpat:
    def test_proyek_baru_langsung_punya_kerangka(self, client):
        project = client.post(
            "/api/projects",
            json={"name": "Skripsi Uji", "work_type": "tugas_akhir",
                  "research_type": "kuantitatif_asosiatif"},
        ).json()
        outline = client.get(f"/api/projects/{project['id']}/outline").json()
        assert len(outline["sections"]) > 10
        assert outline["target_words"] == project["target_words"]

    def test_target_kata_terbagi_ke_tiap_bagian(self, client, project):
        outline = client.get(f"/api/projects/{project['id']}/outline").json()
        # Target keseluruhan terbagi habis ke bagian terkecil.
        assert outline["target_words"] == project["target_words"]
        # Tiap bab melaporkan jumlah target sub-bagiannya, dan totalnya utuh.
        chapters = [s for s in outline["sections"] if s["level"] == 1]
        assert sum(c["target_words"] for c in chapters) == pytest.approx(
            project["target_words"], rel=0.02
        )

    def test_jenis_karya_tak_dikenal_ditolak(self, client):
        response = client.post("/api/projects", json={"name": "X", "work_type": "novel"})
        assert response.status_code == 400
        assert "tidak dikenal" in response.json()["detail"]

    def test_bangun_ulang_kerangka_butuh_reset_eksplisit(self, client, project):
        response = client.post(
            f"/api/projects/{project['id']}/outline/generate", json={"reset": False}
        )
        assert response.status_code == 409

    def test_riwayat_versi_dan_pemulihan(self, client, project, conn):
        pid = project["id"]
        sections = _section_ids(client, pid)
        target = sections["Latar Belakang Masalah"]
        client.post(f"/api/sections/{target}/blocks", json={"content": "Teks versi pertama."})

        version = client.post(f"/api/projects/{pid}/versions", json={"label": "v1"}).json()
        blocks = client.get(f"/api/projects/{pid}/manuscript").json()
        block_id = _find_block(blocks["sections"], target)
        client.patch(f"/api/blocks/{block_id}", json={"content": "Teks yang keliru arah."})

        restored = client.post(f"/api/projects/{pid}/versions/{version['id']}/restore").json()
        assert restored["restored"] == version["id"]
        text = client.get(f"/api/projects/{pid}/manuscript").json()
        assert "versi pertama" in _all_text(text["sections"])


class TestLangkahTujuhDanDelapan:
    def test_pemeriksaan_lengkap_berjalan(self, client, project):
        pid = project["id"]
        sections = _section_ids(client, pid)
        client.post(
            f"/api/sections/{sections['Latar Belakang Masalah']}/blocks",
            json={"content": "Analisa awal menunjukkan produktifitas menurun dimana motivasi rendah."},
        )
        result = client.post(f"/api/projects/{pid}/checks").json()
        assert set(result["checks"]) == {"bahasa", "sitasi", "konsistensi", "kemiripan", "batas"}
        assert result["checks"]["bahasa"]["total"] >= 3
        assert result["summary"]["ready_to_submit"] is False

    def test_pemeriksaan_terpilih_saja(self, client, project):
        result = client.post(f"/api/projects/{project['id']}/checks?kinds=bahasa,batas").json()
        assert set(result["checks"]) == {"bahasa", "batas"}

    def test_pemeriksaan_tak_dikenal_ditolak(self, client, project):
        response = client.post(f"/api/projects/{project['id']}/checks?kinds=ramalan")
        assert response.status_code == 400

    def test_ekspor_docx_menghasilkan_berkas_word_sah(self, client, project, tmp_path):
        pid = project["id"]
        sections = _section_ids(client, pid)
        client.post(
            f"/api/sections/{sections['Latar Belakang Masalah']}/blocks",
            json={"content": "Kinerja karyawan dipengaruhi banyak faktor."},
        )
        result = client.post(
            f"/api/projects/{pid}/export",
            json={"format": "docx", "meta": {"author": "Bayu", "institution": "Universitas Contoh"}},
        ).json()

        assert result["size_bytes"] > 5000
        with zipfile.ZipFile(result["path"]) as archive:
            names = archive.namelist()
            assert "word/document.xml" in names
            document = archive.read("word/document.xml").decode("utf-8")
        assert "Kinerja karyawan dipengaruhi" in document
        # Penomoran romawi untuk bagian awal, arab untuk bagian isi.
        assert 'w:fmt="lowerRoman"' in document
        assert 'w:fmt="decimal"' in document
        # Daftar isi disisipkan sebagai field agar Word bisa memperbaruinya.
        assert "TOC" in document

    def test_ekspor_menerapkan_aturan_pedoman(self, client, project):
        pid = project["id"]
        client.post(
            f"/api/projects/{pid}/guidelines/text",
            json={"text": "Huruf Arial ukuran 11 pt dengan jarak 1,5 spasi. Margin kiri 3 cm."},
        )
        result = client.post(f"/api/projects/{pid}/export", json={"format": "docx"}).json()
        assert "Arial 11.0pt" in result["applied_rules"]["font"]
        assert result["applied_rules"]["line_spacing"] == 1.5
        assert result["applied_rules"]["margins"]["left_cm"] == 3.0

    def test_format_yang_tidak_berlaku_ditolak(self, client, project):
        response = client.post(f"/api/projects/{project['id']}/export", json={"format": "latex"})
        assert response.status_code == 400
        assert "tidak berlaku" in response.json()["detail"]

    def test_prosiding_boleh_ekspor_latex(self, client):
        project = client.post(
            "/api/projects", json={"name": "Paper", "work_type": "prosiding"}
        ).json()
        result = client.post(
            f"/api/projects/{project['id']}/export", json={"format": "latex"}
        ).json()
        assert result["path"].endswith(".tex")
        content = open(result["path"], encoding="utf-8").read()
        assert "\\documentclass" in content and "\\begin{document}" in content

    def test_pelacak_bimbingan(self, client, project):
        pid = project["id"]
        created = client.post(
            f"/api/projects/{pid}/revisions",
            json={"text": "Perbaiki rumusan masalah nomor 2.", "source": "pembimbing"},
        ).json()
        listing = client.get(f"/api/projects/{pid}/revisions").json()
        assert listing["total"] == 1
        assert listing["by_status"]["terbuka"] == 1

        client.patch(f"/api/revisions/{created['id']}", json={"status": "selesai"})
        done = client.get(f"/api/projects/{pid}/revisions").json()
        assert done["by_status"]["selesai"] == 1
        assert done["revisions"][0]["resolved_at"]

    def test_mode_sidang_hanya_untuk_tugas_akhir(self, client):
        makalah = client.post(
            "/api/projects", json={"name": "Makalah", "work_type": "makalah"}
        ).json()
        assert client.post(f"/api/projects/{makalah['id']}/defense").status_code == 400

    def test_mode_sidang_menyusun_pertanyaan_dari_titik_rawan(self, client, project):
        result = client.post(f"/api/projects/{project['id']}/defense").json()
        assert result["questions"]
        assert all("pertanyaan" in q for q in result["questions"])


class TestPaketAkses:
    def test_paket_tidak_mengunci_fitur(self):
        """Yang membedakan paket adalah kuota dan durasi, bukan fitur."""
        for plan in PLANS.values():
            assert "Seluruh fitur" in plan.feature_access

    def test_fitur_lokal_tidak_menagih_kredit(self, client):
        plans = client.get("/api/plans").json()
        free = set(plans["free_actions"])
        assert {"analisis_data", "cek_naskah", "auto_format", "ekspor"} <= free

    def test_kuota_proyek_paket_coba(self, client):
        """Paket coba dibatasi satu proyek — batas kuota, bukan kunci fitur."""
        first = client.post("/api/projects", json={"name": "Satu", "work_type": "makalah"})
        assert first.status_code == 201
        second = client.post("/api/projects", json={"name": "Dua", "work_type": "makalah"})
        assert second.status_code == 402

    def test_naik_paket_membuka_proyek_tak_terbatas(self, client):
        client.post("/api/account/plan", json={"plan": "semester"})
        for name in ("Satu", "Dua", "Tiga"):
            response = client.post(
                "/api/projects", json={"name": name, "work_type": "makalah"}
            )
            assert response.status_code == 201

    def test_proyek_tidak_bisa_dititipkan_ke_akun_lain(self, client, second_client):
        """Pemilik diambil dari sesi, sehingga ``account_id`` kiriman diabaikan."""
        created = client.post(
            "/api/projects",
            json={"name": "Titipan", "work_type": "makalah", "account_id": 999},
        ).json()
        assert client.get(f"/api/projects/{created['id']}").status_code == 200
        assert second_client.get(f"/api/projects/{created['id']}").status_code == 404


class TestKesehatanSistem:
    def test_health_menjelaskan_keadaan_tanpa_kunci_api(self, client):
        health = client.get("/api/health").json()
        assert health["status"] == "ok"
        assert health["language_model"]["available"] is False
        assert "deterministik" in health["language_model"]["note"]

    def test_katalog_memuat_batas_produk(self, client):
        catalog = client.get("/api/catalog").json()
        assert len(catalog["product_limits"]) == 5
        assert len(catalog["work_types"]) == 9
        assert len(catalog["steps"]) == 8

    def test_ruang_kerja_web_tersaji(self, client):
        """Hasil build frontend ikut di-commit, sehingga aplikasi jalan tanpa Node."""
        import re

        response = client.get("/")
        assert response.status_code == 200
        assert "Recens" in response.text

        # Berkas aset yang dirujuk index.html harus benar-benar tersaji.
        assets = re.findall(r'(?:src|href)="(/static/assets/[^"]+)"', response.text)
        assert assets, "index.html tidak merujuk satu pun aset hasil build"
        for asset in assets:
            assert client.get(asset).status_code == 200, f"aset hilang: {asset}"

    def test_halaman_depan_dan_ruang_kerja_dilayani_berkas_yang_sama(self, client):
        """Pemilihan halaman terjadi di sisi klien, jadi keduanya berbagi index.html."""
        assert client.get("/app").text == client.get("/").text
        assert client.get("/app/menulis").status_code == 200

    def test_alamat_tak_dikenal_tetap_404(self, client):
        """Routing sisi klien tidak boleh menutupi alamat yang memang salah."""
        assert client.get("/entah-apa").status_code == 404


# --- pembantu ---------------------------------------------------------------


def _section_ids(client, project_id: int) -> dict[str, int]:
    manuscript = client.get(f"/api/projects/{project_id}/manuscript").json()
    ids: dict[str, int] = {}

    def walk(sections):
        for s in sections:
            ids[s["title"]] = s["id"]
            walk(s["children"])

    walk(manuscript["sections"])
    return ids


def _find_block(sections, section_id):
    for s in sections:
        if s["id"] == section_id and s["blocks"]:
            return s["blocks"][0]["id"]
        found = _find_block(s["children"], section_id)
        if found:
            return found
    return None


def _all_text(sections) -> str:
    parts = []
    for s in sections:
        parts.extend(b["content"] for b in s["blocks"])
        parts.append(_all_text(s["children"]))
    return " ".join(parts)
