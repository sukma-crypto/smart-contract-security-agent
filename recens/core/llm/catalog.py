"""Katalog model, harga, dan penjenjangan tugas.

Tiga penyedia dipakai berdampingan supaya biaya mengikuti berat pekerjaannya:
melanjutkan satu kalimat dan menalar atas naskah utuh tidak layak dibayar
dengan tarif yang sama.

Satu keputusan perlu disebut terus terang karena ia bertentangan dengan cara
orang biasa membayangkan penjenjangan: **model tidak dipilih berdasarkan
jenjang pendidikan penggunanya.** Skripsi S1 tidak lebih ringan daripada
disertasi S3 dalam arti yang menentukan di sini — kesalahan angka pada BAB IV
sama fatalnya bagi keduanya, dan memberi mahasiswa S1 model yang lebih lemah
untuk pekerjaan yang sama persis adalah menjual dua mutu dengan satu janji.
Modul ini menjenjangkan **tugas**, bukan orang. Kebetulan hasil akhirnya mirip:
pekerjaan yang berat memang lebih sering muncul di disertasi.

Harga disimpan sebagai bilangan bulat mikro-dolar per juta token. Bilangan
bulat, bukan pecahan: biaya dijumlahkan ribuan kali dan galat pembulatan
pecahan biner akan menumpuk diam-diam sampai catatan pengeluaran tidak lagi
cocok dengan tagihan yang benar-benar datang.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    """Berat sebuah tugas, bukan jenjang penggunanya."""

    RINGAN = "ringan"
    SEDANG = "sedang"
    BERAT = "berat"


@dataclass(frozen=True)
class Model:
    key: str
    provider: str
    model_id: str
    label: str
    #: Mikro-dolar per satu juta token.
    input_micros_per_mtok: int
    output_micros_per_mtok: int
    #: Batas token masukan yang kita izinkan — bukan batas teknis modelnya,
    #: melainkan batas belanja yang kita tetapkan sendiri.
    max_input_tokens: int
    tier: Tier

    def cost_micros(self, input_tokens: int, output_tokens: int) -> int:
        """Biaya satu panggilan dalam mikro-dolar, dibulatkan ke atas.

        Dibulatkan ke atas supaya catatan kita tidak pernah lebih rendah
        daripada tagihan sebenarnya. Menaksir terlalu rendah pada pengendali
        anggaran berarti pagarnya jebol tepat ketika ia paling dibutuhkan.
        """
        total = input_tokens * self.input_micros_per_mtok
        total += output_tokens * self.output_micros_per_mtok
        return -(-total // 1_000_000)


#: Harga per Agustus 2026, dalam mikro-dolar per juta token.
#:
#: Angka di sini menentukan keputusan perutean dan isi catatan pengeluaran,
#: jadi ia harus ditinjau tiap kali penyedia mengubah tarif. Yang keliru di
#: sini tidak membuat apa pun rusak — ia hanya membuat laporan biaya berbohong,
#: dan itu justru jenis kerusakan yang paling lama tidak ketahuan.
MODELS: dict[str, Model] = {
    "deepseek-chat": Model(
        key="deepseek-chat",
        provider="deepseek",
        model_id="deepseek-chat",
        label="DeepSeek V3",
        input_micros_per_mtok=270_000,
        output_micros_per_mtok=1_100_000,
        max_input_tokens=48_000,
        tier=Tier.RINGAN,
    ),
    "gpt-4.1-mini": Model(
        key="gpt-4.1-mini",
        provider="openai",
        model_id="gpt-4.1-mini",
        label="GPT-4.1 mini",
        input_micros_per_mtok=400_000,
        output_micros_per_mtok=1_600_000,
        max_input_tokens=64_000,
        tier=Tier.RINGAN,
    ),
    "gpt-4.1": Model(
        key="gpt-4.1",
        provider="openai",
        model_id="gpt-4.1",
        label="GPT-4.1",
        input_micros_per_mtok=2_000_000,
        output_micros_per_mtok=8_000_000,
        max_input_tokens=96_000,
        tier=Tier.SEDANG,
    ),
    "claude-sonnet-5": Model(
        key="claude-sonnet-5",
        provider="anthropic",
        model_id="claude-sonnet-5",
        label="Claude Sonnet 5",
        input_micros_per_mtok=3_000_000,
        output_micros_per_mtok=15_000_000,
        max_input_tokens=120_000,
        tier=Tier.SEDANG,
    ),
    "claude-opus-5": Model(
        key="claude-opus-5",
        provider="anthropic",
        model_id="claude-opus-5",
        label="Claude Opus 5",
        input_micros_per_mtok=15_000_000,
        output_micros_per_mtok=75_000_000,
        max_input_tokens=160_000,
        tier=Tier.BERAT,
    ),
}


#: Urutan pilihan per jenjang, dari yang paling murah.
#:
#: Cadangan hanya boleh bergerak ke samping atau ke bawah harga, tidak pernah
#: ke atas. Sistem yang diam-diam naik kelas ketika penyedia murahnya sedang
#: mati adalah cara paling umum tagihan membengkak tanpa ada yang mengubah apa
#: pun: tidak ada satu keputusan yang bisa ditunjuk, hanya seminggu gangguan
#: jaringan yang berujung tagihan berlipat.
RANTAI: dict[Tier, tuple[str, ...]] = {
    Tier.RINGAN: ("deepseek-chat", "gpt-4.1-mini"),
    Tier.SEDANG: ("gpt-4.1", "claude-sonnet-5"),
    Tier.BERAT: ("claude-opus-5", "claude-sonnet-5"),
}


@dataclass(frozen=True)
class Task:
    key: str
    tier: Tier
    label: str
    #: Batas keluaran. Diterapkan sebagai pagar, bukan saran: tanpa ini satu
    #: perintah yang salah bentuk bisa menghasilkan keluaran sepanjang batas
    #: teknis model, dan itu dibayar penuh.
    max_output_tokens: int
    #: Naikkan satu tingkat sekali saja bila penjaga menolak hasilnya. Hanya
    #: untuk tugas yang hasilnya memang diperiksa mesin, sehingga penolakannya
    #: berarti sesuatu dan tidak berulang tanpa henti.
    escalate_on_reject: bool = False


#: Tiap tugas yang memanggil model harus terdaftar di sini. Tidak ada jalur
#: yang boleh memanggil model tanpa jenjang, batas keluaran, dan namanya
#: sendiri — panggilan tak bernama adalah pengeluaran yang tidak bisa
#: ditelusuri, dan pengeluaran yang tidak bisa ditelusuri tidak bisa ditekan.
TASKS: dict[str, Task] = {
    # Ringan: pendek, berpola, bervolume tinggi.
    "lanjutan_kalimat": Task("lanjutan_kalimat", Tier.RINGAN, "Lanjutan kalimat", 300),
    "parafrase": Task("parafrase", Tier.RINGAN, "Parafrase", 700),
    "bahasa_akademik": Task("bahasa_akademik", Tier.RINGAN, "Perbaikan bahasa", 900),
    "terjemahan": Task("terjemahan", Tier.RINGAN, "Terjemahan istilah", 900),
    "pencarian_literatur": Task("pencarian_literatur", Tier.RINGAN, "Perluasan kueri", 300),
    # Sedang: menyusun sesuatu yang berstruktur.
    "outline": Task("outline", Tier.SEDANG, "Penyusunan outline", 1_200),
    "matriks_sintesis": Task("matriks_sintesis", Tier.SEDANG, "Matriks sintesis", 1_500),
    "abstrak_terstruktur": Task("abstrak_terstruktur", Tier.SEDANG, "Abstrak", 800),
    "cover_letter": Task("cover_letter", Tier.SEDANG, "Cover letter", 900),
    "respon_reviewer": Task("respon_reviewer", Tier.SEDANG, "Respon reviewer", 1_200),
    "tanya_jurnal": Task("tanya_jurnal", Tier.SEDANG, "Tanya jurnal", 900),
    # Narasi hasil dijalankan di jenjang sedang meski taruhannya tinggi, sebab
    # angkanya diperiksa penjaga penelusuran: keliru berarti ditolak, bukan
    # lolos ke naskah. Naik tingkat sekali bila memang ditolak — dengan begitu
    # yang mahal hanya panggilan yang benar-benar membutuhkannya.
    "narasi_hasil": Task(
        "narasi_hasil", Tier.SEDANG, "Narasi hasil analisis", 1_200, escalate_on_reject=True
    ),
    # Berat: menalar atas naskah utuh, atau keliru sulit ketahuan.
    "konversi_naskah": Task("konversi_naskah", Tier.BERAT, "Konversi naskah", 2_000),
    "mode_sidang": Task("mode_sidang", Tier.BERAT, "Mode sidang", 2_000),
}


def task_for(key: str) -> Task:
    task = TASKS.get(key)
    if task is None:
        raise KeyError(
            f"Tugas '{key}' belum terdaftar di katalog. Tiap panggilan model harus "
            f"punya jenjang dan batas keluaran sendiri."
        )
    return task


def estimate_tokens(text: str) -> int:
    """Taksiran kasar jumlah token sebuah teks.

    Dipakai sebelum memanggil, ketika jumlah sebenarnya belum diketahui, untuk
    memotong masukan yang kepanjangan dan menaksir biayanya. Empat karakter per
    token adalah pendekatan yang cukup untuk bahasa Indonesia dan Inggris;
    ketelitiannya tidak perlu tinggi karena ia hanya menjaga pagar, sedangkan
    catatan pengeluaran memakai jumlah token sebenarnya dari penyedia.
    """
    return max(1, len(text or "") // 4)


def truncate_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    """Potong teks agar muat dalam anggaran token. Kembalikan (teks, terpotong)."""
    batas_karakter = max_tokens * 4
    if len(text or "") <= batas_karakter:
        return text, False
    return text[:batas_karakter], True
