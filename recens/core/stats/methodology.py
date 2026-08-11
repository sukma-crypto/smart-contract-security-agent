"""Pemandu metodologi — menjawab kebingungan paling umum di BAB III.

Pemilihan uji statistik bukan soal selera: ia mengikuti pertanyaan penelitian,
skala data, jumlah kelompok, dan sebaran data. Karena itu pemandu ini berupa
pohon keputusan yang eksplisit dan bisa diperiksa, bukan tebakan model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class Purpose(str, Enum):
    DESKRIPSI = "deskripsi"
    HUBUNGAN = "hubungan"
    PENGARUH = "pengaruh"
    PERBEDAAN = "perbedaan"
    MEDIASI_MODERASI = "mediasi_moderasi"
    PENGEMBANGAN = "pengembangan"
    EKSPLORASI = "eksplorasi"


class Scale(str, Enum):
    NOMINAL = "nominal"
    ORDINAL = "ordinal"
    INTERVAL = "interval"
    RASIO = "rasio"


PURPOSE_LABELS = {
    Purpose.DESKRIPSI: "Menggambarkan keadaan satu variabel apa adanya",
    Purpose.HUBUNGAN: "Menguji keeratan hubungan antarvariabel",
    Purpose.PENGARUH: "Menguji pengaruh variabel bebas terhadap variabel terikat",
    Purpose.PERBEDAAN: "Membandingkan dua kelompok atau lebih",
    Purpose.MEDIASI_MODERASI: "Menguji peran variabel mediasi atau moderasi",
    Purpose.PENGEMBANGAN: "Mengembangkan produk dan menguji kelayakannya",
    Purpose.EKSPLORASI: "Menggali makna, proses, atau pengalaman informan",
}


@dataclass
class Recommendation:
    design: str
    approach: str
    tests: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    instrument: str = ""
    sampling: str = ""
    reasoning: list[str] = field(default_factory=list)
    cautions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "design": self.design,
            "approach": self.approach,
            "tests": self.tests,
            "prerequisites": self.prerequisites,
            "instrument": self.instrument,
            "sampling": self.sampling,
            "reasoning": self.reasoning,
            "cautions": self.cautions,
        }


def recommend(
    purpose: str,
    dependent_scale: str = "interval",
    n_independent: int = 1,
    n_groups: int = 2,
    paired: bool = False,
    normal: bool | None = None,
    sample_size: int | None = None,
    latent_variables: bool = False,
) -> Recommendation:
    """Pilih rancangan dan rangkaian uji yang sesuai dengan pertanyaan penelitian."""
    purpose_enum = Purpose(purpose)
    scale = Scale(dependent_scale)
    reasoning: list[str] = [
        f"Tujuan penelitian: {PURPOSE_LABELS[purpose_enum].lower()}.",
        f"Skala data variabel terikat: {scale.value}.",
    ]
    cautions: list[str] = []
    parametric_ok = scale in (Scale.INTERVAL, Scale.RASIO)

    if normal is False and parametric_ok:
        cautions.append(
            "Data tidak berdistribusi normal, sehingga uji parametrik diganti "
            "padanan non-parametriknya."
        )
        parametric_ok = False
    if sample_size is not None and sample_size < 30 and normal is None:
        cautions.append(
            f"Jumlah sampel {sample_size} tergolong kecil; uji normalitas wajib "
            f"dijalankan lebih dahulu sebelum memilih uji parametrik."
        )

    if purpose_enum is Purpose.EKSPLORASI:
        return Recommendation(
            design="Penelitian kualitatif (studi kasus, fenomenologi, atau naratif)",
            approach="kualitatif",
            tests=["Pengodean terbuka", "Penyusunan tema", "Triangulasi sumber"],
            prerequisites=["Transkrip wawancara yang sudah diketik lengkap"],
            instrument="Pedoman wawancara semi-terstruktur dan catatan lapangan",
            sampling="Purposive sampling atau snowball sampling",
            reasoning=reasoning
            + ["Pertanyaan penelitian menuntut kedalaman makna, bukan generalisasi angka."],
            cautions=cautions,
        )

    if purpose_enum is Purpose.PENGEMBANGAN:
        return Recommendation(
            design="Research and Development (ADDIE atau 4-D)",
            approach="kuantitatif deskriptif",
            tests=["Validasi ahli (Aiken's V)", "Uji kelayakan pengguna", "Uji N-Gain"],
            prerequisites=["Lembar validasi ahli", "Skor pretest dan posttest"],
            instrument="Lembar validasi ahli dan angket respons pengguna",
            sampling="Purposive sampling untuk ahli, cluster untuk pengguna",
            reasoning=reasoning + ["Produk harus dinilai kelayakannya sebelum diuji efektivitas."],
            cautions=cautions,
        )

    if purpose_enum is Purpose.DESKRIPSI:
        tests = ["Statistik deskriptif", "Distribusi frekuensi", "Kategorisasi jawaban responden"]
        if scale in (Scale.NOMINAL, Scale.ORDINAL):
            tests.append("Tabulasi silang")
        return Recommendation(
            design="Penelitian kuantitatif deskriptif",
            approach="kuantitatif deskriptif",
            tests=tests,
            prerequisites=["Instrumen yang sudah diuji validitas dan reliabilitasnya"],
            instrument="Kuesioner tertutup dengan skala Likert",
            sampling="Simple random sampling bila kerangka sampel tersedia",
            reasoning=reasoning + ["Tidak ada hipotesis hubungan yang perlu diuji."],
            cautions=cautions,
        )

    if purpose_enum is Purpose.MEDIASI_MODERASI or latent_variables:
        return Recommendation(
            design="Penelitian kuantitatif asosiatif dengan variabel laten",
            approach="SEM-PLS",
            tests=[
                "Model pengukuran: outer loading, AVE, Composite Reliability",
                "Validitas diskriminan Fornell-Larcker",
                "Model struktural: R², path coefficient, bootstrapping",
                "Uji efek mediasi atau moderasi",
            ],
            prerequisites=["Instrumen dengan indikator reflektif atau formatif yang jelas"],
            instrument="Kuesioner dengan beberapa indikator per konstruk",
            sampling="Purposive sampling; minimal 10× jalur terbanyak menuju satu konstruk",
            reasoning=reasoning
            + ["Variabel diukur lewat indikator, dan model memuat jalur tidak langsung."],
            cautions=cautions
            + [
                "Recens membaca keluaran SmartPLS atau Lisrel dan menghitung AVE serta CR "
                "dari nilai loading; estimasi model tetap dijalankan di perangkat tersebut."
            ],
        )

    if purpose_enum is Purpose.PERBEDAAN:
        if paired:
            test = "Uji t berpasangan" if parametric_ok else "Uji Wilcoxon Signed Rank"
            reasoning.append("Pengukuran dilakukan pada subjek yang sama sebelum dan sesudah.")
        elif n_groups <= 2:
            test = "Uji t sampel bebas" if parametric_ok else "Uji Mann-Whitney U"
            reasoning.append("Dua kelompok yang saling bebas dibandingkan.")
        else:
            test = "ANOVA satu jalur" if parametric_ok else "Uji Kruskal-Wallis"
            reasoning.append(f"Terdapat {n_groups} kelompok yang dibandingkan sekaligus.")

        prerequisites = ["Uji validitas dan reliabilitas instrumen"]
        if parametric_ok:
            prerequisites += ["Uji normalitas", "Uji homogenitas varian (Levene)"]
        tests = [test]
        if not paired and n_groups > 2 and parametric_ok:
            tests.append("Uji lanjut Tukey HSD bila ANOVA signifikan")

        return Recommendation(
            design="Penelitian komparatif" + (" (pretest-posttest)" if paired else ""),
            approach="kuantitatif komparatif",
            tests=tests,
            prerequisites=prerequisites,
            instrument="Tes hasil belajar atau kuesioner, sesuai variabel yang diukur",
            sampling="Cluster random sampling atau purposive sampling",
            reasoning=reasoning,
            cautions=cautions,
        )

    if purpose_enum is Purpose.HUBUNGAN:
        if scale in (Scale.NOMINAL,):
            test = "Uji chi-square"
        elif scale is Scale.ORDINAL or not parametric_ok:
            test = "Korelasi Rank Spearman"
        else:
            test = "Korelasi Product Moment Pearson"
        return Recommendation(
            design="Penelitian kuantitatif asosiatif (korelasional)",
            approach="kuantitatif asosiatif",
            tests=[test],
            prerequisites=["Uji validitas dan reliabilitas", "Uji normalitas"]
            if parametric_ok
            else ["Uji validitas dan reliabilitas"],
            instrument="Kuesioner tertutup dengan skala Likert",
            sampling="Simple random sampling atau proportionate stratified random sampling",
            reasoning=reasoning
            + ["Yang diuji adalah keeratan hubungan, bukan arah pengaruh."],
            cautions=cautions
            + ["Hubungan yang signifikan tidak dengan sendirinya berarti sebab-akibat."],
        )

    # Purpose.PENGARUH
    tests = [
        "Regresi linear sederhana" if n_independent == 1 else "Regresi linear berganda",
        "Uji t (parsial)",
        "Koefisien determinasi (R²)",
    ]
    if n_independent > 1:
        tests.insert(1, "Uji F (simultan)")
    prerequisites = [
        "Uji validitas dan reliabilitas instrumen",
        "Uji normalitas residual",
    ]
    if n_independent > 1:
        prerequisites.append("Uji multikolinearitas (VIF dan tolerance)")
    prerequisites += ["Uji heteroskedastisitas (Glejser)", "Uji autokorelasi (Durbin-Watson)"]

    reasoning.append(
        f"Terdapat {n_independent} variabel bebas yang diuji pengaruhnya terhadap satu "
        f"variabel terikat."
    )
    if not parametric_ok:
        cautions.append(
            "Skala data variabel terikat belum interval/rasio; pertimbangkan regresi "
            "ordinal atau regresi logistik."
        )

    return Recommendation(
        design="Penelitian kuantitatif asosiatif (kausal)",
        approach="kuantitatif asosiatif",
        tests=tests,
        prerequisites=prerequisites,
        instrument="Kuesioner tertutup dengan skala Likert 1–5",
        sampling="Proportionate stratified random sampling atau purposive sampling",
        reasoning=reasoning,
        cautions=cautions,
    )


# --- Penentuan ukuran sampel -------------------------------------------------


def slovin(population: int, margin_of_error: float = 0.05) -> dict:
    """Rumus Slovin: n = N / (1 + N·e²)."""
    if population <= 0:
        raise ValueError("Jumlah populasi harus lebih besar dari nol.")
    n = population / (1 + population * margin_of_error**2)
    return {
        "formula": "n = N / (1 + N·e²)",
        "population": population,
        "margin_of_error": margin_of_error,
        "sample_size": math.ceil(n),
        "exact": round(n, 2),
        "narrative": (
            f"Dengan populasi sebanyak {population} orang dan taraf kesalahan "
            f"{margin_of_error * 100:.0f}%, diperoleh ukuran sampel minimal "
            f"{math.ceil(n)} responden."
        ),
    }


def sample_size_for_regression(n_predictors: int) -> dict:
    """Aturan praktis Green: n ≥ 50 + 8m untuk uji simultan."""
    minimum = 50 + 8 * n_predictors
    return {
        "formula": "n ≥ 50 + 8m",
        "n_predictors": n_predictors,
        "sample_size": minimum,
        "narrative": (
            f"Untuk regresi dengan {n_predictors} variabel bebas, ukuran sampel minimal "
            f"yang disarankan adalah {minimum} responden."
        ),
    }


SAMPLING_TECHNIQUES = {
    "simple_random": {
        "label": "Simple random sampling",
        "when": "Populasi homogen dan kerangka sampel lengkap tersedia.",
    },
    "stratified": {
        "label": "Proportionate stratified random sampling",
        "when": "Populasi berlapis, mis. angkatan atau kelas, dan tiap lapis perlu terwakili.",
    },
    "cluster": {
        "label": "Cluster random sampling",
        "when": "Populasi tersebar dalam kelompok alami seperti sekolah atau desa.",
    },
    "purposive": {
        "label": "Purposive sampling",
        "when": "Responden dipilih karena memenuhi kriteria tertentu; lazim pada kualitatif.",
    },
    "snowball": {
        "label": "Snowball sampling",
        "when": "Populasi sulit dijangkau dan informan merujuk informan berikutnya.",
    },
    "accidental": {
        "label": "Accidental/incidental sampling",
        "when": "Kerangka sampel tidak tersedia; keterwakilan harus dibahas sebagai keterbatasan.",
    },
    "total": {
        "label": "Sampling jenuh (sensus)",
        "when": "Seluruh anggota populasi dijadikan sampel karena jumlahnya kecil.",
    },
}
