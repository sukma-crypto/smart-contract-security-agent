"""Dua Bahasa: penerjemahan yang menjaga konsistensi istilah teknis.

Hampir semua kampus mewajibkan abstrak dwibahasa, dan di situlah istilah teknis
paling sering goyah: "uji reliabilitas" menjadi *reliability test* di satu
kalimat lalu *dependability test* di kalimat berikutnya. Penguji dan reviewer
membaca ketidakkonsistenan itu sebagai ketidakcermatan.

Karena itu bagian yang bisa dipastikan tidak diserahkan ke model: glosarium per
bidang ilmu ditegakkan sebagai daftar, dan hasil terjemahan diperiksa ulang
terhadapnya. Model menyusun kalimatnya; padanan istilahnya ditentukan glosarium.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Istilah metodologi penelitian — berlaku lintas bidang.
METODOLOGI: dict[str, str] = {
    "penelitian": "research",
    "penelitian ini": "this study",
    "populasi": "population",
    "sampel": "sample",
    "teknik pengambilan sampel": "sampling technique",
    "purposive sampling": "purposive sampling",
    "simple random sampling": "simple random sampling",
    "responden": "respondents",
    "informan": "informants",
    "instrumen penelitian": "research instrument",
    "kuesioner": "questionnaire",
    "angket": "questionnaire",
    "wawancara": "interview",
    "observasi": "observation",
    "dokumentasi": "documentation",
    "skala likert": "Likert scale",
    "variabel bebas": "independent variable",
    "variabel terikat": "dependent variable",
    "variabel mediasi": "mediating variable",
    "variabel moderasi": "moderating variable",
    "uji validitas": "validity test",
    "uji reliabilitas": "reliability test",
    "uji normalitas": "normality test",
    "uji multikolinearitas": "multicollinearity test",
    "uji heteroskedastisitas": "heteroscedasticity test",
    "uji autokorelasi": "autocorrelation test",
    "uji asumsi klasik": "classical assumption test",
    "uji hipotesis": "hypothesis testing",
    "analisis regresi linear berganda": "multiple linear regression analysis",
    "analisis regresi linear sederhana": "simple linear regression analysis",
    "regresi": "regression",
    "korelasi": "correlation",
    "koefisien determinasi": "coefficient of determination",
    "uji parsial": "partial test",
    "uji simultan": "simultaneous test",
    "signifikan": "significant",
    "tidak signifikan": "not significant",
    "taraf signifikansi": "significance level",
    "hipotesis": "hypothesis",
    "kerangka berpikir": "conceptual framework",
    "landasan teori": "theoretical foundation",
    "tinjauan pustaka": "literature review",
    "penelitian terdahulu": "previous studies",
    "celah penelitian": "research gap",
    "rumusan masalah": "research problem",
    "tujuan penelitian": "research objective",
    "manfaat penelitian": "research benefit",
    "metode penelitian": "research method",
    "pendekatan kuantitatif": "quantitative approach",
    "pendekatan kualitatif": "qualitative approach",
    "metode campuran": "mixed methods",
    "studi kasus": "case study",
    "deskriptif": "descriptive",
    "asosiatif": "associative",
    "komparatif": "comparative",
    "triangulasi": "triangulation",
    "pengodean": "coding",
    "reduksi data": "data reduction",
    "temuan": "findings",
    "simpulan": "conclusion",
    "kesimpulan": "conclusion",
    "saran": "recommendation",
    "keterbatasan penelitian": "research limitation",
    "implikasi": "implication",
    "kebaruan": "novelty",
    "data primer": "primary data",
    "data sekunder": "secondary data",
    "uji beda": "difference test",
    "uji t": "t-test",
    "uji f": "F-test",
    "analisis jalur": "path analysis",
    "validitas konvergen": "convergent validity",
    "validitas diskriminan": "discriminant validity",
}

#: Istilah per bidang ilmu.
BIDANG: dict[str, dict[str, str]] = {
    "manajemen": {
        "kinerja karyawan": "employee performance",
        "kepuasan kerja": "job satisfaction",
        "motivasi kerja": "work motivation",
        "budaya organisasi": "organizational culture",
        "gaya kepemimpinan": "leadership style",
        "lingkungan kerja": "work environment",
        "disiplin kerja": "work discipline",
        "kompensasi": "compensation",
        "produktivitas": "productivity",
        "loyalitas": "loyalty",
        "kepuasan pelanggan": "customer satisfaction",
        "keputusan pembelian": "purchase decision",
        "citra merek": "brand image",
        "kualitas pelayanan": "service quality",
        "sumber daya manusia": "human resources",
    },
    "akuntansi": {
        "laporan keuangan": "financial statements",
        "profitabilitas": "profitability",
        "likuiditas": "liquidity",
        "solvabilitas": "solvency",
        "nilai perusahaan": "firm value",
        "struktur modal": "capital structure",
        "audit": "audit",
        "kualitas audit": "audit quality",
        "manajemen laba": "earnings management",
        "kepatuhan pajak": "tax compliance",
        "pengendalian internal": "internal control",
    },
    "pendidikan": {
        "hasil belajar": "learning outcomes",
        "motivasi belajar": "learning motivation",
        "prestasi belajar": "academic achievement",
        "model pembelajaran": "learning model",
        "media pembelajaran": "learning media",
        "kurikulum": "curriculum",
        "peserta didik": "students",
        "keaktifan siswa": "student engagement",
        "kemampuan berpikir kritis": "critical thinking skills",
        "bahan ajar": "teaching materials",
        "uji kelayakan": "feasibility test",
        "validasi ahli": "expert validation",
    },
    "kesehatan": {
        "kepatuhan": "adherence",
        "pengetahuan": "knowledge",
        "sikap": "attitude",
        "perilaku": "behavior",
        "kualitas hidup": "quality of life",
        "tenaga kesehatan": "health workers",
        "pelayanan kesehatan": "health services",
        "faktor risiko": "risk factors",
        "prevalensi": "prevalence",
        "insidensi": "incidence",
    },
    "psikologi": {
        "kesejahteraan psikologis": "psychological well-being",
        "harga diri": "self-esteem",
        "efikasi diri": "self-efficacy",
        "dukungan sosial": "social support",
        "kecemasan": "anxiety",
        "regulasi diri": "self-regulation",
        "resiliensi": "resilience",
        "kematangan emosi": "emotional maturity",
    },
    "teknik": {
        "perancangan": "design",
        "pengujian": "testing",
        "sistem informasi": "information system",
        "perangkat lunak": "software",
        "antarmuka pengguna": "user interface",
        "kinerja sistem": "system performance",
        "efisiensi": "efficiency",
        "optimasi": "optimization",
        "kekuatan tekan": "compressive strength",
    },
    "hukum": {
        "perlindungan hukum": "legal protection",
        "kepastian hukum": "legal certainty",
        "penegakan hukum": "law enforcement",
        "peraturan perundang-undangan": "legislation",
        "putusan pengadilan": "court decision",
        "tanggung jawab hukum": "legal liability",
        "asas": "principle",
        "yuridis normatif": "normative juridical",
    },
}


@dataclass
class TermIssue:
    term_id: str
    expected_en: str
    found: list[str] = field(default_factory=list)
    kind: str = "hilang"  # hilang | tidak_konsisten

    def to_dict(self) -> dict:
        return {
            "term_id": self.term_id,
            "expected_en": self.expected_en,
            "found": self.found,
            "kind": self.kind,
            "message": (
                f"Istilah '{self.term_id}' seharusnya diterjemahkan menjadi "
                f"'{self.expected_en}'"
                + (
                    f", tetapi tidak ditemukan di versi Inggris."
                    if self.kind == "hilang"
                    else f", tetapi ditulis sebagai: {', '.join(self.found)}."
                )
            ),
        }


def build_glossary(field_of_study: str | None = None) -> dict[str, str]:
    """Glosarium metodologi ditambah istilah bidang ilmu terkait."""
    glossary = dict(METODOLOGI)
    if field_of_study:
        key = field_of_study.strip().lower()
        for name, terms in BIDANG.items():
            if name in key or key in name:
                glossary.update(terms)
    return glossary


def find_terms(text: str, glossary: dict[str, str]) -> list[tuple[str, str]]:
    """Istilah glosarium yang muncul di teks, terpanjang lebih dahulu.

    Urutan terpanjang penting: "uji validitas" harus dikenali sebagai satu
    istilah, bukan sebagai "uji" ditambah "validitas".
    """
    lowered = (text or "").lower()
    found: list[tuple[str, str]] = []
    consumed: list[tuple[int, int]] = []

    for term in sorted(glossary, key=len, reverse=True):
        for match in re.finditer(rf"\b{re.escape(term)}\b", lowered):
            span = (match.start(), match.end())
            if any(span[0] < end and start < span[1] for start, end in consumed):
                continue
            consumed.append(span)
            found.append((term, glossary[term]))
    return found


def check_translation(
    indonesian: str, english: str, field_of_study: str | None = None
) -> dict:
    """Periksa apakah istilah teknis diterjemahkan konsisten sesuai glosarium."""
    glossary = build_glossary(field_of_study)
    terms = find_terms(indonesian, glossary)
    english_lower = (english or "").lower()

    issues: list[TermIssue] = []
    checked: set[str] = set()
    for term_id, expected in terms:
        if term_id in checked:
            continue
        checked.add(term_id)
        if re.search(rf"\b{re.escape(expected.lower())}\b", english_lower):
            continue
        issues.append(TermIssue(term_id=term_id, expected_en=expected, kind="hilang"))

    return {
        "field_of_study": field_of_study,
        "terms_detected": len(checked),
        "terms_consistent": len(checked) - len(issues),
        "issues": [i.to_dict() for i in issues],
        "glossary_used": {t: glossary[t] for t in checked},
        "passed": not issues,
    }


def glossary_hint(text: str, field_of_study: str | None = None) -> str:
    """Daftar padanan wajib untuk disertakan ke model penerjemah."""
    glossary = build_glossary(field_of_study)
    terms = find_terms(text, glossary)
    if not terms:
        return ""
    unique = dict(terms)
    lines = "\n".join(f"- {source} → {target}" for source, target in unique.items())
    return (
        "Padanan istilah yang WAJIB dipakai persis seperti di bawah ini "
        f"(jangan memakai sinonim lain):\n{lines}"
    )


def apply_glossary(text: str, field_of_study: str | None = None) -> str:
    """Terjemahan kasar berbasis glosarium, untuk jalur tanpa model bahasa.

    Hasilnya bukan kalimat Inggris yang mengalir — ia daftar padanan istilah
    yang sudah pasti benar. Menyatakannya apa adanya lebih berguna daripada
    menyajikan terjemahan mesin yang istilah teknisnya justru meleset.
    """
    glossary = build_glossary(field_of_study)
    terms = find_terms(text, glossary)
    if not terms:
        return ""
    unique = dict(terms)
    return "\n".join(f"{source} = {target}" for source, target in unique.items())
