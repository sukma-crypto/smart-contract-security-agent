"""Jenis karya tulis ilmiah yang didukung Recens (Bagian 02 & 03).

Modul ini adalah sumber kebenaran untuk pertanyaan "karya jenis apa yang
sedang disusun" — dan karenanya menentukan struktur bawaan, langkah alur
kerja mana yang dipakai, dari mana aturan penulisan berasal, serta bentuk
keluaran yang diharapkan.

Satu alur kerja dipakai untuk semua jenis karya; yang menyesuaikan hanyalah
panjang, struktur, dan sumber aturannya.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Family(str, Enum):
    """Tiga kelompok perlakuan pada Bagian 2.2 dan 3.1."""

    PENDEK = "karya_pendek"
    TUGAS_AKHIR = "tugas_akhir"
    PUBLIKASI = "artikel_publikasi"


class StepMode(str, Enum):
    """Apakah sebuah langkah berlaku untuk jenis karya tertentu."""

    YA = "ya"
    OPSIONAL = "opsional"
    BERSYARAT = "bersyarat"  # ya, bila penelitian kuantitatif/kualitatif


@dataclass(frozen=True)
class Step:
    number: int
    key: str
    title: str
    summary: str


#: Delapan langkah dari proyek baru sampai naskah siap serah (Bagian 3.2).
STEPS: tuple[Step, ...] = (
    Step(
        1,
        "buat_proyek",
        "Buat proyek",
        "Pengguna memilih jenis karya dan jenis penelitiannya bila ada. Pilihan ini "
        "menentukan struktur bawaan, batas panjang, dan langkah mana yang dipakai.",
    ),
    Step(
        2,
        "muat_aturan",
        "Muat aturan penulisan",
        "Pedoman yang berlaku dibaca menjadi aturan: struktur, gaya sitasi, margin, "
        "huruf, spasi, penomoran, dan batas panjang.",
    ),
    Step(
        3,
        "kumpulkan_referensi",
        "Kumpulkan referensi",
        "Pencarian jurnal ke sumber nasional dan internasional, atau unggahan PDF "
        "sendiri. Referensi masuk ke pustaka proyek lengkap dengan metadata resminya.",
    ),
    Step(
        4,
        "susun_outline",
        "Susun outline",
        "Kerangka bagian dan sub-bagian dibangun mengikuti struktur yang berlaku, "
        "lengkap dengan target jumlah kata per bagian.",
    ),
    Step(
        5,
        "menulis",
        "Menulis di editor",
        "Sistem melanjutkan kalimat, memperbaiki bahasa, memparafrase, dan menyisipkan "
        "sitasi dari pustaka proyek.",
    ),
    Step(
        6,
        "olah_data",
        "Olah data penelitian",
        "Pemandu pemilihan uji, pengolahan data mentah, serta pembacaan output SPSS, "
        "R, Excel, dan SmartPLS.",
    ),
    Step(
        7,
        "periksa_naskah",
        "Periksa naskah",
        "Pemeriksaan keselarasan rumusan masalah sampai kesimpulan, kelengkapan silang "
        "sitasi, kaidah PUEBI, serta indikasi kemiripan.",
    ),
    Step(
        8,
        "ekspor_revisi",
        "Ekspor & kelola revisi",
        "Naskah diekspor sudah terformat penuh. Catatan dosen maupun reviewer dicatat "
        "sebagai daftar tugas.",
    ),
)

STEPS_BY_KEY: dict[str, Step] = {s.key: s for s in STEPS}


#: Langkah yang berlaku per kelompok karya (tabel 3.1).
STEP_MATRIX: dict[Family, dict[str, StepMode]] = {
    Family.PENDEK: {
        "buat_proyek": StepMode.YA,
        "muat_aturan": StepMode.YA,
        "kumpulkan_referensi": StepMode.YA,
        "susun_outline": StepMode.YA,
        "menulis": StepMode.YA,
        "olah_data": StepMode.OPSIONAL,
        "periksa_naskah": StepMode.YA,
        "ekspor_revisi": StepMode.YA,
    },
    Family.TUGAS_AKHIR: {
        "buat_proyek": StepMode.YA,
        "muat_aturan": StepMode.YA,
        "kumpulkan_referensi": StepMode.YA,
        "susun_outline": StepMode.YA,
        "menulis": StepMode.YA,
        "olah_data": StepMode.BERSYARAT,
        "periksa_naskah": StepMode.YA,
        "ekspor_revisi": StepMode.YA,
    },
    Family.PUBLIKASI: {
        "buat_proyek": StepMode.YA,
        "muat_aturan": StepMode.YA,
        "kumpulkan_referensi": StepMode.YA,
        "susun_outline": StepMode.YA,
        "menulis": StepMode.YA,
        "olah_data": StepMode.BERSYARAT,
        "periksa_naskah": StepMode.YA,
        "ekspor_revisi": StepMode.YA,
    },
}

#: Catatan tambahan per langkah untuk kelompok tertentu (kolom tabel 3.1).
STEP_NOTES: dict[Family, dict[str, str]] = {
    Family.PENDEK: {"ekspor_revisi": "Ekspor saja."},
    Family.TUGAS_AKHIR: {
        "olah_data": "Ya, bila kuantitatif atau kualitatif.",
        "ekspor_revisi": "Ditambah pelacak bimbingan dan mode sidang.",
    },
    Family.PUBLIKASI: {
        "olah_data": "Ya, bila artikel hasil penelitian.",
        "periksa_naskah": "Ditambah cek batas kata.",
        "ekspor_revisi": "Ditambah template jurnal dan berkas submisi.",
    },
}


#: Perbedaan perlakuan per kelompok (tabel 2.2).
TREATMENT: dict[Family, dict[str, str]] = {
    Family.PENDEK: {
        "sumber_aturan": "Instruksi dosen atau panitia",
        "struktur": "Pendahuluan, pembahasan, penutup",
        "batas_panjang": "Jumlah halaman",
        "gaya_sitasi": "Sesuai permintaan pengampu",
        "siklus_revisi": "Sekali serah",
        "keluaran": "DOCX atau PDF",
    },
    Family.TUGAS_AKHIR: {
        "sumber_aturan": "Pedoman penulisan fakultas",
        "struktur": "BAB I sampai V",
        "batas_panjang": "Target kata per bab",
        "gaya_sitasi": "Gaya baku kampus",
        "siklus_revisi": "Bimbingan berulang sampai sidang",
        "keluaran": "DOCX terformat penuh",
    },
    Family.PUBLIKASI: {
        "sumber_aturan": "Pedoman penulis jurnal atau konferensi",
        "struktur": "IMRAD: pendahuluan, metode, hasil, pembahasan",
        "batas_panjang": "Batas kata ketat, termasuk abstrak",
        "gaya_sitasi": "Gaya wajib jurnal tujuan",
        "siklus_revisi": "Peer review dan revisi bertahap",
        "keluaran": "Naskah bertemplate, cover letter, berkas pendukung",
    },
}


@dataclass(frozen=True)
class SectionTemplate:
    """Satu bagian pada struktur bawaan sebuah jenis karya."""

    title: str
    #: Bobot target kata relatif terhadap total target proyek.
    weight: float = 1.0
    children: tuple["SectionTemplate", ...] = ()
    #: Penanda peran bagian, dipakai pemeriksaan konsistensi (Bagian 4.5).
    role: str | None = None


def _s(title: str, weight: float = 1.0, children: tuple = (), role: str | None = None):
    return SectionTemplate(title=title, weight=weight, children=children, role=role)


# --- Struktur bawaan ---------------------------------------------------------

STRUKTUR_PENDEK: tuple[SectionTemplate, ...] = (
    _s(
        "Pendahuluan",
        0.25,
        (
            _s("Latar Belakang", 0.6, role="latar_belakang"),
            _s("Rumusan Masalah", 0.2, role="rumusan_masalah"),
            _s("Tujuan", 0.2, role="tujuan"),
        ),
    ),
    _s("Pembahasan", 0.6, role="pembahasan"),
    _s(
        "Penutup",
        0.15,
        (_s("Simpulan", 0.6, role="simpulan"), _s("Saran", 0.4, role="saran")),
    ),
)

STRUKTUR_LAPORAN: tuple[SectionTemplate, ...] = (
    _s(
        "BAB I PENDAHULUAN",
        0.15,
        (
            _s("Latar Belakang", 0.5, role="latar_belakang"),
            _s("Rumusan Masalah", 0.2, role="rumusan_masalah"),
            _s("Tujuan", 0.15, role="tujuan"),
            _s("Manfaat", 0.15, role="manfaat"),
        ),
    ),
    _s("BAB II TINJAUAN PUSTAKA", 0.2, (_s("Landasan Teori", 1.0, role="landasan_teori"),)),
    _s(
        "BAB III METODE PELAKSANAAN",
        0.2,
        (
            _s("Waktu dan Tempat", 0.3),
            _s("Alat dan Bahan", 0.3),
            _s("Prosedur Kerja", 0.4, role="metode"),
        ),
    ),
    _s(
        "BAB IV HASIL DAN PEMBAHASAN",
        0.35,
        (_s("Hasil", 0.5, role="hasil"), _s("Pembahasan", 0.5, role="pembahasan")),
    ),
    _s(
        "BAB V PENUTUP",
        0.1,
        (_s("Simpulan", 0.6, role="simpulan"), _s("Saran", 0.4, role="saran")),
    ),
)

STRUKTUR_TUGAS_AKHIR: tuple[SectionTemplate, ...] = (
    _s(
        "BAB I PENDAHULUAN",
        0.15,
        (
            _s("Latar Belakang Masalah", 0.45, role="latar_belakang"),
            _s("Rumusan Masalah", 0.15, role="rumusan_masalah"),
            _s("Tujuan Penelitian", 0.15, role="tujuan"),
            _s("Manfaat Penelitian", 0.15, role="manfaat"),
            _s("Batasan Masalah", 0.10, role="batasan"),
        ),
    ),
    _s(
        "BAB II TINJAUAN PUSTAKA",
        0.25,
        (
            _s("Landasan Teori", 0.5, role="landasan_teori"),
            _s("Penelitian Terdahulu", 0.2, role="penelitian_terdahulu"),
            _s("Kerangka Berpikir", 0.2, role="kerangka_berpikir"),
            _s("Hipotesis Penelitian", 0.1, role="hipotesis"),
        ),
    ),
    _s(
        "BAB III METODE PENELITIAN",
        0.2,
        (
            _s("Jenis dan Pendekatan Penelitian", 0.15, role="metode"),
            _s("Populasi dan Sampel", 0.2, role="populasi_sampel"),
            _s("Teknik Pengumpulan Data", 0.2),
            _s("Instrumen Penelitian", 0.2, role="instrumen"),
            _s("Teknik Analisis Data", 0.25, role="teknik_analisis"),
        ),
    ),
    _s(
        "BAB IV HASIL DAN PEMBAHASAN",
        0.3,
        (
            _s("Gambaran Umum Objek Penelitian", 0.15),
            _s("Hasil Penelitian", 0.45, role="hasil"),
            _s("Pembahasan", 0.4, role="pembahasan"),
        ),
    ),
    _s(
        "BAB V PENUTUP",
        0.1,
        (_s("Simpulan", 0.6, role="simpulan"), _s("Saran", 0.4, role="saran")),
    ),
)

STRUKTUR_PROPOSAL: tuple[SectionTemplate, ...] = STRUKTUR_TUGAS_AKHIR[:3]

STRUKTUR_IMRAD: tuple[SectionTemplate, ...] = (
    _s("Abstrak", 0.05, role="abstrak"),
    _s("Pendahuluan", 0.2, role="latar_belakang"),
    _s("Metode", 0.2, role="metode"),
    _s("Hasil", 0.25, role="hasil"),
    _s("Pembahasan", 0.25, role="pembahasan"),
    _s("Simpulan", 0.05, role="simpulan"),
)

STRUKTUR_TINJAUAN: tuple[SectionTemplate, ...] = (
    _s("Abstrak", 0.05, role="abstrak"),
    _s("Pendahuluan", 0.15, role="latar_belakang"),
    _s("Metode Tinjauan", 0.15, role="metode"),
    _s("Hasil Sintesis Literatur", 0.35, role="hasil"),
    _s("Pembahasan", 0.25, role="pembahasan"),
    _s("Simpulan", 0.05, role="simpulan"),
)

STRUKTUR_ESAI: tuple[SectionTemplate, ...] = (
    _s("Pendahuluan", 0.2, role="latar_belakang"),
    _s("Argumen Utama", 0.5, role="pembahasan"),
    _s("Argumen Tandingan", 0.2),
    _s("Simpulan", 0.1, role="simpulan"),
)


@dataclass(frozen=True)
class WorkType:
    """Satu jenis karya pada tabel 2.1."""

    key: str
    label: str
    family: Family
    ciri_khas: str
    fitur_utama: tuple[str, ...]
    structure: tuple[SectionTemplate, ...]
    default_target_words: int
    #: Batas kata keras bila jenis karya memang menetapkannya (mis. artikel jurnal).
    hard_word_limit: int | None = None
    citation_style: str = "apa"
    #: Ketiga format tersedia untuk seluruh jenis karya.
    #:
    #: Versi sebelumnya membatasi LaTeX hanya untuk jenis artikel, dengan alasan
    #: di situlah ia paling sering dipakai. Pembatasan itu keliru: mahasiswa
    #: teknik, matematika, dan fisika lazim menulis skripsi langsung di LaTeX,
    #: dan menutup pilihannya berarti memaksa mereka merakit ulang dokumennya
    #: di luar Recens — persis pekerjaan yang hendak dihapus produk ini.
    export_formats: tuple[str, ...] = ("docx", "pdf", "latex")
    #: Fitur khusus yang aktif pada langkah 8.
    supervision_tracking: bool = False
    defense_mode: bool = False
    submission_kit: bool = False

    @property
    def steps(self) -> dict[str, StepMode]:
        return STEP_MATRIX[self.family]

    @property
    def treatment(self) -> dict[str, str]:
        return TREATMENT[self.family]

    def step_note(self, step_key: str) -> str | None:
        return STEP_NOTES.get(self.family, {}).get(step_key)


WORK_TYPES: dict[str, WorkType] = {
    "makalah": WorkType(
        key="makalah",
        label="Makalah kuliah",
        family=Family.PENDEK,
        ciri_khas=(
            "Pendek, tenggat mingguan, struktur pendahuluan–pembahasan–penutup, "
            "aturan datang dari dosen pengampu."
        ),
        fitur_utama=(
            "Generator Outline",
            "Lanjutan Kalimat",
            "Sitasi Otomatis",
            "Bahasa Akademik Indonesia",
            "Ekspor Multi-format",
        ),
        structure=STRUKTUR_PENDEK,
        default_target_words=2500,
    ),
    "laporan": WorkType(
        key="laporan",
        label="Laporan praktikum, kerja praktik, magang",
        family=Family.PENDEK,
        ciri_khas="Struktur baku dari program studi, banyak tabel, gambar, dan lampiran.",
        fitur_utama=(
            "Pedoman Kampus sebagai Basis",
            "Auto-Format Dokumen",
            "Tabel & Narasi Hasil",
            "Penomoran caption",
        ),
        structure=STRUKTUR_LAPORAN,
        default_target_words=6000,
    ),
    "kti_lomba": WorkType(
        key="kti_lomba",
        label="Karya tulis ilmiah lomba",
        family=Family.PENDEK,
        ciri_khas="Format ditentukan panitia, batas halaman ketat, sering ditulis beregu.",
        fitur_utama=(
            "Pedoman lomba",
            "Cek Batas Panjang",
            "Cek Kemiripan Mandiri",
            "Manajemen Proyek",
        ),
        structure=STRUKTUR_LAPORAN,
        default_target_words=5000,
    ),
    "esai": WorkType(
        key="esai",
        label="Esai ilmiah & artikel opini",
        family=Family.PENDEK,
        ciri_khas="Argumentatif, sitasi lebih ringan, penekanan pada alur logika.",
        fitur_utama=("Cek Konsistensi", "Parafrase & Koreksi", "Bahasa Akademik Indonesia"),
        structure=STRUKTUR_ESAI,
        default_target_words=1800,
    ),
    "proposal": WorkType(
        key="proposal",
        label="Proposal penelitian",
        family=Family.TUGAS_AKHIR,
        ciri_khas="Berhenti di metodologi; harus meyakinkan bahwa penelitian layak dan baru.",
        fitur_utama=("Matriks Sintesis", "Pemandu Metodologi", "Pedoman Kampus sebagai Basis"),
        structure=STRUKTUR_PROPOSAL,
        default_target_words=9000,
        supervision_tracking=True,
    ),
    "tugas_akhir": WorkType(
        key="tugas_akhir",
        label="Skripsi, tesis, disertasi",
        family=Family.TUGAS_AKHIR,
        ciri_khas="Karya terpanjang, melalui bimbingan berkali-kali dan sidang.",
        fitur_utama=("Seluruh fitur", "Pelacak Bimbingan", "Mode Siap Sidang"),
        structure=STRUKTUR_TUGAS_AKHIR,
        default_target_words=18000,
        supervision_tracking=True,
        defense_mode=True,
    ),
    "artikel_jurnal": WorkType(
        key="artikel_jurnal",
        label="Artikel jurnal ilmiah",
        family=Family.PUBLIKASI,
        ciri_khas=(
            "Struktur IMRAD, batas kata ketat, aturan dari pedoman penulis jurnal, "
            "melalui peer review."
        ),
        fitur_utama=(
            "Template Jurnal Tujuan",
            "Abstrak Terstruktur",
            "Cover Letter",
            "Respon Reviewer",
        ),
        structure=STRUKTUR_IMRAD,
        default_target_words=6000,
        hard_word_limit=8000,
        export_formats=("docx", "pdf", "latex"),
        submission_kit=True,
    ),
    "prosiding": WorkType(
        key="prosiding",
        label="Artikel prosiding konferensi",
        family=Family.PUBLIKASI,
        ciri_khas=(
            "Lebih ringkas dari artikel jurnal, tenggat submisi ketat, template dari "
            "penyelenggara."
        ),
        fitur_utama=("Template konferensi", "Cek Batas Panjang", "Ekspor LaTeX"),
        structure=STRUKTUR_IMRAD,
        default_target_words=4000,
        hard_word_limit=5000,
        citation_style="ieee",
        export_formats=("docx", "pdf", "latex"),
        submission_kit=True,
    ),
    "tinjauan_pustaka": WorkType(
        key="tinjauan_pustaka",
        label="Artikel tinjauan pustaka",
        family=Family.PUBLIKASI,
        ciri_khas=(
            "Tidak mengumpulkan data primer; nilainya ada pada kualitas sintesis literatur."
        ),
        fitur_utama=("Pencarian Literatur", "Matriks Sintesis", "Tinjauan sistematis"),
        structure=STRUKTUR_TINJAUAN,
        default_target_words=7000,
        hard_word_limit=9000,
        export_formats=("docx", "pdf", "latex"),
        submission_kit=True,
    ),
}


class ResearchType(str, Enum):
    """Jenis penelitian (Bagian 5.1). Menentukan cakupan analisis yang tersedia."""

    NONE = "none"
    KUANTITATIF_DESKRIPTIF = "kuantitatif_deskriptif"
    KUANTITATIF_ASOSIATIF = "kuantitatif_asosiatif"
    KOMPARATIF = "komparatif"
    SEM_PLS = "sem_pls"
    KUALITATIF = "kualitatif"
    CAMPURAN = "campuran"
    EKSPERIMEN_RND = "eksperimen_rnd"


RESEARCH_TYPE_LABELS: dict[ResearchType, str] = {
    ResearchType.NONE: "Tanpa data penelitian",
    ResearchType.KUANTITATIF_DESKRIPTIF: "Kuantitatif deskriptif",
    ResearchType.KUANTITATIF_ASOSIATIF: "Kuantitatif asosiatif",
    ResearchType.KOMPARATIF: "Komparatif",
    ResearchType.SEM_PLS: "SEM & PLS",
    ResearchType.KUALITATIF: "Kualitatif",
    ResearchType.CAMPURAN: "Campuran",
    ResearchType.EKSPERIMEN_RND: "Eksperimen & R&D",
}

#: Kebutuhan analisis per jenis penelitian (tabel 5.1).
RESEARCH_NEEDS: dict[ResearchType, str] = {
    ResearchType.NONE: "—",
    ResearchType.KUANTITATIF_DESKRIPTIF: (
        "Statistik deskriptif, distribusi frekuensi, tabulasi silang, kategorisasi "
        "jawaban responden."
    ),
    ResearchType.KUANTITATIF_ASOSIATIF: (
        "Uji validitas dan reliabilitas, uji asumsi klasik, korelasi, regresi sederhana "
        "dan berganda, uji t, uji F, koefisien determinasi."
    ),
    ResearchType.KOMPARATIF: (
        "Uji beda dua atau lebih kelompok, ANOVA, serta padanan non-parametriknya."
    ),
    ResearchType.SEM_PLS: (
        "Model pengukuran, model struktural, uji jalur, variabel mediasi dan moderasi."
    ),
    ResearchType.KUALITATIF: (
        "Pengodean transkrip, penyusunan tema, reduksi data, triangulasi, penyajian "
        "kutipan informan."
    ),
    ResearchType.CAMPURAN: (
        "Penggabungan temuan kuantitatif dan kualitatif dalam satu pembahasan."
    ),
    ResearchType.EKSPERIMEN_RND: (
        "Uji pretest-posttest, uji efektivitas, validasi ahli, dan uji kelayakan produk."
    ),
}


def get_work_type(key: str) -> WorkType:
    try:
        return WORK_TYPES[key]
    except KeyError:
        raise ValueError(
            f"Jenis karya '{key}' tidak dikenal. Pilihan: {', '.join(sorted(WORK_TYPES))}"
        ) from None


def requires_data_step(work_type: WorkType, research_type: ResearchType) -> bool:
    """Apakah langkah 6 (olah data) wajib untuk kombinasi ini."""
    mode = work_type.steps["olah_data"]
    if mode is StepMode.YA:
        return True
    if mode is StepMode.BERSYARAT:
        return research_type is not ResearchType.NONE
    return False


def applicable_steps(work_type: WorkType, research_type: ResearchType) -> list[dict]:
    """Daftar delapan langkah beserta status pemakaiannya untuk proyek ini."""
    result = []
    for step in STEPS:
        mode = work_type.steps[step.key]
        if step.key == "olah_data" and mode is StepMode.BERSYARAT:
            active = research_type is not ResearchType.NONE
        else:
            active = mode is not StepMode.OPSIONAL
        result.append(
            {
                "number": step.number,
                "key": step.key,
                "title": step.title,
                "summary": step.summary,
                "mode": mode.value,
                "active": active,
                "note": work_type.step_note(step.key),
            }
        )
    return result
