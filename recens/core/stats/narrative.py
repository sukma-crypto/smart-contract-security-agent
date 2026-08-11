"""Tabel & narasi hasil — mengubah tumpukan angka menjadi paragraf BAB IV.

Modul ini juga memuat penjaga yang membuat janji "angka dihitung mesin, model
hanya menyusun kalimat" bisa ditegakkan, bukan sekadar dijanjikan: setiap angka
yang muncul di narasi ditelusuri balik ke hasil perhitungan. Angka yang tidak
tertelusur ditandai dan kalimatnya ditolak.
"""

from __future__ import annotations

import math
import re

from .engine import AnalysisResult, Table, format_id, to_indonesian_decimals  # noqa: F401

#: Ambang dan konstanta yang lazim ditulis di kalimat pembahasan, bukan hasil hitung.
CONVENTIONAL_NUMBERS = {
    0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 100.0,
    0.05, 0.01, 0.001, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,
    1.5, 1.96, 2.5, 30.0, 50.0, 95.0, 99.0,
}

NUMBER_TOKEN = re.compile(r"(?<![\w.,])(-?\d+(?:[.,]\d+)?)(?![\w])")


def parse_numbers(text: str) -> list[float]:
    """Ambil seluruh angka dari narasi, menerima koma maupun titik desimal."""
    return [value for value, _decimals in parse_numbers_with_precision(text)]


def parse_numbers_with_precision(text: str) -> list[tuple[float, int]]:
    """Angka beserta jumlah desimal yang benar-benar ditulis di narasi.

    Ketelitian penulisan ikut dibawa karena ia menentukan seberapa ketat sebuah
    angka boleh dicocokkan: "81,46" wajar merujuk 81,456, tetapi "0,9991" tidak
    wajar merujuk 1,0.
    """
    found = []
    for raw in NUMBER_TOKEN.findall(text or ""):
        cleaned = raw.replace(",", ".")
        try:
            value = float(cleaned)
        except ValueError:
            continue
        decimals = len(cleaned.split(".")[1]) if "." in cleaned else 0
        found.append((value, decimals))
    return found


def untraceable_numbers(
    text: str, result: AnalysisResult, tolerance: float = 5e-4
) -> list[float]:
    """Angka di narasi yang tidak bisa ditelusuri ke hasil perhitungan.

    Inilah pemeriksaan yang menutup celah paling berbahaya: model yang menulis
    "R² sebesar 0,812" padahal mesin menghitung 0,741. Kalimat seperti itu tidak
    diloloskan.
    """
    computed = set(result.all_numbers())
    for value in result.params.values():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            computed.add(round(float(value), 6))

    # Bentuk persen dari tiap angka ikut diterima. "R² sebesar 0,887 yang berarti
    # menjelaskan 88,7% variasi" adalah satu angka yang sama dinyatakan dua kali,
    # bukan angka baru — dan begitulah cara orang menulis Bab 4. Tanpa ini
    # penjaga menolak narasi yang justru benar, dan penolakan palsu yang sering
    # terjadi akan membuat penjaganya dimatikan orang.
    computed |= {round(candidate * 100, 6) for candidate in tuple(computed)}

    flagged = []
    for number, decimals in parse_numbers_with_precision(text):
        # Sebuah angka tertelusur bila ia sama dengan angka hasil hitung ketika
        # keduanya dibulatkan ke ketelitian yang dipakai narasi. Dengan begitu
        # "81,46" tetap cocok dengan 81,456, sementara "0,9991" tidak lolos
        # hanya karena dekat dengan 1,0.
        places = max(decimals, 0)
        target = round(number, places)
        if any(round(candidate, places) == target for candidate in computed):
            continue
        if any(
            math.isclose(number, candidate, rel_tol=0, abs_tol=tolerance)
            for candidate in computed
        ):
            continue
        # Ambang dan konstanta lazim harus cocok persis.
        if round(number, 6) in CONVENTIONAL_NUMBERS:
            continue
        flagged.append(number)
    return flagged


def is_traceable(text: str, result: AnalysisResult) -> bool:
    return not untraceable_numbers(text, result)


# --- Perakitan tabel dan narasi ---------------------------------------------


def table_to_block(table: Table, label: str | None = None) -> dict:
    """Ubah tabel hasil menjadi blok naskah yang bisa dinomori dan diformat."""
    return {
        "kind": "table",
        "content": table.title,
        "meta": {
            "caption": table.title,
            "label": label or _slug(table.title),
            "columns": table.columns,
            "rows": table.rows,
            "note": table.note,
        },
    }


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")[:40]


def result_to_blocks(result: AnalysisResult, include_narrative: bool = True) -> list[dict]:
    """Rakit satu hasil analisis menjadi urutan blok siap sisip ke BAB IV."""
    blocks: list[dict] = []
    for index, table in enumerate(result.tables):
        blocks.append(table_to_block(table, label=f"{result.method}_{index + 1}"))

    if include_narrative and result.findings:
        blocks.append(
            {
                "kind": "paragraph",
                "content": " ".join(result.findings),
                "meta": {"source": "analisis", "method": result.method, "generated": True},
            }
        )
    if result.warnings:
        blocks.append(
            {
                "kind": "paragraph",
                "content": " ".join(result.warnings),
                "meta": {"source": "analisis", "method": result.method, "kind": "catatan"},
            }
        )
    return blocks


def draft_narrative(result: AnalysisResult) -> str:
    """Draf narasi dasar yang seluruh angkanya berasal dari mesin statistik.

    Draf ini sudah bisa dipakai apa adanya. Model bahasa hanya memperhalus
    kalimatnya, dan hasil perhalusan itu tetap harus lolos ``is_traceable``.
    """
    parts = [f"{result.label} dijalankan dengan hasil sebagai berikut."]
    parts.extend(result.findings)
    if result.assumptions:
        parts.append("Ringkasan pemenuhan asumsi: " + "; ".join(result.assumptions) + ".")
    if result.warnings:
        parts.append("Catatan: " + " ".join(result.warnings))
    # Narasi masuk ke naskah berdampingan dengan tabelnya, jadi pemisah
    # desimalnya harus sama. Diterapkan pada teks jadi, bukan pada angkanya,
    # sehingga penjaga penelusuran tetap membandingkan bilangan sungguhan.
    return to_indonesian_decimals(" ".join(parts))


def assumption_summary(results: list[AnalysisResult]) -> dict:
    """Ringkas pemenuhan seluruh uji asumsi klasik dalam satu tabel."""
    rows = []
    for result in results:
        if result.method not in (
            "normality", "multicollinearity", "heteroscedasticity",
        ):
            continue
        for assumption in result.assumptions:
            status = "Terpenuhi" if "tidak terjadi" in assumption or "terpenuhi" in assumption else "Tidak terpenuhi"
            if "tidak terpenuhi" in assumption:
                status = "Tidak terpenuhi"
            rows.append([result.label, assumption, status])
    return {
        "columns": ["Uji", "Hasil", "Status"],
        "rows": rows,
        "all_met": all(row[2] == "Terpenuhi" for row in rows) if rows else None,
    }


def build_results_chapter(results: list[AnalysisResult]) -> list[dict]:
    """Susun seluruh hasil analisis menjadi rangkaian blok BAB IV."""
    blocks: list[dict] = []
    order = [
        "descriptive", "frequency", "crosstab", "categorize",
        "validity", "reliability",
        "normality", "multicollinearity", "heteroscedasticity",
        "correlation", "regression",
        "ttest_independent", "ttest_paired", "anova_oneway",
        "mann_whitney", "wilcoxon", "kruskal",
        "ngain", "aiken_v", "pls_measurement", "pls_structural",
    ]
    ranked = sorted(
        results, key=lambda r: order.index(r.method) if r.method in order else len(order)
    )
    for result in ranked:
        blocks.extend(result_to_blocks(result))
    return blocks
