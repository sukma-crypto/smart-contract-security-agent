"""Pemeriksaan naskah: bahasa, silang sitasi, konsistensi, kemiripan, batas panjang."""

from __future__ import annotations

import pytest

from recens.core.checks.consistency import align_items, check_consistency, extract_items
from recens.core.checks.language import check_text
from recens.core.checks.limits import check_length_limits, estimate_pages
from recens.core.guidelines import RuleSet, parse_guidelines
from recens.core.manuscript import load_manuscript


def rules_of(findings: list) -> set[str]:
    return {f.rule for f in findings}


class TestBahasaAkademik:
    def test_kata_tidak_baku_terdeteksi(self):
        findings = check_text("Analisa data memakai tehnik regresi dengan resiko kecil.")
        assert "kata_tidak_baku" in rules_of(findings)
        suggestions = " ".join(f.suggestion for f in findings)
        assert "analisis" in suggestions and "teknik" in suggestions and "risiko" in suggestions

    def test_ragam_percakapan_terdeteksi(self):
        findings = check_text("Datanya nggak lengkap dan hasilnya bagus banget.")
        assert "ragam_percakapan" in rules_of(findings)
        assert any(f.severity == "tinggi" for f in findings)

    def test_dimana_sebagai_penghubung(self):
        findings = check_text("Penelitian dilakukan di kantor dimana responden bekerja.")
        assert "kata_penghubung" in rules_of(findings)

    def test_awalan_di_yang_dipisah(self):
        findings = check_text("Data di analisis dan hasilnya di sajikan pada tabel.")
        assert "awalan_dipisah" in rules_of(findings)

    def test_kata_depan_di_yang_disatukan(self):
        findings = check_text("Penelitian dilaksanakan dikantor pusat dan disekolah.")
        assert "kata_depan" in rules_of(findings)

    def test_kata_depan_benar_tidak_ditandai(self):
        """Bentuk yang sudah benar tidak boleh ikut dilaporkan."""
        findings = check_text("Penelitian dilaksanakan di kantor pusat dan dianalisis dengan SPSS.")
        assert "kata_depan" not in rules_of(findings)
        assert "awalan_dipisah" not in rules_of(findings)

    def test_redundansi(self):
        findings = check_text("Motivasi adalah merupakan faktor yang sangat penting sekali.")
        assert "redundansi" in rules_of(findings)

    def test_kalimat_terlalu_panjang(self):
        panjang = "Motivasi kerja karyawan " + "yang sangat berpengaruh " * 12 + "terhadap kinerja."
        assert "kalimat_panjang" in rules_of(check_text(panjang))

    def test_kata_ganti_orang_pertama(self):
        assert "kata_ganti_orang" in rules_of(check_text("Saya melakukan penelitian ini."))
        assert "kata_ganti_orang" not in rules_of(
            check_text("Saya melakukan penelitian ini.", allow_first_person=True)
        )

    def test_konjungsi_di_awal_kalimat(self):
        findings = check_text("Data telah terkumpul. Sehingga analisis dapat dilakukan.")
        assert "konjungsi_awal" in rules_of(findings)

    def test_naskah_baku_bersih_dari_temuan_berat(self):
        teks = (
            "Penelitian ini menganalisis pengaruh motivasi kerja terhadap kinerja karyawan. "
            "Data dikumpulkan melalui kuesioner yang telah diuji validitas dan reliabilitasnya. "
            "Teknik analisis yang digunakan adalah regresi linear berganda."
        )
        findings = check_text(teks)
        assert not [f for f in findings if f.severity == "tinggi"]

    def test_temuan_memuat_kutipan_dan_usulan(self):
        finding = check_text("Analisa data dilakukan.")[0]
        assert finding.excerpt and finding.suggestion
        assert finding.offset >= 0


class TestKonsistensi:
    def test_butir_bernomor_terbaca(self):
        teks = "1. Bagaimana motivasi kerja?\n2. Apakah motivasi berpengaruh terhadap kinerja?"
        assert len(extract_items(teks)) == 2

    def test_paragraf_mengalir_tetap_terbaca(self):
        teks = (
            "Berdasarkan latar belakang, masalah dirumuskan sebagai berikut. "
            "Apakah motivasi kerja berpengaruh terhadap kinerja karyawan? "
            "Seberapa besar kontribusinya?"
        )
        assert len(extract_items(teks)) == 2

    def test_pasangan_ditemukan_lewat_irisan_kata_kunci(self):
        rumusan = ["Apakah motivasi kerja berpengaruh terhadap kinerja karyawan?"]
        tujuan = ["Untuk menganalisis pengaruh motivasi kerja terhadap kinerja karyawan."]
        pairs = align_items(rumusan, tujuan)
        assert pairs[0]["matched"] is True

    def test_butir_tanpa_pasangan_ditandai(self):
        rumusan = ["Apakah motivasi kerja berpengaruh terhadap kinerja karyawan?"]
        tujuan = ["Untuk mengetahui tingkat kepuasan pelanggan terhadap layanan purna jual."]
        assert align_items(rumusan, tujuan)[0]["matched"] is False

    def test_jumlah_rumusan_dan_tujuan_tidak_sama_terdeteksi(self, client, project, conn):
        pid = project["id"]
        sections = _section_ids(client, pid)
        _write(client, sections["Rumusan Masalah"],
               "1. Bagaimana motivasi kerja karyawan?\n2. Apakah motivasi berpengaruh pada kinerja?")
        _write(client, sections["Tujuan Penelitian"],
               "1. Untuk mengetahui motivasi kerja karyawan.")
        result = check_consistency(load_manuscript(conn, pid))
        assert any("tidak sama dengan jumlah tujuan" in i["message"] for i in result["issues"])

    def test_istilah_yang_dipakai_bergantian_terdeteksi(self, client, project, conn):
        pid = project["id"]
        sections = _section_ids(client, pid)
        _write(client, sections["Latar Belakang Masalah"],
               "Kinerja karyawan penting. Karyawan perlu motivasi. "
               "Pegawai yang termotivasi bekerja lebih baik. Pegawai juga lebih loyal.")
        result = check_consistency(load_manuscript(conn, pid))
        assert result["terms"]["inconsistent"]


class TestBatasPanjang:
    def test_perkiraan_halaman_ikut_berubah_saat_pedoman_berubah(self):
        padat = RuleSet(line_spacing=1.0)
        renggang = RuleSet(line_spacing=2.0)
        assert estimate_pages(5000, padat) < estimate_pages(5000, renggang)

    def test_margin_lebar_menambah_halaman(self):
        sempit = RuleSet()
        lebar = RuleSet()
        lebar.margins.left_cm = lebar.margins.right_cm = 6.0
        assert estimate_pages(5000, lebar) > estimate_pages(5000, sempit)

    def test_batas_kata_dilanggar_terdeteksi(self, client, project, conn):
        pid = project["id"]
        sections = _section_ids(client, pid)
        _write(client, sections["Latar Belakang Masalah"], "kata " * 500)
        rules = RuleSet(max_words=100)
        result = check_length_limits(load_manuscript(conn, pid), rules)
        assert result["passed"] is False
        assert any("melebihi batas" in i["message"] for i in result["issues"])


class TestPedoman:
    def test_aturan_umum_terbaca_dari_teks_pedoman(self):
        rules = parse_guidelines(
            "Naskah diketik pada kertas A4 dengan huruf Times New Roman ukuran 12 pt. "
            "Jarak antarbaris 2 spasi. Batas tepi atas 4 cm, tepi bawah 3 cm, "
            "tepi kiri 4 cm, dan tepi kanan 3 cm. Gaya sitasi mengikuti APA. "
            "Abstrak maksimal 250 kata. Naskah maksimal 80 halaman."
        )
        assert rules.font_family == "Times New Roman"
        assert rules.font_size_pt == 12
        assert rules.line_spacing == 2.0
        assert (rules.margins.top_cm, rules.margins.left_cm) == (4.0, 4.0)
        assert (rules.margins.bottom_cm, rules.margins.right_cm) == (3.0, 3.0)
        assert rules.citation_style == "apa"
        assert rules.abstract_max_words == 250
        assert rules.max_pages == 80

    def test_spasi_dalam_bentuk_kata(self):
        assert parse_guidelines("Naskah diketik dengan dua spasi.").line_spacing == 2.0
        assert parse_guidelines("Ditulis satu spasi.").line_spacing == 1.0

    def test_dkk_terbaca_sebagai_opsi_gaya(self):
        rules = parse_guidelines("Penulis lebih dari dua orang ditulis dkk. Gaya APA.")
        assert rules.citation_options["et_al_term"] == "dkk."

    def test_bab_wajib_terbaca(self):
        rules = parse_guidelines("BAB I PENDAHULUAN\nBAB II TINJAUAN PUSTAKA\nBAB III METODE")
        assert len(rules.required_sections) == 3
        assert rules.required_sections[0].startswith("BAB I")

    def test_aturan_yang_tidak_ditemukan_dicatat_sebagai_bawaan(self):
        """Yang tidak tertulis di pedoman tidak ditebak diam-diam."""
        rules = parse_guidelines("Dokumen ditulis dengan rapi.")
        assert "font_family" in rules.assumed
        assert "line_spacing" in rules.assumed

    def test_bukti_kalimat_asal_disertakan(self):
        rules = parse_guidelines("Naskah memakai huruf Arial ukuran 11 pt.")
        assert "Arial" in rules.evidence["font_family"]


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


def _write(client, section_id: int, content: str) -> None:
    client.post(f"/api/sections/{section_id}/blocks", json={"content": content})
