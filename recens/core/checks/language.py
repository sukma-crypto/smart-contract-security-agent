"""Pemeriksaan bahasa akademik Indonesia sesuai kaidah PUEBI/EYD.

Ini area yang jarang digarap serius oleh alat sejenis, padahal perbaikannya
langsung terasa dan mudah dibuktikan (Bagian 4.1). Seluruh pemeriksaan di sini
bersifat deterministik: aturan yang jelas, kutipan yang tepat, dan usulan
perbaikan yang bisa ditolak pengguna.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..manuscript import Manuscript, strip_markers

#: Bentuk tidak baku yang paling sering muncul di karya tulis mahasiswa.
KATA_TIDAK_BAKU: dict[str, str] = {
    "analisa": "analisis", "aktifitas": "aktivitas", "aktip": "aktif", "apotik": "apotek",
    "atlit": "atlet", "antri": "antre", "atmosfir": "atmosfer", "azas": "asas",
    "diagnosa": "diagnosis", "difinisi": "definisi", "diskripsi": "deskripsi",
    "effektif": "efektif", "efektifitas": "efektivitas", "ekstrim": "ekstrem",
    "faham": "paham", "fikir": "pikir", "frekwensi": "frekuensi", "hakekat": "hakikat",
    "hipotesa": "hipotesis", "hutang": "utang", "ijasah": "ijazah", "ijin": "izin",
    "jadual": "jadwal", "jaman": "zaman", "karir": "karier", "katagori": "kategori",
    "komplek": "kompleks", "konkrit": "konkret", "kongkrit": "konkret",
    "konsekwensi": "konsekuensi", "kreatifitas": "kreativitas", "kuwalitas": "kualitas",
    "kwalitas": "kualitas", "kwantitas": "kuantitas", "kwartal": "kuartal",
    "kwesioner": "kuesioner", "kwitansi": "kuitansi", "legalisir": "legalisasi",
    "lembab": "lembap", "likwiditas": "likuiditas", "managemen": "manajemen",
    "merubah": "mengubah", "metoda": "metode", "nasehat": "nasihat", "netralisir": "netralisasi",
    "nomer": "nomor", "obyek": "objek", "obyektif": "objektif", "pebruari": "Februari",
    "prakteknya": "praktiknya", "praktek": "praktik", "produktifitas": "produktivitas",
    "prosentase": "persentase", "propinsi": "provinsi", "rapih": "rapi", "realita": "realitas",
    "resiko": "risiko", "rubah": "ubah", "sekedar": "sekadar", "seketaris": "sekretaris",
    "silahkan": "silakan", "sintesa": "sintesis", "sistim": "sistem",
    "sportifitas": "sportivitas", "standarisasi": "standardisasi", "subyek": "subjek",
    "subyektif": "subjektif", "supir": "sopir", "syaraf": "saraf", "tehnik": "teknik",
    "telpon": "telepon", "teoritis": "teoretis", "terlanjur": "telanjur", "trampil": "terampil",
    "trend": "tren", "questioner": "kuesioner", "respon": "respons",
    "mensukseskan": "menyukseskan", "mentaati": "menaati", "terimakasih": "terima kasih",
}

#: Ragam percakapan yang tidak boleh masuk karya ilmiah.
RAGAM_PERCAKAPAN: dict[str, str] = {
    "nggak": "tidak", "enggak": "tidak", "gak": "tidak", "ga": "tidak", "kagak": "tidak",
    "udah": "sudah", "udh": "sudah", "gimana": "bagaimana", "kenapa": "mengapa",
    "bikin": "membuat", "banget": "sangat", "kayak": "seperti", "kaya": "seperti",
    "cuma": "hanya", "cuman": "hanya", "makanya": "oleh karena itu", "tapi": "tetapi",
    "emang": "memang", "doang": "saja", "bareng": "bersama", "dapet": "mendapat",
    "ngomong": "berbicara", "bilang": "menyatakan", "gitu": "seperti itu",
    "gini": "seperti ini", "trus": "kemudian", "keliatan": "terlihat", "ngasih": "memberikan",
    "kalo": "kalau", "gimanapun": "bagaimanapun", "sekedarnya": "sekadarnya",
}

#: Pasangan mubazir: dua kata yang bermakna sama dipakai berdampingan.
REDUNDANSI: dict[str, str] = {
    r"\badalah\s+merupakan\b": "adalah / merupakan",
    r"\bagar\s+supaya\b": "agar / supaya",
    r"\bdemi\s+untuk\b": "demi / untuk",
    r"\bseperti\s+misalnya\b": "seperti / misalnya",
    r"\bsangat\s+\w+\s+sekali\b": "sangat … / … sekali",
    r"\byaitu\s+adalah\b": "yaitu / adalah",
    r"\bnamun\s+(?:akan\s+)?tetapi\b": "namun / tetapi",
    r"\bdisebabkan\s+karena\b": "disebabkan oleh / karena",
    r"\bmengapa\s+sebabnya\b": "mengapa / sebabnya",
    r"\bsaling\s+\w+\s+satu\s+sama\s+lain\b": "saling … / satu sama lain",
    r"\bhanya\s+\w+\s+saja\b": "hanya … / … saja",
    r"\bnaik\s+ke\s+atas\b": "naik",
    r"\bturun\s+ke\s+bawah\b": "turun",
}

#: Kata depan yang harus ditulis terpisah, tetapi sering ditulis serangkai.
KATA_DEPAN_SERANGKAI = (
    "atas", "bawah", "dalam", "luar", "sini", "situ", "sana", "antara", "samping",
    "depan", "belakang", "tengah", "rumah", "sekolah", "kampus", "kelas", "kantor",
    "lapangan", "perpustakaan", "laboratorium", "masyarakat", "indonesia",
)

#: Kata kerja yang menuntut awalan di- ditulis serangkai.
AWALAN_DIPISAH = (
    "lakukan", "gunakan", "berikan", "peroleh", "dapat", "ambil", "buat", "teliti",
    "analisis", "olah", "sajikan", "jelaskan", "uraikan", "tentukan", "hitung",
    "kumpulkan", "sebarkan", "isi", "ukur", "amati", "catat", "susun", "bahas",
    "gunakan", "terapkan", "hasilkan", "temukan", "pilih", "uji", "kaji",
)

KONJUNGSI_AWAL_KALIMAT = ("sehingga", "sedangkan", "yang mana", "dan", "atau", "tetapi")

KATA_GANTI_ORANG = ("saya", "aku", "kami", "kita", "penulis merasa", "menurut saya")

MAX_SENTENCE_WORDS = 32

SEVERITY_ORDER = {"tinggi": 0, "sedang": 1, "rendah": 2}


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    excerpt: str
    suggestion: str = ""
    section_id: int | None = None
    section_title: str = ""
    block_id: int | None = None
    offset: int = 0
    length: int = 0

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "excerpt": self.excerpt,
            "suggestion": self.suggestion,
            "section_id": self.section_id,
            "section_title": self.section_title,
            "block_id": self.block_id,
            "offset": self.offset,
            "length": self.length,
        }


@dataclass
class LanguageReport:
    findings: list[Finding] = field(default_factory=list)
    word_count: int = 0
    sentence_count: int = 0

    def to_dict(self) -> dict:
        by_rule: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for finding in self.findings:
            by_rule[finding.rule] = by_rule.get(finding.rule, 0) + 1
            by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1
        return {
            "total": len(self.findings),
            "word_count": self.word_count,
            "sentence_count": self.sentence_count,
            "by_rule": by_rule,
            "by_severity": by_severity,
            "findings": [f.to_dict() for f in self.findings],
        }


SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"])")


def split_sentences(text: str) -> list[tuple[int, str]]:
    """Pisah teks menjadi kalimat beserta posisi awalnya."""
    sentences: list[tuple[int, str]] = []
    position = 0
    for part in SENTENCE_SPLIT.split(text):
        if part.strip():
            offset = text.find(part, position)
            sentences.append((offset if offset >= 0 else position, part.strip()))
            position = (offset if offset >= 0 else position) + len(part)
    return sentences


def check_text(text: str, allow_first_person: bool = False) -> list[Finding]:
    """Periksa satu potongan teks terhadap seluruh kaidah."""
    findings: list[Finding] = []
    clean = strip_markers(text)

    def add(rule, severity, message, match, suggestion=""):
        findings.append(
            Finding(
                rule=rule,
                severity=severity,
                message=message,
                excerpt=_context(clean, match.start(), match.end()),
                suggestion=suggestion,
                offset=match.start(),
                length=match.end() - match.start(),
            )
        )

    lowered = clean.lower()

    for wrong, right in KATA_TIDAK_BAKU.items():
        for match in re.finditer(rf"\b{re.escape(wrong)}\b", lowered):
            add(
                "kata_tidak_baku", "sedang",
                f"'{wrong}' bukan bentuk baku menurut KBBI.", match,
                f"Gunakan '{right}'.",
            )

    for wrong, right in RAGAM_PERCAKAPAN.items():
        for match in re.finditer(rf"\b{re.escape(wrong)}\b", lowered):
            add(
                "ragam_percakapan", "tinggi",
                f"'{wrong}' termasuk ragam percakapan dan tidak lazim dalam karya ilmiah.",
                match, f"Gunakan '{right}'.",
            )

    for pattern, suggestion in REDUNDANSI.items():
        for match in re.finditer(pattern, lowered):
            add(
                "redundansi", "sedang",
                "Pasangan kata ini mubazir; cukup pakai salah satu.", match,
                f"Pilih salah satu: {suggestion}.",
            )

    # Kata depan 'di' dan 'ke' yang ditulis serangkai.
    for word in KATA_DEPAN_SERANGKAI:
        for match in re.finditer(rf"\bdi{word}\b", lowered):
            add(
                "kata_depan", "tinggi",
                f"'di{word}' adalah kata depan sehingga ditulis terpisah.", match,
                f"Tulis 'di {word}'.",
            )
    for word in ("rumah", "sekolah", "kampus", "sana", "sini", "situ", "atas", "bawah",
                 "dalam", "luar", "depan", "belakang", "samping"):
        for match in re.finditer(rf"\bke{word}\b", lowered):
            add(
                "kata_depan", "tinggi",
                f"'ke{word}' adalah kata depan sehingga ditulis terpisah.", match,
                f"Tulis 'ke {word}'.",
            )

    # Awalan 'di-' yang ditulis terpisah.
    for verb in AWALAN_DIPISAH:
        for match in re.finditer(rf"\bdi\s+{verb}\b", lowered):
            add(
                "awalan_dipisah", "tinggi",
                f"'di {verb}' memakai awalan di-, sehingga ditulis serangkai.", match,
                f"Tulis 'di{verb}'.",
            )
    for match in re.finditer(r"\bdi\s+(\w+kan)\b", lowered):
        add(
            "awalan_dipisah", "tinggi",
            f"'{match.group(0)}' memakai awalan di-, sehingga ditulis serangkai.", match,
            f"Tulis 'di{match.group(1)}'.",
        )

    # 'dimana' dan 'yang mana' sebagai kata penghubung.
    for match in re.finditer(r"\b(di\s?mana|yang\s+mana)\b", lowered):
        add(
            "kata_penghubung", "tinggi",
            f"'{match.group(0)}' tidak dipakai sebagai kata penghubung dalam bahasa Indonesia "
            f"baku; bentuk ini terbawa dari 'where'/'which'.",
            match, "Ganti dengan 'yang', 'tempat', atau pecah menjadi dua kalimat.",
        )

    # Kata ganti orang pertama.
    if not allow_first_person:
        for word in KATA_GANTI_ORANG:
            for match in re.finditer(rf"\b{re.escape(word)}\b", lowered):
                add(
                    "kata_ganti_orang", "sedang",
                    f"'{word}' sebaiknya dihindari; karya ilmiah memakai kalimat pasif atau "
                    f"'penulis'.",
                    match, "Ubah menjadi kalimat pasif, mis. 'penelitian ini menunjukkan …'.",
                )

    # Ejaan mekanis.
    for match in re.finditer(r"\s{2,}", clean):
        add("spasi_ganda", "rendah", "Terdapat spasi lebih dari satu.", match,
            "Gunakan satu spasi.")
    for match in re.finditer(r"[,.;:!?](?=[A-Za-z])", clean):
        add("spasi_tanda_baca", "rendah", "Tidak ada spasi setelah tanda baca.", match,
            "Tambahkan satu spasi setelah tanda baca.")
    for match in re.finditer(r"\s+[,.;:]", clean):
        add("spasi_tanda_baca", "rendah", "Terdapat spasi sebelum tanda baca.", match,
            "Hapus spasi sebelum tanda baca.")

    # Pemeriksaan tingkat kalimat.
    for offset, sentence in split_sentences(clean):
        words = sentence.split()
        if len(words) > MAX_SENTENCE_WORDS:
            findings.append(
                Finding(
                    rule="kalimat_panjang", severity="sedang",
                    message=f"Kalimat sepanjang {len(words)} kata sulit diikuti pembaca.",
                    excerpt=sentence[:160],
                    suggestion="Pecah menjadi dua kalimat atau lebih.",
                    offset=offset, length=len(sentence),
                )
            )
        first_word = words[0].lower().strip(",") if words else ""
        if first_word in KONJUNGSI_AWAL_KALIMAT:
            findings.append(
                Finding(
                    rule="konjungsi_awal", severity="sedang",
                    message=f"Kalimat diawali konjungsi '{first_word}'.",
                    excerpt=sentence[:120],
                    suggestion="Gabungkan dengan kalimat sebelumnya atau ganti dengan "
                               "'oleh karena itu', 'adapun', atau 'sementara itu'.",
                    offset=offset, length=len(sentence),
                )
            )
        if words and re.fullmatch(r"\d+([.,]\d+)?", words[0]):
            findings.append(
                Finding(
                    rule="angka_awal_kalimat", severity="rendah",
                    message="Kalimat tidak diawali angka.",
                    excerpt=sentence[:120],
                    suggestion="Tulis angka dengan huruf atau susun ulang kalimatnya.",
                    offset=offset, length=len(sentence),
                )
            )

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 3), f.offset))
    return findings


def _context(text: str, start: int, end: int, width: int = 60) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    prefix = "…" if left > 0 else ""
    suffix = "…" if right < len(text) else ""
    return f"{prefix}{text[left:right].strip()}{suffix}"


def check_language(manuscript: Manuscript, allow_first_person: bool = False) -> dict:
    """Periksa seluruh naskah dan tautkan setiap temuan ke lokasinya."""
    report = LanguageReport()
    for section, block in manuscript.all_blocks():
        if block.kind in ("table", "figure", "equation"):
            continue
        # Kutipan langsung dikutip apa adanya, termasuk ragam bahasanya.
        if block.kind == "quote":
            continue
        for finding in check_text(block.content, allow_first_person=allow_first_person):
            finding.section_id = section.id
            finding.section_title = section.title
            finding.block_id = block.id
            report.findings.append(finding)

    text = manuscript.text()
    report.word_count = len(re.findall(r"\b[\w'’-]+\b", text))
    report.sentence_count = len(split_sentences(text))
    report.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 3), f.section_id or 0))
    return report.to_dict()
