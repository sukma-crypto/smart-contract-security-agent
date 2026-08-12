"""Penerjemah keluaran jadi menjadi tabel dan narasi BAB IV.

Inilah yang dicari mahasiswa yang datang membawa hasil olahan SPSS-nya. Ia
sudah punya angkanya — yang tidak ia punya adalah kalimatnya. Yang tertulis di
layar SPSS adalah "Sig. ,000"; yang harus tertulis di naskahnya adalah kenapa
angka itu berarti hipotesisnya diterima, dan itulah jarak yang ditutup modul
ini.

Satu aturan mengikat seluruh berkas ini: **angka dibaca apa adanya.** Tidak
ada nilai yang dihitung ulang, dibulatkan diam-diam, atau diperbaiki. Kalau
tabelnya menuliskan R Square 0,659, naskahnya menuliskan 0,659 — sebab
mahasiswa akan ditanya penguji sambil memegang cetakan output yang sama, dan
angka yang berbeda seujung pun antara layar dan naskah adalah bencana kecil di
ruang sidang.

Yang boleh ditambahkan Recens hanyalah pembanding yang memang bukan milik
output itu: nilai r, t, dan F tabel pada taraf 5%. Ketiganya dihitung dari
distribusinya, disebut asalnya secara terbuka di narasi, dan tidak pernah
menggantikan angka mana pun.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from . import output
from .engine import (
    ALPHA_DEFAULT,
    AnalysisResult,
    Table,
    f_table,
    interpret_alpha,
    r_table,
    t_table,
)

CATATAN_TEMPEL = (
    "Angka pada tabel di atas dibaca apa adanya dari keluaran yang Anda tempel. "
    "Recens tidak menghitung ulang maupun mengubahnya."
)


# --- Pembantu ----------------------------------------------------------------


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def _num(value: Any, digits: int = 3) -> str:
    """Tulis angka untuk narasi.

    Titik desimal dipertahankan di sini; ``to_indonesian_decimals`` mengubahnya
    menjadi koma pada tahap akhir, setelah penjaga penelusuran angka selesai
    membandingkan bilangannya.
    """
    if value is None:
        return "-"
    number = float(value)
    if number.is_integer() and abs(number) < 1e9:
        return str(int(number))
    return f"{number:.{digits}f}"


def _p_kalimat(p: float | None, batas_atas: bool = False) -> str:
    """Tulis nilai signifikansi sebagaimana SPSS menampilkannya, lalu perbaiki.

    SPSS mencetak ",000" yang secara harfiah berarti nol, padahal maksudnya
    "lebih kecil dari 0,0005". Mahasiswa menyalinnya mentah-mentah dan ditegur
    penguji. Yang ditulis di sini keduanya: angka yang ia lihat di layar,
    beserta bentuk yang benar untuk naskah.
    """
    if p is None:
        return "signifikansi tidak tersedia"
    if batas_atas or p < 0.0005:
        # SPSS mencetak ",000" dan R mencetak "2.2e-16"; keduanya berarti hal
        # yang sama dan ditulis dengan cara yang sama di naskah. Menuliskan
        # "0,00000" hanya memindahkan kebingungannya, tidak menyelesaikannya.
        return "signifikansi 0,000 (dilaporkan sebagai p < 0,001)"
    if p < 0.001:
        return f"signifikansi {_num(p, 4)} (dilaporkan sebagai p < 0,001)"
    return f"signifikansi {_num(p)}"


def _kekuatan(r: float) -> str:
    besar = abs(r)
    if besar < 0.2:
        return "sangat lemah"
    if besar < 0.4:
        return "lemah"
    if besar < 0.6:
        return "sedang"
    if besar < 0.8:
        return "kuat"
    return "sangat kuat"


def _cari_kolom(block: output.Block, *petunjuk: str, ekor: str | None = None) -> int | None:
    """Indeks kolom yang judulnya memuat seluruh petunjuk sebagai kata utuh.

    Kata utuh, bukan potongan. Kolom statistik banyak yang bernama satu huruf,
    dan pencocokan potongan membuat "F" cocok dengan "df" — persis kekeliruan
    yang membuat nilai F hitung terbaca sebagai derajat bebas, lalu tertulis di
    naskah sebagai "F hitung sebesar 2".
    """
    for index, header in enumerate(block.columns):
        tokens = _norm(header).split()
        if not tokens:
            continue
        if not all(all(t in tokens for t in _norm(p).split()) for p in petunjuk):
            continue
        if ekor is not None:
            ekor_tokens = _norm(ekor).split()
            if tokens[-len(ekor_tokens) :] != ekor_tokens:
                continue
        return index
    return None


def _kolom_label(block: output.Block) -> int:
    """Kolom yang memuat nama baris — variabel, butir, atau konstruk.

    Dipilih dari isinya, bukan judulnya: SPSS kerap membiarkan judul kolom ini
    kosong, dan pada tabel Coefficients ia bahkan kolom kedua karena kolom
    pertama diisi nomor model.
    """
    terbaik, skor_terbaik = 0, -1.0
    for index in range(len(block.columns)):
        nilai = block.column_at(index)
        teks = [v for v in nilai if isinstance(v, str) and v.strip()]
        if not teks:
            continue
        skor = len(teks) / max(len(nilai), 1)
        if skor > skor_terbaik:
            terbaik, skor_terbaik = index, skor
    return terbaik


def _angka(row: list[Any], index: int | None) -> float | None:
    if index is None or index >= len(row):
        return None
    value = row[index]
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _teks(row: list[Any], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index]).strip()


def _dari_catatan(block: output.Block, pola: str) -> str | None:
    for catatan in block.notes:
        match = re.search(pola, catatan, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")
    return None


@dataclass
class Konteks:
    """Keterangan yang dipungut dari satu blok dan berguna bagi blok lain.

    Keluaran regresi SPSS datang bertiga — Model Summary, ANOVA, Coefficients —
    dan derajat bebas hanya tercetak di ANOVA sementara yang membutuhkannya
    untuk membandingkan t hitung dengan t tabel adalah Coefficients. Karena
    mahasiswa menempel ketiganya sekaligus, keterangan itu bisa dipakai bersama.
    """

    dependent: str | None = None
    df_model: int | None = None
    df_residual: int | None = None
    n: int | None = None
    sumber: str = "SPSS"


def _hasil(
    method: str,
    label: str,
    block: output.Block | None,
    judul_tabel: str,
    ctx: Konteks,
    *,
    tables: list[Table] | None = None,
    values: dict | None = None,
    findings: list[str] | None = None,
    assumptions: list[str] | None = None,
    warnings: list[str] | None = None,
) -> AnalysisResult:
    if tables is None:
        tables = [block.to_table(judul_tabel, note=CATATAN_TEMPEL)] if block else []
    return AnalysisResult(
        method=f"tempel_{method}",
        label=label,
        params={
            "sumber": ctx.sumber,
            "tabel_asal": block.title if block else "",
            "dibaca": "apa adanya, tanpa dihitung ulang",
        },
        tables=tables,
        values=values or {},
        findings=findings or [],
        assumptions=[a.rstrip(" .") for a in (assumptions or [])],
        warnings=warnings or [],
    )


# --- Pengenal blok SPSS ------------------------------------------------------


def _baca_model_summary(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_r = _cari_kolom(block, "r", ekor="r")
    kol_r2 = _cari_kolom(block, "r square")
    if kol_r2 is None:
        return None
    kol_adj = _cari_kolom(block, "adjusted")
    kol_see = _cari_kolom(block, "std error")
    kol_dw = _cari_kolom(block, "durbin")
    if kol_adj is not None and kol_r2 == kol_adj:
        kol_r2 = _cari_kolom(block, "r square", ekor="r square")

    row = block.rows[0]
    r = _angka(row, kol_r)
    r2 = _angka(row, kol_r2)
    if r2 is None:
        return None
    adj = _angka(row, kol_adj)
    see = _angka(row, kol_see)
    dw = _angka(row, kol_dw)

    dep = ctx.dependent or _dari_catatan(block, r"Dependent Variable\s*:\s*(.+)")
    sasaran = f"variabel {dep}" if dep else "variabel terikat"

    persen = round(r2 * 100, 3)
    sisa = round(100 - persen, 3)
    values: dict[str, Any] = {"r_square": r2, "persen_dijelaskan": persen, "sisa_persen": sisa}
    findings = []

    if r is not None:
        values["r"] = r
        findings.append(
            f"Nilai koefisien korelasi (R) sebesar {_num(r)} menunjukkan hubungan yang "
            f"{_kekuatan(r)} antara variabel bebas dan {sasaran}."
        )
    findings.append(
        f"Nilai R Square sebesar {_num(r2)} berarti variabel bebas dalam model mampu "
        f"menjelaskan {_num(persen, 1)}% variasi {sasaran}, sedangkan sisanya "
        f"{_num(sisa, 1)}% dipengaruhi variabel lain di luar model penelitian ini."
    )
    if adj is not None:
        values["adjusted_r_square"] = adj
        findings.append(
            f"Adjusted R Square sebesar {_num(adj)} merupakan nilai yang telah disesuaikan "
            f"terhadap jumlah variabel bebas, sehingga lebih tepat dipakai bila variabel "
            f"bebasnya lebih dari satu."
        )
    if see is not None:
        values["std_error_estimate"] = see
        findings.append(
            f"Standard Error of the Estimate sebesar {_num(see)} menunjukkan rata-rata "
            f"simpangan nilai prediksi model terhadap nilai sebenarnya."
        )

    warnings = []
    if dw is not None:
        values["durbin_watson"] = dw
        findings.append(f"Nilai Durbin-Watson sebesar {_num(dw)}.")
        warnings.append(
            "Kesimpulan autokorelasi menuntut pembandingan nilai Durbin-Watson dengan "
            "batas dL dan dU pada tabel Durbin-Watson sesuai jumlah sampel dan jumlah "
            "variabel bebas. Nilai batas itu tidak termuat dalam keluaran yang Anda "
            "tempel, sehingga kesimpulannya belum bisa ditarik di sini."
        )

    return _hasil(
        "model_summary",
        "Koefisien Determinasi (Model Summary)",
        block,
        "Hasil Uji Koefisien Determinasi",
        ctx,
        values=values,
        findings=findings,
        warnings=warnings,
    )


def _baca_anova_regresi(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_f = _cari_kolom(block, "f", ekor="f")
    kol_sig = _cari_kolom(block, "sig")
    kol_df = _cari_kolom(block, "df")
    if kol_f is None or kol_sig is None:
        return None

    label_kolom = _kolom_label(block)
    baris_regresi = next(
        (r for r in block.rows if "regression" in _norm(_teks(r, label_kolom))), None
    )
    if baris_regresi is None:
        return None
    baris_residual = next(
        (r for r in block.rows if "residual" in _norm(_teks(r, label_kolom))), None
    )

    f_hitung = _angka(baris_regresi, kol_f)
    p = _angka(baris_regresi, kol_sig)
    if f_hitung is None:
        return None
    batas_atas = output.is_upper_bound(
        baris_regresi[kol_sig] if kol_sig < len(block.raw[0] if block.raw else []) else ""
    )
    df1 = _angka(baris_regresi, kol_df)
    df2 = _angka(baris_residual, kol_df) if baris_residual else None
    if df1:
        ctx.df_model = int(df1)
    if df2:
        ctx.df_residual = int(df2)

    dep = ctx.dependent or _dari_catatan(block, r"Dependent Variable\s*:\s*(.+)")
    sasaran = f"variabel {dep}" if dep else "variabel terikat"

    values: dict[str, Any] = {"f_hitung": f_hitung, "signifikansi": p}
    findings = [
        f"Uji F menghasilkan nilai F hitung sebesar {_num(f_hitung)} dengan "
        f"{_p_kalimat(p, batas_atas)}."
    ]
    if df1 and df2:
        values.update({"df1": int(df1), "df2": int(df2)})
        f_tab = f_table(int(df1), int(df2))
        if not math.isnan(f_tab):
            values["f_tabel"] = round(f_tab, 3)
            perbandingan = "lebih besar" if f_hitung > f_tab else "tidak lebih besar"
            findings.append(
                f"Sebagai pembanding, F tabel pada taraf 5% dengan df1 = {int(df1)} dan "
                f"df2 = {int(df2)} adalah {_num(f_tab)} — dihitung Recens dari distribusi F, "
                f"bukan bagian dari keluaran yang Anda tempel. Nilai F hitung {perbandingan} "
                f"daripada F tabel."
            )

    signifikan = p is not None and p < ALPHA_DEFAULT
    if signifikan:
        findings.append(
            f"Karena nilai signifikansi lebih kecil dari 0,05, model regresi dinyatakan "
            f"layak digunakan dan seluruh variabel bebas secara simultan berpengaruh "
            f"signifikan terhadap {sasaran}."
        )
    else:
        findings.append(
            f"Karena nilai signifikansi tidak lebih kecil dari 0,05, variabel bebas secara "
            f"simultan belum terbukti berpengaruh signifikan terhadap {sasaran}. Temuan ini "
            f"tetap dilaporkan apa adanya dan justru perlu dibahas sebab-sebabnya."
        )

    return _hasil(
        "anova_regresi",
        "Uji Kelayakan Model (Uji F)",
        block,
        "Hasil Uji F (ANOVA)",
        ctx,
        values=values,
        findings=findings,
    )


def _baca_koefisien(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_b = _cari_kolom(block, "unstandardized", "b", ekor="b") or _cari_kolom(block, "b", ekor="b")
    kol_beta = _cari_kolom(block, "beta")
    kol_t = _cari_kolom(block, "t", ekor="t")
    kol_sig = _cari_kolom(block, "sig")
    if kol_b is None or kol_sig is None:
        return None

    kol_vif = _cari_kolom(block, "vif")
    kol_tol = _cari_kolom(block, "tolerance")
    label = _kolom_label(block)

    dep = ctx.dependent or _dari_catatan(block, r"Dependent Variable\s*:\s*(.+)") or "Y"
    ctx.dependent = dep

    konstanta: float | None = None
    suku: list[tuple[str, float]] = []
    values: dict[str, Any] = {}
    findings: list[str] = []
    assumptions: list[str] = []
    beta_terbesar: tuple[str, float] | None = None

    t_tab = t_table(ctx.df_residual) if ctx.df_residual else float("nan")
    if not math.isnan(t_tab):
        values["t_tabel"] = round(t_tab, 3)

    for row in block.rows:
        nama = _teks(row, label)
        if not nama:
            continue
        b = _angka(row, kol_b)
        if b is None:
            continue
        adalah_konstanta = "constant" in _norm(nama) or "intercept" in _norm(nama)
        t_hitung = _angka(row, kol_t)
        p = _angka(row, kol_sig)

        if adalah_konstanta:
            konstanta = b
            values["konstanta"] = b
            findings.append(
                f"Nilai konstanta sebesar {_num(b)} berarti apabila seluruh variabel bebas "
                f"bernilai nol, {dep} diperkirakan sebesar {_num(b)}."
            )
            continue

        suku.append((nama, b))
        values[f"koefisien_{nama}"] = b
        arah = "positif" if b >= 0 else "negatif"
        gerak = "menaikkan" if b >= 0 else "menurunkan"
        kalimat = (
            f"Variabel {nama} memiliki koefisien regresi sebesar {_num(b)} yang bernilai "
            f"{arah}, artinya setiap kenaikan satu satuan {nama} akan {gerak} {dep} sebesar "
            f"{_num(abs(b))} satuan dengan asumsi variabel bebas lain tetap."
        )
        if t_hitung is not None:
            values[f"t_{nama}"] = t_hitung
            kalimat += f" Nilai t hitung sebesar {_num(t_hitung)}"
            if not math.isnan(t_tab):
                banding = "lebih besar" if abs(t_hitung) > t_tab else "tidak lebih besar"
                kalimat += f" ({banding} daripada t tabel {_num(t_tab)})"
            kalimat += f" dengan {_p_kalimat(p)}."
        else:
            kalimat += f" Diperoleh {_p_kalimat(p)}."

        if p is not None:
            values[f"sig_{nama}"] = p
            if p < ALPHA_DEFAULT:
                kalimat += (
                    f" Karena signifikansi lebih kecil dari 0,05, {nama} berpengaruh "
                    f"{arah} dan signifikan terhadap {dep}."
                )
            else:
                kalimat += (
                    f" Karena signifikansi tidak lebih kecil dari 0,05, {nama} belum "
                    f"terbukti berpengaruh signifikan terhadap {dep}."
                )
        findings.append(kalimat)

        beta = _angka(row, kol_beta)
        if beta is not None:
            values[f"beta_{nama}"] = beta
            if beta_terbesar is None or abs(beta) > abs(beta_terbesar[1]):
                beta_terbesar = (nama, beta)

        vif = _angka(row, kol_vif)
        tol = _angka(row, kol_tol)
        if vif is not None:
            values[f"vif_{nama}"] = vif
            aman = vif < 10 and (tol is None or tol > 0.10)
            bagian = f"Nilai VIF {nama} sebesar {_num(vif)}"
            if tol is not None:
                values[f"tolerance_{nama}"] = tol
                bagian += f" dengan tolerance {_num(tol)}"
            bagian += (
                "; karena VIF di bawah 10 dan tolerance di atas 0,10, tidak terjadi "
                "multikolinearitas." if aman else
                "; nilai ini melewati batas VIF 10 atau tolerance 0,10, sehingga terdapat "
                "indikasi multikolinearitas yang perlu ditangani."
            )
            assumptions.append(bagian)

    if not suku:
        return None

    persamaan = f"{dep} = {_num(konstanta) if konstanta is not None else '0'}"
    for nama, b in suku:
        persamaan += f" {'+' if b >= 0 else '−'} {_num(abs(b))} {nama}"
    findings.insert(0, f"Persamaan regresi yang terbentuk adalah {persamaan}.")

    if beta_terbesar and len(suku) > 1:
        findings.append(
            f"Berdasarkan nilai Standardized Coefficients Beta, variabel {beta_terbesar[0]} "
            f"memberikan pengaruh paling besar terhadap {dep} dengan beta "
            f"{_num(beta_terbesar[1])}."
        )

    tabel = block.to_table("Hasil Uji Regresi Linear Berganda", note=CATATAN_TEMPEL)
    hasil = _hasil(
        "koefisien",
        "Koefisien Regresi dan Uji t",
        block,
        "Hasil Uji Regresi Linear Berganda",
        ctx,
        tables=[tabel],
        values=values,
        findings=findings,
        assumptions=assumptions,
    )
    hasil.params["persamaan"] = persamaan
    return hasil


def _baca_reliabilitas(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    # Berakhir pada "alpha", bukan sekadar memuat "cronbach". Tabel Item-Total
    # punya kolom "Cronbach's Alpha if Item Deleted", dan tanpa syarat ini nilai
    # alpha-bila-butir-dihapus terbaca sebagai alpha instrumennya.
    kol_alpha = _cari_kolom(block, "cronbach", ekor="alpha")
    if kol_alpha is None or not block.rows:
        return None
    kol_n = _cari_kolom(block, "n of items")
    alpha = _angka(block.rows[0], kol_alpha)
    if alpha is None:
        return None
    butir = _angka(block.rows[0], kol_n)

    values: dict[str, Any] = {"cronbach_alpha": alpha}
    pembuka = f"Nilai Cronbach's Alpha sebesar {_num(alpha)}"
    if butir:
        values["jumlah_butir"] = int(butir)
        pembuka += f" dari {int(butir)} butir pernyataan"
    reliabel = alpha >= 0.7
    findings = [
        pembuka + ".",
        f"Karena nilai tersebut {'lebih besar' if reliabel else 'lebih kecil'} daripada 0,70, "
        f"instrumen dinyatakan {'reliabel' if reliabel else 'belum reliabel'} dengan tingkat "
        f"keandalan {interpret_alpha(alpha)}.",
    ]
    warnings = (
        []
        if reliabel
        else [
            "Instrumen yang belum reliabel sebaiknya diperbaiki butirnya sebelum dipakai "
            "menarik kesimpulan, bukan dilaporkan seolah memenuhi syarat."
        ]
    )
    return _hasil(
        "reliabilitas",
        "Uji Reliabilitas",
        block,
        "Hasil Uji Reliabilitas",
        ctx,
        values=values,
        findings=findings,
        warnings=warnings,
    )


def _baca_item_total(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_r = _cari_kolom(block, "corrected item total")
    if kol_r is None:
        return None
    kol_alpha_hapus = _cari_kolom(block, "alpha if item deleted")
    label = _kolom_label(block)

    batas, asal_batas = 0.300, "batas lazim 0,300"
    if ctx.n and ctx.n > 2:
        nilai = r_table(ctx.n)
        if not math.isnan(nilai):
            batas = round(nilai, 3)
            asal_batas = f"r tabel {_num(batas)} untuk n = {ctx.n}"

    valid, gugur, values = [], [], {"batas_r": batas}
    for row in block.rows:
        nama = _teks(row, label)
        r = _angka(row, kol_r)
        if not nama or r is None:
            continue
        values[f"r_{nama}"] = r
        (valid if r >= batas else gugur).append((nama, r))

    if not valid and not gugur:
        return None

    findings = [
        f"Uji validitas butir dilakukan dengan membandingkan nilai Corrected Item-Total "
        f"Correlation terhadap {asal_batas}."
    ]
    if not gugur:
        findings.append(
            f"Seluruh {len(valid)} butir memiliki nilai di atas batas tersebut, sehingga "
            f"semuanya dinyatakan valid dan layak dipakai untuk analisis selanjutnya."
        )
    else:
        rincian = ", ".join(f"{nama} ({_num(r)})" for nama, r in gugur)
        findings.append(
            f"Sebanyak {len(valid)} butir dinyatakan valid, sedangkan {len(gugur)} butir "
            f"berada di bawah batas dan dinyatakan tidak valid: {rincian}."
        )
        findings.append(
            "Butir yang tidak valid perlu digugurkan atau diperbaiki, lalu uji diulang "
            "pada butir yang tersisa."
        )

    warnings = []
    if kol_alpha_hapus is not None:
        naik = [
            (_teks(row, label), _angka(row, kol_alpha_hapus))
            for row in block.rows
            if _angka(row, kol_alpha_hapus) is not None
        ]
        if naik:
            tertinggi = max(naik, key=lambda pair: pair[1])
            values["alpha_tertinggi_bila_dihapus"] = tertinggi[1]
            warnings.append(
                f"Kolom Cronbach's Alpha if Item Deleted menunjukkan nilai tertinggi "
                f"{_num(tertinggi[1])} bila butir {tertinggi[0]} dihapus. Bandingkan dengan "
                f"alpha keseluruhan untuk memutuskan perlu tidaknya butir itu digugurkan."
            )

    return _hasil(
        "item_total",
        "Uji Validitas Butir",
        block,
        "Hasil Uji Validitas Instrumen",
        ctx,
        values=values,
        findings=findings,
        warnings=warnings,
    )


def _baca_normalitas(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    # Kolom "Sig." ada di hampir setiap tabel SPSS, jadi ia bukan penanda apa
    # pun. Yang menandai uji normalitas adalah nama ujinya sendiri — tanpa
    # syarat ini, tabel Independent Samples Test ikut terbaca sebagai uji
    # normalitas dan menghasilkan kesimpulan yang sama sekali keliru.
    jejak = _norm(block.title) + " " + " ".join(_norm(h) for h in block.columns)
    if not any(kata in jejak for kata in ("normality", "kolmogorov", "shapiro", "liliefors")):
        return None
    kolom_sig = [i for i, h in enumerate(block.columns) if "sig" in _norm(h)]
    if not kolom_sig:
        return None
    label = _kolom_label(block)
    values, findings, assumptions = {}, [], []

    for index in kolom_sig:
        judul = block.columns[index]
        nama_uji = (
            "Shapiro-Wilk" if "shapiro" in _norm(judul)
            else "Kolmogorov-Smirnov" if "kolmogorov" in _norm(judul)
            else "normalitas"
        )
        for row in block.rows:
            variabel = _teks(row, label)
            p = _angka(row, index)
            if p is None:
                continue
            kunci = f"sig_{nama_uji}_{variabel or 'residual'}".replace(" ", "_")
            values[kunci] = p
            normal = p >= ALPHA_DEFAULT
            sasaran = f"variabel {variabel}" if variabel else "residual"
            assumptions.append(
                f"Uji {nama_uji} pada {sasaran} menghasilkan signifikansi {_num(p)} "
                f"({'>' if normal else '<'} 0,05), sehingga data "
                f"{'berdistribusi normal' if normal else 'tidak berdistribusi normal'}"
            )

    if not assumptions:
        return None
    findings.append(
        "Uji normalitas dibaca dari nilai signifikansi: data dinyatakan berdistribusi "
        "normal bila signifikansinya lebih besar dari 0,05."
    )
    warnings = []
    if any("tidak berdistribusi normal" in a for a in assumptions):
        warnings.append(
            "Terdapat data yang tidak berdistribusi normal. Pertimbangkan uji "
            "nonparametrik atau transformasi data, dan laporkan pilihannya secara terbuka."
        )

    return _hasil(
        "normalitas",
        "Uji Normalitas",
        block,
        "Hasil Uji Normalitas",
        ctx,
        values=values,
        findings=findings,
        assumptions=assumptions,
        warnings=warnings,
    )


#: Isi sel yang menerangkan baris, bukan menamai apa yang diuji. SPSS menaruh
#: keduanya berdampingan pada tabel uji beda.
_BUKAN_NAMA = ("equal variances", "pair ")


def _nama_subjek(block: output.Block, baris: list[Any]) -> str:
    """Nama hal yang diuji, bukan nama barisnya.

    Tanpa ini narasinya berbunyi "terdapat perbedaan signifikan pada Equal
    variances assumed" — menyebut label asumsi seolah itu variabel penelitian.
    """
    kandidat = [c for c in baris if isinstance(c, str) and c.strip()]
    if not kandidat and block.rows:
        kandidat = [c for c in block.rows[0] if isinstance(c, str) and c.strip()]
    if block.rows:
        kandidat += [c for c in block.rows[0] if isinstance(c, str) and c.strip()]
    baik = [c for c in kandidat if not any(t in _norm(c) + " " for t in _BUKAN_NAMA)]
    return (baik or kandidat or ["kelompok yang dibandingkan"])[0]


def _baca_uji_beda(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    """Independent Samples Test dan Paired Samples Test."""
    kol_t = _cari_kolom(block, "t", ekor="t")
    kol_sig2 = _cari_kolom(block, "sig", "2 tailed")
    if kol_t is None or kol_sig2 is None:
        return None

    berpasangan = "paired" in _norm(block.title)
    kol_levene_sig = None
    if not berpasangan:
        kandidat = [i for i, h in enumerate(block.columns) if "levene" in _norm(h) and "sig" in _norm(h)]
        kol_levene_sig = kandidat[0] if kandidat else None

    label = _kolom_label(block)
    baris = block.rows[0]
    values, findings, assumptions = {}, [], []

    if kol_levene_sig is not None:
        p_levene = _angka(baris, kol_levene_sig)
        if p_levene is not None:
            values["sig_levene"] = p_levene
            homogen = p_levene >= ALPHA_DEFAULT
            assumptions.append(
                f"Uji Levene menghasilkan signifikansi {_num(p_levene)} "
                f"({'>' if homogen else '<'} 0,05), sehingga varians kedua kelompok "
                f"{'homogen' if homogen else 'tidak homogen'}. Pembacaan uji t memakai baris "
                f"{'Equal variances assumed' if homogen else 'Equal variances not assumed'}."
            )
            if not homogen and len(block.rows) > 1:
                baris = block.rows[1]

    t_hitung = _angka(baris, kol_t)
    p = _angka(baris, kol_sig2)
    if t_hitung is None:
        return None
    values.update({"t_hitung": t_hitung, "sig_2_tailed": p})

    kol_df = _cari_kolom(block, "df")
    df = _angka(baris, kol_df)
    nama = _nama_subjek(block, baris)

    kalimat = f"Nilai t hitung sebesar {_num(t_hitung)}"
    if df is not None:
        values["df"] = df
        kalimat += f" dengan df sebesar {_num(df)}"
        t_tab = t_table(int(df)) if df >= 1 else float("nan")
        if not math.isnan(t_tab):
            values["t_tabel"] = round(t_tab, 3)
            kalimat += f" dan t tabel {_num(t_tab)} pada taraf 5%"
    kalimat += f", serta {_p_kalimat(p)}."
    findings.append(kalimat)

    beda = p is not None and p < ALPHA_DEFAULT
    jenis = "sebelum dan sesudah perlakuan" if berpasangan else "kedua kelompok"
    findings.append(
        f"Karena signifikansi {'lebih kecil' if beda else 'tidak lebih kecil'} dari 0,05, "
        f"{'terdapat' if beda else 'tidak terdapat'} perbedaan yang signifikan antara "
        f"{jenis} pada {nama}."
    )

    kol_selisih = _cari_kolom(block, "mean difference")
    selisih = _angka(baris, kol_selisih)
    if selisih is not None:
        values["selisih_rata_rata"] = selisih
        findings.append(
            f"Selisih rata-rata sebesar {_num(selisih)} menunjukkan arah perbedaannya."
        )

    return _hasil(
        "uji_beda",
        "Uji t Berpasangan" if berpasangan else "Uji t Sampel Bebas",
        block,
        "Hasil Uji t Berpasangan" if berpasangan else "Hasil Uji t Sampel Bebas",
        ctx,
        values=values,
        findings=findings,
        assumptions=assumptions,
    )


def _baca_anova_satu_jalur(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_f = _cari_kolom(block, "f", ekor="f")
    kol_sig = _cari_kolom(block, "sig")
    if kol_f is None or kol_sig is None:
        return None
    label = _kolom_label(block)
    baris = next((r for r in block.rows if "between" in _norm(_teks(r, label))), None)
    if baris is None:
        return None

    f_hitung = _angka(baris, kol_f)
    p = _angka(baris, kol_sig)
    if f_hitung is None:
        return None

    beda = p is not None and p < ALPHA_DEFAULT
    findings = [
        f"Uji ANOVA satu jalur menghasilkan F hitung sebesar {_num(f_hitung)} dengan "
        f"{_p_kalimat(p)}.",
        f"Karena signifikansi {'lebih kecil' if beda else 'tidak lebih kecil'} dari 0,05, "
        f"{'terdapat' if beda else 'tidak terdapat'} perbedaan rata-rata yang signifikan "
        f"antar kelompok.",
    ]
    if beda:
        findings.append(
            "Untuk mengetahui kelompok mana yang berbeda, diperlukan uji lanjut "
            "(post hoc) seperti Tukey atau Bonferroni."
        )
    return _hasil(
        "anova_satu_jalur",
        "ANOVA Satu Jalur",
        block,
        "Hasil Uji ANOVA Satu Jalur",
        ctx,
        values={"f_hitung": f_hitung, "signifikansi": p},
        findings=findings,
    )


# --- Pengenal blok SmartPLS --------------------------------------------------


def _baca_outer_loading(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    if "loading" not in _norm(block.title):
        return None
    label = _kolom_label(block)
    ctx.sumber = "SmartPLS"

    valid, lemah, values = [], [], {}
    for row in block.rows:
        indikator = _teks(row, label)
        if not indikator:
            continue
        for index, konstruk in enumerate(block.columns):
            if index == label:
                continue
            nilai = _angka(row, index)
            if nilai is None:
                continue
            values[f"loading_{indikator}"] = nilai
            (valid if nilai >= 0.7 else lemah).append((indikator, konstruk, nilai))

    if not valid and not lemah:
        return None

    findings = [
        "Validitas konvergen dinilai dari nilai outer loading, dengan batas 0,70 sebagai "
        "syarat indikator dinyatakan valid."
    ]
    if not lemah:
        findings.append(
            f"Seluruh {len(valid)} indikator memiliki outer loading di atas 0,70, sehingga "
            f"semuanya memenuhi validitas konvergen."
        )
    else:
        rincian = ", ".join(f"{i} pada konstruk {k} ({_num(v)})" for i, k, v in lemah)
        findings.append(
            f"Sebanyak {len(valid)} indikator memenuhi batas 0,70, sedangkan {len(lemah)} "
            f"indikator berada di bawahnya: {rincian}."
        )
        findings.append(
            "Indikator dengan loading antara 0,40 dan 0,70 boleh dipertahankan bila "
            "penghapusannya tidak menaikkan AVE maupun composite reliability; di bawah "
            "0,40 sebaiknya dikeluarkan dari model."
        )
    return _hasil(
        "outer_loading",
        "Outer Loading (Validitas Konvergen)",
        block,
        "Hasil Uji Outer Loading",
        ctx,
        values=values,
        findings=findings,
    )


def _baca_reliabilitas_konstruk(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_ave = _cari_kolom(block, "average variance extracted") or _cari_kolom(block, "ave")
    kol_cr = _cari_kolom(block, "composite reliability")
    kol_alpha = _cari_kolom(block, "cronbach")
    if kol_ave is None and kol_cr is None:
        return None
    ctx.sumber = "SmartPLS"
    label = _kolom_label(block)

    values, findings, kurang = {}, [], []
    for row in block.rows:
        konstruk = _teks(row, label)
        if not konstruk:
            continue
        ave = _angka(row, kol_ave)
        cr = _angka(row, kol_cr)
        alpha = _angka(row, kol_alpha)
        bagian = [f"Konstruk {konstruk} memiliki"]
        if alpha is not None:
            values[f"alpha_{konstruk}"] = alpha
            bagian.append(f"Cronbach's Alpha {_num(alpha)},")
        if cr is not None:
            values[f"cr_{konstruk}"] = cr
            bagian.append(f"composite reliability {_num(cr)},")
        if ave is not None:
            values[f"ave_{konstruk}"] = ave
            bagian.append(f"dan AVE {_num(ave)}.")
        memenuhi = (ave is None or ave >= 0.5) and (cr is None or cr >= 0.7)
        if not memenuhi:
            kurang.append(konstruk)
        bagian.append(
            "Nilai ini memenuhi syarat AVE minimal 0,50 dan composite reliability minimal 0,70."
            if memenuhi
            else "Nilai ini belum memenuhi syarat AVE minimal 0,50 atau composite "
                 "reliability minimal 0,70."
        )
        findings.append(" ".join(bagian))

    if not findings:
        return None
    ringkas = (
        "Seluruh konstruk memenuhi syarat reliabilitas dan validitas konvergen."
        if not kurang
        else f"Konstruk yang belum memenuhi syarat: {', '.join(kurang)}."
    )
    findings.append(ringkas)
    return _hasil(
        "reliabilitas_konstruk",
        "Reliabilitas dan Validitas Konstruk",
        block,
        "Hasil Uji Reliabilitas dan Validitas Konstruk",
        ctx,
        values=values,
        findings=findings,
    )


def _baca_koefisien_jalur(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    kol_p = _cari_kolom(block, "p values") or _cari_kolom(block, "p value")
    kol_t = _cari_kolom(block, "t statistics")
    kol_o = (
        _cari_kolom(block, "original sample")
        or _cari_kolom(block, "path coefficient")
        or _cari_kolom(block, "sample mean")
    )
    if kol_p is None and kol_t is None:
        return None
    ctx.sumber = "SmartPLS"
    label = _kolom_label(block)

    values, findings = {}, []
    diterima = ditolak = 0
    for row in block.rows:
        jalur = _teks(row, label)
        if not jalur:
            continue
        koefisien = _angka(row, kol_o)
        t_stat = _angka(row, kol_t)
        p = _angka(row, kol_p)

        bagian = f"Pengaruh {jalur}"
        if koefisien is not None:
            values[f"jalur_{jalur}"] = koefisien
            arah = "positif" if koefisien >= 0 else "negatif"
            bagian += f" memiliki koefisien jalur {_num(koefisien)} yang bernilai {arah}"
        if t_stat is not None:
            values[f"t_{jalur}"] = t_stat
            banding = "lebih besar" if abs(t_stat) > 1.96 else "tidak lebih besar"
            bagian += f", dengan t statistik {_num(t_stat)} yang {banding} daripada 1,96"
        if p is not None:
            values[f"p_{jalur}"] = p
            bagian += f" dan {_p_kalimat(p)}"
        signifikan = (p is not None and p < ALPHA_DEFAULT) or (
            p is None and t_stat is not None and abs(t_stat) > 1.96
        )
        diterima += int(signifikan)
        ditolak += int(not signifikan)
        bagian += (
            ". Dengan demikian hipotesis pada jalur ini diterima."
            if signifikan
            else ". Dengan demikian hipotesis pada jalur ini tidak diterima."
        )
        findings.append(bagian)

    if not findings:
        return None
    findings.insert(
        0,
        "Pengujian hipotesis dilakukan dengan membandingkan nilai t statistik terhadap "
        "1,96 dan nilai p terhadap 0,05 pada taraf keyakinan 95%.",
    )
    values.update({"hipotesis_diterima": diterima, "hipotesis_ditolak": ditolak})
    return _hasil(
        "koefisien_jalur",
        "Koefisien Jalur dan Uji Hipotesis",
        block,
        "Hasil Uji Koefisien Jalur",
        ctx,
        values=values,
        findings=findings,
    )


# --- Cadangan ----------------------------------------------------------------


def _baca_tabel_umum(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    """Tabel yang belum dikenali tetap dirapikan dan tetap bisa masuk naskah.

    Menolak tabel yang tidak dikenali akan membuang pekerjaan yang sudah benar:
    angkanya sudah terbaca, penomoran dan pemformatannya sudah bisa dikerjakan,
    dan yang belum ada hanya penafsirannya. Lebih baik menyerahkan tabel rapi
    tanpa narasi daripada tidak menyerahkan apa pun.
    """
    if not block.rows:
        return None
    judul = block.title or "Tabel Hasil"
    return _hasil(
        "tabel",
        judul,
        block,
        judul,
        ctx,
        findings=[],
        warnings=[
            "Recens belum mengenali jenis tabel ini, sehingga hanya merapikan dan "
            "menomorinya tanpa menyusun narasi. Tabelnya tetap bisa disisipkan ke naskah, "
            "dan pembahasannya Anda tulis sendiri."
        ],
    )


#: Diperiksa berurutan; yang pertama cocok dipakai. Yang khusus didahulukan,
#: sebab tabel Coefficients juga memuat kolom "Sig." seperti ANOVA.
PENGENAL: list[tuple[str, Callable[[output.Block, Konteks], AnalysisResult | None]]] = [
    ("model summary", _baca_model_summary),
    ("coefficients", _baca_koefisien),
    ("anova regresi", _baca_anova_regresi),
    ("item total", _baca_item_total),
    ("reliability statistics", _baca_reliabilitas),
    ("normality", _baca_normalitas),
    ("samples test", _baca_uji_beda),
    ("anova satu jalur", _baca_anova_satu_jalur),
    ("outer loading", _baca_outer_loading),
    ("construct reliability", _baca_reliabilitas_konstruk),
    ("path coefficients", _baca_koefisien_jalur),
]


def _kenali(block: output.Block, ctx: Konteks) -> AnalysisResult | None:
    for _nama, pembaca in PENGENAL:
        try:
            hasil = pembaca(block, ctx)
        except (IndexError, TypeError, ValueError):
            # Satu tabel yang bentuknya tidak terduga tidak boleh menjatuhkan
            # seluruh tempelan; ia turun ke pembaca umum.
            continue
        if hasil is not None:
            return hasil
    return _baca_tabel_umum(block, ctx)


# --- Keluaran R --------------------------------------------------------------


def _dari_r(text: str, ctx: Konteks) -> list[AnalysisResult]:
    ctx.sumber = "R"
    hasil: list[AnalysisResult] = []

    model = output.read_r_lm(text)
    if model:
        ctx.dependent = model.get("dependent")
        ctx.df_residual = model.get("df_residual")
        hasil.extend(_r_ringkasan_model(model, ctx))
        hasil.append(_r_koefisien(model, ctx))

    for uji in output.read_r_tests(text):
        satu = _r_uji_ringkas(uji, ctx)
        if satu is not None:
            hasil.append(satu)
    return hasil


def _r_ringkasan_model(model: dict, ctx: Konteks) -> list[AnalysisResult]:
    r2 = model.get("r_squared")
    if r2 is None:
        return []
    adj = model.get("adj_r_squared")
    f = model.get("f_statistic")
    p = model.get("f_p_value")
    dep = ctx.dependent or "variabel terikat"

    persen = round(r2 * 100, 3)
    sisa = round(100 - persen, 3)
    values: dict[str, Any] = {
        "r_square": r2, "persen_dijelaskan": persen, "sisa_persen": sisa,
    }
    baris = [["R-squared", r2]]
    findings = [
        f"Nilai R-squared sebesar {_num(r2)} berarti variabel bebas dalam model menjelaskan "
        f"{_num(persen, 1)}% variasi {dep}, sedangkan {_num(sisa, 1)}% sisanya dipengaruhi "
        f"variabel lain di luar model."
    ]
    if adj is not None:
        values["adjusted_r_square"] = adj
        baris.append(["Adjusted R-squared", adj])
    if f is not None:
        values["f_hitung"] = f
        baris.append(["F-statistic", f])
        if p is not None:
            values["signifikansi"] = p
            baris.append(["p-value", p])
        layak = p is not None and p < ALPHA_DEFAULT
        findings.append(
            f"Uji F menghasilkan nilai {_num(f)} dengan {_p_kalimat(p, model.get('f_p_upper_bound', False))}, "
            f"sehingga model {'dinyatakan layak dan variabel bebas secara simultan berpengaruh signifikan' if layak else 'belum terbukti layak secara statistik'}."
        )

    tabel = Table(
        title="Ringkasan Model Regresi",
        columns=["Statistik", "Nilai"],
        rows=baris,
        note=CATATAN_TEMPEL,
    )
    return [
        _hasil(
            "model_summary",
            "Ringkasan Model Regresi (R)",
            None,
            "Ringkasan Model Regresi",
            ctx,
            tables=[tabel],
            values=values,
            findings=findings,
        )
    ]


def _r_koefisien(model: dict, ctx: Konteks) -> AnalysisResult:
    dep = ctx.dependent or "Y"
    baris, values, findings = [], {}, []
    konstanta, suku = None, []

    for koefisien in model["coefficients"]:
        nama = koefisien["term"]
        b = koefisien["estimate"]
        baris.append([nama, b, koefisien["std_error"], koefisien["t"], koefisien["p_value"]])
        if "intercept" in _norm(nama) or "constant" in _norm(nama):
            konstanta = b
            values["konstanta"] = b
            findings.append(
                f"Nilai intercept sebesar {_num(b)} berarti apabila seluruh variabel bebas "
                f"bernilai nol, {dep} diperkirakan sebesar {_num(b)}."
            )
            continue

        suku.append((nama, b))
        values[f"koefisien_{nama}"] = b
        p = koefisien["p_value"]
        if p is not None:
            values[f"sig_{nama}"] = p
        arah = "positif" if b >= 0 else "negatif"
        gerak = "menaikkan" if b >= 0 else "menurunkan"
        signifikan = p is not None and p < ALPHA_DEFAULT
        kalimat = (
            f"Variabel {nama} memiliki estimasi koefisien sebesar {_num(b)} yang bernilai "
            f"{arah}, artinya setiap kenaikan satu satuan {nama} akan {gerak} {dep} sebesar "
            f"{_num(abs(b))} satuan dengan asumsi variabel lain tetap."
        )
        if koefisien["t"] is not None:
            values[f"t_{nama}"] = koefisien["t"]
            kalimat += f" Nilai t sebesar {_num(koefisien['t'])} dengan {_p_kalimat(p, koefisien.get('p_upper_bound', False))}."
        kalimat += (
            f" Karena p lebih kecil dari 0,05, {nama} berpengaruh {arah} dan signifikan "
            f"terhadap {dep}."
            if signifikan
            else f" Karena p tidak lebih kecil dari 0,05, {nama} belum terbukti berpengaruh "
                 f"signifikan terhadap {dep}."
        )
        findings.append(kalimat)

    persamaan = f"{dep} = {_num(konstanta) if konstanta is not None else '0'}"
    for nama, b in suku:
        persamaan += f" {'+' if b >= 0 else '−'} {_num(abs(b))} {nama}"
    findings.insert(0, f"Persamaan regresi yang terbentuk adalah {persamaan}.")

    tabel = Table(
        title="Hasil Uji Regresi Linear Berganda",
        columns=["Variabel", "Estimasi", "Std. Error", "t", "p"],
        rows=baris,
        note=CATATAN_TEMPEL,
    )
    hasil = _hasil(
        "koefisien",
        "Koefisien Regresi dan Uji t (R)",
        None,
        "Hasil Uji Regresi Linear Berganda",
        ctx,
        tables=[tabel],
        values=values,
        findings=findings,
    )
    hasil.params["persamaan"] = persamaan
    return hasil


_LABEL_UJI_R = {
    "shapiro": ("Uji Normalitas Shapiro-Wilk", "w", "W"),
    "ks": ("Uji Normalitas Kolmogorov-Smirnov", "d", "D"),
    "t": ("Uji t", "t", "t"),
    "chisq": ("Uji Chi-Square", "chi", "chi-squared"),
    "wilcox": ("Uji Nonparametrik", "stat", "statistik"),
}


def _r_uji_ringkas(uji: dict, ctx: Konteks) -> AnalysisResult | None:
    jenis = uji["jenis"]
    label, kunci_stat, nama_stat = _LABEL_UJI_R.get(jenis, ("Uji Statistik", "stat", "statistik"))
    stats = uji["stats"]
    p = stats.get("p")
    statistik = stats.get(kunci_stat)
    if p is None:
        return None

    judul = uji.get("nama") or label
    values = {"signifikansi": p}
    baris = []
    if statistik is not None:
        values["statistik"] = statistik
        baris.append([nama_stat, statistik])
    if "df" in stats and stats["df"] is not None:
        values["df"] = stats["df"]
        baris.append(["df", stats["df"]])
    baris.append(["p-value", p])

    signifikan = p < ALPHA_DEFAULT
    if jenis in ("shapiro", "ks"):
        kesimpulan = (
            f"Karena p tidak lebih kecil dari 0,05, data dinyatakan berdistribusi normal."
            if not signifikan
            else "Karena p lebih kecil dari 0,05, data dinyatakan tidak berdistribusi normal."
        )
    else:
        kesimpulan = (
            "Karena p lebih kecil dari 0,05, perbedaan yang diuji dinyatakan signifikan."
            if signifikan
            else "Karena p tidak lebih kecil dari 0,05, perbedaan yang diuji belum terbukti "
                 "signifikan. Hasil ini tetap dilaporkan apa adanya."
        )

    pembuka = f"{judul} dijalankan"
    if uji.get("data"):
        pembuka += f" pada {uji['data']}"
    pembuka += f" dan menghasilkan {_p_kalimat(p, uji.get('p_upper_bound', False))}."

    return _hasil(
        "uji_r",
        judul,
        None,
        judul,
        ctx,
        tables=[Table(title=judul, columns=["Statistik", "Nilai"], rows=baris, note=CATATAN_TEMPEL)],
        values=values,
        findings=[pembuka, kesimpulan],
    )


# --- Pintu masuk -------------------------------------------------------------


def translate(text: str) -> list[AnalysisResult]:
    """Baca satu tempelan keluaran menjadi rangkaian hasil siap masuk naskah.

    Kembaliannya berupa ``AnalysisResult`` yang sama persis bentuknya dengan
    hasil uji yang dihitung Recens sendiri. Itu disengaja: dengan begitu
    tempelan mengalir lewat jalur yang sama — dinarasikan, dinomori, diperiksa
    penelusuran angkanya, lalu disisipkan ke BAB IV — tanpa satu pun cabang
    khusus yang harus dirawat terpisah.
    """
    if not (text or "").strip():
        return []

    ctx = Konteks()
    if output.looks_like_r(text):
        hasil = _dari_r(text, ctx)
        if hasil:
            return hasil

    blocks = output.split_blocks(text)
    if not blocks:
        return []

    # Nama variabel terikat dan derajat bebas dipungut lebih dulu, sebab tabel
    # yang membutuhkannya bisa muncul sebelum tabel yang memuatnya.
    for block in blocks:
        dep = _dari_catatan(block, r"Dependent Variable\s*:\s*(.+)")
        if dep:
            ctx.dependent = dep
        if "anova" in _norm(block.title):
            kol_df = _cari_kolom(block, "df")
            label = _kolom_label(block)
            for row in block.rows:
                nama = _norm(_teks(row, label))
                nilai = _angka(row, kol_df)
                if nilai is None:
                    continue
                if "regression" in nama:
                    ctx.df_model = int(nilai)
                elif "residual" in nama:
                    ctx.df_residual = int(nilai)
        if "reliability" in _norm(block.title):
            kol_n = _cari_kolom(block, "n of items")
            if kol_n is None:
                kol_n = _cari_kolom(block, "n")
            if kol_n is not None and block.rows:
                nilai = _angka(block.rows[0], kol_n)
                if nilai and nilai > 20:
                    ctx.n = int(nilai)

    hasil = []
    for block in blocks:
        satu = _kenali(block, ctx)
        if satu is not None:
            hasil.append(satu)
    return hasil
