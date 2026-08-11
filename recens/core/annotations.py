"""Pelacak Bimbingan: mengubah coretan dosen menjadi daftar revisi berstatus.

Catatan pembimbing datang dalam bentuk yang berantakan — komentar PDF, dokumen
Word bertanda, atau foto tulisan tangan — lalu tersebar di pesan, coretan, dan
berkas berbeda. Akibatnya revisi terlewat dan hal yang sama dibahas berulang
kali (Bagian 4.6).

Modul ini membaca berkas bertanda menjadi daftar komentar, lalu menautkan tiap
komentar ke bagian naskah yang paling mungkin dimaksudkan. Penautan dilakukan
lewat teks yang benar-benar disorot pembimbing, bukan tebakan: bila komentar
menyorot sepotong kalimat, potongan itu dicari di naskah.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from .manuscript import Manuscript, strip_markers
from .retrieval import tokenize

#: Anotasi PDF yang membawa komentar pembaca.
COMMENT_SUBTYPES = {
    "/Text": "catatan",
    "/FreeText": "catatan",
    "/Highlight": "sorotan",
    "/Underline": "garis bawah",
    "/StrikeOut": "coretan",
    "/Squiggly": "garis berombak",
    "/Popup": "catatan",
    "/Caret": "sisipan",
}

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@dataclass
class Comment:
    """Satu coretan pembimbing beserta konteks tempatnya ditulis."""

    text: str
    kind: str = "catatan"
    page: int | None = None
    author: str | None = None
    #: Teks naskah yang disorot pembimbing, bila ada.
    anchor: str = ""
    section_id: int | None = None
    section_title: str = ""
    block_id: int | None = None
    match_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "kind": self.kind,
            "page": self.page,
            "author": self.author,
            "anchor": self.anchor,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "block_id": self.block_id,
            "match_score": round(self.match_score, 3),
        }


@dataclass
class ImportResult:
    comments: list[Comment] = field(default_factory=list)
    #: Hal yang perlu diketahui pengguna, mis. halaman tanpa lapisan teks.
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        linked = sum(1 for c in self.comments if c.section_id is not None)
        return {
            "count": len(self.comments),
            "linked": linked,
            "unlinked": len(self.comments) - linked,
            "comments": [c.to_dict() for c in self.comments],
            "notes": self.notes,
        }


class UnsupportedAnnotationSource(ValueError):
    pass


# --- PDF ---------------------------------------------------------------------


def extract_pdf_comments(path: Path | str) -> ImportResult:
    """Ambil komentar dari PDF yang sudah dianotasi pembimbing."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    result = ImportResult()
    pages_with_text = 0

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            pages_with_text += 1

        for reference in page.get("/Annots") or []:
            try:
                annotation = reference.get_object()
            except Exception:  # pragma: no cover - anotasi rusak
                continue

            subtype = str(annotation.get("/Subtype", ""))
            if subtype not in COMMENT_SUBTYPES:
                continue

            contents = _clean(annotation.get("/Contents"))
            anchor = _highlighted_text(annotation, page, page_text)
            if not contents and not anchor:
                continue

            # Sorotan tanpa catatan tetap bermakna: pembimbing menandai sesuatu.
            text = contents or f"Bagian ini ditandai ({COMMENT_SUBTYPES[subtype]})."
            result.comments.append(
                Comment(
                    text=text,
                    kind=COMMENT_SUBTYPES[subtype],
                    page=page_number,
                    author=_clean(annotation.get("/T")) or None,
                    anchor=anchor,
                )
            )

    if not pages_with_text and len(reader.pages):
        result.notes.append(
            "PDF ini tidak memuat lapisan teks — kemungkinan hasil pindaian. Komentar "
            "tetap terbaca, tetapi penautan ke bagian naskah tidak dapat dilakukan "
            "tanpa OCR."
        )
    if not result.comments:
        result.notes.append(
            "Tidak ditemukan anotasi pada berkas ini. Pastikan pembimbing memakai fitur "
            "komentar atau sorotan, bukan mencoret di atas hasil cetak."
        )
    return result


def _clean(value) -> str:
    if value is None:
        return ""
    text = str(value)
    return re.sub(r"\s+", " ", text).strip()


def _highlighted_text(annotation, page, page_text: str) -> str:
    """Ambil teks yang disorot, dari QuadPoints bila tersedia.

    Teks inilah jangkar yang paling dapat dipercaya untuk menautkan komentar ke
    lokasinya di naskah, karena ia benar-benar berasal dari halaman itu.
    """
    quad_points = annotation.get("/QuadPoints")
    if not quad_points:
        return ""
    try:
        numbers = [float(v) for v in quad_points]
    except (TypeError, ValueError):
        return ""
    if len(numbers) < 8:
        return ""

    # QuadPoints tersusun per empat titik (x1,y1 … x4,y4) tiap baris sorotan.
    xs = numbers[0::2]
    ys = numbers[1::2]
    box = (min(xs), min(ys), max(xs), max(ys))

    captured: list[str] = []

    def visitor(text, _cm, tm, _font_dict, _font_size):
        if not text.strip():
            return
        x, y = tm[4], tm[5]
        if box[0] - 2 <= x <= box[2] + 2 and box[1] - 2 <= y <= box[3] + 2:
            captured.append(text)

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:  # pragma: no cover - bergantung struktur PDF
        return ""
    return re.sub(r"\s+", " ", "".join(captured)).strip()


# --- DOCX --------------------------------------------------------------------


def extract_docx_comments(path: Path | str) -> ImportResult:
    """Ambil komentar dari dokumen Word bertanda.

    python-docx belum membuka bagian komentar, sehingga ``word/comments.xml``
    dibaca langsung dari arsip .docx.
    """
    result = ImportResult()
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        if "word/comments.xml" not in names:
            result.notes.append(
                "Dokumen ini tidak memuat komentar. Bila pembimbing memakai Track "
                "Changes, terima atau tolak perubahannya lebih dahulu, lalu impor "
                "komentarnya."
            )
            return result
        comments_xml = archive.read("word/comments.xml")
        document_xml = archive.read("word/document.xml") if "word/document.xml" in names else b""

    anchors = _docx_comment_anchors(document_xml)
    root = ElementTree.fromstring(comments_xml)
    for element in root.findall(f"{{{W_NS}}}comment"):
        comment_id = element.get(f"{{{W_NS}}}id")
        author = element.get(f"{{{W_NS}}}author")
        text = " ".join(
            node.text or "" for node in element.iter(f"{{{W_NS}}}t")
        ).strip()
        if not text:
            continue
        result.comments.append(
            Comment(
                text=re.sub(r"\s+", " ", text),
                kind="catatan",
                author=author,
                anchor=anchors.get(comment_id, ""),
            )
        )
    return result


def _docx_comment_anchors(document_xml: bytes) -> dict[str, str]:
    """Petakan id komentar ke teks yang dirujuknya di dalam dokumen."""
    if not document_xml:
        return {}
    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:  # pragma: no cover
        return {}

    anchors: dict[str, list[str]] = {}
    active: set[str] = set()
    for node in root.iter():
        tag = node.tag
        if tag == f"{{{W_NS}}}commentRangeStart":
            active.add(node.get(f"{{{W_NS}}}id"))
        elif tag == f"{{{W_NS}}}commentRangeEnd":
            active.discard(node.get(f"{{{W_NS}}}id"))
        elif tag == f"{{{W_NS}}}t" and active and node.text:
            for comment_id in active:
                anchors.setdefault(comment_id, []).append(node.text)
    return {k: re.sub(r"\s+", " ", "".join(v)).strip() for k, v in anchors.items()}


# --- Penautan ke naskah ------------------------------------------------------


def link_to_manuscript(
    comments: list[Comment], manuscript: Manuscript, threshold: float = 0.3
) -> list[Comment]:
    """Tautkan tiap komentar ke bagian naskah yang paling mungkin dimaksud.

    Jangkar sorotan dipakai lebih dahulu karena ia potongan naskah yang
    sesungguhnya. Bila tidak ada, isi komentar dicocokkan dengan kata kunci tiap
    blok — dan bila tetap tidak meyakinkan, komentar dibiarkan tanpa tautan
    alih-alih ditempelkan ke bagian yang keliru.
    """
    blocks = [
        (section, block, strip_markers(block.content))
        for section, block in manuscript.all_blocks()
        if block.kind not in ("table", "figure")
    ]
    if not blocks:
        return comments

    for comment in comments:
        best, best_score = None, 0.0

        if comment.anchor:
            needle = _normalize(comment.anchor)
            for section, block, text in blocks:
                haystack = _normalize(text)
                if needle and needle in haystack:
                    best, best_score = (section, block), 1.0
                    break

        if best is None:
            query = set(tokenize(f"{comment.anchor} {comment.text}"))
            if query:
                for section, block, text in blocks:
                    candidate = set(tokenize(text))
                    if not candidate:
                        continue
                    score = len(query & candidate) / len(query)
                    if score > best_score:
                        best, best_score = (section, block), score

        if best is not None and best_score >= threshold:
            section, block = best
            comment.section_id = section.id
            comment.section_title = section.title
            comment.block_id = block.id
            comment.match_score = best_score

    return comments


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def import_comments(path: Path | str, manuscript: Manuscript | None = None) -> ImportResult:
    """Baca berkas bertanda apa pun bentuknya, lalu tautkan ke naskah."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        result = extract_pdf_comments(path)
    elif suffix == ".docx":
        result = extract_docx_comments(path)
    elif suffix in (".png", ".jpg", ".jpeg", ".webp", ".heic"):
        raise UnsupportedAnnotationSource(
            "Foto tulisan tangan memerlukan OCR, yang belum tersambung pada pemasangan "
            "ini. Ketik ulang catatannya sebagai revisi manual agar tetap terlacak, atau "
            "minta pembimbing memakai komentar PDF."
        )
    else:
        raise UnsupportedAnnotationSource(
            f"Format '{suffix}' belum didukung. Impor komentar menerima berkas .pdf "
            f"(anotasi) dan .docx (komentar Word)."
        )

    if manuscript is not None:
        link_to_manuscript(result.comments, manuscript)
        unlinked = sum(1 for c in result.comments if c.section_id is None)
        if unlinked:
            result.notes.append(
                f"{unlinked} komentar tidak dapat ditautkan ke bagian tertentu dan "
                f"dicatat tanpa lokasi. Menempelkannya ke bagian yang keliru lebih "
                f"menyesatkan daripada membiarkannya kosong."
            )
    return result
