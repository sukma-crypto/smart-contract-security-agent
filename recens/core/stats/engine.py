"""Mesin statistik: uji instrumen, asumsi klasik, komparatif, dan regresi.

Setiap fungsi mengembalikan ``AnalysisResult`` yang memuat tabel siap format,
angka mentah, dan temuan faktual yang diturunkan langsung dari angka tersebut.

Dua hal yang dijaga modul ini:

1. Angka dihitung, bukan diperkirakan. Tidak ada jalur kode yang menerima nilai
   statistik dari luar mesin ini.
2. Hasil yang tidak signifikan dilaporkan apa adanya. Tidak ada parameter yang
   bisa membuat sebuah uji "diterima" bila datanya tidak mendukung.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats as sps

ALPHA_DEFAULT = 0.05


class AnalysisError(ValueError):
    """Kesalahan yang bisa dijelaskan ke pengguna, mis. kolom tidak ditemukan."""


@dataclass
class Table:
    """Tabel hasil yang sudah siap dirakit ke format kampus."""

    title: str
    columns: list[str]
    rows: list[list[Any]]
    note: str = ""

    def to_dict(self) -> dict:
        return {"title": self.title, "columns": self.columns, "rows": self.rows, "note": self.note}


@dataclass
class AnalysisResult:
    method: str
    label: str
    params: dict = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)
    #: Angka kunci hasil perhitungan — sumber kebenaran bagi narasi.
    values: dict = field(default_factory=dict)
    #: Pernyataan faktual yang mengikuti langsung dari angka.
    findings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "label": self.label,
            "params": self.params,
            "tables": [t.to_dict() for t in self.tables],
            "values": self.values,
            "findings": self.findings,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
        }

    def all_numbers(self) -> set[float]:
        """Seluruh angka yang benar-benar dihitung.

        Dipakai penjaga penelusuran: setiap angka yang muncul di narasi harus
        ada di himpunan ini.
        """
        found: set[float] = set()

        def collect(value: Any) -> None:
            if isinstance(value, bool):
                return
            if isinstance(value, (int, float, np.integer, np.floating)):
                if not (isinstance(value, float) and math.isnan(value)):
                    found.add(round(float(value), 6))
            elif isinstance(value, dict):
                for item in value.values():
                    collect(item)
            elif isinstance(value, (list, tuple, set)):
                for item in value:
                    collect(item)

        collect(self.values)
        for table in self.tables:
            collect(table.rows)
        return found


# --- Pembantu ----------------------------------------------------------------


def _r(value: Any, digits: int = 3) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise AnalysisError(
            f"Kolom tidak ditemukan pada data: {', '.join(missing)}. "
            f"Kolom yang tersedia: {', '.join(map(str, frame.columns))}."
        )
    return list(columns)


def _numeric(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    subset = frame[list(columns)].apply(pd.to_numeric, errors="coerce")
    return subset


def _sig(p: float, alpha: float = ALPHA_DEFAULT) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "tidak dapat dihitung"
    return "signifikan" if p < alpha else "tidak signifikan"


def _p_label(p: float) -> str:
    if p is None or math.isnan(p):
        return "-"
    return "< 0,001" if p < 0.001 else f"{p:.3f}".replace(".", ",")


def r_table(n: int, alpha: float = ALPHA_DEFAULT, two_tailed: bool = True) -> float:
    """Nilai r tabel product moment untuk n responden.

    Dihitung dari distribusi t, bukan diambil dari tabel yang disalin manual:
    r = t / sqrt(df + t²) dengan df = n - 2.
    """
    df = n - 2
    if df <= 0:
        return float("nan")
    prob = 1 - alpha / 2 if two_tailed else 1 - alpha
    t_crit = float(sps.t.ppf(prob, df))
    return t_crit / math.sqrt(df + t_crit**2)


def t_table(df: int, alpha: float = ALPHA_DEFAULT, two_tailed: bool = True) -> float:
    prob = 1 - alpha / 2 if two_tailed else 1 - alpha
    return float(sps.t.ppf(prob, df)) if df > 0 else float("nan")


def f_table(df1: int, df2: int, alpha: float = ALPHA_DEFAULT) -> float:
    return float(sps.f.ppf(1 - alpha, df1, df2)) if df1 > 0 and df2 > 0 else float("nan")


# --- Statistik deskriptif ----------------------------------------------------


def descriptive(frame: pd.DataFrame, columns: list[str] | None = None) -> AnalysisResult:
    """Statistik deskriptif per variabel."""
    columns = _require_columns(frame, columns or list(frame.select_dtypes("number").columns))
    data = _numeric(frame, columns)
    if data.empty:
        raise AnalysisError("Tidak ada kolom numerik untuk dianalisis.")

    rows, values = [], {}
    for column in columns:
        series = data[column].dropna()
        n = int(series.size)
        if n == 0:
            continue
        mode_values = series.mode()
        stat = {
            "n": n,
            "missing": int(data[column].isna().sum()),
            "mean": float(series.mean()),
            "median": float(series.median()),
            "mode": float(mode_values.iloc[0]) if not mode_values.empty else None,
            "std": float(series.std(ddof=1)) if n > 1 else 0.0,
            "variance": float(series.var(ddof=1)) if n > 1 else 0.0,
            "se": float(series.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0,
            "min": float(series.min()),
            "max": float(series.max()),
            "range": float(series.max() - series.min()),
            "skewness": float(sps.skew(series, bias=False)) if n > 2 else None,
            "kurtosis": float(sps.kurtosis(series, bias=False)) if n > 3 else None,
        }
        values[column] = {k: _r(v) for k, v in stat.items()}
        rows.append(
            [
                column, stat["n"], stat["missing"], _r(stat["mean"]), _r(stat["median"]),
                _r(stat["mode"]), _r(stat["std"]), _r(stat["min"]), _r(stat["max"]),
                _r(stat["skewness"]), _r(stat["kurtosis"]),
            ]
        )

    table = Table(
        title="Statistik Deskriptif",
        columns=["Variabel", "N", "Missing", "Mean", "Median", "Modus", "Std. Deviasi",
                 "Minimum", "Maksimum", "Skewness", "Kurtosis"],
        rows=rows,
    )
    findings = [
        f"Variabel {col} memiliki rata-rata {_r(v['mean'])} dengan simpangan baku "
        f"{_r(v['std'])} pada rentang {_r(v['min'])} sampai {_r(v['max'])}."
        for col, v in values.items()
    ]
    return AnalysisResult(
        method="descriptive",
        label="Statistik deskriptif",
        params={"columns": columns},
        tables=[table],
        values=values,
        findings=findings,
    )


def frequency(frame: pd.DataFrame, column: str) -> AnalysisResult:
    """Distribusi frekuensi satu variabel."""
    _require_columns(frame, [column])
    series = frame[column].dropna()
    counts = series.value_counts().sort_index()
    total = int(counts.sum())
    rows, cumulative = [], 0.0
    for value, count in counts.items():
        percent = 100.0 * count / total if total else 0.0
        cumulative += percent
        rows.append([value, int(count), _r(percent, 1), _r(cumulative, 1)])

    return AnalysisResult(
        method="frequency",
        label=f"Distribusi frekuensi {column}",
        params={"column": column},
        tables=[
            Table(
                title=f"Distribusi Frekuensi {column}",
                columns=[column, "Frekuensi", "Persen (%)", "Persen Kumulatif (%)"],
                rows=rows,
            )
        ],
        values={
            "total": total,
            "missing": int(frame[column].isna().sum()),
            "categories": {str(k): int(v) for k, v in counts.items()},
        },
        findings=[
            f"Dari {total} responden, kategori terbanyak pada variabel {column} adalah "
            f"{counts.idxmax()} sebanyak {int(counts.max())} responden "
            f"({_r(100.0 * counts.max() / total, 1)}%)."
        ]
        if total
        else [],
    )


def crosstab(frame: pd.DataFrame, row: str, column: str) -> AnalysisResult:
    """Tabulasi silang dua variabel beserta uji chi-square."""
    _require_columns(frame, [row, column])
    table = pd.crosstab(frame[row], frame[column])
    if table.size == 0:
        raise AnalysisError("Tabulasi silang kosong.")

    chi2, p, dof, _expected = sps.chi2_contingency(table.values)
    n = int(table.values.sum())
    min_dim = min(table.shape) - 1
    cramers_v = math.sqrt(chi2 / (n * min_dim)) if n and min_dim > 0 else float("nan")

    rows = [[str(index)] + [int(v) for v in values] + [int(sum(values))]
            for index, values in zip(table.index, table.values)]
    rows.append(["Total"] + [int(v) for v in table.sum().values] + [n])

    return AnalysisResult(
        method="crosstab",
        label=f"Tabulasi silang {row} × {column}",
        params={"row": row, "column": column},
        tables=[
            Table(
                title=f"Tabulasi Silang {row} dan {column}",
                columns=[row] + [str(c) for c in table.columns] + ["Total"],
                rows=rows,
            )
        ],
        values={
            "chi_square": _r(chi2),
            "df": int(dof),
            "p_value": _r(p, 4),
            "n": n,
            "cramers_v": _r(cramers_v),
        },
        findings=[
            f"Uji chi-square menghasilkan χ² = {_r(chi2)} dengan df = {dof} dan "
            f"nilai signifikansi {_p_label(p)}, sehingga hubungan antara {row} dan "
            f"{column} {_sig(p)} pada taraf 5%."
        ],
    )


def categorize(
    frame: pd.DataFrame,
    columns: list[str],
    scale_min: float = 1,
    scale_max: float = 5,
    n_categories: int = 5,
    labels: list[str] | None = None,
) -> AnalysisResult:
    """Kategorisasi jawaban responden berdasarkan rata-rata skor.

    Panjang kelas interval dihitung (skala maksimum − skala minimum) / jumlah
    kategori, cara yang lazim dipakai pada analisis deskriptif kuesioner.
    """
    columns = _require_columns(frame, columns)
    data = _numeric(frame, columns)
    interval = (scale_max - scale_min) / n_categories
    default_labels = {
        3: ["Rendah", "Sedang", "Tinggi"],
        4: ["Tidak Baik", "Kurang Baik", "Baik", "Sangat Baik"],
        5: ["Sangat Rendah", "Rendah", "Sedang", "Tinggi", "Sangat Tinggi"],
    }
    labels = labels or default_labels.get(n_categories) or [
        f"Kategori {i + 1}" for i in range(n_categories)
    ]

    bounds = [(scale_min + i * interval, scale_min + (i + 1) * interval) for i in range(n_categories)]

    rows, values = [], {}
    for column in columns:
        mean = float(data[column].dropna().mean())
        index = min(int((mean - scale_min) / interval), n_categories - 1) if interval else 0
        index = max(index, 0)
        values[column] = {"mean": _r(mean), "category": labels[index]}
        rows.append([column, _r(mean), labels[index]])

    interval_rows = [
        [labels[i], f"{_r(low, 2)} – {_r(high, 2)}"] for i, (low, high) in enumerate(bounds)
    ]

    return AnalysisResult(
        method="categorize",
        label="Kategorisasi jawaban responden",
        params={
            "columns": columns, "scale_min": scale_min, "scale_max": scale_max,
            "n_categories": n_categories,
        },
        tables=[
            Table(
                title="Kelas Interval Kategori",
                columns=["Kategori", "Rentang Rata-rata"],
                rows=interval_rows,
                note=f"Panjang kelas interval = ({scale_max} − {scale_min}) / {n_categories} "
                     f"= {_r(interval, 2)}.",
            ),
            Table(
                title="Kategorisasi Variabel",
                columns=["Variabel", "Rata-rata", "Kategori"],
                rows=rows,
            ),
        ],
        values={"interval": _r(interval, 3), **values},
        findings=[
            f"Rata-rata variabel {col} sebesar {v['mean']} termasuk kategori "
            f"{v['category'].lower()}."
            for col, v in values.items()
        ],
    )


# --- Uji instrumen -----------------------------------------------------------


def validity_test(
    frame: pd.DataFrame,
    items: list[str],
    alpha: float = ALPHA_DEFAULT,
    corrected: bool = False,
) -> AnalysisResult:
    """Uji validitas butir kuesioner (korelasi product moment).

    ``corrected=True`` memakai corrected item-total correlation seperti keluaran
    Reliability Analysis SPSS; bawaannya memakai korelasi butir dengan skor
    total, konvensi yang paling umum dipakai pada skripsi.
    """
    items = _require_columns(frame, items)
    data = _numeric(frame, items).dropna()
    n = int(data.shape[0])
    if n < 3:
        raise AnalysisError(f"Uji validitas memerlukan minimal 3 responden lengkap; tersedia {n}.")

    total = data.sum(axis=1)
    critical = r_table(n, alpha)

    rows, values, invalid, inflated = [], {}, [], []
    for item in items:
        series = data[item]
        if series.std(ddof=1) == 0:
            rows.append([item, None, None, _r(critical), None, "Tidak dapat dihitung"])
            values[item] = {"r_hitung": None, "status": "tidak dapat dihitung"}
            continue

        # Korelasi butir dengan skor total, dan versi terkoreksi yang mengeluarkan
        # butir itu sendiri dari total. Keduanya selalu dihitung: yang pertama
        # adalah konvensi yang dipakai mayoritas skripsi, yang kedua lebih jujur
        # karena butir tidak ikut menaikkan korelasinya sendiri.
        r_uncorrected, p_uncorrected = sps.pearsonr(series, total)
        rest = total - series
        if rest.std(ddof=1) == 0:
            r_corrected, p_corrected = float("nan"), float("nan")
        else:
            r_corrected, p_corrected = sps.pearsonr(series, rest)

        r_value = r_corrected if corrected else r_uncorrected
        p_value = p_corrected if corrected else p_uncorrected
        valid = bool(r_value > critical and p_value < alpha)
        if not valid:
            invalid.append(item)
        elif not math.isnan(r_corrected) and r_corrected <= critical:
            # Butir lolos hanya karena ikut menyumbang skor totalnya sendiri.
            inflated.append(item)

        rows.append(
            [item, _r(r_uncorrected), _r(r_corrected), _r(critical), _p_label(p_value),
             "Valid" if valid else "Tidak valid"]
        )
        values[item] = {
            "r_hitung": _r(r_value),
            "r_item_total": _r(r_uncorrected),
            "r_item_total_terkoreksi": _r(r_corrected),
            "r_tabel": _r(critical),
            "p_value": _r(p_value, 4),
            "valid": valid,
        }

    findings = [
        f"Dengan N = {n} pada taraf signifikansi {int(alpha * 100)}%, diperoleh r tabel "
        f"sebesar {_r(critical)}."
    ]
    if invalid:
        findings.append(
            f"Sebanyak {len(invalid)} butir memiliki r hitung di bawah r tabel dan "
            f"dinyatakan tidak valid: {', '.join(invalid)}. Butir tersebut perlu "
            f"digugurkan atau diperbaiki sebelum instrumen dipakai."
        )
    else:
        findings.append(
            f"Seluruh {len(items)} butir memiliki r hitung lebih besar daripada r tabel, "
            f"sehingga semua butir dinyatakan valid."
        )

    warnings = []
    if invalid:
        warnings.append(
            f"Butir yang perlu dipertimbangkan untuk digugurkan: {', '.join(invalid)}."
        )
    if inflated:
        warnings.append(
            f"Butir {', '.join(inflated)} dinyatakan valid memakai korelasi butir dengan "
            f"skor total, tetapi tidak lolos bila memakai korelasi terkoreksi. Korelasi "
            f"biasa ikut terangkat karena butir tersebut menyumbang skor totalnya sendiri. "
            f"Periksa ulang butir ini — inilah yang biasanya ditanyakan penguji."
        )

    return AnalysisResult(
        method="validity",
        label="Uji validitas instrumen",
        params={"items": items, "alpha": alpha, "corrected": corrected, "n": n},
        tables=[
            Table(
                title="Hasil Uji Validitas",
                columns=["Butir", "r butir-total", "r terkoreksi", "r tabel", "Sig.",
                         "Keterangan"],
                rows=rows,
                note=(
                    f"N = {n}; df = {n - 2}; taraf signifikansi {int(alpha * 100)}%. "
                    f"Keputusan memakai kolom "
                    f"{'r terkoreksi' if corrected else 'r butir-total'}."
                ),
            )
        ],
        values={
            "n": n,
            "r_tabel": _r(critical),
            "invalid_items": invalid,
            "inflated_items": inflated,
            "items": values,
        },
        findings=findings,
        warnings=warnings,
    )


def cronbach_alpha(data: pd.DataFrame) -> float:
    """α = k/(k−1) × (1 − Σσ²ᵢ / σ²ₜₒₜₐₗ)."""
    k = data.shape[1]
    if k < 2:
        return float("nan")
    item_variances = data.var(axis=0, ddof=1).sum()
    total_variance = data.sum(axis=1).var(ddof=1)
    if total_variance == 0:
        return float("nan")
    return float((k / (k - 1)) * (1 - item_variances / total_variance))


def interpret_alpha(alpha_value: float) -> str:
    if math.isnan(alpha_value):
        return "tidak dapat dihitung"
    if alpha_value >= 0.9:
        return "sangat tinggi"
    if alpha_value >= 0.8:
        return "tinggi"
    if alpha_value >= 0.7:
        return "cukup tinggi"
    if alpha_value >= 0.6:
        return "dapat diterima"
    return "rendah"


def reliability_test(
    frame: pd.DataFrame, items: list[str], threshold: float = 0.6
) -> AnalysisResult:
    """Uji reliabilitas Cronbach's Alpha beserta alpha bila butir dihapus."""
    items = _require_columns(frame, items)
    data = _numeric(frame, items).dropna()
    if data.shape[0] < 3 or data.shape[1] < 2:
        raise AnalysisError("Uji reliabilitas memerlukan minimal 2 butir dan 3 responden.")

    overall = cronbach_alpha(data)
    rows, improvements = [], []
    for item in items:
        remaining = data.drop(columns=[item])
        alpha_deleted = cronbach_alpha(remaining) if remaining.shape[1] >= 2 else float("nan")
        rows.append([item, _r(data[item].mean()), _r(data[item].std(ddof=1)), _r(alpha_deleted)])
        if not math.isnan(alpha_deleted) and alpha_deleted > overall + 0.01:
            improvements.append((item, alpha_deleted))

    reliable = bool(overall >= threshold)
    findings = [
        f"Nilai Cronbach's Alpha sebesar {_r(overall)} dengan {len(items)} butir, "
        f"termasuk kategori {interpret_alpha(overall)}.",
        f"Karena nilai alpha {'lebih besar' if reliable else 'lebih kecil'} daripada "
        f"batas {threshold}, instrumen dinyatakan {'reliabel' if reliable else 'belum reliabel'}.",
    ]
    warnings = []
    if improvements:
        detail = ", ".join(f"{item} (α menjadi {_r(value)})" for item, value in improvements)
        warnings.append(f"Alpha meningkat bila butir berikut dihapus: {detail}.")

    return AnalysisResult(
        method="reliability",
        label="Uji reliabilitas instrumen",
        params={"items": items, "threshold": threshold},
        tables=[
            Table(
                title="Statistik Reliabilitas",
                columns=["Cronbach's Alpha", "Jumlah Butir", "Keterangan"],
                rows=[[_r(overall), len(items), "Reliabel" if reliable else "Belum reliabel"]],
            ),
            Table(
                title="Statistik Butir-Total",
                columns=["Butir", "Rata-rata", "Std. Deviasi", "Alpha bila butir dihapus"],
                rows=rows,
            ),
        ],
        values={
            "cronbach_alpha": _r(overall),
            "n_items": len(items),
            "n": int(data.shape[0]),
            "reliable": reliable,
            "threshold": threshold,
        },
        findings=findings,
        warnings=warnings,
    )


# --- Uji asumsi klasik -------------------------------------------------------


def normality(
    frame: pd.DataFrame, columns: list[str], alpha: float = ALPHA_DEFAULT
) -> AnalysisResult:
    """Uji normalitas Shapiro-Wilk dan Kolmogorov-Smirnov (koreksi Lilliefors)."""
    columns = _require_columns(frame, columns)
    data = _numeric(frame, columns)

    rows, values = [], {}
    for column in columns:
        series = data[column].dropna()
        n = int(series.size)
        if n < 3:
            rows.append([column, n, None, None, None, None, "Data terlalu sedikit"])
            continue
        shapiro_w, shapiro_p = sps.shapiro(series)
        ks_stat, ks_p = _lilliefors(series)
        normal = bool((shapiro_p if n <= 50 else ks_p) > alpha)
        rows.append(
            [column, n, _r(shapiro_w), _p_label(shapiro_p), _r(ks_stat), _p_label(ks_p),
             "Normal" if normal else "Tidak normal"]
        )
        values[column] = {
            "n": n,
            "shapiro_w": _r(shapiro_w),
            "shapiro_p": _r(shapiro_p, 4),
            "ks_stat": _r(ks_stat),
            "ks_p": _r(ks_p, 4),
            "normal": normal,
        }

    not_normal = [c for c, v in values.items() if not v["normal"]]
    findings = [
        "Uji normalitas memakai Shapiro-Wilk untuk N ≤ 50 dan Kolmogorov-Smirnov "
        "dengan koreksi Lilliefors untuk N > 50."
    ]
    if not_normal:
        findings.append(
            f"Variabel {', '.join(not_normal)} memiliki nilai signifikansi di bawah "
            f"{alpha}, sehingga datanya tidak berdistribusi normal. Uji parametrik "
            f"sebaiknya diganti padanan non-parametriknya atau data ditransformasi."
        )
    else:
        findings.append(
            "Seluruh variabel memiliki nilai signifikansi di atas 0,05 sehingga data "
            "dinyatakan berdistribusi normal dan asumsi normalitas terpenuhi."
        )

    return AnalysisResult(
        method="normality",
        label="Uji normalitas",
        params={"columns": columns, "alpha": alpha},
        tables=[
            Table(
                title="Hasil Uji Normalitas",
                columns=["Variabel", "N", "Shapiro-Wilk", "Sig. (SW)",
                         "Kolmogorov-Smirnov", "Sig. (KS)", "Keterangan"],
                rows=rows,
            )
        ],
        values=values,
        findings=findings,
        assumptions=["Normalitas " + ("terpenuhi" if not not_normal else "tidak terpenuhi")],
        warnings=(
            [f"Variabel tidak berdistribusi normal: {', '.join(not_normal)}."]
            if not_normal
            else []
        ),
    )


def _lilliefors(series: pd.Series) -> tuple[float, float]:
    try:
        from statsmodels.stats.diagnostic import lilliefors

        stat, p_value = lilliefors(series, dist="norm")
        return float(stat), float(p_value)
    except Exception:  # pragma: no cover - jalur cadangan
        standardized = (series - series.mean()) / series.std(ddof=1)
        stat, p_value = sps.kstest(standardized, "norm")
        return float(stat), float(p_value)


def multicollinearity(frame: pd.DataFrame, predictors: list[str]) -> AnalysisResult:
    """Uji multikolinearitas lewat VIF dan tolerance."""
    predictors = _require_columns(frame, predictors)
    if len(predictors) < 2:
        raise AnalysisError("Uji multikolinearitas memerlukan minimal dua variabel bebas.")
    data = _numeric(frame, predictors).dropna()

    import statsmodels.api as sm
    from statsmodels.stats.outliers_influence import variance_inflation_factor

    design = sm.add_constant(data, has_constant="add")
    rows, values, problematic = [], {}, []
    for index, predictor in enumerate(predictors, start=1):
        vif = float(variance_inflation_factor(design.values, index))
        tolerance = 1.0 / vif if vif else float("nan")
        ok = bool(vif < 10 and tolerance > 0.1)
        if not ok:
            problematic.append(predictor)
        rows.append([predictor, _r(tolerance), _r(vif),
                     "Bebas multikolinearitas" if ok else "Terjadi multikolinearitas"])
        values[predictor] = {"vif": _r(vif), "tolerance": _r(tolerance), "ok": ok}

    findings = [
        "Kriteria yang dipakai: tidak terjadi multikolinearitas bila nilai tolerance "
        "lebih besar dari 0,1 dan VIF lebih kecil dari 10."
    ]
    findings.append(
        f"Variabel {', '.join(problematic)} melanggar kriteria tersebut."
        if problematic
        else "Seluruh variabel bebas memenuhi kriteria sehingga tidak terjadi multikolinearitas."
    )

    return AnalysisResult(
        method="multicollinearity",
        label="Uji multikolinearitas",
        params={"predictors": predictors},
        tables=[
            Table(
                title="Hasil Uji Multikolinearitas",
                columns=["Variabel", "Tolerance", "VIF", "Keterangan"],
                rows=rows,
            )
        ],
        values=values,
        findings=findings,
        assumptions=[
            "Multikolinearitas " + ("tidak terjadi" if not problematic else "terjadi")
        ],
        warnings=([f"Multikolinearitas pada: {', '.join(problematic)}."] if problematic else []),
    )


def heteroscedasticity(
    frame: pd.DataFrame, dependent: str, predictors: list[str], method: str = "glejser"
) -> AnalysisResult:
    """Uji heteroskedastisitas dengan metode Glejser atau Breusch-Pagan."""
    _require_columns(frame, [dependent, *predictors])
    data = _numeric(frame, [dependent, *predictors]).dropna()

    import statsmodels.api as sm

    y = data[dependent]
    X = sm.add_constant(data[predictors], has_constant="add")
    model = sm.OLS(y, X).fit()
    residuals = model.resid

    if method == "breusch_pagan":
        from statsmodels.stats.diagnostic import het_breuschpagan

        lm_stat, lm_p, f_stat, f_p = het_breuschpagan(residuals, X)
        homoscedastic = bool(lm_p > ALPHA_DEFAULT)
        return AnalysisResult(
            method="heteroscedasticity",
            label="Uji heteroskedastisitas (Breusch-Pagan)",
            params={"dependent": dependent, "predictors": predictors, "method": method},
            tables=[
                Table(
                    title="Hasil Uji Breusch-Pagan",
                    columns=["Statistik LM", "Sig. LM", "Statistik F", "Sig. F", "Keterangan"],
                    rows=[[_r(lm_stat), _p_label(lm_p), _r(f_stat), _p_label(f_p),
                           "Bebas heteroskedastisitas" if homoscedastic
                           else "Terjadi heteroskedastisitas"]],
                )
            ],
            values={
                "lm_statistic": _r(lm_stat), "lm_p": _r(lm_p, 4),
                "f_statistic": _r(f_stat), "f_p": _r(f_p, 4),
                "homoscedastic": homoscedastic,
            },
            findings=[
                f"Uji Breusch-Pagan menghasilkan nilai signifikansi {_p_label(lm_p)}, "
                f"sehingga model {'bebas dari' if homoscedastic else 'mengalami'} "
                f"heteroskedastisitas."
            ],
            assumptions=[
                "Heteroskedastisitas " + ("tidak terjadi" if homoscedastic else "terjadi")
            ],
        )

    # Glejser: regresi nilai mutlak residual terhadap variabel bebas.
    glejser = sm.OLS(np.abs(residuals), X).fit()
    rows, problematic = [], []
    for predictor in predictors:
        p_value = float(glejser.pvalues[predictor])
        ok = p_value > ALPHA_DEFAULT
        if not ok:
            problematic.append(predictor)
        rows.append([predictor, _r(glejser.params[predictor]), _r(glejser.tvalues[predictor]),
                     _p_label(p_value),
                     "Bebas heteroskedastisitas" if ok else "Terjadi heteroskedastisitas"])

    homoscedastic = not problematic
    return AnalysisResult(
        method="heteroscedasticity",
        label="Uji heteroskedastisitas (Glejser)",
        params={"dependent": dependent, "predictors": predictors, "method": "glejser"},
        tables=[
            Table(
                title="Hasil Uji Glejser",
                columns=["Variabel", "Koefisien", "t hitung", "Sig.", "Keterangan"],
                rows=rows,
                note="Nilai mutlak residual diregresikan terhadap variabel bebas.",
            )
        ],
        values={
            "homoscedastic": homoscedastic,
            "significant_predictors": problematic,
            **{p: {"p_value": _r(float(glejser.pvalues[p]), 4)} for p in predictors},
        },
        findings=[
            "Seluruh variabel bebas memiliki nilai signifikansi di atas 0,05 pada uji "
            "Glejser, sehingga model bebas dari heteroskedastisitas."
            if homoscedastic
            else f"Variabel {', '.join(problematic)} memiliki nilai signifikansi di bawah "
                 f"0,05, sehingga terjadi gejala heteroskedastisitas."
        ],
        assumptions=["Heteroskedastisitas " + ("tidak terjadi" if homoscedastic else "terjadi")],
        warnings=([f"Heteroskedastisitas pada: {', '.join(problematic)}."] if problematic else []),
    )


# --- Korelasi & regresi ------------------------------------------------------


def correlation(
    frame: pd.DataFrame, columns: list[str], method: str = "pearson"
) -> AnalysisResult:
    """Matriks korelasi Pearson atau Spearman beserta signifikansinya."""
    columns = _require_columns(frame, columns)
    data = _numeric(frame, columns).dropna()
    n = int(data.shape[0])
    if n < 3:
        raise AnalysisError("Analisis korelasi memerlukan minimal 3 pengamatan lengkap.")

    test = sps.pearsonr if method == "pearson" else sps.spearmanr
    rows, values = [], {}
    for row_var in columns:
        line = [row_var]
        for col_var in columns:
            if row_var == col_var:
                line.append("1")
                continue
            result = test(data[row_var], data[col_var])
            coefficient, p_value = float(result[0]), float(result[1])
            line.append(f"{_r(coefficient)} ({_p_label(p_value)})")
            key = f"{row_var}__{col_var}"
            values[key] = {
                "coefficient": _r(coefficient), "p_value": _r(p_value, 4),
                "significant": bool(p_value < ALPHA_DEFAULT),
            }
        rows.append(line)

    strong = [
        (k, v) for k, v in values.items()
        if v["significant"] and abs(v["coefficient"] or 0) >= 0.5
    ]
    findings = [
        f"Analisis korelasi {method.title()} dijalankan pada {n} pengamatan lengkap."
    ]
    for key, value in strong[: len(columns)]:
        left, right = key.split("__")
        findings.append(
            f"Terdapat hubungan yang signifikan antara {left} dan {right} dengan "
            f"koefisien korelasi {value['coefficient']} (Sig. {value['p_value']})."
        )

    return AnalysisResult(
        method="correlation",
        label=f"Analisis korelasi {method}",
        params={"columns": columns, "method": method, "n": n},
        tables=[
            Table(
                title=f"Matriks Korelasi {method.title()}",
                columns=["Variabel"] + columns,
                rows=rows,
                note="Angka dalam kurung adalah nilai signifikansi (2-tailed).",
            )
        ],
        values={"n": n, **values},
        findings=findings,
    )


def regression(
    frame: pd.DataFrame, dependent: str, predictors: list[str], alpha: float = ALPHA_DEFAULT
) -> AnalysisResult:
    """Regresi linear sederhana maupun berganda dengan OLS."""
    _require_columns(frame, [dependent, *predictors])
    data = _numeric(frame, [dependent, *predictors]).dropna()
    n = int(data.shape[0])
    if n <= len(predictors) + 1:
        raise AnalysisError(
            f"Jumlah pengamatan ({n}) tidak cukup untuk {len(predictors)} variabel bebas."
        )

    import statsmodels.api as sm
    from statsmodels.stats.stattools import durbin_watson

    y = data[dependent]
    X = sm.add_constant(data[predictors], has_constant="add")
    model = sm.OLS(y, X).fit()

    df_residual = int(model.df_resid)
    t_critical = t_table(df_residual, alpha)
    f_critical = f_table(int(model.df_model), df_residual, alpha)
    y_std = float(y.std(ddof=1))

    rows, values, significant = [], {}, []
    for name in ["const", *predictors]:
        coefficient = float(model.params[name])
        std_error = float(model.bse[name])
        t_value = float(model.tvalues[name])
        p_value = float(model.pvalues[name])
        beta = (
            coefficient * float(data[name].std(ddof=1)) / y_std
            if name != "const" and y_std
            else None
        )
        is_significant = bool(p_value < alpha)
        if name != "const" and is_significant:
            significant.append(name)
        rows.append(
            [
                "Konstanta" if name == "const" else name,
                _r(coefficient), _r(std_error), _r(beta), _r(t_value), _p_label(p_value),
                "" if name == "const" else ("Signifikan" if is_significant else "Tidak signifikan"),
            ]
        )
        values[name] = {
            "coefficient": _r(coefficient), "std_error": _r(std_error), "beta": _r(beta),
            "t_value": _r(t_value), "p_value": _r(p_value, 4), "significant": is_significant,
        }

    dw = float(durbin_watson(model.resid))
    r_squared = float(model.rsquared)
    values.update(
        {
            "n": n,
            "r_squared": _r(r_squared),
            "adj_r_squared": _r(float(model.rsquared_adj)),
            "r": _r(math.sqrt(max(r_squared, 0.0))),
            "f_statistic": _r(float(model.fvalue)),
            "f_p_value": _r(float(model.f_pvalue), 4),
            "f_table": _r(f_critical),
            "t_table": _r(t_critical),
            "df_model": int(model.df_model),
            "df_residual": df_residual,
            "durbin_watson": _r(dw),
            "std_error_estimate": _r(float(np.sqrt(model.mse_resid))),
        }
    )

    equation = f"{dependent} = {_r(model.params['const'])}"
    for predictor in predictors:
        coefficient = float(model.params[predictor])
        equation += f" {'+' if coefficient >= 0 else '−'} {_r(abs(coefficient))}{predictor}"

    f_significant = bool(float(model.f_pvalue) < alpha)
    findings = [
        f"Persamaan regresi yang terbentuk adalah {equation}.",
        f"Nilai koefisien determinasi (R²) sebesar {_r(r_squared)} yang berarti "
        f"variabel bebas menjelaskan {_r(r_squared * 100, 1)}% variasi {dependent}, "
        f"sedangkan sisanya dijelaskan faktor lain di luar model.",
        f"Uji F menghasilkan F hitung sebesar {_r(float(model.fvalue))} dengan "
        f"signifikansi {_p_label(float(model.f_pvalue))} "
        f"(F tabel = {_r(f_critical)}), sehingga secara simultan variabel bebas "
        f"{'berpengaruh' if f_significant else 'tidak berpengaruh'} terhadap {dependent}.",
    ]
    for predictor in predictors:
        info = values[predictor]
        findings.append(
            f"Variabel {predictor} memiliki t hitung {info['t_value']} "
            f"(t tabel = {_r(t_critical)}) dengan signifikansi {info['p_value']}, "
            f"sehingga secara parsial {'berpengaruh' if info['significant'] else 'tidak berpengaruh'} "
            f"terhadap {dependent}."
        )

    warnings = []
    if not 1.5 <= dw <= 2.5:
        warnings.append(
            f"Nilai Durbin-Watson {_r(dw)} berada di luar rentang aman 1,5–2,5; "
            f"periksa autokorelasi dengan tabel dL dan dU untuk n = {n}."
        )
    if not significant and predictors:
        warnings.append(
            "Tidak ada variabel bebas yang berpengaruh signifikan secara parsial. "
            "Hasil ini tetap dilaporkan apa adanya dan dibahas sebagai temuan."
        )

    return AnalysisResult(
        method="regression",
        label=(
            "Regresi linear sederhana" if len(predictors) == 1 else "Regresi linear berganda"
        ),
        params={"dependent": dependent, "predictors": predictors, "alpha": alpha},
        tables=[
            Table(
                title="Ringkasan Model",
                columns=["R", "R Square", "Adjusted R Square", "Std. Error of the Estimate",
                         "Durbin-Watson"],
                rows=[[values["r"], values["r_squared"], values["adj_r_squared"],
                       values["std_error_estimate"], values["durbin_watson"]]],
            ),
            Table(
                title="Hasil Uji F (ANOVA)",
                columns=["F hitung", "F tabel", "df1", "df2", "Sig.", "Keterangan"],
                rows=[[values["f_statistic"], values["f_table"], values["df_model"],
                       values["df_residual"], _p_label(float(model.f_pvalue)),
                       "Signifikan" if f_significant else "Tidak signifikan"]],
            ),
            Table(
                title="Hasil Uji t (Koefisien Regresi)",
                columns=["Variabel", "B", "Std. Error", "Beta", "t hitung", "Sig.", "Keterangan"],
                rows=rows,
                note=f"t tabel = {_r(t_critical)} pada df = {df_residual}.",
            ),
        ],
        values=values,
        findings=findings,
        warnings=warnings,
    )


# --- Uji beda ----------------------------------------------------------------


def ttest_independent(
    frame: pd.DataFrame, value: str, group: str, alpha: float = ALPHA_DEFAULT
) -> AnalysisResult:
    """Uji beda dua kelompok bebas, dengan uji Levene sebagai penentu varian."""
    _require_columns(frame, [value, group])
    data = frame[[value, group]].dropna()
    data[value] = pd.to_numeric(data[value], errors="coerce")
    data = data.dropna()
    groups = list(data[group].unique())
    if len(groups) != 2:
        raise AnalysisError(
            f"Uji t independen memerlukan tepat 2 kelompok; ditemukan {len(groups)}: {groups}. "
            f"Untuk lebih dari dua kelompok gunakan ANOVA."
        )

    first = data.loc[data[group] == groups[0], value]
    second = data.loc[data[group] == groups[1], value]
    levene_stat, levene_p = sps.levene(first, second)
    equal_variance = bool(levene_p > alpha)
    t_stat, p_value = sps.ttest_ind(first, second, equal_var=equal_variance)

    df = (
        len(first) + len(second) - 2
        if equal_variance
        else _welch_df(first, second)
    )
    pooled = math.sqrt(
        ((len(first) - 1) * first.var(ddof=1) + (len(second) - 1) * second.var(ddof=1))
        / (len(first) + len(second) - 2)
    )
    cohens_d = (first.mean() - second.mean()) / pooled if pooled else float("nan")
    significant = bool(p_value < alpha)

    return AnalysisResult(
        method="ttest_independent",
        label="Uji t sampel bebas",
        params={"value": value, "group": group, "alpha": alpha},
        tables=[
            Table(
                title="Statistik Kelompok",
                columns=["Kelompok", "N", "Rata-rata", "Std. Deviasi", "Std. Error"],
                rows=[
                    [str(groups[0]), len(first), _r(first.mean()), _r(first.std(ddof=1)),
                     _r(first.std(ddof=1) / math.sqrt(len(first)))],
                    [str(groups[1]), len(second), _r(second.mean()), _r(second.std(ddof=1)),
                     _r(second.std(ddof=1) / math.sqrt(len(second)))],
                ],
            ),
            Table(
                title="Hasil Uji t",
                columns=["Levene F", "Sig. Levene", "t hitung", "df", "Sig. (2-tailed)",
                         "Selisih Rata-rata", "Cohen's d", "Keterangan"],
                rows=[[_r(levene_stat), _p_label(levene_p), _r(t_stat), _r(df, 1),
                       _p_label(p_value), _r(first.mean() - second.mean()), _r(cohens_d),
                       "Berbeda signifikan" if significant else "Tidak berbeda signifikan"]],
                note=(
                    "Varian kelompok homogen sehingga dipakai uji t Student."
                    if equal_variance
                    else "Varian kelompok tidak homogen sehingga dipakai koreksi Welch."
                ),
            ),
        ],
        values={
            "groups": [str(g) for g in groups],
            "mean_1": _r(first.mean()), "mean_2": _r(second.mean()),
            "n_1": len(first), "n_2": len(second),
            "levene_p": _r(levene_p, 4), "equal_variance": equal_variance,
            "t_statistic": _r(t_stat), "df": _r(df, 1), "p_value": _r(p_value, 4),
            "mean_difference": _r(first.mean() - second.mean()),
            "cohens_d": _r(cohens_d), "significant": significant,
            "t_table": _r(t_table(int(df), alpha)),
        },
        findings=[
            f"Uji Levene menghasilkan signifikansi {_p_label(levene_p)}, sehingga varian "
            f"kedua kelompok {'homogen' if equal_variance else 'tidak homogen'}.",
            f"Nilai t hitung sebesar {_r(t_stat)} dengan signifikansi {_p_label(p_value)}, "
            f"sehingga terdapat perbedaan yang {_sig(p_value, alpha)} pada {value} antara "
            f"kelompok {groups[0]} dan {groups[1]}.",
        ],
    )


def _welch_df(first: pd.Series, second: pd.Series) -> float:
    v1, v2 = first.var(ddof=1), second.var(ddof=1)
    n1, n2 = len(first), len(second)
    if n1 < 2 or n2 < 2:
        return float(max(n1 + n2 - 2, 1))
    numerator = (v1 / n1 + v2 / n2) ** 2
    denominator = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
    return float(numerator / denominator) if denominator else float(n1 + n2 - 2)


def ttest_paired(
    frame: pd.DataFrame, before: str, after: str, alpha: float = ALPHA_DEFAULT
) -> AnalysisResult:
    """Uji t berpasangan — dipakai pada rancangan pretest-posttest."""
    _require_columns(frame, [before, after])
    data = _numeric(frame, [before, after]).dropna()
    n = int(data.shape[0])
    if n < 3:
        raise AnalysisError("Uji t berpasangan memerlukan minimal 3 pasangan data.")

    t_stat, p_value = sps.ttest_rel(data[before], data[after])
    difference = data[after] - data[before]
    cohens_d = difference.mean() / difference.std(ddof=1) if difference.std(ddof=1) else float("nan")
    significant = bool(p_value < alpha)

    return AnalysisResult(
        method="ttest_paired",
        label="Uji t berpasangan",
        params={"before": before, "after": after, "alpha": alpha},
        tables=[
            Table(
                title="Statistik Berpasangan",
                columns=["Pengukuran", "N", "Rata-rata", "Std. Deviasi"],
                rows=[
                    [before, n, _r(data[before].mean()), _r(data[before].std(ddof=1))],
                    [after, n, _r(data[after].mean()), _r(data[after].std(ddof=1))],
                ],
            ),
            Table(
                title="Hasil Uji t Berpasangan",
                columns=["Selisih Rata-rata", "Std. Deviasi", "t hitung", "df",
                         "Sig. (2-tailed)", "Cohen's d", "Keterangan"],
                rows=[[_r(difference.mean()), _r(difference.std(ddof=1)), _r(t_stat), n - 1,
                       _p_label(p_value), _r(cohens_d),
                       "Berbeda signifikan" if significant else "Tidak berbeda signifikan"]],
            ),
        ],
        values={
            "n": n, "mean_before": _r(data[before].mean()), "mean_after": _r(data[after].mean()),
            "mean_difference": _r(difference.mean()), "t_statistic": _r(t_stat),
            "df": n - 1, "p_value": _r(p_value, 4), "cohens_d": _r(cohens_d),
            "significant": significant, "t_table": _r(t_table(n - 1, alpha)),
        },
        findings=[
            f"Rata-rata {before} sebesar {_r(data[before].mean())} berubah menjadi "
            f"{_r(data[after].mean())} pada {after}, dengan selisih {_r(difference.mean())}.",
            f"Nilai t hitung {_r(t_stat)} dengan signifikansi {_p_label(p_value)} menunjukkan "
            f"perbedaan yang {_sig(p_value, alpha)} antara kedua pengukuran.",
        ],
    )


def anova_oneway(
    frame: pd.DataFrame, value: str, group: str, alpha: float = ALPHA_DEFAULT
) -> AnalysisResult:
    """ANOVA satu jalur beserta uji homogenitas dan uji lanjut Tukey."""
    _require_columns(frame, [value, group])
    data = frame[[value, group]].dropna()
    data[value] = pd.to_numeric(data[value], errors="coerce")
    data = data.dropna()
    groups = list(data[group].unique())
    if len(groups) < 3:
        raise AnalysisError(
            f"ANOVA satu jalur memerlukan minimal 3 kelompok; ditemukan {len(groups)}. "
            f"Untuk dua kelompok gunakan uji t sampel bebas."
        )

    samples = [data.loc[data[group] == g, value] for g in groups]
    levene_stat, levene_p = sps.levene(*samples)
    f_stat, p_value = sps.f_oneway(*samples)

    grand_mean = data[value].mean()
    ss_between = sum(len(s) * (s.mean() - grand_mean) ** 2 for s in samples)
    ss_within = sum(((s - s.mean()) ** 2).sum() for s in samples)
    df_between = len(groups) - 1
    df_within = int(data.shape[0]) - len(groups)
    significant = bool(p_value < alpha)

    descriptive_rows = [
        [str(g), len(s), _r(s.mean()), _r(s.std(ddof=1))] for g, s in zip(groups, samples)
    ]
    tables = [
        Table(
            title="Statistik Deskriptif per Kelompok",
            columns=["Kelompok", "N", "Rata-rata", "Std. Deviasi"],
            rows=descriptive_rows,
        ),
        Table(
            title="Hasil Uji Homogenitas (Levene)",
            columns=["Levene Statistic", "df1", "df2", "Sig.", "Keterangan"],
            rows=[[_r(levene_stat), df_between, df_within, _p_label(levene_p),
                   "Homogen" if levene_p > alpha else "Tidak homogen"]],
        ),
        Table(
            title="Hasil Uji ANOVA",
            columns=["Sumber", "Jumlah Kuadrat", "df", "Rata-rata Kuadrat", "F", "Sig."],
            rows=[
                ["Antar Kelompok", _r(ss_between), df_between, _r(ss_between / df_between),
                 _r(f_stat), _p_label(p_value)],
                ["Dalam Kelompok", _r(ss_within), df_within, _r(ss_within / df_within), "", ""],
                ["Total", _r(ss_between + ss_within), df_between + df_within, "", "", ""],
            ],
        ),
    ]

    posthoc_pairs = []
    if significant:
        try:
            from statsmodels.stats.multicomp import pairwise_tukeyhsd

            tukey = pairwise_tukeyhsd(data[value], data[group], alpha=alpha)
            posthoc_rows = []
            for row in tukey.summary().data[1:]:
                posthoc_rows.append([str(c) for c in row])
                if str(row[-1]).strip().lower() == "true":
                    posthoc_pairs.append(f"{row[0]}–{row[1]}")
            tables.append(
                Table(
                    title="Uji Lanjut Tukey HSD",
                    columns=[str(c) for c in tukey.summary().data[0]],
                    rows=posthoc_rows,
                )
            )
        except Exception as exc:  # pragma: no cover
            tables.append(
                Table(title="Uji Lanjut Tukey HSD", columns=["Catatan"],
                      rows=[[f"Uji lanjut tidak dapat dijalankan: {exc}"]])
            )

    findings = [
        f"Uji homogenitas Levene menghasilkan signifikansi {_p_label(levene_p)}, sehingga "
        f"varian antarkelompok {'homogen' if levene_p > alpha else 'tidak homogen'}.",
        f"Uji ANOVA menghasilkan F hitung {_r(f_stat)} dengan signifikansi "
        f"{_p_label(p_value)} (F tabel = {_r(f_table(df_between, df_within, alpha))}), "
        f"sehingga terdapat perbedaan {value} yang {_sig(p_value, alpha)} antarkelompok.",
    ]
    if posthoc_pairs:
        findings.append(
            f"Uji lanjut Tukey menunjukkan perbedaan signifikan pada pasangan: "
            f"{', '.join(posthoc_pairs)}."
        )

    return AnalysisResult(
        method="anova_oneway",
        label="ANOVA satu jalur",
        params={"value": value, "group": group, "alpha": alpha},
        tables=tables,
        values={
            "groups": [str(g) for g in groups],
            "f_statistic": _r(f_stat), "p_value": _r(p_value, 4),
            "df_between": df_between, "df_within": df_within,
            "levene_p": _r(levene_p, 4), "significant": significant,
            "f_table": _r(f_table(df_between, df_within, alpha)),
            "ss_between": _r(ss_between), "ss_within": _r(ss_within),
        },
        findings=findings,
    )


def nonparametric(
    frame: pd.DataFrame,
    test: str,
    value: str,
    group: str | None = None,
    second: str | None = None,
    alpha: float = ALPHA_DEFAULT,
) -> AnalysisResult:
    """Padanan non-parametrik: Mann-Whitney, Wilcoxon, dan Kruskal-Wallis."""
    labels = {
        "mann_whitney": "Uji Mann-Whitney U",
        "wilcoxon": "Uji Wilcoxon Signed Rank",
        "kruskal": "Uji Kruskal-Wallis",
    }
    if test not in labels:
        raise AnalysisError(f"Uji '{test}' tidak dikenal. Pilihan: {', '.join(labels)}.")

    if test == "wilcoxon":
        _require_columns(frame, [value, second or ""])
        data = _numeric(frame, [value, second]).dropna()
        statistic, p_value = sps.wilcoxon(data[value], data[second])
        detail = Table(
            title="Statistik Berpasangan",
            columns=["Pengukuran", "N", "Median"],
            rows=[[value, len(data), _r(data[value].median())],
                  [second, len(data), _r(data[second].median())]],
        )
        values = {
            "statistic": _r(statistic), "p_value": _r(p_value, 4), "n": len(data),
            "median_1": _r(data[value].median()), "median_2": _r(data[second].median()),
        }
    else:
        _require_columns(frame, [value, group or ""])
        data = frame[[value, group]].dropna()
        data[value] = pd.to_numeric(data[value], errors="coerce")
        data = data.dropna()
        groups = list(data[group].unique())
        samples = [data.loc[data[group] == g, value] for g in groups]
        if test == "mann_whitney":
            if len(groups) != 2:
                raise AnalysisError(f"Mann-Whitney memerlukan 2 kelompok; ditemukan {len(groups)}.")
            statistic, p_value = sps.mannwhitneyu(samples[0], samples[1], alternative="two-sided")
        else:
            if len(groups) < 3:
                raise AnalysisError(
                    f"Kruskal-Wallis memerlukan minimal 3 kelompok; ditemukan {len(groups)}."
                )
            statistic, p_value = sps.kruskal(*samples)
        detail = Table(
            title="Statistik Kelompok",
            columns=["Kelompok", "N", "Median", "Rata-rata Peringkat"],
            rows=[
                [str(g), len(s), _r(s.median()),
                 _r(data[value].rank().loc[s.index].mean())]
                for g, s in zip(groups, samples)
            ],
        )
        values = {
            "statistic": _r(statistic), "p_value": _r(p_value, 4),
            "groups": [str(g) for g in groups],
        }

    significant = bool(p_value < alpha)
    values["significant"] = significant

    return AnalysisResult(
        method=test,
        label=labels[test],
        params={"value": value, "group": group, "second": second, "alpha": alpha},
        tables=[
            detail,
            Table(
                title=f"Hasil {labels[test]}",
                columns=["Statistik", "Sig. (2-tailed)", "Keterangan"],
                rows=[[_r(statistic), _p_label(p_value),
                       "Berbeda signifikan" if significant else "Tidak berbeda signifikan"]],
            ),
        ],
        values=values,
        findings=[
            f"{labels[test]} menghasilkan statistik {_r(statistic)} dengan signifikansi "
            f"{_p_label(p_value)}, sehingga perbedaan yang diuji {_sig(p_value, alpha)} "
            f"pada taraf {int(alpha * 100)}%."
        ],
    )


# --- Eksperimen & R&D --------------------------------------------------------


def ngain(
    frame: pd.DataFrame, pretest: str, posttest: str, ideal_score: float | None = None
) -> AnalysisResult:
    """Uji efektivitas lewat N-Gain ternormalisasi Hake."""
    _require_columns(frame, [pretest, posttest])
    data = _numeric(frame, [pretest, posttest]).dropna()
    if data.empty:
        raise AnalysisError("Tidak ada pasangan pretest-posttest yang lengkap.")

    ideal = ideal_score if ideal_score is not None else float(data[posttest].max())
    denominator = ideal - data[pretest]
    gains = (data[posttest] - data[pretest]) / denominator.replace(0, np.nan)
    gains = gains.dropna()
    mean_gain = float(gains.mean())

    def category(value: float) -> str:
        if value >= 0.7:
            return "Tinggi"
        if value >= 0.3:
            return "Sedang"
        return "Rendah"

    distribution = gains.map(category).value_counts()
    paired = ttest_paired(data, pretest, posttest)

    return AnalysisResult(
        method="ngain",
        label="Uji efektivitas N-Gain",
        params={"pretest": pretest, "posttest": posttest, "ideal_score": ideal},
        tables=[
            Table(
                title="Hasil Uji N-Gain",
                columns=["N", "Rata-rata Pretest", "Rata-rata Posttest", "Skor Ideal",
                         "Rata-rata N-Gain", "Kategori"],
                rows=[[len(gains), _r(data[pretest].mean()), _r(data[posttest].mean()),
                       _r(ideal), _r(mean_gain), category(mean_gain)]],
                note="N-Gain = (posttest − pretest) / (skor ideal − pretest).",
            ),
            Table(
                title="Sebaran Kategori N-Gain",
                columns=["Kategori", "Frekuensi", "Persen (%)"],
                rows=[[k, int(v), _r(100 * v / len(gains), 1)] for k, v in distribution.items()],
            ),
        ],
        values={
            "n": len(gains), "mean_pretest": _r(data[pretest].mean()),
            "mean_posttest": _r(data[posttest].mean()), "ideal_score": _r(ideal),
            "mean_ngain": _r(mean_gain), "category": category(mean_gain),
            "paired_t": paired.values,
        },
        findings=[
            f"Rata-rata skor meningkat dari {_r(data[pretest].mean())} pada pretest menjadi "
            f"{_r(data[posttest].mean())} pada posttest.",
            f"Rata-rata N-Gain sebesar {_r(mean_gain)} termasuk kategori "
            f"{category(mean_gain).lower()}.",
            *paired.findings[1:],
        ],
    )


def aiken_v(
    ratings: list[list[float]],
    scale_min: float = 1,
    scale_max: float = 5,
    item_labels: list[str] | None = None,
) -> AnalysisResult:
    """Validasi ahli dengan koefisien Aiken's V.

    ``ratings`` berisi satu baris per butir dan satu kolom per penilai ahli.
    V = Σs / (n(c−1)) dengan s = r − lo.
    """
    if not ratings or not ratings[0]:
        raise AnalysisError("Data penilaian ahli kosong.")

    n_raters = len(ratings[0])
    c = scale_max - scale_min + 1
    labels = item_labels or [f"Butir {i + 1}" for i in range(len(ratings))]

    rows, values, low = [], {}, []
    for label, item in zip(labels, ratings):
        s_total = sum(float(r) - scale_min for r in item)
        v = s_total / (n_raters * (c - 1)) if n_raters and c > 1 else float("nan")
        interpretation = "Tinggi" if v >= 0.8 else ("Sedang" if v >= 0.4 else "Rendah")
        if v < 0.6:
            low.append(label)
        rows.append([label, *[_r(x, 2) for x in item], _r(s_total, 2), _r(v)])
        values[label] = {"aiken_v": _r(v), "category": interpretation}

    overall = float(np.mean([v["aiken_v"] for v in values.values() if v["aiken_v"] is not None]))
    return AnalysisResult(
        method="aiken_v",
        label="Validasi ahli (Aiken's V)",
        params={"n_raters": n_raters, "scale_min": scale_min, "scale_max": scale_max},
        tables=[
            Table(
                title="Hasil Validasi Ahli",
                columns=["Butir", *[f"Ahli {i + 1}" for i in range(n_raters)], "Σs", "V"],
                rows=rows,
                note=f"V = Σs / (n(c−1)) dengan n = {n_raters} penilai dan c = {int(c)} "
                     f"kategori skala.",
            )
        ],
        values={"overall_v": _r(overall), "items": values, "low_items": low},
        findings=[
            f"Rata-rata koefisien Aiken's V seluruh butir sebesar {_r(overall)}, "
            f"termasuk kategori {'tinggi' if overall >= 0.8 else ('sedang' if overall >= 0.4 else 'rendah')}.",
            (
                f"Butir dengan V di bawah 0,6 dan perlu direvisi: {', '.join(low)}."
                if low
                else "Seluruh butir memperoleh koefisien V yang memadai."
            ),
        ],
        warnings=([f"Butir perlu revisi: {', '.join(low)}."] if low else []),
    )


# --- SEM & PLS ---------------------------------------------------------------


def pls_measurement_model(
    loadings: dict[str, dict[str, float]],
    correlations: dict[str, dict[str, float]] | None = None,
) -> AnalysisResult:
    """Baca output model pengukuran SmartPLS/Lisrel menjadi tabel dan narasi.

    Recens tidak mengestimasi ulang model PLS; ia membaca nilai loading yang
    dikeluarkan perangkat, lalu menghitung AVE dan Composite Reliability dari
    nilai tersebut serta menguji kriteria Fornell-Larcker bila matriks korelasi
    antarkonstruk disertakan.

    AVE = Σλ²/k;  CR = (Σλ)² / ((Σλ)² + Σ(1−λ²)).
    """
    if not loadings:
        raise AnalysisError("Nilai loading belum diisi.")

    loading_rows, construct_rows, values = [], [], {}
    low_loadings = []
    for construct, items in loadings.items():
        lambdas = [float(v) for v in items.values()]
        k = len(lambdas)
        if k == 0:
            continue
        ave = sum(v**2 for v in lambdas) / k
        sum_lambda = sum(lambdas)
        sum_error = sum(1 - v**2 for v in lambdas)
        cr = (
            (sum_lambda**2) / ((sum_lambda**2) + sum_error)
            if (sum_lambda or sum_error)
            else float("nan")
        )

        for item, value in items.items():
            valid = float(value) >= 0.7
            if not valid:
                low_loadings.append(f"{construct}.{item}")
            loading_rows.append([construct, item, _r(value), "Valid" if valid else "Di bawah 0,70"])

        construct_rows.append(
            [construct, k, _r(ave), _r(cr),
             "Memenuhi" if ave >= 0.5 and cr >= 0.7 else "Belum memenuhi"]
        )
        values[construct] = {
            "ave": _r(ave), "cr": _r(cr), "sqrt_ave": _r(math.sqrt(ave)), "n_items": k,
            "meets_criteria": bool(ave >= 0.5 and cr >= 0.7),
        }

    tables = [
        Table(
            title="Nilai Outer Loading",
            columns=["Konstruk", "Indikator", "Loading", "Keterangan"],
            rows=loading_rows,
            note="Indikator dinyatakan valid bila nilai loading ≥ 0,70.",
        ),
        Table(
            title="Validitas Konvergen dan Reliabilitas Konstruk",
            columns=["Konstruk", "Jumlah Indikator", "AVE", "Composite Reliability",
                     "Keterangan"],
            rows=construct_rows,
            note="Kriteria: AVE ≥ 0,50 dan Composite Reliability ≥ 0,70. Cronbach's Alpha "
                 "tidak dapat diturunkan dari nilai loading; salin nilainya langsung dari "
                 "keluaran perangkat bila diperlukan.",
        ),
    ]

    findings = [
        "Nilai AVE dan Composite Reliability dihitung dari nilai loading yang "
        "dikeluarkan perangkat analisis.",
    ]
    failing = [c for c, v in values.items() if not v["meets_criteria"]]
    findings.append(
        f"Konstruk {', '.join(failing)} belum memenuhi kriteria validitas konvergen."
        if failing
        else "Seluruh konstruk memenuhi kriteria validitas konvergen dan reliabilitas."
    )

    if correlations:
        discriminant_rows, violations = [], []
        for construct, row in correlations.items():
            sqrt_ave = values.get(construct, {}).get("sqrt_ave")
            line = [construct, sqrt_ave]
            for other, corr_value in row.items():
                if other == construct:
                    line.append("—")
                    continue
                line.append(_r(corr_value))
                if sqrt_ave is not None and abs(float(corr_value)) > sqrt_ave:
                    violations.append(f"{construct}–{other}")
            discriminant_rows.append(line)
        tables.append(
            Table(
                title="Uji Validitas Diskriminan (Fornell-Larcker)",
                columns=["Konstruk", "√AVE"] + [c for c in next(iter(correlations.values()))],
                rows=discriminant_rows,
                note="Akar AVE tiap konstruk harus lebih besar daripada korelasinya "
                     "dengan konstruk lain.",
            )
        )
        findings.append(
            f"Kriteria Fornell-Larcker belum terpenuhi pada pasangan: {', '.join(set(violations))}."
            if violations
            else "Seluruh konstruk memenuhi kriteria Fornell-Larcker sehingga validitas "
                 "diskriminan terpenuhi."
        )
        values["fornell_larcker_violations"] = sorted(set(violations))

    return AnalysisResult(
        method="pls_measurement",
        label="Model pengukuran PLS",
        params={"constructs": list(loadings)},
        tables=tables,
        values=values,
        findings=findings,
        warnings=(
            [f"Indikator dengan loading di bawah 0,70: {', '.join(low_loadings)}."]
            if low_loadings
            else []
        ),
    )


def pls_structural_model(paths: list[dict]) -> AnalysisResult:
    """Baca hasil uji jalur (bootstrapping) menjadi tabel dan narasi.

    Tiap jalur berisi ``from``, ``to``, ``coefficient``, ``t_statistic``, dan
    ``p_value`` sebagaimana dikeluarkan SmartPLS.
    """
    if not paths:
        raise AnalysisError("Daftar jalur struktural kosong.")

    rows, values, supported = [], {}, []
    for index, path in enumerate(paths, start=1):
        source, target = path.get("from", "?"), path.get("to", "?")
        coefficient = float(path.get("coefficient", float("nan")))
        t_statistic = float(path.get("t_statistic", float("nan")))
        p_value = float(path.get("p_value", float("nan")))
        is_significant = bool(p_value < ALPHA_DEFAULT) if not math.isnan(p_value) else False
        label = f"{source} → {target}"
        if is_significant:
            supported.append(label)
        rows.append([f"H{index}", label, _r(coefficient), _r(t_statistic), _p_label(p_value),
                     "Diterima" if is_significant else "Ditolak"])
        values[label] = {
            "coefficient": _r(coefficient), "t_statistic": _r(t_statistic),
            "p_value": _r(p_value, 4), "significant": is_significant,
        }

    return AnalysisResult(
        method="pls_structural",
        label="Model struktural PLS",
        params={"n_paths": len(paths)},
        tables=[
            Table(
                title="Hasil Uji Jalur (Path Coefficients)",
                columns=["Hipotesis", "Jalur", "Koefisien", "T Statistik", "P Values",
                         "Keputusan"],
                rows=rows,
                note="Jalur dinyatakan signifikan bila T statistik > 1,96 dan p < 0,05.",
            )
        ],
        values=values,
        findings=[
            f"Dari {len(paths)} jalur yang diuji, {len(supported)} jalur berpengaruh "
            f"signifikan: {', '.join(supported) if supported else 'tidak ada'}.",
            *[
                f"Jalur {label} memiliki koefisien {info['coefficient']} dengan T statistik "
                f"{info['t_statistic']} dan p {info['p_value']}, sehingga hipotesis "
                f"{'diterima' if info['significant'] else 'ditolak'}."
                for label, info in values.items()
            ],
        ],
    )
