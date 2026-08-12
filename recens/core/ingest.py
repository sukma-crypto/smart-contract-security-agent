"""Impor naskah yang sudah jadi dari berkas Word.

Sebagian besar orang tidak datang ke Recens dengan tangan kosong. Yang sudah
mengerjakan BAB I sampai III berbulan-bulan lalu mentok di BAB IV tidak boleh
diminta mengetik ulang tiga bab hanya untuk bisa memakai satu fitur. Modul ini
membaca naskahnya kembali menjadi bagian-bagian bernaskah.

Kesulitan sesungguhnya bukan membaca berkasnya, melainkan mengenali mana yang
judul bab. Pedoman kampus menyuruh mahasiswa menulis "BAB I PENDAHULUAN" rata
tengah dan tebal — dan hampir tidak ada yang mengerjakannya lewat gaya
*Heading 1* di Word. Mereka mengetiknya sebagai paragraf biasa lalu menebalkan
dan meratakannya sendiri. Pembaca yang hanya mempercayai gaya Word akan
menyimpulkan seluruh skripsi terdiri dari satu bagian tanpa judul.

Karena itu judul dikenali dari tiga sisi sekaligus: gaya Word bila memang
dipakai, pola penomoran yang baku di naskah Indonesia, dan bentuk barisnya
sendiri. Yang tidak dikenali tetap masuk sebagai isi, tidak dibuang.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


class UnsupportedManuscript(ValueError):
    pass


#: "BAB IV", "BAB 4", "BAB IV HASIL DAN PEMBAHASAN".
_BAB = re.compile(r"^\s*BAB\s+([IVXLCDM]+|\d+)\b[\s.:-]*(.*)$", re.IGNORECASE)

#: Penomoran bertingkat: "1.1", "2.3.4" — kedalamannya menentukan tingkatnya.
_SUB_ANGKA = re.compile(r"^\s*(\d+(?:\.\d+)+)\.?\s+(\S.{0,120})$")

#: Penomoran huruf: "A. Latar Belakang". Lazim pada pedoman yang mengikuti EYD.
_SUB_HURUF = re.compile(r"^\s*([A-Z])\.\s+(\S.{0,120})$")

#: Bagian di luar batang tubuh yang judulnya baku dan berdiri sendiri.
_BAGIAN_AWAL = {
    "halaman judul", "lembar pengesahan", "lembar persetujuan", "pernyataan keaslian",
    "motto", "persembahan", "kata pengantar", "abstrak", "abstract", "intisari",
    "daftar isi", "daftar tabel", "daftar gambar", "daftar lampiran", "daftar singkatan",
    "daftar pustaka", "lampiran", "riwayat hidup", "biodata penulis",
}

#: Gaya Word yang berarti judul, dalam pemasangan berbahasa Inggris dan Indonesia.
_GAYA_JUDUL = re.compile(r"^(heading|judul)\s*(\d)", re.IGNORECASE)


@dataclass
class ImportedSection:
    title: str
    level: int
    blocks: list[dict] = field(default_factory=list)
    children: list["ImportedSection"] = field(default_factory=list)

    def word_count(self) -> int:
        sendiri = sum(len(b.get("content", "").split()) for b in self.blocks)
        return sendiri + sum(c.word_count() for c in self.children)


@dataclass
class ImportedManuscript:
    sections: list[ImportedSection]
    notes: list[str] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return sum(s.word_count() for s in self.sections)

    def flat(self) -> Iterator[ImportedSection]:
        def jalan(nodes: list[ImportedSection]) -> Iterator[ImportedSection]:
            for node in nodes:
                yield node
                yield from jalan(node.children)

        return jalan(self.sections)


def _lucuti_nomor(judul: str, cadangan: str) -> str:
    """Buang penomoran bawaan naskah dari judul bagian.

    Recens menomori bagiannya sendiri saat merakit naskah. Nomor yang ikut
    terbawa dari dokumen asal karena itu bertumpuk dengan nomor baru, dan
    daftar isinya berbunyi "3.1 2.1 Motivasi Kerja" — dua sistem penomoran
    berebut satu baris.
    """
    bersih = judul.strip()
    for pola in (_SUB_ANGKA, _SUB_HURUF):
        cocok = pola.match(bersih)
        if cocok:
            return cocok.group(2).strip() or cadangan
    return bersih or cadangan


def _tingkat_judul(text: str, style: str) -> tuple[int, str] | None:
    """Kembalikan (tingkat, judul bersih) bila baris ini judul bagian."""
    bersih = " ".join((text or "").split())
    if not bersih or len(bersih) > 160:
        return None

    bab = _BAB.match(bersih)
    if bab:
        nomor, sisa = bab.group(1).upper(), bab.group(2).strip()
        # Nama babnya yang dipakai; nomornya diserahkan ke penomoran Recens.
        # Bab tanpa nama tetap memakai "BAB N" agar tidak berjudul kosong.
        return 1, sisa or f"BAB {nomor}"

    if bersih.lower().strip(" :.") in _BAGIAN_AWAL:
        return 1, bersih.strip(" :.")

    angka = _SUB_ANGKA.match(bersih)
    if angka:
        # "1.1" berarti tingkat dua, "1.1.1" tingkat tiga: kedalaman penomoran
        # itulah kedalaman bagiannya.
        return min(angka.group(1).count(".") + 1, 4), _lucuti_nomor(bersih, bersih)

    gaya = _GAYA_JUDUL.match(style or "")
    if gaya:
        return min(int(gaya.group(2)), 4), bersih

    huruf = _SUB_HURUF.match(bersih)
    if huruf:
        return 2, _lucuti_nomor(bersih, bersih)

    return None


def _elemen(document) -> Iterator[tuple[str, Any]]:
    """Paragraf dan tabel dalam urutan aslinya di dokumen.

    python-docx menyediakan ``paragraphs`` dan ``tables`` sebagai dua daftar
    terpisah, sehingga tabel yang berada di tengah bab akan pindah ke ujung
    naskah bila keduanya dibaca sendiri-sendiri. Urutannya hanya ada di pohon
    XML-nya, jadi dari sanalah dibaca.
    """
    from docx.table import Table as DocxTable
    from docx.text.paragraph import Paragraph

    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            yield "p", Paragraph(child, document)
        elif tag == "tbl":
            yield "tbl", DocxTable(child, document)


def _tabel_ke_blok(table) -> dict | None:
    rows = [[" ".join(cell.text.split()) for cell in row.cells] for row in table.rows]
    rows = [r for r in rows if any(c for c in r)]
    if len(rows) < 2:
        return None
    header, isi = rows[0], rows[1:]
    return {
        "kind": "table",
        "content": "",
        "meta": {"caption": "", "columns": header, "rows": isi, "note": ""},
    }


def read_docx_manuscript(path: Path | str) -> ImportedManuscript:
    """Baca naskah .docx menjadi bagian bertingkat beserta isinya."""
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise UnsupportedManuscript(
            "Membaca naskah Word memerlukan python-docx. Jalankan: pip install python-docx"
        ) from exc

    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise UnsupportedManuscript(
            "Berkas tidak bisa dibuka sebagai dokumen Word. Pastikan berformat .docx, "
            "bukan .doc lama — buka di Word lalu simpan ulang sebagai .docx."
        ) from exc

    akar: list[ImportedSection] = []
    tumpukan: list[ImportedSection] = []
    lepas: list[dict] = []
    jumlah_tabel = 0

    def tampung(block: dict) -> None:
        if tumpukan:
            tumpukan[-1].blocks.append(block)
        else:
            lepas.append(block)

    def buka(level: int, judul: str) -> None:
        node = ImportedSection(title=judul, level=level)
        while tumpukan and tumpukan[-1].level >= level:
            tumpukan.pop()
        if tumpukan:
            tumpukan[-1].children.append(node)
        else:
            akar.append(node)
        tumpukan.append(node)

    for jenis, elemen in _elemen(document):
        if jenis == "tbl":
            block = _tabel_ke_blok(elemen)
            if block:
                jumlah_tabel += 1
                tampung(block)
            continue

        teks = " ".join(elemen.text.split())
        if not teks:
            continue
        style = getattr(getattr(elemen, "style", None), "name", "") or ""
        judul = _tingkat_judul(teks, style)

        if judul is not None:
            level, bersih = judul
            # "BAB I" kerap berdiri sendiri dengan judulnya di baris berikutnya.
            # Digabung supaya bagiannya bernama, bukan bernomor saja.
            if (
                tumpukan
                and tumpukan[-1].level == 1
                and re.fullmatch(r"BAB [IVXLCDM\d]+", tumpukan[-1].title)
                and not tumpukan[-1].blocks
                and not tumpukan[-1].children
                and level != 1
                and len(bersih) <= 60
                and bersih.upper() == bersih
            ):
                tumpukan[-1].title = bersih
                continue
            buka(level, bersih)
            continue

        if (
            tumpukan
            and re.fullmatch(r"BAB [IVXLCDM\d]+", tumpukan[-1].title)
            and not tumpukan[-1].blocks
            and not tumpukan[-1].children
            and len(teks) <= 60
            and teks.upper() == teks
        ):
            tumpukan[-1].title = teks
            continue

        tampung({"kind": "paragraph", "content": teks, "meta": {"source": "impor"}})

    notes = []
    if lepas:
        # Paragraf sebelum judul pertama tidak punya rumah. Dibuang berarti
        # menghilangkan tulisan orang; ditaruh di bagian bernama sendiri
        # membuatnya terlihat dan bisa dipindahkan.
        akar.insert(0, ImportedSection(title="Bagian Awal", level=1, blocks=lepas))
        notes.append(
            f"{len(lepas)} paragraf berada sebelum judul bab pertama dan ditempatkan "
            f"pada bagian 'Bagian Awal'."
        )
    if jumlah_tabel:
        notes.append(f"{jumlah_tabel} tabel terbaca beserta isinya.")
    if not akar:
        raise UnsupportedManuscript(
            "Tidak ada teks yang bisa dibaca dari dokumen tersebut."
        )
    if len(akar) == 1 and not akar[0].children:
        notes.append(
            "Judul bab tidak terdeteksi, sehingga seluruh isi masuk sebagai satu bagian. "
            "Pastikan judul bab ditulis sebagai 'BAB I PENDAHULUAN' atau memakai gaya "
            "Heading di Word, lalu impor ulang bila ingin terpecah per bab."
        )

    return ImportedManuscript(sections=akar, notes=notes)
