"""Lantai mutu keluaran model.

Modul ini yang membuat "murah" dan "bagus" berhenti bertentangan. Tanpa
pemeriksa, penjenjangan biaya adalah taruhan: model murah dipakai karena lebih
hemat, dan tidak ada yang tahu apakah hasilnya layak sampai pembimbing yang
menemukannya. Dengan pemeriksa, urutannya terbalik — yang murah dicoba lebih
dulu, dan yang tidak lolos naik tingkat dengan sendirinya.

Seluruh pemeriksaan di sini **deterministik**. Tidak ada model yang menilai
model lain: itu hanya memindahkan pertanyaan mutu satu lapis ke dalam, dengan
biaya tambahan dan tanpa jaminan tambahan. Yang diperiksa adalah hal-hal yang
bisa dinyatakan dengan aturan dan dibuktikan salah — kalimat yang terputus di
tengah, jawaban yang berpindah bahasa, sitasi yang tidak ada di pustaka.

Yang **tidak** diperiksa di sini juga perlu disebut, supaya tidak ada yang
mengira pemeriksa ini lebih pintar daripada kenyataannya: keindahan kalimat,
ketepatan argumen, dan kesesuaian dengan maksud penulis tidak bisa diukur
aturan. Untuk itulah jenjangnya ada — bukan pemeriksanya.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    #: ``berat`` memicu naik tingkat; ``ringan`` hanya dicatat.
    severity: str = "berat"


@dataclass
class Spec:
    """Apa yang diharapkan dari keluaran sebuah tugas."""

    #: Bahasa yang diminta: "id", "en", atau None bila tidak dipersoalkan.
    language: str | None = "id"
    min_words: int = 3
    max_words: int | None = None
    #: Sitasi yang boleh muncul. None berarti sitasi tidak diperiksa.
    citekeys: set[str] | None = None
    #: Naskah ilmiah dirakit dari blok berstruktur, bukan dari markdown.
    allow_markdown: bool = False


@dataclass
class Report:
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "berat" for i in self.issues)

    @property
    def codes(self) -> list[str]:
        return [i.code for i in self.issues]

    def ringkas(self) -> str:
        return "; ".join(f"{i.code}: {i.message}" for i in self.issues)


#: Kata fungsi yang muncul di hampir tiap kalimat, dipakai menebak bahasa.
#: Kata isi tidak bisa dipakai karena istilah teknis Inggris lazim dipertahankan
#: apa adanya di naskah Indonesia — "outer loading" dan "composite reliability"
#: bukan tanda jawabannya berpindah bahasa.
_FUNGSI_ID = {
    "yang", "dan", "dengan", "untuk", "pada", "dari", "adalah", "tidak", "ini",
    "itu", "dalam", "akan", "dapat", "oleh", "karena", "tersebut", "secara",
    "telah", "juga", "atau", "bahwa", "sebagai", "lebih", "terhadap",
}
_FUNGSI_EN = {
    "the", "of", "and", "to", "in", "is", "that", "for", "with", "as", "are",
    "this", "be", "by", "on", "it", "from", "which", "have", "has",
}

#: Pembuka basa-basi. Kalimat semacam ini bukan sekadar mubazir — ia menandakan
#: model menjawab percakapan, bukan menghasilkan naskah, dan mahasiswa yang
#: menyalinnya bulat-bulat akan menyerahkan "Berikut adalah parafrasenya:"
#: kepada pembimbingnya.
_BASA_BASI = re.compile(
    r"^\s*(?:tentu|baik|berikut|ini dia|semoga membantu|sebagai (?:ai|asisten|model)|"
    r"here (?:is|are)|sure|certainly|of course|as an ai)\b",
    re.IGNORECASE,
)

_MARKDOWN = re.compile(r"(\*\*[^*]+\*\*|^#{1,6}\s|^\s*[-*]\s+|```)", re.MULTILINE)

_SITASI = re.compile(r"\[\[cite:([^\]]+)\]\]")

#: Akhir kalimat yang wajar. Keluaran yang terhenti di luar ini besar
#: kemungkinan terpotong batas token — dan itu dibayar penuh untuk kalimat yang
#: tidak bisa dipakai.
_AKHIR_WAJAR = tuple('.!?"”)]:;')


def _kata(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ']+", (text or "").lower())


def inspect(text: str, spec: Spec | None = None) -> Report:
    """Periksa satu keluaran model terhadap harapannya."""
    spec = spec or Spec()
    issues: list[Issue] = []
    bersih = (text or "").strip()
    kata = _kata(bersih)

    if not bersih:
        return Report([Issue("kosong", "Model tidak mengembalikan teks apa pun.")])
    if len(kata) < spec.min_words:
        issues.append(
            Issue("terlalu_pendek", f"Hanya {len(kata)} kata, di bawah batas {spec.min_words}.")
        )

    if spec.max_words and len(kata) > spec.max_words:
        issues.append(
            Issue(
                "melebihi_batas",
                f"{len(kata)} kata melewati batas {spec.max_words}.",
                severity="berat",
            )
        )

    # Terpotong di tengah kalimat. Diperiksa hanya pada keluaran yang cukup
    # panjang: jawaban pendek memang sering tidak berakhir titik, dan menandai
    # semuanya akan membuat naik tingkat terjadi terus-menerus tanpa alasan.
    if len(bersih) > 200 and not bersih.endswith(_AKHIR_WAJAR):
        issues.append(
            Issue("terpotong", "Teks berhenti di tengah kalimat; kemungkinan kena batas token.")
        )

    if _BASA_BASI.match(bersih):
        issues.append(
            Issue("basa_basi", "Dibuka kalimat pengantar percakapan, bukan isi naskah.")
        )

    if not spec.allow_markdown and _MARKDOWN.search(bersih):
        issues.append(
            Issue(
                "markah_markdown",
                "Memuat markah markdown; naskah dirakit dari blok berstruktur.",
                severity="ringan",
            )
        )

    if spec.language and len(kata) >= 20:
        id_count = sum(1 for w in kata if w in _FUNGSI_ID)
        en_count = sum(1 for w in kata if w in _FUNGSI_EN)
        diminta, lawan = (
            (id_count, en_count) if spec.language == "id" else (en_count, id_count)
        )
        if lawan > diminta:
            issues.append(
                Issue(
                    "bahasa_keliru",
                    f"Jawaban tampak bukan dalam bahasa yang diminta ({spec.language}).",
                )
            )

    ulang = _pengulangan(kata)
    if ulang:
        issues.append(
            Issue("pengulangan", f"Potongan '{ulang}' berulang; keluaran model merosot.")
        )

    if spec.citekeys is not None:
        karangan = {k.strip() for k in _SITASI.findall(bersih)} - spec.citekeys
        if karangan:
            issues.append(
                Issue(
                    "sitasi_karangan",
                    f"Menyebut sitasi yang tidak ada di pustaka proyek: "
                    f"{', '.join(sorted(karangan))}.",
                )
            )

    return Report(issues)


def _pengulangan(kata: list[str], n: int = 6, ambang: int = 3) -> str | None:
    """Deteksi keluaran yang merosot menjadi pengulangan.

    Gejala khas model kecil yang kehabisan arah: satu potongan kalimat berputar
    berkali-kali. Tidak pernah muncul pada tulisan manusia dengan panjang
    sependek ini, jadi ia penanda yang cukup bersih.
    """
    if len(kata) < n * ambang:
        return None
    gram = Counter(tuple(kata[i : i + n]) for i in range(len(kata) - n + 1))
    potongan, jumlah = gram.most_common(1)[0]
    return " ".join(potongan) if jumlah >= ambang else None


#: Harapan bawaan tiap tugas. Yang tidak terdaftar diperiksa dengan ``Spec()``.
#:
#: Batas kata sengaja tidak dipasang di sini melainkan diteruskan pemanggil,
#: sebab batasnya milik permintaannya — abstrak 250 kata dan abstrak 150 kata
#: sama-sama sah, dan yang tahu mana yang berlaku hanya pemanggilnya.
SPESIFIKASI: dict[str, Spec] = {
    "lanjutan_kalimat": Spec(min_words=4),
    "parafrase": Spec(min_words=5),
    "bahasa_akademik": Spec(min_words=5),
    "terjemahan": Spec(language=None, min_words=3),
    "pencarian_literatur": Spec(language=None, min_words=1),
    "outline": Spec(min_words=10, allow_markdown=True),
    "matriks_sintesis": Spec(min_words=10),
    "abstrak_terstruktur": Spec(min_words=40),
    "cover_letter": Spec(language=None, min_words=40),
    "respon_reviewer": Spec(min_words=20),
    "tanya_jurnal": Spec(min_words=10),
    "narasi_hasil": Spec(min_words=20),
    "konversi_naskah": Spec(min_words=20),
    "mode_sidang": Spec(min_words=20, allow_markdown=True),
}


def spec_for(task_key: str, **ubah) -> Spec:
    """Harapan sebuah tugas, boleh disesuaikan per permintaan."""
    dasar = SPESIFIKASI.get(task_key, Spec())
    if not ubah:
        return dasar
    return Spec(
        language=ubah.get("language", dasar.language),
        min_words=ubah.get("min_words", dasar.min_words),
        max_words=ubah.get("max_words", dasar.max_words),
        citekeys=ubah.get("citekeys", dasar.citekeys),
        allow_markdown=ubah.get("allow_markdown", dasar.allow_markdown),
    )
