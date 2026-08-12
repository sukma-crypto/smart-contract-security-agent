"""Perutean model dan pengendalian biaya API.

Yang diuji di sini bukan mutu kalimat melainkan uang. Tiap kebocoran yang
pernah membuat tagihan membengkak punya satu uji yang menahannya, sebab
kebocoran biaya adalah jenis kerusakan yang tidak memunculkan galat apa pun:
sistemnya berjalan normal, hasilnya benar, dan yang berubah hanya angka pada
tagihan bulan depan.
"""

from __future__ import annotations

import pytest

from recens import db
from recens.core.llm import quality, router
from recens.core.llm.base import Completion, LLMUnavailable
from recens.core.llm.catalog import MODELS, RANTAI, TASKS, Tier, task_for, truncate_to_tokens


class PenyediaPalsu:
    """Penyedia yang mencatat panggilan, bukan mengirimkannya ke mana pun."""

    available = True

    def __init__(self, name: str, gagal: bool = False, keluaran_token: int = 100):
        self.name = name
        self.gagal = gagal
        self.keluaran_token = keluaran_token
        self.panggilan: list[dict] = []

    def complete(self, system, user, model_id="", max_tokens=1024, temperature=0.3):
        self.panggilan.append(
            {"model": model_id, "max_tokens": max_tokens, "panjang_user": len(user)}
        )
        if self.gagal:
            raise LLMUnavailable(f"{self.name} sedang mati")
        return Completion(
            text="Kalimat hasil.",
            model=model_id,
            provider=self.name,
            input_tokens=len(user) // 4,
            output_tokens=self.keluaran_token,
        )


@pytest.fixture
def penyedia(monkeypatch):
    """Ketiga penyedia hidup, sehingga yang diuji murni keputusan peruteannya."""
    peta = {
        "deepseek": PenyediaPalsu("deepseek"),
        "openai": PenyediaPalsu("openai"),
        "anthropic": PenyediaPalsu("anthropic"),
    }
    monkeypatch.setattr(router, "get_providers", lambda *a, **k: peta)
    return peta


class TestPenjenjangan:
    def test_tugas_ringan_memakai_model_termurah(self, penyedia):
        pilihan = router.candidates_for(task_for("lanjutan_kalimat"))
        assert pilihan[0].key == "deepseek-chat"
        assert pilihan[0].provider == "deepseek"

    def test_tugas_sedang_memakai_jenjang_menengah(self, penyedia):
        assert router.candidates_for(task_for("outline"))[0].key == "gpt-4.1"

    def test_tugas_berat_memakai_model_terkuat(self, penyedia):
        assert router.candidates_for(task_for("mode_sidang"))[0].key == "claude-opus-5"

    def test_tiap_jenjang_berurutan_makin_mahal(self):
        """Penjenjangan yang tidak berurut harga bukan penjenjangan."""
        harga = {}
        for tier, kunci in RANTAI.items():
            model = MODELS[kunci[0]]
            harga[tier] = model.input_micros_per_mtok + model.output_micros_per_mtok
        assert harga[Tier.RINGAN] < harga[Tier.SEDANG] < harga[Tier.BERAT]

    def test_tiap_tugas_terdaftar_lengkap(self):
        """Panggilan tak bernama adalah pengeluaran yang tidak bisa ditelusuri."""
        for task in TASKS.values():
            assert task.max_output_tokens > 0
            assert task.tier in RANTAI

    def test_tugas_tak_terdaftar_ditolak(self):
        with pytest.raises(KeyError):
            task_for("tugas_karangan")


class TestCadanganTidakPernahNaikHarga:
    """Kebocoran paling licin: yang berubah cuma cuaca jaringan, bukan keputusan.

    Sistem yang diam-diam pindah ke model mahal ketika penyedia murahnya mati
    membuat tagihan berlipat tanpa ada satu pun perubahan yang bisa ditunjuk.
    """

    def test_penyedia_mati_diturunkan_bukan_dinaikkan(self, monkeypatch):
        # Hanya OpenAI dan Anthropic yang hidup; tugas ringan tidak boleh
        # melompat ke Claude selama masih ada yang lebih murah.
        monkeypatch.setattr(
            router,
            "get_providers",
            lambda *a, **k: {"openai": PenyediaPalsu("openai"), "anthropic": PenyediaPalsu("anthropic")},
        )
        pilihan = router.candidates_for(task_for("lanjutan_kalimat"))
        assert pilihan[0].key == "gpt-4.1-mini"
        assert all(m.provider != "anthropic" for m in pilihan)

    def test_jenjang_berat_turun_bila_anthropic_tidak_terpasang(self, monkeypatch):
        monkeypatch.setattr(
            router, "get_providers", lambda *a, **k: {"openai": PenyediaPalsu("openai")}
        )
        pilihan = router.candidates_for(task_for("mode_sidang"))
        assert pilihan and all(m.provider == "openai" for m in pilihan)

    def test_tanpa_penyedia_sama_sekali_panggilan_ditolak(self, monkeypatch):
        monkeypatch.setattr(router, "get_providers", lambda *a, **k: {})
        with pytest.raises(LLMUnavailable):
            router.route("lanjutan_kalimat", "sistem", "isi")

    def test_gagal_pada_yang_murah_pindah_ke_cadangan_sekali(self, penyedia, conn):
        penyedia["deepseek"].gagal = True
        hasil = router.route(
            "lanjutan_kalimat", "sistem", "isi", billing=router.Billing(conn=conn)
        )
        assert hasil.model.key == "gpt-4.1-mini"
        # Tiap jenjang dicoba paling banyak sekali; tanpa batas ini kegagalan
        # jaringan berubah menjadi biaya berlipat.
        assert len(penyedia["deepseek"].panggilan) == 1
        assert len(penyedia["openai"].panggilan) == 1


class TestPagarKeluaranDanMasukan:
    def test_batas_keluaran_diambil_dari_katalog_bukan_pemanggil(self, penyedia):
        router.route("lanjutan_kalimat", "sistem", "isi")
        assert penyedia["deepseek"].panggilan[0]["max_tokens"] == 300

        router.route("mode_sidang", "sistem", "isi")
        assert penyedia["anthropic"].panggilan[0]["max_tokens"] == 2_000

    def test_masukan_kepanjangan_dipotong_ke_anggaran_model(self, penyedia):
        """Perintah yang menyertakan naskah utuh dibayar per token, tiap kali."""
        raksasa = "kata " * 400_000
        hasil = router.route("lanjutan_kalimat", "sistem", raksasa)

        model = MODELS["deepseek-chat"]
        assert hasil.completion.truncated is True
        assert penyedia["deepseek"].panggilan[0]["panjang_user"] < len(raksasa)
        assert penyedia["deepseek"].panggilan[0]["panjang_user"] <= model.max_input_tokens * 4

    def test_pemotongan_dilaporkan_bukan_didiamkan(self, penyedia):
        biasa = router.route("lanjutan_kalimat", "sistem", "pendek saja")
        assert biasa.completion.truncated is False

    def test_pemotong_teks_tidak_merusak_yang_sudah_muat(self):
        teks, terpotong = truncate_to_tokens("pendek", 1000)
        assert (teks, terpotong) == ("pendek", False)


class TestPerhitunganBiaya:
    def test_biaya_dibulatkan_ke_atas(self):
        """Menaksir terlalu rendah berarti pagar jebol saat paling dibutuhkan."""
        model = MODELS["deepseek-chat"]
        assert model.cost_micros(1, 0) == 1
        assert model.cost_micros(0, 0) == 0

    def test_model_murah_jauh_lebih_murah(self):
        murah = MODELS["deepseek-chat"].cost_micros(10_000, 2_000)
        mahal = MODELS["claude-opus-5"].cost_micros(10_000, 2_000)
        assert mahal > murah * 20

    def test_panggilan_berhasil_tercatat_beserta_biayanya(self, penyedia, conn):
        akun = db.insert(
            conn, "accounts", email="a@b.ac.id", display_name="A", plan="coba",
            credits=100, created_at=db.now(),
        )
        router.route(
            "lanjutan_kalimat", "sistem", "isi", billing=router.Billing(conn=conn, account_id=akun)
        )
        baris = db.fetch_one(conn, "SELECT * FROM llm_calls WHERE account_id = ?", (akun,))
        assert baris["provider"] == "deepseek"
        assert baris["task"] == "lanjutan_kalimat"
        assert baris["outcome"] == "berhasil"
        assert baris["cost_micros"] > 0

    def test_panggilan_gagal_ikut_tercatat(self, penyedia, conn):
        """Yang gagal tetap sudah dibayar, dan pola kegagalan yang mahal hanya
        terlihat bila ia tercatat."""
        akun = db.insert(
            conn, "accounts", email="b@b.ac.id", display_name="B", plan="coba",
            credits=100, created_at=db.now(),
        )
        penyedia["deepseek"].gagal = True
        router.route(
            "lanjutan_kalimat", "sistem", "isi", billing=router.Billing(conn=conn, account_id=akun)
        )
        hasil = db.fetch_all(
            conn, "SELECT * FROM llm_calls WHERE account_id = ? ORDER BY id", (akun,)
        )
        assert [r["outcome"] for r in hasil] == ["gagal", "berhasil"]


class TestPagarAnggaran:
    def _akun(self, conn, email="c@b.ac.id"):
        return db.insert(
            conn, "accounts", email=email, display_name="C", plan="coba",
            credits=100, created_at=db.now(),
        )

    def test_pagar_menahan_sebelum_memanggil(self, penyedia, conn, monkeypatch):
        """Pagar yang menyala setelah uangnya keluar bukan pagar."""
        from recens import config

        akun = self._akun(conn)
        pengaturan = config.get_settings()
        monkeypatch.setattr(pengaturan, "budget_daily_cents", 1)

        # Belanja melewati batas satu sen.
        router.record_call(
            conn, account_id=akun, project_id=None, task="lanjutan_kalimat",
            provider="deepseek", model="deepseek-chat", input_tokens=0, output_tokens=0,
            cost_micros=20_000, outcome="berhasil",
        )
        with pytest.raises(router.BudgetExceeded):
            router.route(
                "lanjutan_kalimat", "sistem", "isi",
                billing=router.Billing(conn=conn, account_id=akun),
            )
        # Tidak satu pun penyedia dihubungi.
        assert penyedia["deepseek"].panggilan == []

    def test_batas_nol_berarti_tanpa_batas(self, penyedia, conn, monkeypatch):
        from recens import config

        akun = self._akun(conn, "d@b.ac.id")
        pengaturan = config.get_settings()
        monkeypatch.setattr(pengaturan, "budget_daily_cents", 0)
        monkeypatch.setattr(pengaturan, "budget_monthly_cents", 0)
        router.record_call(
            conn, account_id=akun, project_id=None, task="lanjutan_kalimat",
            provider="deepseek", model="deepseek-chat", input_tokens=0, output_tokens=0,
            cost_micros=999_000_000, outcome="berhasil",
        )
        router.check_budget(conn, akun)  # tidak melempar

    def test_pemakaian_akun_lain_tidak_ikut_terhitung(self, conn):
        satu, dua = self._akun(conn, "e@b.ac.id"), self._akun(conn, "f@b.ac.id")
        router.record_call(
            conn, account_id=satu, project_id=None, task="lanjutan_kalimat",
            provider="deepseek", model="deepseek-chat", input_tokens=0, output_tokens=0,
            cost_micros=5_000, outcome="berhasil",
        )
        assert router.spend_micros(conn, satu) == 5_000
        assert router.spend_micros(conn, dua) == 0

    def test_ringkasan_memerinci_per_model_dan_per_tugas(self, penyedia, conn):
        """Total saja tidak menolong siapa pun menekan biaya."""
        akun = self._akun(conn, "g@b.ac.id")
        billing = router.Billing(conn=conn, account_id=akun)
        router.route("lanjutan_kalimat", "sistem", "isi", billing=billing)
        router.route("mode_sidang", "sistem", "isi", billing=billing)

        ringkasan = router.usage_summary(conn, akun)
        assert ringkasan["bulan_ini_usd"] > 0
        assert {r["provider"] for r in ringkasan["per_model"]} == {"deepseek", "anthropic"}
        assert {r["task"] for r in ringkasan["per_tugas"]} == {"lanjutan_kalimat", "mode_sidang"}


class TestEndpointPemakaian:
    def test_pemakaian_hanya_milik_akun_sendiri(self, client, second_client, conn):
        milik_saya = client.get("/api/account/usage")
        assert milik_saya.status_code == 200
        data = milik_saya.json()
        assert data["bulan_ini_usd"] == 0
        assert "batas_harian_usd" in data

    def test_katalog_model_terbuka_dan_menyebut_dasarnya(self, anon_client):
        data = anon_client.get("/api/models").json()
        assert {m["provider"] for m in data["models"]} == {"deepseek", "openai", "anthropic"}
        assert set(data["rantai"]) == {"ringan", "sedang", "berat"}
        assert "bukan jenjang pendidikan" in data["catatan"]

    def test_kesehatan_menyebut_penyedia_dan_pagar(self, anon_client):
        data = anon_client.get("/api/health").json()["language_model"]
        assert set(data["providers"]) == {"deepseek", "openai", "anthropic"}
        assert set(data["tiers"]) == {"ringan", "sedang", "berat"}
        assert data["budget"]["harian_usd"] >= 0


class TestLantaiMutu:
    """Yang membuat "murah" dan "bagus" berhenti bertentangan.

    Tanpa pemeriksa, penjenjangan biaya adalah taruhan: model murah dipakai
    karena hemat, dan tidak ada yang tahu hasilnya layak sampai pembimbing
    yang menemukannya.
    """

    @pytest.mark.parametrize(
        "teks, kode",
        [
            ("", "kosong"),
            ("Tentu, berikut adalah parafrase yang Anda minta untuk naskah ini.", "basa_basi"),
            (
                "Motivasi kerja berpengaruh positif terhadap kinerja karyawan pada perusahaan "
                "yang diteliti, dan hal ini sejalan dengan sejumlah penelitian terdahulu yang "
                "menunjukkan bahwa dorongan internal maupun eksternal sama-sama berperan dalam",
                "terpotong",
            ),
            (
                "The results show that work motivation has a positive and significant effect "
                "on employee performance in the company that was studied by the researcher.",
                "bahasa_keliru",
            ),
            ("Hasil penelitian menunjukkan bahwa motivasi berpengaruh. " * 5, "pengulangan"),
        ],
    )
    def test_cacat_yang_bisa_dibuktikan_salah_ditolak(self, teks, kode):
        laporan = quality.inspect(teks, quality.Spec())
        assert kode in laporan.codes
        assert laporan.ok is False

    def test_naskah_wajar_lolos(self):
        teks = (
            "Motivasi kerja berpengaruh positif dan signifikan terhadap kinerja karyawan. "
            "Temuan ini sejalan dengan penelitian terdahulu yang menunjukkan hubungan serupa "
            "pada konteks organisasi yang berbeda."
        )
        assert quality.inspect(teks, quality.Spec()).ok is True

    def test_istilah_teknis_inggris_bukan_tanda_salah_bahasa(self):
        """Naskah Indonesia lazim mempertahankan istilah teknis apa adanya.

        Menandainya sebagai salah bahasa akan memicu naik tingkat pada tulisan
        yang justru benar — dan penolakan palsu yang sering terjadi adalah cara
        tercepat membuat pemeriksanya dimatikan orang.
        """
        teks = (
            "Nilai outer loading dan composite reliability pada tabel di atas menunjukkan "
            "bahwa seluruh indikator memenuhi convergent validity yang disyaratkan dalam "
            "analisis structural equation modeling."
        )
        assert "bahasa_keliru" not in quality.inspect(teks, quality.Spec()).codes

    def test_sitasi_di_luar_pustaka_ditolak(self):
        teks = "Motivasi memengaruhi kinerja [[cite:hantu2020]] menurut kajian terdahulu."
        laporan = quality.inspect(teks, quality.Spec(citekeys={"nyata2021"}))
        assert "sitasi_karangan" in laporan.codes

    def test_markah_markdown_hanya_dicatat_tidak_memicu_naik_tingkat(self):
        """Cacat ringan tidak layak dibayar dengan model yang lebih mahal."""
        teks = "**Motivasi kerja** berpengaruh positif terhadap kinerja karyawan yang diteliti."
        laporan = quality.inspect(teks, quality.Spec())
        assert "markah_markdown" in laporan.codes
        assert laporan.ok is True


class TestNaikTingkatKarenaMutu:
    def _penyedia_cacat(self, monkeypatch, cacat_pada: set[str]):
        """Penyedia yang keluarannya cacat hanya pada model tertentu."""

        class Bervariasi(PenyediaPalsu):
            def complete(self, system, user, model_id="", max_tokens=1024, temperature=0.3):
                hasil = super().complete(system, user, model_id, max_tokens, temperature)
                if model_id in cacat_pada:
                    hasil.text = "Tentu, berikut adalah jawaban yang Anda minta untuk naskah."
                else:
                    hasil.text = (
                        "Motivasi kerja berpengaruh positif dan signifikan terhadap kinerja "
                        "karyawan pada perusahaan yang diteliti dalam penelitian ini."
                    )
                return hasil

        peta = {
            "deepseek": Bervariasi("deepseek"),
            "openai": Bervariasi("openai"),
            "anthropic": Bervariasi("anthropic"),
        }
        monkeypatch.setattr(router, "get_providers", lambda *a, **k: peta)
        return peta

    def test_keluaran_cacat_memicu_satu_kenaikan(self, monkeypatch, conn):
        from recens.core.llm import services

        peta = self._penyedia_cacat(monkeypatch, {"deepseek-chat"})
        akun = db.insert(
            conn, "accounts", email="mutu@b.ac.id", display_name="M", plan="coba",
            credits=100, created_at=db.now(),
        )
        hasil = services._call(
            "parafrase", "sistem", "isi", billing=router.Billing(conn=conn, account_id=akun)
        )

        assert hasil.escalated is True
        assert "Motivasi kerja berpengaruh" in hasil.text
        # Jenjang murah dicoba lebih dulu, lalu naik — bukan langsung mahal.
        assert peta["deepseek"].panggilan and peta["openai"].panggilan

        baris = db.fetch_all(conn, "SELECT * FROM llm_calls ORDER BY id")
        assert baris[0]["outcome"] == "mutu_ditolak"
        assert "basa_basi" in baris[0]["detail"]
        assert baris[1]["outcome"] == "naik_tingkat"

    def test_keluaran_bagus_tidak_pernah_naik(self, monkeypatch, conn):
        from recens.core.llm import services

        peta = self._penyedia_cacat(monkeypatch, set())
        akun = db.insert(
            conn, "accounts", email="hemat@b.ac.id", display_name="H", plan="coba",
            credits=100, created_at=db.now(),
        )
        hasil = services._call(
            "parafrase", "sistem", "isi", billing=router.Billing(conn=conn, account_id=akun)
        )
        assert hasil.escalated is False
        assert peta["openai"].panggilan == []
        assert peta["anthropic"].panggilan == []

    def test_cacat_di_kedua_jenjang_berhenti_setelah_sekali_naik(self, monkeypatch, conn):
        """Satu kenaikan sudah membuktikan masalahnya bukan kekuatan model."""
        from recens.core.llm import services

        peta = self._penyedia_cacat(monkeypatch, {"deepseek-chat", "gpt-4.1-mini"})
        akun = db.insert(
            conn, "accounts", email="gagal@b.ac.id", display_name="G", plan="coba",
            credits=100, created_at=db.now(),
        )
        services._call(
            "parafrase", "sistem", "isi", billing=router.Billing(conn=conn, account_id=akun)
        )
        # Dua panggilan saja: yang murah dan satu kenaikan. Tidak lebih.
        assert db.fetch_one(conn, "SELECT COUNT(*) AS n FROM llm_calls")["n"] == 2

    def test_laporan_mutu_menunjuk_tugas_yang_salah_ditempatkan(self, monkeypatch, conn):
        from recens.core.llm import services

        self._penyedia_cacat(monkeypatch, {"deepseek-chat"})
        akun = db.insert(
            conn, "accounts", email="lapor@b.ac.id", display_name="L", plan="coba",
            credits=100, created_at=db.now(),
        )
        billing = router.Billing(conn=conn, account_id=akun)
        for _ in range(3):
            services._call("parafrase", "sistem", "isi", billing=billing)

        laporan = router.quality_report(conn, akun)
        ditolak = next(r for r in laporan if r["model"] == "deepseek-chat")
        assert ditolak["ditolak"] == 3
        assert ditolak["angka_penolakan"] == 1.0
