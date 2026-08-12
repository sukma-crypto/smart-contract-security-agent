"""Pembacaan keluaran perangkat statistik lain (SPSS, R, SmartPLS).

Contoh di berkas ini disalin mengikuti bentuk aslinya, bukan dirapikan. Justru
kerapian palsu itulah yang membuat pembaca sebelumnya lolos uji tetapi gagal
pada tempelan sungguhan: nol di depan koma yang dibuang SPSS, huruf catatan
kaki yang menempel pada angka, dan judul kolom yang tersebar di dua baris.
"""

from __future__ import annotations

import pytest

from recens.core.stats import output

MODEL_SUMMARY = """Model Summary
Model\tR\tR Square\tAdjusted R Square\tStd. Error of the Estimate
1\t.812a\t.659\t.648\t2.31449
a. Predictors: (Constant), X2, X1"""

COEFFICIENTS = """Coefficientsa
Model\t\tUnstandardized Coefficients\t\tStandardized Coefficients\tt\tSig.
\t\tB\tStd. Error\tBeta\t\t
1\t(Constant)\t4.212\t2.145\t\t1.964\t.054
\tX1\t.523\t.098\t.512\t5.337\t.000
\tX2\t.311\t.087\t.343\t3.575\t.001
a. Dependent Variable: Y"""

RINGKASAN_R = """Call:
lm(formula = Y ~ X1 + X2, data = data)

Coefficients:
            Estimate Std. Error t value Pr(>|t|)
(Intercept)  4.21200    2.14500   1.964   0.0544 .
X1           0.52300    0.09800   5.337 1.53e-06 ***
X2           0.31100    0.08700   3.575 0.000692 ***
---
Signif. codes:  0 '***' 0.001 '**' 0.01 '*' 0.05 '.' 0.1 ' ' 1

Residual standard error: 2.314 on 59 degrees of freedom
Multiple R-squared:  0.659,\tAdjusted R-squared:  0.6475
F-statistic: 57.16 on 2 and 59 DF,  p-value: 2.2e-14"""


class TestPembacaanAngka:
    @pytest.mark.parametrize(
        "teks, harapan",
        [
            (".659", 0.659),      # SPSS membuang nol di depan
            ("-.523", -0.523),
            (".812a", 0.812),     # penanda catatan kaki menempel
            (".200c,d", 0.200),   # beberapa penanda sekaligus
            ("0.523***", 0.523),  # kode signifikansi R
            ("1.53e-06", 1.53e-06),
            ("2.31449", 2.31449),
            ("61", 61.0),
            ("−0.42", -0.42),     # minus bukan ASCII, dari salinan Word
        ],
    )
    def test_bentuk_angka_yang_benar_benar_muncul(self, teks, harapan):
        assert output.parse_number(teks) == pytest.approx(harapan)

    @pytest.mark.parametrize("teks", ["", ".", "-", "Beta", "Sig. (2-tailed)", "N of Items"])
    def test_yang_bukan_angka_tidak_dipaksa_jadi_angka(self, teks):
        assert output.parse_number(teks) is None

    def test_nol_di_depan_yang_dibuang_bukan_teks(self):
        """Cacat yang paling mahal bila terlewat.

        Nyaris seluruh nilai penting pada keluaran SPSS — R Square, korelasi,
        dan setiap Sig. — ditulis tanpa nol di depan. Pembaca yang menuntut
        digit sebelum titik akan membaca semuanya sebagai teks, dan tabelnya
        tampak terbaca padahal tidak ada satu angka pun yang tertangkap.
        """
        blok = output.split_blocks(MODEL_SUMMARY)[0]
        assert blok.rows[0][2] == pytest.approx(0.659)
        assert isinstance(blok.rows[0][2], float)

    def test_penanda_batas_atas_dikenali(self):
        assert output.parse_number("<,001") == pytest.approx(0.001)
        assert output.is_upper_bound("<,001") is True
        assert output.is_upper_bound(".001") is False


class TestPemisahDesimalTempelan:
    """SPSS berlokal Indonesia memakai koma, dan salah baca di sini senyap.

    ``2,145`` yang dibaca sebagai pemisah ribuan menjadi 2145 — koefisien yang
    keliru seribu kali lipat, ditulis ke naskah tanpa satu pun tanda bahaya.
    """

    def test_koma_dikenali_dari_buktinya(self):
        tempelan = "Cronbach's Alpha\tN of Items\n,874\t10"
        blok = output.split_blocks(tempelan)[0]
        assert blok.decimal == ","
        assert blok.rows[0][0] == pytest.approx(0.874)

    def test_titik_tetap_bawaan_bila_tak_ada_bukti_koma(self):
        assert output.split_blocks(MODEL_SUMMARY)[0].decimal == "."

    def test_ribuan_dan_desimal_tidak_tertukar(self):
        assert output.parse_number("1.234,56", ",") == pytest.approx(1234.56)
        assert output.parse_number("1,234.56", ".") == pytest.approx(1234.56)

    def test_angka_berawalan_koma_selalu_desimal(self):
        """Berlaku walau tempelannya ditebak berpemisah titik.

        Tidak ada notasi ribuan yang dibuka pemisah, jadi bentuk ini tidak
        pernah ambigu — dan menebaknya salah akan mengubah 0,874 menjadi 874.
        """
        assert output.parse_number(",874", ".") == pytest.approx(0.874)


class TestPemotonganBlok:
    def test_judul_tidak_dimakan_jadi_baris_judul_kolom(self):
        blok = output.split_blocks(MODEL_SUMMARY)[0]
        assert blok.title == "Model Summary"
        assert blok.columns[1] == "R"
        assert len(blok.rows) == 1

    def test_catatan_kaki_disimpan_bukan_jadi_baris_data(self):
        """"a. Dependent Variable: Y" adalah satu-satunya tempat nama variabel
        terikat muncul pada keluaran regresi SPSS, dan narasinya butuh nama itu."""
        blok = output.split_blocks(COEFFICIENTS)[0]
        assert any("Dependent Variable" in c for c in blok.notes)
        assert all(isinstance(r[1], str) for r in blok.rows)
        assert len(blok.rows) == 3

    def test_judul_kolom_bertingkat_digabung(self):
        blok = output.split_blocks(COEFFICIENTS)[0]
        assert "Unstandardized Coefficients B" in blok.columns
        assert "Unstandardized Coefficients Std. Error" in blok.columns
        assert "Standardized Coefficients Beta" in blok.columns

    def test_huruf_catatan_kaki_dilucuti_dari_judul(self):
        assert output.split_blocks(COEFFICIENTS)[0].title == "Coefficients"
        assert output.strip_footnote_letter("ANOVAa") == "ANOVA"
        # Kata yang memang berakhiran huruf tidak boleh ikut terpotong.
        assert output.strip_footnote_letter("Beta") == "Beta"

    def test_beberapa_tabel_dalam_satu_tempelan_terpisah(self):
        """Mahasiswa jarang menempel satu tabel; yang disalin biasanya seluruh
        keluaran regresi sekaligus."""
        blok = output.split_blocks(MODEL_SUMMARY + "\n\n" + COEFFICIENTS)
        assert [b.title for b in blok] == ["Model Summary", "Coefficients"]

    def test_matriks_tanpa_sel_sudut_tidak_bergeser(self):
        """Bentuk yang dipakai SmartPLS pada outer loading: baris judulnya satu
        kolom lebih pendek karena kolom nama indikator tidak diberi nama."""
        pls = "\tKepuasan\tKinerja\nKP1\t0.812\t\nKN1\t\t0.901"
        blok = output.split_blocks(pls)[0]
        assert blok.columns[1:3] == ["Kepuasan", "Kinerja"]
        assert blok.rows[0][0] == "KP1"
        assert blok.rows[0][1] == pytest.approx(0.812)


class TestKonsolR:
    def test_dikenali_sebagai_keluaran_r(self):
        assert output.looks_like_r(RINGKASAN_R) is True
        assert output.looks_like_r(MODEL_SUMMARY) is False

    def test_blok_koefisien_terbaca_utuh(self):
        hasil = output.read_r_lm(RINGKASAN_R)
        assert hasil["formula"] == "Y ~ X1 + X2"
        assert hasil["dependent"] == "Y"
        assert [c["term"] for c in hasil["coefficients"]] == ["(Intercept)", "X1", "X2"]

        x1 = hasil["coefficients"][1]
        assert x1["estimate"] == pytest.approx(0.523)
        assert x1["std_error"] == pytest.approx(0.098)
        assert x1["t"] == pytest.approx(5.337)
        # Notasi ilmiah, bukan dibulatkan menjadi nol.
        assert x1["p_value"] == pytest.approx(1.53e-06)

    def test_ringkasan_model_terbaca(self):
        hasil = output.read_r_lm(RINGKASAN_R)
        assert hasil["r_squared"] == pytest.approx(0.659)
        assert hasil["adj_r_squared"] == pytest.approx(0.6475)
        assert hasil["f_statistic"] == pytest.approx(57.16)
        assert (hasil["df_model"], hasil["df_residual"]) == (2, 59)

    def test_uji_ringkas_terbaca(self):
        teks = """\tShapiro-Wilk normality test

data:  residuals
W = 0.97231, p-value = 0.1523"""
        uji = output.read_r_tests(teks)
        assert len(uji) == 1
        assert uji[0]["jenis"] == "shapiro"
        assert uji[0]["stats"]["w"] == pytest.approx(0.97231)
        assert uji[0]["stats"]["p"] == pytest.approx(0.1523)
