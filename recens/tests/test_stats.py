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
from recens.core.stats.narrative import draft_narrative, untraceable_numbers


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

    def test_selisih_dan_t_berpasangan_bertanda_sama(self, survey_frame):
        """Tabel yang menampilkan selisih positif di sebelah t negatif akan
        ditanya penguji, padahal keduanya menggambarkan peningkatan yang sama."""
        result = engine.ttest_paired(survey_frame, "Pretest", "Posttest")
        selisih = result.values["mean_difference"]
        t_hitung = result.values["t_statistic"]
        assert selisih > 0 and t_hitung > 0, (selisih, t_hitung)
        assert "Posttest − Pretest" in result.tables[1].columns[0]


class TestNGain:
    """Skor ideal menentukan seluruh hasil N-Gain, jadi ia dijaga sendiri.

    Versi pertama memakai nilai posttest tertinggi yang teramati sebagai skor
    ideal. Itu salah dalam dua hal sekaligus: penyebutnya mengecil sehingga
    N-Gain menggelembung, dan angkanya berubah setiap ada responden baru —
    pembimbing yang menghitung ulang tidak akan menemukan angka yang sama.
    """

    @pytest.fixture
    def pretest_posttest(self) -> pd.DataFrame:
        rng = np.random.default_rng(21)
        pre = rng.normal(52, 9, 100).round(1)
        return pd.DataFrame({"Pretest": pre, "Posttest": (pre + rng.normal(16, 6, 100)).round(1)})

    def test_skor_ideal_diterka_dari_skala_baku_bukan_nilai_teramati(self, pretest_posttest):
        result = engine.ngain(pretest_posttest, "Pretest", "Posttest")
        teramati = float(pretest_posttest["Posttest"].max())
        assert teramati < 100, "data uji harus punya nilai tertinggi di bawah 100"
        assert result.values["ideal_score"] == 100.0
        assert result.values["ideal_score_assumed"] is True

    def test_terkaan_dinyatakan_terus_terang(self, pretest_posttest):
        result = engine.ngain(pretest_posttest, "Pretest", "Posttest")
        assert any("diterka" in w for w in result.warnings)
        assert "diterka" in result.tables[0].note

        diisi = engine.ngain(pretest_posttest, "Pretest", "Posttest", ideal_score=100)
        assert diisi.values["ideal_score_assumed"] is False
        assert not any("diterka" in w for w in diisi.warnings)
        assert "diisi peneliti" in diisi.tables[0].note

    def test_hasilnya_sama_dengan_hitungan_tangan(self, pretest_posttest):
        result = engine.ngain(pretest_posttest, "Pretest", "Posttest", ideal_score=100)
        manual = (
            (pretest_posttest["Posttest"] - pretest_posttest["Pretest"])
            / (100 - pretest_posttest["Pretest"])
        ).mean()
        assert result.values["mean_ngain"] == round(manual, 3)

    @pytest.mark.parametrize(
        "maksimum,harapan",
        [(3.8, 4.0), (4.6, 5.0), (9.2, 10.0), (88.0, 100.0), (100.0, 100.0), (132.0, 140.0)],
    )
    def test_skala_baku_dikenali(self, maksimum, harapan):
        assert engine.infer_ideal_score(maksimum) == harapan

    def test_skor_ideal_di_bawah_data_ditolak(self, pretest_posttest):
        with pytest.raises(engine.AnalysisError, match="lebih kecil daripada nilai tertinggi"):
            engine.ngain(pretest_posttest, "Pretest", "Posttest", ideal_score=50)

    def test_responden_berpenyebut_nol_dikeluarkan_dan_dilaporkan(self):
        """Responden yang skor pretest-nya sudah menyentuh skor ideal tidak
        punya ruang untuk meningkat, sehingga N-Gain-nya tak terdefinisi.
        Mengeluarkannya diam-diam membuat N tidak cocok dengan jumlah
        responden yang ditulis di Bab 3, jadi jumlahnya ikut dilaporkan."""
        frame = pd.DataFrame(
            {"Pretest": [40.0, 60.0, 100.0, 100.0], "Posttest": [70.0, 80.0, 100.0, 95.0]}
        )
        result = engine.ngain(frame, "Pretest", "Posttest", ideal_score=100)
        assert result.values["n"] == 2
        assert result.values["excluded"] == 2
        assert any("tidak diikutkan" in w for w in result.warnings)
        assert result.values["mean_ngain"] == round(((30 / 60) + (20 / 40)) / 2, 3)

    def test_nilai_sempurna_tidak_membatalkan_seluruh_analisis(self):
        """Skor ideal yang sama persis dengan nilai tertinggi itu wajar."""
        frame = pd.DataFrame({"Pretest": [40.0, 55.0, 62.0], "Posttest": [100.0, 80.0, 88.0]})
        result = engine.ngain(frame, "Pretest", "Posttest", ideal_score=100)
        assert result.values["n"] == 3
        assert result.values["excluded"] == 0


class TestKolomKembar:
    """Memilih kolom yang sama dua kali harus ditolak, bukan memecahkan server.

    Dua daftar kolom berdampingan pada satu formulir membuat kekeliruan ini
    wajar terjadi — dan antarmuka sempat menjadikannya bawaan. Enam uji
    menjawab 500 karena ``frame[[a, a]]`` menghasilkan kolom kembar, sehingga
    ``data[a]`` mengembalikan DataFrame alih-alih Series.
    """

    @pytest.fixture
    def frame(self) -> pd.DataFrame:
        rng = np.random.default_rng(1)
        return pd.DataFrame(
            {
                "A": rng.normal(50, 10, 40).round(1),
                "B": rng.normal(60, 9, 40).round(1),
                "G": rng.choice(["x", "y"], 40),
            }
        )

    @pytest.mark.parametrize(
        "jalankan",
        [
            pytest.param(lambda f: engine.crosstab(f, "A", "A"), id="crosstab"),
            pytest.param(lambda f: engine.ttest_independent(f, "A", "A"), id="uji_t_bebas"),
            pytest.param(lambda f: engine.ttest_paired(f, "A", "A"), id="uji_t_berpasangan"),
            pytest.param(lambda f: engine.ngain(f, "A", "A"), id="ngain"),
            pytest.param(lambda f: engine.correlation(f, ["A", "A"]), id="korelasi"),
            pytest.param(lambda f: engine.validity_test(f, ["A", "A"]), id="validitas"),
            pytest.param(lambda f: engine.reliability_test(f, ["A", "A"]), id="reliabilitas"),
            pytest.param(lambda f: engine.multicollinearity(f, ["A", "A"]), id="multikolinearitas"),
            pytest.param(lambda f: engine.regression(f, "A", ["A"]), id="regresi_y_di_x"),
            pytest.param(lambda f: engine.regression(f, "A", ["B", "B"]), id="regresi_x_kembar"),
            pytest.param(
                lambda f: engine.heteroscedasticity(f, "A", ["A"]), id="heteroskedastisitas"
            ),
            pytest.param(
                lambda f: engine.nonparametric(f, test="wilcoxon", value="A", second="A"),
                id="wilcoxon",
            ),
            pytest.param(
                lambda f: engine.nonparametric(f, test="mann_whitney", value="A", group="A"),
                id="mann_whitney",
            ),
            pytest.param(
                lambda f: engine.nonparametric(f, test="kruskal", value="A", group="A"),
                id="kruskal",
            ),
        ],
    )
    def test_ditolak_dengan_kalimat_yang_menuntun(self, frame, jalankan):
        with pytest.raises(engine.AnalysisError) as caught:
            jalankan(frame)
        pesan = str(caught.value)
        assert "A" in pesan or "B" in pesan, pesan
        assert any(kata in pesan for kata in ("Pilih kolom", "satu kali", "dirinya sendiri"))

    def test_variabel_terikat_tidak_boleh_jadi_variabel_bebas(self, frame):
        """R² akan selalu 1 dan tabelnya tidak berarti apa pun."""
        with pytest.raises(engine.AnalysisError, match="dirinya sendiri"):
            engine.regression(frame, "A", ["A", "B"])


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

    def test_bentuk_persen_bukan_angka_baru(self, survey_frame):
        """"R² 0,887 berarti menjelaskan 88,7% variasi" adalah satu angka yang
        sama dinyatakan dua kali — dan begitulah orang menulis Bab 4. Penolakan
        palsu yang sering terjadi akan membuat penjaganya dimatikan orang."""
        result = engine.regression(survey_frame, "Kinerja", ["Motivasi"])
        r2 = result.values["r_squared"]
        narasi = f"Variabel bebas menjelaskan {str(round(r2 * 100, 1)).replace('.', ',')}% variasi."
        assert untraceable_numbers(narasi, result) == []

    def test_narasi_deterministik_lolos_penjaganya_sendiri(self, survey_frame):
        """Draf bawaan adalah tolok ukur yang harus dipenuhi narasi model.
        Bila draf itu sendiri tidak lolos, ambangnya keliru — bukan narasinya."""
        for result in (
            engine.regression(survey_frame, "Kinerja", ["Motivasi", "Usia"]),
            engine.reliability_test(survey_frame, [f"X1.{i}" for i in range(1, 6)]),
            engine.ttest_paired(survey_frame, "Pretest", "Posttest"),
            engine.ngain(survey_frame, "Pretest", "Posttest", ideal_score=100),
        ):
            sisa = untraceable_numbers(draft_narrative(result), result)
            assert sisa == [], f"{result.method}: {sisa}"

    def test_angka_karangan_tetap_tertangkap_setelah_bentuk_persen_diterima(self, survey_frame):
        result = engine.regression(survey_frame, "Kinerja", ["Motivasi"])
        narasi = draft_narrative(result).replace(
            str(result.values["r_squared"]).replace(".", ","), "0,995"
        )
        assert 0.995 in untraceable_numbers(narasi, result)


class TestPemisahDesimal:
    """Skripsi Indonesia memakai koma desimal; tabel bertitik dikembalikan pembimbing."""

    def test_sel_tabel_memakai_koma(self, survey_frame):
        rendered = engine.regression(survey_frame, "Kinerja", ["Motivasi"]).to_dict()
        angka = [c for row in rendered["tables"][0]["rows"] for c in row if isinstance(c, str)]
        assert angka and all("." not in c for c in angka), angka
        assert any("," in c for c in angka), angka

    def test_kalimat_hasil_memakai_koma(self, survey_frame):
        rendered = engine.reliability_test(
            survey_frame, [f"X1.{i}" for i in range(1, 6)]
        ).to_dict()
        assert any("," in f for f in rendered["findings"])

    def test_nama_butir_tidak_ikut_diubah(self, survey_frame):
        """"X1.1" adalah nama butir, bukan bilangan desimal."""
        items = [f"X1.{i}" for i in range(1, 6)]
        rendered = engine.validity_test(survey_frame, items).to_dict()
        assert [row[0] for row in rendered["tables"][0]["rows"]] == items

    def test_angka_di_values_tetap_bilangan(self, survey_frame):
        """Penjaga penelusuran membandingkan bilangan, bukan teks — dan angka
        yang sudah menjadi teks tidak bisa dihitung ulang siapa pun."""
        rendered = engine.regression(survey_frame, "Kinerja", ["Motivasi"]).to_dict()
        assert isinstance(rendered["values"]["r_squared"], float)
        assert isinstance(rendered["values"]["Motivasi"]["coefficient"], float)

    def test_nilai_p_ditulis_sama_dengan_tabelnya(self, survey_frame):
        """"signifikansi 0,0" salah: nilai p tidak pernah tepat nol, dan tabel
        di sebelahnya sudah menulis "< 0,001"."""
        rendered = engine.regression(survey_frame, "Kinerja", ["Motivasi"]).to_dict()
        kalimat = " ".join(rendered["findings"])
        assert "signifikansi 0,0," not in kalimat and "signifikansi 0,0 " not in kalimat
        assert "< 0,001" in kalimat

    def test_persamaan_regresi_memberi_spasi_antara_koefisien_dan_variabel(self, survey_frame):
        rendered = engine.regression(survey_frame, "Kinerja", ["Motivasi"]).to_dict()
        persamaan = next(f for f in rendered["findings"] if "Persamaan regresi" in f)
        assert " Motivasi" in persamaan and "Motivasi" in persamaan
        assert not any(f"{d}Motivasi" in persamaan for d in "0123456789")


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
