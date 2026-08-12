"""Batas produk yang melekat dan tidak dapat dimatikan (Bagian 8.1).

Batasan pada rancangan produk ditulis sebagai janji. Di sini janji itu menjadi
kode yang berjalan pada setiap permintaan dan setiap keluaran, tanpa saklar
untuk mematikannya:

======================================  ==================================================
Yang dilakukan Recens                   Yang tidak dilakukan Recens
======================================  ==================================================
Menyusun kerangka dan struktur bab      Menghasilkan bab utuh sekali jalan
Melanjutkan kalimat yang sedang diketik Mengarang data penelitian, hasil uji, atau temuan
Menyarankan sitasi terverifikasi        Menghasilkan referensi tak terlacak
Mengolah data dan menampilkan langkah   Memanipulasi hasil agar hipotesis diterima
Memparafrase disertai alasan perubahan  Memparafrase untuk mengelabui sistem deteksi
======================================  ==================================================

Perhatikan bahwa penjagaan dilakukan di dua sisi: permintaan yang masuk
(``guard_request``) dan keluaran yang dihasilkan (``guard_output``). Menjaga
hanya di sisi prompt tidak cukup, karena prompt bisa diakali; menjaga hanya di
sisi keluaran tidak cukup, karena niat permintaan perlu dijawab terus terang.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..manuscript import CITE_PATTERN, count_words

#: Batas kata untuk satu kali pemanggilan penulisan.
#: Melanjutkan kalimat, bukan menuliskan bab.
MAX_WORDS_CONTINUATION = 80
MAX_WORDS_PARAGRAPH = 320
MAX_WORDS_PER_CALL = 700


class GuardrailError(RuntimeError):
    """Permintaan ditolak karena melanggar batas yang melekat pada produk."""

    def __init__(self, verdict: "Verdict"):
        super().__init__(verdict.reason)
        self.verdict = verdict


@dataclass
class Verdict:
    allowed: bool
    rule: str = ""
    reason: str = ""
    alternative: str = ""
    #: Perubahan yang dilakukan pada keluaran agar tetap patuh.
    adjustments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "rule": self.rule,
            "reason": self.reason,
            "alternative": self.alternative,
            "adjustments": self.adjustments,
        }


ALLOWED = Verdict(allowed=True)


# --- Penjagaan permintaan ----------------------------------------------------

#: Permintaan mengarang data penelitian atau hasil uji.
POLA_KARANG_DATA = (
    r"\b(buat|buatkan|bikin|karang|karangkan|generate|hasilkan)\b[^.]{0,40}?"
    r"\b(data|dataset|responden|jawaban kuesioner|hasil uji|hasil penelitian|temuan)\b",
    r"\bdata\b[^.]{0,20}\b(palsu|fiktif|karangan|bohongan|dummy untuk skripsi)\b",
    r"\b(isi|lengkapi)\b[^.]{0,30}\b(kuesioner|angket)\b[^.]{0,30}\bsendiri\b",
    r"\bsimulasikan\b[^.]{0,30}\bdata\s+(responden|penelitian)\b",
)

#: Permintaan memanipulasi hasil agar hipotesis diterima.
POLA_MANIPULASI = (
    r"\b(ubah|ganti|atur|sesuaikan|manipulasi|otak-atik|permak)\b[^.]{0,50}?"
    r"\b(data|hasil|angka|nilai|output|signifikansi)\b",
    r"\b(agar|supaya|biar)\b[^.]{0,40}?\b(signifikan|hipotesis diterima|h1 diterima|"
    r"berpengaruh|valid|reliabel|normal)\b",
    r"\bsig(nifikansi)?\b[^.]{0,20}\b(di ?bawah|kurang dari|<)\s*0[.,]05\b[^.]{0,20}\bbuat\b",
    r"\bhilangkan\b[^.]{0,30}\b(outlier|responden)\b[^.]{0,30}\b(agar|supaya|biar)\b",
)

#: Permintaan memparafrase untuk mengelabui sistem deteksi.
POLA_KELABUI_DETEKSI = (
    r"\b(lolos|bypass|akali|kelabui|hindari|ngakalin|akalin)\b[^.]{0,40}?"
    r"\b(turnitin|plagiaris\w*|plagiat|cek kemiripan|similarity|deteksi ai|ai detector|"
    r"detektor ai|gptzero)\b",
    r"\b(agar|supaya|biar)\b[^.]{0,40}?\btidak\s+(ter)?deteksi\b",
    r"\b(agar|supaya|biar)\b[^.]{0,40}?\bturun\b[^.]{0,25}\b(persentase|persen|angka)\b"
    r"[^.]{0,25}\b(plagia\w*|kemiripan|similarity)\b",
    r"\bhumanize\b[^.]{0,30}\b(teks|tulisan|ai)\b",
    r"\btulis(kan)?\b[^.]{0,30}\bseolah-olah\b[^.]{0,30}\bmanusia\b",
)

#: Permintaan menuliskan bab utuh sekali jalan.
POLA_BAB_UTUH = (
    r"\b(tulis(kan)?|buat(kan)?|susun(kan)?|generate|kerjakan)\b[^.]{0,30}?"
    r"\b(seluruh|semua|full|lengkap|utuh|satu)?\s*"
    r"\b(bab|skripsi|tesis|disertasi|makalah|artikel|proposal)\b"
    r"[^.]{0,30}\b(utuh|lengkap|sekaligus|dari awal sampai akhir|full|selesai)\b",
    r"\b(tulis(kan)?|buat(kan)?)\b[^.]{0,20}\bbab\s+[iv1-5]+\b[^.]{0,20}\bsampai\b"
    r"[^.]{0,10}\bbab\s+[iv1-5]+\b",
    r"\bkerjakan\b[^.]{0,20}\b(skripsi|tesis|makalah)\s*(saya|ku|aku)\b",
)

#: Permintaan referensi tanpa penelusuran ke sumber resmi.
POLA_REFERENSI_KARANGAN = (
    r"\b(buat|buatkan|karang|karangkan|bikin)\b[^.]{0,40}?\b(daftar pustaka|referensi|sitasi)\b"
    r"[^.]{0,40}\b(saja|sendiri|palsu|fiktif|asal|karangan)\b",
    r"\b(daftar pustaka|referensi)\b[^.]{0,30}\b(tanpa|nggak usah|tidak usah)\b"
    r"[^.]{0,30}\b(dicari|dicek|diverifikasi|nyata|asli)\b",
    # Permintaan agar model menuliskan referensi lengkap dengan penandanya.
    # DOI, ISSN, dan tautan hanya sah bila berasal dari basis data resmi; begitu
    # model diminta menuliskannya sendiri, yang keluar pasti karangan. Inilah
    # bentuk permintaan yang paling sering muncul dan paling berbahaya, karena
    # hasilnya terlihat meyakinkan.
    r"\b(buat|buatkan|bikin|tulis|tuliskan|sebutkan|berikan|kasih)\b[^.]{0,40}?"
    r"\b(daftar pustaka|referensi|sitasi|jurnal|pustaka)\b[^.]{0,60}?"
    r"\b(doi|issn|isbn|tautan|link|url|beserta sumbernya)\b",
    # Permintaan sejumlah tertentu referensi lewat jalur penulisan — bukan lewat
    # pencarian literatur. Angka pada permintaan itulah tandanya: yang diminta
    # bukan bantuan mencari, melainkan daftar yang langsung jadi.
    r"\b(buat|buatkan|bikin|tulis|tuliskan|sebutkan|berikan|kasih|carikan)\b[^.]{0,25}?"
    r"\b\d{1,3}\b[^.]{0,25}?\b(daftar pustaka|referensi|sitasi|jurnal|pustaka|artikel)\b",
)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(re.search(pattern, lowered) for pattern in patterns)


def guard_request(instruction: str, kind: str = "umum") -> Verdict:
    """Periksa niat permintaan sebelum apa pun dikerjakan.

    Penolakan di sini selalu disertai jalan keluar yang sah, karena di balik
    permintaan yang melanggar biasanya ada kebutuhan yang wajar: mahasiswa yang
    datanya belum terkumpul, atau yang panik melihat angka kemiripan.
    """
    if _matches(instruction, POLA_KARANG_DATA):
        return Verdict(
            allowed=False,
            rule="tidak_mengarang_data",
            reason=(
                "Recens tidak mengarang data penelitian, hasil uji, atau temuan. Data yang "
                "diolah harus benar-benar berasal dari pengumpulan data Anda."
            ),
            alternative=(
                "Yang bisa dikerjakan sekarang: menyusun instrumen dan kisi-kisi kuesioner, "
                "menghitung ukuran sampel yang dibutuhkan, menyiapkan template tabulasi data, "
                "dan menuliskan BAB III lengkap. Begitu data sungguhan masuk, seluruh uji "
                "berjalan otomatis."
            ),
        )

    if _matches(instruction, POLA_MANIPULASI):
        return Verdict(
            allowed=False,
            rule="tidak_memanipulasi_hasil",
            reason=(
                "Recens tidak mengubah data atau hasil analisis agar hipotesis diterima. "
                "Angka hasil uji ditampilkan apa adanya, termasuk ketika tidak signifikan."
            ),
            alternative=(
                "Hasil yang tidak signifikan bukan kegagalan penelitian dan tetap layak "
                "dibahas. Recens membantu menuliskan pembahasannya secara ilmiah: "
                "membandingkan dengan penelitian terdahulu, menelusuri kemungkinan "
                "penyebabnya, dan merumuskannya sebagai keterbatasan serta saran penelitian "
                "berikutnya."
            ),
        )

    if _matches(instruction, POLA_KELABUI_DETEKSI):
        return Verdict(
            allowed=False,
            rule="tidak_mengelabui_deteksi",
            reason=(
                "Recens tidak memparafrase dengan tujuan mengelabui sistem deteksi kemiripan "
                "atau deteksi AI."
            ),
            alternative=(
                "Cek Kemiripan Mandiri menunjukkan bagian mana yang bermasalah beserta "
                "sumbernya. Parafrase di Recens selalu disertai penjelasan apa yang diubah "
                "dan mengapa, sehingga tulisan menjadi benar-benar milik Anda — bukan sekadar "
                "lolos pemeriksaan. Bagian yang memang perlu dikutip utuh bisa dijadikan "
                "kutipan langsung lengkap dengan sitasinya."
            ),
        )

    if _matches(instruction, POLA_BAB_UTUH):
        return Verdict(
            allowed=False,
            rule="tidak_menulis_bab_utuh",
            reason=(
                "Recens tidak menghasilkan bab utuh sekali jalan tanpa keterlibatan Anda. "
                "Yang ditulis sistem tanpa Anda baca tidak akan bisa Anda pertahankan di "
                "hadapan penguji."
            ),
            alternative=(
                "Alurnya per bagian: kerangka bab dan target kata disusun lebih dahulu, lalu "
                "tiap sub-bagian dikerjakan bergantian — Anda menulis, sistem melanjutkan "
                "kalimat, memperbaiki bahasa, dan menyisipkan sitasi."
            ),
        )

    if _matches(instruction, POLA_REFERENSI_KARANGAN):
        return Verdict(
            allowed=False,
            rule="tidak_mengarang_referensi",
            reason=(
                "Recens tidak menghasilkan referensi yang tidak terlacak ke sumber resmi. "
                "Referensi karangan adalah kesalahan paling fatal pada karya ilmiah."
            ),
            alternative=(
                "Pencarian Literatur menelusuri Crossref, OpenAlex, Semantic Scholar, dan "
                "jurnal nasional terakreditasi sekaligus. Setiap metadata yang masuk pustaka "
                "berasal dari basis data tersebut dan bisa ditelusuri kembali lewat DOI-nya."
            ),
        )

    return ALLOWED


# --- Penjagaan keluaran ------------------------------------------------------


def strip_unverified_citations(text: str, allowed_citekeys: set[str]) -> tuple[str, list[str]]:
    """Buang penanda sitasi yang tidak ada di pustaka proyek.

    Model bisa saja menuliskan sitasi yang terdengar masuk akal. Selama citekey
    itu tidak ada di pustaka — dan pustaka hanya diisi metadata dari basis data
    resmi — penanda tersebut dibuang sebelum masuk naskah.
    """
    removed: list[str] = []

    def replace(match: re.Match) -> str:
        citekey = match.group(1)
        if citekey in allowed_citekeys:
            return match.group(0)
        removed.append(citekey)
        return ""

    cleaned = CITE_PATTERN.sub(replace, text)
    return re.sub(r"\s{2,}", " ", cleaned).strip(), removed


def enforce_length(text: str, max_words: int) -> tuple[str, bool]:
    """Potong keluaran yang melampaui batas satu kali pemanggilan."""
    words = text.split()
    if len(words) <= max_words:
        return text, False
    truncated = " ".join(words[:max_words])
    # Potong di batas kalimat terakhir agar hasilnya tidak menggantung.
    last_stop = max(truncated.rfind("."), truncated.rfind("?"), truncated.rfind("!"))
    if last_stop > len(truncated) * 0.6:
        truncated = truncated[: last_stop + 1]
    return truncated, True


def guard_output(
    text: str,
    kind: str,
    allowed_citekeys: set[str] | None = None,
    analysis_result=None,
    max_words: int | None = None,
) -> tuple[str, Verdict]:
    """Saring keluaran model sebelum sampai ke naskah pengguna.

    ``analysis_result`` bila diisi mengaktifkan pemeriksaan penelusuran angka:
    setiap angka pada narasi harus ada di hasil perhitungan mesin statistik.
    """
    verdict = Verdict(allowed=True, rule=kind)
    cleaned = text

    if allowed_citekeys is not None:
        cleaned, removed = strip_unverified_citations(cleaned, allowed_citekeys)
        if removed:
            verdict.adjustments.append(
                f"{len(removed)} sitasi tidak dikenal dibuang karena tidak ada di pustaka "
                f"proyek: {', '.join(sorted(set(removed)))}."
            )

    limit = max_words or {
        "lanjutan_kalimat": MAX_WORDS_CONTINUATION,
        "parafrase": MAX_WORDS_PARAGRAPH,
        "narasi_hasil": MAX_WORDS_PARAGRAPH,
    }.get(kind, MAX_WORDS_PER_CALL)

    cleaned, truncated = enforce_length(cleaned, limit)
    if truncated:
        verdict.adjustments.append(
            f"Keluaran dipotong pada {limit} kata. Recens menulis per bagian, bukan "
            f"per bab sekali jalan."
        )

    if analysis_result is not None:
        from ..stats.narrative import untraceable_numbers

        flagged = untraceable_numbers(cleaned, analysis_result)
        if flagged:
            verdict.allowed = False
            verdict.rule = "angka_tidak_tertelusur"
            verdict.reason = (
                f"Narasi memuat angka yang tidak ada di hasil perhitungan: "
                f"{', '.join(str(n) for n in flagged[:8])}. Narasi ditolak dan diganti "
                f"draf yang seluruh angkanya berasal dari mesin statistik."
            )
    return cleaned, verdict


def word_budget(kind: str) -> int:
    return {
        "lanjutan_kalimat": MAX_WORDS_CONTINUATION,
        "parafrase": MAX_WORDS_PARAGRAPH,
        "narasi_hasil": MAX_WORDS_PARAGRAPH,
    }.get(kind, MAX_WORDS_PER_CALL)


def describe_limits() -> list[dict]:
    """Daftar batas produk untuk ditampilkan di antarmuka."""
    return [
        {
            "does": "Menyusun kerangka dan struktur bab",
            "does_not": "Menghasilkan bab utuh sekali jalan tanpa keterlibatan pengguna",
            "rule": "tidak_menulis_bab_utuh",
        },
        {
            "does": "Melanjutkan kalimat yang sedang diketik pengguna",
            "does_not": "Mengarang data penelitian, hasil uji, atau temuan",
            "rule": "tidak_mengarang_data",
        },
        {
            "does": "Menyarankan sitasi dari sumber yang terverifikasi",
            "does_not": "Menghasilkan referensi yang tidak terlacak ke sumber resmi",
            "rule": "tidak_mengarang_referensi",
        },
        {
            "does": "Mengolah data yang diunggah dan menampilkan langkahnya",
            "does_not": "Memanipulasi hasil analisis agar hipotesis diterima",
            "rule": "tidak_memanipulasi_hasil",
        },
        {
            "does": "Memparafrase disertai penjelasan alasan perubahan",
            "does_not": "Memparafrase khusus untuk mengelabui sistem deteksi",
            "rule": "tidak_mengelabui_deteksi",
        },
    ]
