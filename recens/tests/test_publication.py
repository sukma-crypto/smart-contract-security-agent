"""Pelacak bimbingan, konversi naskah, jurnal tujuan, dan dua bahasa."""

from __future__ import annotations

import io
import zipfile

import pytest
from reportlab.pdfgen import canvas as rlcanvas

from recens.core import annotations, conversion, glossary, journals
from recens.core.manuscript import load_manuscript

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# --- pembantu berkas uji -----------------------------------------------------


def make_annotated_pdf(path, lines: list[str], notes: list[tuple[int, str]]):
    """PDF berisi teks nyata, disorot pada baris tertentu seperti coretan dosen."""
    from pypdf import PdfWriter
    from pypdf.annotations import Highlight, Text
    from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject

    buffer = io.BytesIO()
    pdf = rlcanvas.Canvas(buffer)
    pdf.setFont("Times-Roman", 12)
    for index, line in enumerate(lines):
        pdf.drawString(72, 760 - index * 20, line)
    pdf.save()
    buffer.seek(0)

    writer = PdfWriter(clone_from=buffer)
    for line_index, note in notes:
        top = 772 - line_index * 20
        quads = ArrayObject(
            [FloatObject(v) for v in [72, top, 520, top, 72, top - 17, 520, top - 17]]
        )
        highlight = Highlight(
            rect=(72, top - 17, 520, top), quad_points=quads, highlight_color="ffff00"
        )
        highlight[NameObject("/Contents")] = TextStringObject(note)
        writer.add_annotation(page_number=0, annotation=highlight)
    with open(path, "wb") as handle:
        writer.write(handle)
    return path


def make_docx_with_comments(path, body: str, comments: list[tuple[str, str]]):
    """Dokumen Word minimal berisi komentar pada rentang teks."""
    document = (
        f'<?xml version="1.0"?><w:document xmlns:w="{W_NS}"><w:body><w:p>'
        + "".join(
            f'<w:commentRangeStart w:id="{i}"/><w:r><w:t>{anchor}</w:t></w:r>'
            f'<w:commentRangeEnd w:id="{i}"/>'
            for i, (anchor, _text) in enumerate(comments)
        )
        + f"<w:r><w:t>{body}</w:t></w:r></w:p></w:body></w:document>"
    )
    comments_xml = (
        f'<?xml version="1.0"?><w:comments xmlns:w="{W_NS}">'
        + "".join(
            f'<w:comment w:id="{i}" w:author="Dr. Andi"><w:p><w:r><w:t>{text}</w:t>'
            f"</w:r></w:p></w:comment>"
            for i, (_anchor, text) in enumerate(comments)
        )
        + "</w:comments>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/comments.xml", comments_xml)
    return path


def write_sections(client, project_id: int, content: dict[str, str]) -> dict[str, int]:
    manuscript = client.get(f"/api/projects/{project_id}/manuscript").json()
    ids: dict[str, int] = {}

    def walk(sections):
        for s in sections:
            ids[s["title"]] = s["id"]
            walk(s["children"])

    walk(manuscript["sections"])
    for title, text in content.items():
        client.post(f"/api/sections/{ids[title]}/blocks", json={"content": text})
    return ids


NASKAH = {
    "Latar Belakang Masalah": "Kinerja karyawan merupakan faktor penting dalam organisasi.",
    "Rumusan Masalah": "1. Apakah motivasi kerja berpengaruh terhadap kinerja karyawan?",
    "Tujuan Penelitian": "1. Untuk menganalisis pengaruh motivasi kerja terhadap kinerja.",
    "Manfaat Penelitian": "Penelitian ini bermanfaat bagi perusahaan dan akademisi.",
    "Landasan Teori": "Teori motivasi Herzberg menjelaskan faktor higiene dan motivator.",
    "Jenis dan Pendekatan Penelitian": "Penelitian ini memakai pendekatan kuantitatif.",
    "Populasi dan Sampel": "Populasi 250 karyawan dengan sampel 154 responden.",
    "Hasil Penelitian": "Koefisien determinasi yang diperoleh sebesar 0,816.",
    "Pembahasan": "Temuan ini sejalan dengan teori Herzberg mengenai motivator.",
    "Simpulan": "1. Motivasi kerja berpengaruh signifikan terhadap kinerja karyawan.",
}


# --- Pelacak bimbingan -------------------------------------------------------


class TestImporKomentar:
    def test_anotasi_pdf_terbaca(self, tmp_path):
        path = make_annotated_pdf(
            tmp_path / "catatan.pdf",
            ["Kinerja karyawan merupakan faktor penting dalam organisasi."],
            [(0, "Kalimat ini terlalu umum, beri data pendukung.")],
        )
        result = annotations.extract_pdf_comments(path)
        assert len(result.comments) == 1
        assert result.comments[0].text.startswith("Kalimat ini terlalu umum")

    def test_teks_yang_disorot_ikut_terbaca(self, tmp_path):
        """Jangkar sorotan adalah dasar penautan yang paling dapat dipercaya."""
        path = make_annotated_pdf(
            tmp_path / "catatan.pdf",
            ["Kinerja karyawan merupakan faktor penting dalam organisasi."],
            [(0, "Beri data pendukung.")],
        )
        comment = annotations.extract_pdf_comments(path).comments[0]
        assert "Kinerja karyawan" in comment.anchor

    def test_komentar_tertaut_ke_bagian_yang_benar(self, client, project, conn, tmp_path):
        write_sections(client, project["id"], NASKAH)
        path = make_annotated_pdf(
            tmp_path / "catatan.pdf",
            [
                "Kinerja karyawan merupakan faktor penting dalam organisasi.",
                "Teori motivasi Herzberg menjelaskan faktor higiene dan motivator.",
            ],
            [(0, "Beri data pendukung."), (1, "Tambahkan sitasi primer Herzberg.")],
        )
        manuscript = load_manuscript(conn, project["id"])
        result = annotations.import_comments(path, manuscript)

        by_note = {c.text: c.section_title for c in result.comments}
        assert by_note["Beri data pendukung."] == "Latar Belakang Masalah"
        assert by_note["Tambahkan sitasi primer Herzberg."] == "Landasan Teori"

    def test_komentar_tanpa_jangkar_meyakinkan_tidak_ditempelkan_sembarangan(
        self, client, project, conn
    ):
        """Menempelkan ke bagian keliru lebih menyesatkan daripada membiarkan kosong."""
        write_sections(client, project["id"], NASKAH)
        manuscript = load_manuscript(conn, project["id"])
        comment = annotations.Comment(text="Perbaiki penulisan daftar pustaka.")
        annotations.link_to_manuscript([comment], manuscript)
        assert comment.section_id is None

    def test_komentar_docx_terbaca_beserta_penulisnya(self, tmp_path):
        path = make_docx_with_comments(
            tmp_path / "naskah.docx",
            "Sisa naskah.",
            [("Kinerja karyawan merupakan faktor penting", "Perjelas indikatornya.")],
        )
        result = annotations.extract_docx_comments(path)
        assert len(result.comments) == 1
        assert result.comments[0].author == "Dr. Andi"
        assert "Kinerja karyawan" in result.comments[0].anchor

    def test_foto_tulisan_tangan_ditolak_dengan_terus_terang(self, tmp_path):
        photo = tmp_path / "coretan.jpg"
        photo.write_bytes(b"bukan gambar sungguhan")
        with pytest.raises(annotations.UnsupportedAnnotationSource, match="OCR"):
            annotations.import_comments(photo)

    def test_impor_lewat_api_menjadi_daftar_revisi(self, client, project, tmp_path):
        write_sections(client, project["id"], NASKAH)
        path = make_annotated_pdf(
            tmp_path / "catatan.pdf",
            ["Kinerja karyawan merupakan faktor penting dalam organisasi."],
            [(0, "Beri data pendukung.")],
        )
        with open(path, "rb") as handle:
            response = client.post(
                f"/api/projects/{project['id']}/revisions/import",
                files={"file": ("catatan.pdf", handle, "application/pdf")},
                data={"source": "pembimbing"},
            )
        assert response.status_code == 201
        payload = response.json()
        assert payload["created"] == 1
        assert payload["linked"] == 1

        revisions = client.get(f"/api/projects/{project['id']}/revisions").json()
        assert revisions["total"] == 1
        assert revisions["revisions"][0]["section_title"] == "Latar Belakang Masalah"

    def test_dry_run_tidak_menyimpan_apa_pun(self, client, project, tmp_path):
        write_sections(client, project["id"], NASKAH)
        path = make_annotated_pdf(
            tmp_path / "catatan.pdf", ["Kinerja karyawan penting."], [(0, "Perjelas.")]
        )
        with open(path, "rb") as handle:
            payload = client.post(
                f"/api/projects/{project['id']}/revisions/import",
                files={"file": ("catatan.pdf", handle, "application/pdf")},
                data={"dry_run": "true"},
            ).json()
        assert payload["count"] == 1
        assert payload["created"] == 0
        assert client.get(f"/api/projects/{project['id']}/revisions").json()["total"] == 0


# --- Konversi naskah ---------------------------------------------------------


class TestKonversiNaskah:
    def test_bab_dipetakan_ke_struktur_imrad(self, client, project, conn):
        write_sections(client, project["id"], NASKAH)
        plan = conversion.plan_conversion(load_manuscript(conn, project["id"]), 6000)
        by_target = {s.target: s for s in plan.sections}

        assert [x["title"] for x in by_target["Metode"].sources] == [
            "Jenis dan Pendekatan Penelitian",
            "Populasi dan Sampel",
        ]
        assert by_target["Hasil"].sources[0]["title"] == "Hasil Penelitian"
        assert by_target["Simpulan"].sources[0]["title"] == "Simpulan"
        assert any(s["title"] == "Latar Belakang Masalah" for s in by_target["Pendahuluan"].sources)

    def test_manfaat_penelitian_tidak_dibawa(self, client, project, conn):
        write_sections(client, project["id"], NASKAH)
        plan = conversion.plan_conversion(load_manuscript(conn, project["id"]), 6000)
        assert "Manfaat Penelitian" in [d["title"] for d in plan.dropped]

    def test_anggaran_kata_terbagi_habis(self, client, project, conn):
        write_sections(client, project["id"], NASKAH)
        plan = conversion.plan_conversion(load_manuscript(conn, project["id"]), 6000)
        assert sum(s.target_words for s in plan.sections) == pytest.approx(6000, abs=10)

    def test_naskah_lebih_pendek_dari_target_diperingatkan(self, client, project, conn):
        write_sections(client, project["id"], NASKAH)
        plan = conversion.plan_conversion(load_manuscript(conn, project["id"]), 6000)
        assert any("lebih pendek" in w for w in plan.warnings)

    def test_bab_hasil_dan_pembahasan_gabungan_diingatkan(self, client, project, conn):
        """Banyak pedoman menggabungkannya; IMRAD memisahkan keduanya."""
        ids = write_sections(client, project["id"], {})
        client.post(
            f"/api/sections/{ids['BAB IV HASIL DAN PEMBAHASAN']}/blocks",
            json={"content": "kata " * 100},
        )
        plan = conversion.plan_conversion(load_manuscript(conn, project["id"]), 6000)
        assert any("menggabungkan hasil dan pembahasan" in w for w in plan.warnings)
        hasil = next(s for s in plan.sections if s.target == "Hasil")
        assert hasil.sources[0]["combined"] is True

    def test_pemadatan_berat_diperingatkan(self, client, project, conn):
        write_sections(client, project["id"], {k: "kata " * 400 for k in NASKAH})
        plan = conversion.plan_conversion(load_manuscript(conn, project["id"]), 1000)
        assert any("Pemadatan sebesar ini" in w for w in plan.warnings)

    def test_proyek_artikel_dibangun_dengan_bahan_dan_pustaka(self, client, project, conn):
        from recens.core.citations import library as reflib

        from .conftest import CROSSREF_ENTRY

        write_sections(client, project["id"], NASKAH)
        reflib.add_reference(conn, project["id"], CROSSREF_ENTRY, source_db="crossref")

        result = client.post(
            f"/api/projects/{project['id']}/conversion/apply", json={"target_words": 6000}
        ).json()
        assert result["references_copied"] == 1

        article = client.get(f"/api/projects/{result['project_id']}/manuscript").json()
        assert [s["title"] for s in article["sections"]] == [
            "Abstrak", "Pendahuluan", "Metode", "Hasil", "Pembahasan", "Simpulan",
        ]
        metode = next(s for s in article["sections"] if s["title"] == "Metode")
        assert metode["blocks"]
        assert metode["blocks"][0]["meta"]["perlu_dipadatkan"] is True
        assert metode["blocks"][0]["meta"]["asal_bagian"]

    def test_naskah_asli_tidak_diubah(self, client, project):
        write_sections(client, project["id"], NASKAH)
        before = client.get(f"/api/projects/{project['id']}/manuscript").json()
        client.post(
            f"/api/projects/{project['id']}/conversion/apply", json={"target_words": 6000}
        )
        after = client.get(f"/api/projects/{project['id']}/manuscript").json()
        assert before["word_count"] == after["word_count"]

    def test_artikel_tidak_bisa_dikonversi_lagi(self, client):
        article = client.post(
            "/api/projects", json={"name": "Artikel", "work_type": "artikel_jurnal"}
        ).json()
        response = client.post(
            f"/api/projects/{article['id']}/conversion/plan", json={"target_words": 6000}
        )
        assert response.status_code == 400

    def test_naskah_kosong_ditolak(self, client, project):
        response = client.post(
            f"/api/projects/{project['id']}/conversion/plan", json={"target_words": 6000}
        )
        assert response.status_code == 400


# --- Template jurnal ---------------------------------------------------------


class TestJurnalTujuan:
    def test_struktur_indonesia_memenuhi_profil_indonesia(self, client, conn):
        article = client.post(
            "/api/projects", json={"name": "Artikel", "work_type": "artikel_jurnal"}
        ).json()
        manuscript = load_manuscript(conn, article["id"])
        report = journals.check_readiness(manuscript, journals.get_profile("sinta_umum"))
        assert not report.missing_sections

    def test_hasil_dan_pembahasan_terpisah_tetap_memenuhi(self, client, conn):
        """Jurnal menulis 'Hasil dan Pembahasan'; naskah IMRAD memisahkannya."""
        article = client.post(
            "/api/projects", json={"name": "Artikel", "work_type": "artikel_jurnal"}
        ).json()
        manuscript = load_manuscript(conn, article["id"])
        report = journals.check_readiness(manuscript, journals.get_profile("sinta_umum"))
        assert "Hasil dan Pembahasan" in report.matched_sections

    def test_bagian_wajib_yang_hilang_terdeteksi(self, client, conn):
        makalah = client.post(
            "/api/projects", json={"name": "Makalah", "work_type": "makalah"}
        ).json()
        manuscript = load_manuscript(conn, makalah["id"])
        report = journals.check_readiness(manuscript, journals.get_profile("internasional_imrad"))
        assert "Methods" in report.missing_sections
        assert report.ready is False

    def test_batas_kata_dilanggar_terdeteksi(self, client, conn):
        article = client.post(
            "/api/projects", json={"name": "Artikel", "work_type": "prosiding"}
        ).json()
        write_sections(client, article["id"], {"Hasil": "kata " * 6000})
        manuscript = load_manuscript(conn, article["id"])
        report = journals.check_readiness(manuscript, journals.get_profile("konferensi_ieee"))
        assert any("melebihi batas" in i["message"] for i in report.issues)
        assert report.ready is False

    def test_profil_jadi_aturan_yang_mengikat(self, client):
        article = client.post(
            "/api/projects", json={"name": "Paper", "work_type": "prosiding"}
        ).json()
        result = client.post(
            f"/api/projects/{article['id']}/journal/apply", json={"profile": "konferensi_ieee"}
        ).json()
        assert result["rules"]["citation_style"] == "ieee"
        assert result["rules"]["font_size_pt"] == 10.0
        assert result["rules"]["include_toc"] is False

        # Aturan itu benar-benar dipakai saat merakit dokumen.
        export = client.post(
            f"/api/projects/{article['id']}/export", json={"format": "docx"}
        ).json()
        assert "IEEE" in export["applied_rules"]["citation_style"]

    def test_profil_tak_dikenal_ditolak_dengan_pilihan(self, client):
        article = client.post(
            "/api/projects", json={"name": "A", "work_type": "artikel_jurnal"}
        ).json()
        response = client.post(
            f"/api/projects/{article['id']}/journal/readiness", json={"profile": "entah"}
        )
        assert response.status_code == 404
        assert "sinta_umum" in response.json()["detail"]


# --- Dua bahasa --------------------------------------------------------------


class TestDuaBahasa:
    def test_istilah_panjang_dikenali_utuh(self):
        """'uji validitas' satu istilah, bukan 'uji' ditambah 'validitas'."""
        terms = dict(
            glossary.find_terms("Dilakukan uji validitas instrumen.", glossary.build_glossary())
        )
        assert terms["uji validitas"] == "validity test"
        assert "validitas" not in terms

    def test_glosarium_bidang_ditambahkan(self):
        umum = glossary.build_glossary()
        manajemen = glossary.build_glossary("Manajemen")
        assert "kinerja karyawan" not in umum
        assert manajemen["kinerja karyawan"] == "employee performance"

    def test_terjemahan_konsisten_lolos(self):
        result = glossary.check_translation(
            "Penelitian ini menguji pengaruh motivasi kerja terhadap kinerja karyawan "
            "menggunakan uji validitas dan uji reliabilitas.",
            "This study examines the effect of work motivation on employee performance "
            "using validity test and reliability test.",
            field_of_study="Manajemen",
        )
        assert result["passed"] is True
        assert result["terms_detected"] >= 4

    def test_istilah_meleset_ditandai(self):
        result = glossary.check_translation(
            "Penelitian ini memakai uji reliabilitas.",
            "This research uses dependability checking.",
        )
        assert result["passed"] is False
        assert any(i["term_id"] == "uji reliabilitas" for i in result["issues"])

    def test_glosarium_lewat_api(self, client, project):
        result = client.post(
            f"/api/projects/{project['id']}/terminology",
            json={
                "indonesian": "Penelitian ini memakai uji validitas.",
                "english": "This study uses validity test.",
            },
        ).json()
        assert result["passed"] is True

    def test_arah_terjemahan_tidak_dikenal_ditolak(self, client, project):
        response = client.post(
            f"/api/projects/{project['id']}/translate",
            json={"text": "Uji validitas.", "direction": "id-jp"},
        )
        assert response.status_code == 400

    def test_tanpa_model_glosarium_tetap_diberikan(self, client, project):
        """Tanpa kunci API, padanan istilah tetap bisa dipastikan."""
        result = client.post(
            f"/api/projects/{project['id']}/translate",
            json={"text": "Penelitian ini memakai uji validitas dan uji reliabilitas."},
        ).json()
        assert result["source"] == "deterministik"
        assert "validity test" in result["meta"]["glossary"]
