"""Sitasi: perenderan gaya, verifikasi sumber, dan kesinkronan dengan daftar pustaka."""

from __future__ import annotations

import pytest

from recens.core.citations import library as reflib
from recens.core.citations.styles import build_index_map, get_style, render_bibliography
from recens.core.manuscript import make_citation_marker
from recens.core.render import render_citations

from .conftest import CROSSREF_ENTRY

BUKU = {
    "id": "arikunto2019",
    "type": "book",
    "title": "Prosedur Penelitian: Suatu Pendekatan Praktik",
    "author": [{"family": "Arikunto", "given": "Suharsimi"}],
    "issued": {"date-parts": [[2019]]},
    "publisher": "Rineka Cipta",
}

TIGA_PENULIS = {
    "id": "ghozali2020",
    "type": "article-journal",
    "title": "Aplikasi Analisis Multivariate",
    "author": [
        {"family": "Ghozali", "given": "Imam"},
        {"family": "Latan", "given": "Hengky"},
        {"family": "Setiawan", "given": "Budi"},
    ],
    "issued": {"date-parts": [[2020]]},
    "container-title": "Jurnal Ekonomi",
    "volume": "8",
    "issue": "1",
    "page": "12-25",
    "DOI": "10.5555/je.2020.8",
}


class TestGayaSitasi:
    def test_apa_dalam_teks_dan_daftar_pustaka(self):
        style = get_style("apa")
        entry = {**CROSSREF_ENTRY, "id": "sugiyono2021"}
        assert style.in_text(entry) == "(Sugiyono & Hasibuan, 2021)"
        biblio = style.bibliography(entry)
        assert biblio.startswith("Sugiyono, B., & Hasibuan, M. (2021).")
        assert "Jurnal Manajemen Indonesia, 12(2), 101-115." in biblio
        assert "https://doi.org/10.1234/jmi.2021.12" in biblio

    def test_apa_tiga_penulis_memakai_et_al(self):
        assert get_style("apa").in_text(TIGA_PENULIS) == "(Ghozali et al., 2020)"

    def test_gaya_kampus_memakai_dkk(self):
        style = get_style("kampus", {"citation_options": {"et_al_term": "dkk."}})
        assert style.in_text(TIGA_PENULIS) == "(Ghozali dkk., 2020)"

    def test_ieee_bernomor(self):
        style = get_style("ieee")
        assert style.in_text(TIGA_PENULIS, index=3) == "[3]"
        biblio = style.bibliography(TIGA_PENULIS, index=3)
        assert biblio.startswith('[3] I. Ghozali, H. Latan, and B. Setiawan, "Aplikasi')
        assert "vol. 8," in biblio and "pp. 12-25," in biblio

    def test_vancouver(self):
        biblio = get_style("vancouver").bibliography(TIGA_PENULIS, index=1)
        assert biblio.startswith("1. Ghozali I, Latan H, Setiawan B.")
        assert "2020;8(1):12-25." in biblio

    def test_harvard(self):
        assert get_style("harvard").in_text(BUKU) == "(Arikunto 2019)"

    def test_locator_ikut_dirender(self):
        entry = {**CROSSREF_ENTRY, "id": "s2021"}
        assert get_style("apa").in_text(entry, locator="hlm. 104") == (
            "(Sugiyono & Hasibuan, 2021, hlm. 104)"
        )

    def test_gaya_tidak_dikenal_jatuh_ke_apa(self):
        assert get_style("gaya-antah-berantah").key == "apa"


class TestUrutanDaftarPustaka:
    def test_gaya_penulis_tahun_urut_abjad(self):
        style = get_style("apa")
        entries = [TIGA_PENULIS, BUKU]
        result = render_bibliography(style, entries, order=["ghozali2020", "arikunto2019"])
        assert [r["citekey"] for r in result] == ["arikunto2019", "ghozali2020"]

    def test_gaya_numerik_urut_kemunculan(self):
        style = get_style("ieee")
        entries = [TIGA_PENULIS, BUKU]
        order = ["ghozali2020", "arikunto2019"]
        result = render_bibliography(style, entries, order=order)
        assert [r["citekey"] for r in result] == order
        assert build_index_map(style, order) == {"ghozali2020": 1, "arikunto2019": 2}


class TestVerifikasiSumber:
    def test_sumber_resmi_otomatis_terverifikasi(self, conn, client):
        project = client.post(
            "/api/projects", json={"name": "P", "work_type": "makalah"}
        ).json()
        reference = reflib.add_reference(
            conn, project["id"], CROSSREF_ENTRY, source_db="crossref", external_id="10.1234/x"
        )
        assert reference["verified"] == 1
        assert reference["citekey"] == "sugiyono2021"

    def test_unggahan_mandiri_tidak_pernah_terverifikasi(self, conn, client):
        """Tidak ada jalur kode yang bisa menandai metadata tak tertelusur sebagai sah."""
        project = client.post(
            "/api/projects", json={"name": "P", "work_type": "makalah"}
        ).json()
        reference = reflib.add_reference(
            conn, project["id"], CROSSREF_ENTRY, source_db="unggahan"
        )
        assert reference["verified"] == 0

    def test_citekey_bentrok_diberi_pembeda(self, conn, client):
        project = client.post(
            "/api/projects", json={"name": "P", "work_type": "makalah"}
        ).json()
        first = reflib.add_reference(conn, project["id"], CROSSREF_ENTRY, source_db="crossref")
        second = reflib.add_reference(conn, project["id"], CROSSREF_ENTRY, source_db="crossref")
        assert first["citekey"] == "sugiyono2021"
        assert second["citekey"] == "sugiyono2021a"


class TestPerenderanDalamNaskah:
    def test_penanda_diganti_sesuai_gaya(self):
        entries = {"ghozali2020": TIGA_PENULIS}
        teks = f"Analisis multivariat {make_citation_marker('ghozali2020')} banyak dipakai."
        assert render_citations(teks, entries, get_style("apa")) == (
            "Analisis multivariat (Ghozali et al., 2020) banyak dipakai."
        )
        assert render_citations(teks, entries, get_style("ieee"), {"ghozali2020": 2}) == (
            "Analisis multivariat [2] banyak dipakai."
        )

    def test_sitasi_tak_dikenal_ditandai_mencolok_bukan_dihapus(self):
        """Sitasi hilang diam-diam lebih berbahaya daripada sitasi yang salah."""
        teks = "Pernyataan ini [[cite:tidakada2020]] perlu sumber."
        hasil = render_citations(teks, {}, get_style("apa"))
        assert "[SITASI TIDAK DITEMUKAN: tidakada2020]" in hasil


class TestDaftarPustakaSinkron:
    def test_hanya_memuat_sumber_yang_dikutip(self, conn, client):
        project = client.post("/api/projects", json={"name": "P", "work_type": "makalah"}).json()
        pid = project["id"]
        reflib.add_reference(conn, pid, CROSSREF_ENTRY, source_db="crossref")
        reflib.add_reference(conn, pid, BUKU, source_db="crossref")

        result = reflib.build_bibliography(conn, pid, "apa", order=["sugiyono2021"])
        assert [e["citekey"] for e in result["entries"]] == ["sugiyono2021"]
        assert result["uncited"] == ["arikunto2019"]

    def test_dapat_memuat_seluruh_pustaka_bila_diminta(self, conn, client):
        project = client.post("/api/projects", json={"name": "P", "work_type": "makalah"}).json()
        pid = project["id"]
        reflib.add_reference(conn, pid, CROSSREF_ENTRY, source_db="crossref")
        reflib.add_reference(conn, pid, BUKU, source_db="crossref")
        result = reflib.build_bibliography(conn, pid, "apa", order=[], only_cited=False)
        assert len(result["entries"]) == 2
