"""Mesin statistik diuji terhadap nilai yang sudah diketahui benar.

Karena seluruh angka pada BAB IV berasal dari modul ini, kebenarannya diperiksa
terhadap tabel statistik yang dipublikasikan dan terhadap contoh yang hasilnya
bisa dihitung tangan — bukan sekadar dibandingkan dengan keluaran sendiri.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from recens.core.stats import engine, methodology
from recens.core.stats.narrative import untraceable_numbers


class TestNilaiTabel:
    @pytest.mark.parametrize(
        "n, expected",
        # Nilai r tabel product moment yang lazim dicetak di lampiran skripsi.
        [(10, 0.6319), (30, 0.3610), (60, 0.2542), (100, 0.1966)],
    )
    def test_r_tabel_cocok_dengan_tabel_tercetak(self, n, expected):
        assert engine.r_table(n) == pytest.approx(expected, abs=5e-4)

    def test_t_tabel(self):
        # t(0,025; 30) = 2,042
        assert engine.t_table(30) == pytest.approx(2.042, abs=1e-3)

    def test_f_tabel(self):
        # F(0,05; 2, 30) = 3,32
        assert engine.f_table(2, 30) == pytest.approx(3.316, abs=1e-3)

    def test_r_tabel_tidak_terdefinisi_untuk_n_terlalu_kecil(self):
        assert math.isnan(engine.r_table(2))


class TestUjiInstrumen:
    def test_cronbach_alpha_dihitung_benar(self):
        """Diperiksa terhadap contoh yang komponennya bisa dihitung tangan."""
        data = pd.DataFrame(
            {
                "i1": [4, 4, 3, 3, 4, 3, 4, 3, 3, 4],
                "i2": [4, 3, 3, 3, 4, 3, 4, 4, 3, 4],
                "i3": [3, 4, 3, 2, 4, 3, 4, 3, 3, 4],
                "i4": [4, 4, 2, 3, 4, 2, 4, 3, 2, 4],
                "i5": [4, 3, 3, 3, 3, 3, 4, 3, 3, 4],
            }
        )
        k = 5
        sum_var = data.var(ddof=1).sum()
        total_var = data.sum(axis=1).var(ddof=1)
        expected = (k / (k - 1)) * (1 - sum_var / total_var)
        assert engine.cronbach_alpha(data) == pytest.approx(expected)
        assert engine.cronbach_alpha(data) == pytest.approx(0.8805, abs=1e-3)

    def test_alpha_negatif_dilaporkan_apa_adanya(self):
        """Instrumen buruk tidak dipoles menjadi seolah-olah reliabel."""
        rng = np.random.default_rng(0)
        frame = pd.DataFrame({f"i{i}": rng.integers(1, 6, 40) for i in range(1, 6)})
        result = engine.reliability_test(frame, list(frame.columns))
        assert result.values["cronbach_alpha"] < 0.6
        assert result.values["reliable"] is False
        assert "belum reliabel" in " ".join(result.findings)

    def test_validitas_menandai_butir_yang_perlu_digugurkan(self, survey_frame):
        items = [c for c in survey_frame.columns if c.startswith("X1.")]
        frame = survey_frame.copy()
        frame["X1.rusak"] = np.arange(len(frame)) % 3  # butir tanpa hubungan dengan konstruk
        result = engine.validity_test(frame, items + ["X1.rusak"], corrected=True)
        assert "X1.rusak" in result.values["invalid_items"]
        assert result.values["r_tabel"] == pytest.approx(engine.r_table(len(frame)), abs=1e-3)
        assert result.warnings

    def test_butir_yang_lolos_hanya_karena_korelasi_tak_terkoreksi_ditandai(self, survey_frame):
        """Korelasi butir–total terangkat oleh butir itu sendiri.

        Konvensi yang dipakai mayoritas skripsi memakai korelasi tak terkoreksi,
        sehingga butir buruk bisa lolos. Recens tetap memakai konvensi itu untuk
        keputusan, tetapi memberi tahu ketika keputusannya berbeda dari korelasi
        terkoreksi.
        """
        items = [c for c in survey_frame.columns if c.startswith("X1.")]
        frame = survey_frame.copy()
        frame["X1.rusak"] = np.arange(len(frame)) % 3
        result = engine.validity_test(frame, items + ["X1.rusak"])

        assert "X1.rusak" in result.values["inflated_items"]
        detail = result.values["items"]["X1.rusak"]
        assert detail["r_item_total"] > detail["r_item_total_terkoreksi"]
        assert any("terkoreksi" in w for w in result.warnings)


class TestAsumsiKlasik:
    def test_normalitas_mengenali_data_normal_dan_tidak(self):
        rng = np.random.default_rng(7)
        frame = pd.DataFrame(
            {"normal": rng.normal(50, 10, 60), "miring": rng.exponential(3, 60)}
        )
        result = engine.normality(frame, ["normal", "miring"])
        assert result.values["normal"]["normal"] is True
        assert result.values["miring"]["normal"] is False
        assert "miring" in result.warnings[0]

    def test_multikolinearitas_terdeteksi_pada_variabel_kembar(self):
        rng = np.random.default_rng(3)
        x = rng.normal(0, 1, 60)
        frame = pd.DataFrame({"X1": x, "X2": x * 2 + rng.normal(0, 0.01, 60), "X3": rng.normal(0, 1, 60)})
        result = engine.multicollinearity(frame, ["X1", "X2", "X3"])
        assert result.values["X1"]["vif"] > 10
        assert result.values["X3"]["ok"] is True

    def test_heteroskedastisitas_glejser_berjalan(self, survey_frame):
        result = engine.heteroscedasticity(survey_frame, "Kinerja", ["Motivasi"])
        assert "homoscedastic" in result.values
        assert result.tables[0].title.startswith("Hasil Uji Glejser")


class TestRegresiDanBeda:
    def test_regresi_memulihkan_koefisien_yang_diketahui(self):
        rng = np.random.default_rng(11)
        n = 400
        x1, x2 = rng.normal(0, 1, n), rng.normal(0, 1, n)
        y = 3.0 + 2.0 * x1 - 1.5 * x2 + rng.normal(0, 0.3, n)
        frame = pd.DataFrame({"X1": x1, "X2": x2, "Y": y})
        result = engine.regression(frame, "Y", ["X1", "X2"])
        assert result.values["const"]["coefficient"] == pytest.approx(3.0, abs=0.06)
        assert result.values["X1"]["coefficient"] == pytest.approx(2.0, abs=0.06)
        assert result.values["X2"]["coefficient"] == pytest.approx(-1.5, abs=0.06)
        assert result.values["r_squared"] > 0.95
        assert result.values["f_table"] == pytest.approx(engine.f_table(2, n - 3), abs=1e-3)

    def test_regresi_melaporkan_ketidaksignifikanan(self):
        rng = np.random.default_rng(5)
        frame = pd.DataFrame({"X": rng.normal(0, 1, 50), "Y": rng.normal(0, 1, 50)})
        result = engine.regression(frame, "Y", ["X"])
        assert result.values["X"]["significant"] is False
        assert any("tidak berpengaruh" in f for f in result.findings)
        assert any("tetap dilaporkan apa adanya" in w for w in result.warnings)

    def test_uji_t_memilih_welch_saat_varian_tidak_homogen(self):
        rng = np.random.default_rng(13)
        frame = pd.DataFrame(
            {
                "nilai": np.concatenate([rng.normal(50, 1, 40), rng.normal(52, 12, 40)]),
                "grup": ["A"] * 40 + ["B"] * 40,
            }
        )
        result = engine.ttest_independent(frame, "nilai", "grup")
        assert result.values["equal_variance"] is False
        assert "Welch" in result.tables[1].note

    def test_anova_menolak_dua_kelompok_dengan_pesan_yang_menuntun(self, survey_frame):
        with pytest.raises(engine.AnalysisError, match="uji t sampel bebas"):
            engine.anova_oneway(survey_frame, "Kinerja", "Kelompok")

    def test_uji_t_menolak_tiga_kelompok(self, survey_frame):
        with pytest.raises(engine.AnalysisError, match="ANOVA"):
            engine.ttest_independent(survey_frame, "Kinerja", "Divisi")

    def test_ngain_mengategorikan_peningkatan(self, survey_frame):
        result = engine.ngain(survey_frame, "Pretest", "Posttest", ideal_score=100)
        assert result.values["category"] in ("Rendah", "Sedang", "Tinggi")
        assert result.values["mean_posttest"] > result.values["mean_pretest"]


class TestPLS:
    def test_ave_dan_cr_dihitung_dari_loading(self):
        loadings = {"Kepuasan": {"X1": 0.8, "X2": 0.8, "X3": 0.8}}
        result = engine.pls_measurement_model(loadings)
        # AVE = mean(λ²) = 0,64 ; CR = (2,4)² / ((2,4)² + 3×0,36) = 5,76 / 6,84
        assert result.values["Kepuasan"]["ave"] == pytest.approx(0.64, abs=1e-3)
        assert result.values["Kepuasan"]["cr"] == pytest.approx(5.76 / 6.84, abs=1e-3)
        assert result.values["Kepuasan"]["meets_criteria"] is True

    def test_loading_rendah_ditandai(self):
        result = engine.pls_measurement_model({"K": {"X1": 0.9, "X2": 0.4}})
        assert result.warnings and "K.X2" in result.warnings[0]


class TestValidasiAhli:
    def test_aiken_v(self):
        # 3 penilai, skala 1–5, semua memberi 5 -> V = 12 / (3 × 4) = 1,0
        result = engine.aiken_v([[5, 5, 5]], scale_min=1, scale_max=5)
        assert result.values["overall_v"] == pytest.approx(1.0)
        # semua memberi 3 -> s = 2 tiap penilai -> V = 6 / 12 = 0,5
        result = engine.aiken_v([[3, 3, 3]], scale_min=1, scale_max=5)
        assert result.values["overall_v"] == pytest.approx(0.5)


class TestPenelusuranAngka:
    """Penjaga yang membuat 'angka dihitung mesin' bisa ditegakkan."""

    def test_angka_hasil_hitung_lolos(self, survey_frame):
        result = engine.regression(survey_frame, "Kinerja", ["Motivasi"])
        r2 = result.values["r_squared"]
        narasi = f"Koefisien determinasi sebesar {r2} menunjukkan besarnya kontribusi."
        assert untraceable_numbers(narasi, result) == []

    def test_angka_karangan_ditandai(self, survey_frame):
        result = engine.regression(survey_frame, "Kinerja", ["Motivasi"])
        narasi = "Koefisien determinasi sebesar 0,987 menunjukkan pengaruh yang sangat kuat."
        assert 0.987 in untraceable_numbers(narasi, result)

    def test_ambang_lazim_tidak_dianggap_karangan(self, survey_frame):
        result = engine.normality(survey_frame, ["Kinerja"])
        narasi = "Nilai signifikansi dibandingkan dengan taraf 0,05 pada tingkat kepercayaan 95%."
        assert untraceable_numbers(narasi, result) == []

    def test_desimal_koma_dan_titik_sama_diperlakukan(self, survey_frame):
        result = engine.descriptive(survey_frame, ["Usia"])
        mean = result.values["Usia"]["mean"]
        assert untraceable_numbers(f"Rata-rata usia {mean}", result) == []
        assert untraceable_numbers(f"Rata-rata usia {str(mean).replace('.', ',')}", result) == []


class TestPemanduMetodologi:
    def test_dua_kelompok_tidak_normal_memakai_mann_whitney(self):
        rec = methodology.recommend("perbedaan", n_groups=2, normal=False)
        assert "Mann-Whitney" in rec.tests[0]

    def test_tiga_kelompok_normal_memakai_anova_dan_uji_lanjut(self):
        rec = methodology.recommend("perbedaan", n_groups=3, normal=True)
        assert "ANOVA" in rec.tests[0]
        assert any("Tukey" in t for t in rec.tests)

    def test_berpasangan_memakai_uji_t_berpasangan(self):
        rec = methodology.recommend("perbedaan", paired=True, normal=True)
        assert "berpasangan" in rec.tests[0]

    def test_pengaruh_berganda_menuntut_multikolinearitas(self):
        rec = methodology.recommend("pengaruh", n_independent=3)
        assert any("multikolinearitas" in p.lower() for p in rec.prerequisites)
        assert any("Uji F" in t for t in rec.tests)

    def test_variabel_laten_diarahkan_ke_sem_pls(self):
        rec = methodology.recommend("pengaruh", latent_variables=True)
        assert rec.approach == "SEM-PLS"

    def test_eksplorasi_diarahkan_ke_kualitatif(self):
        rec = methodology.recommend("eksplorasi")
        assert rec.approach == "kualitatif"
        assert "Purposive" in rec.sampling

    def test_slovin(self):
        # n = 250 / (1 + 250 × 0,05²) = 153,8 -> 154
        assert methodology.slovin(250, 0.05)["sample_size"] == 154
        assert methodology.slovin(1000, 0.1)["sample_size"] == 91

    def test_ukuran_sampel_regresi(self):
        assert methodology.sample_size_for_regression(3)["sample_size"] == 74
