"""Fitur penulisan yang memakai model bahasa, lengkap dengan jalur cadangannya.

Tiap layanan di sini punya dua jalur: jalur model (kalimatnya lebih luwes) dan
jalur deterministik yang berjalan tanpa kunci API. Jalur kedua bukan sekadar
pesan kesalahan — ia mengerjakan bagian pekerjaan yang memang tidak menuntut
model, misalnya menyunting bentuk tidak baku, menyusun kerangka dari struktur
yang berlaku, atau menjawab pertanyaan dengan mengembalikan kutipan sumber
beserta halamannya.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..checks.language import KATA_TIDAK_BAKU, RAGAM_PERCAKAPAN, check_text
from ..manuscript import Manuscript
from ..retrieval import Hit, format_evidence
from ..stats.engine import AnalysisResult
from ..stats.narrative import draft_narrative
from . import prompts
from .base import LLMUnavailable
from .guardrails import GuardrailError, Verdict, guard_output, guard_request, word_budget
from .providers import get_provider
from . import quality
from .router import Billing, BudgetExceeded, mark_quality, route


@dataclass
class ServiceResult:
    text: str
    source: str = "model"  # model | deterministik
    verdict: Verdict | None = None
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "verdict": self.verdict.to_dict() if self.verdict else None,
            "meta": self.meta,
        }


def _call(
    task: str,
    system: str,
    user: str,
    temperature=0.3,
    billing: Billing | None = None,
    mutu: quality.Spec | None = None,
):
    """Satu-satunya jalan menuju model, lengkap dengan lantai mutunya.

    Urutannya disengaja: **coba yang murah dulu, naikkan hanya bila terbukti
    gagal.** Kebalikannya — memakai model mahal untuk semua demi berjaga-jaga —
    membayar penuh untuk pekerjaan yang model murah sudah sanggup, dan itu
    justru pemborosan yang paling sering tidak disadari karena hasilnya memang
    bagus.

    Yang menentukan "gagal" bukan perasaan melainkan pemeriksaan deterministik:
    kalimat terputus, jawaban berpindah bahasa, sitasi yang tidak ada di
    pustaka, keluaran yang merosot jadi pengulangan. Menilai mutu dengan model
    lain hanya memindahkan pertanyaannya satu lapis ke dalam, dengan biaya
    tambahan dan tanpa jaminan tambahan.

    Batas keluaran tidak lagi datang dari pemanggil melainkan dari katalog
    tugas. Sebelumnya dua belas tempat memilih ``max_tokens`` sendiri, dan
    angka yang dipilih di satu tempat tidak pernah ditinjau dari tempat lain.

    Pagar anggaran yang tersentuh dijadikan ``LLMUnavailable`` supaya seluruh
    pemanggil menanganinya lewat jalur yang sudah ada: turun ke jalur
    deterministik, bukan gagal ke muka pengguna. Kehabisan anggaran bukan
    kerusakan; ia keadaan yang memang direncanakan.
    """
    spec = mutu or quality.spec_for(task)
    try:
        pertama = route(task, system, user, temperature=temperature, billing=billing)
    except BudgetExceeded as exc:
        raise LLMUnavailable(str(exc)) from exc

    laporan = quality.inspect(pertama.completion.text, spec)
    if laporan.ok:
        return pertama.completion

    conn = billing.conn if billing else None
    mark_quality(conn, pertama.call_id, laporan.codes)

    try:
        kedua = route(
            task, system, user, temperature=temperature, billing=billing, escalated=True
        )
    except (LLMUnavailable, BudgetExceeded):
        # Hasil yang cacat tetap lebih berguna daripada tidak ada apa-apa;
        # pemanggil masih punya jalur deterministiknya sendiri bila ia menilai
        # hasil ini tidak layak.
        return pertama.completion

    laporan_kedua = quality.inspect(kedua.completion.text, spec)
    kedua.completion.escalated = True
    if laporan_kedua.ok:
        return kedua.completion

    mark_quality(conn, kedua.call_id, laporan_kedua.codes)
    # Dua-duanya cacat: kembalikan yang cacatnya paling sedikit, dan jangan
    # naik lagi. Satu kali kenaikan sudah membuktikan bahwa masalahnya bukan
    # pada kekuatan modelnya.
    if len(laporan_kedua.issues) < len(laporan.issues):
        return kedua.completion
    return pertama.completion


# --- Penulisan & bahasa ------------------------------------------------------


def continue_sentence(
    context: str,
    section_title: str = "",
    work_type_label: str = "",
    citekeys: set[str] | None = None,
    billing: Billing | None = None,
) -> ServiceResult:
    """Lanjutan kalimat: menghapus kebuntuan halaman kosong."""
    verdict = guard_request(context, kind="lanjutan_kalimat")
    if not verdict.allowed:
        raise GuardrailError(verdict)

    budget = word_budget("lanjutan_kalimat")
    system = prompts.render(prompts.CONTINUATION, max_words=budget)
    user = (
        f"Jenis karya: {work_type_label or 'karya tulis ilmiah'}\n"
        f"Bagian yang sedang ditulis: {section_title or 'tidak disebutkan'}\n"
        f"Citekey yang tersedia di pustaka: {', '.join(sorted(citekeys or [])) or 'belum ada'}\n\n"
        f"Teks sejauh ini:\n{context}\n\nLanjutkan:"
    )
    try:
        completion = _call("lanjutan_kalimat", system, user, temperature=0.4, billing=billing)
    except LLMUnavailable as exc:
        return ServiceResult(
            text="",
            source="deterministik",
            meta={
                "unavailable": str(exc),
                "hint": (
                    "Lanjutan kalimat memerlukan model bahasa. Fitur lain — outline, "
                    "sitasi, analisis data, pemeriksaan naskah, dan ekspor — tetap berjalan."
                ),
            },
        )

    text, output_verdict = guard_output(
        completion.text, kind="lanjutan_kalimat", allowed_citekeys=citekeys
    )
    return ServiceResult(
        text=text,
        verdict=output_verdict,
        meta={"model": completion.model, "tokens": completion.total_tokens},
    )


def paraphrase(text: str, instruction: str = "", billing: Billing | None = None) -> ServiceResult:
    """Parafrase yang selalu disertai penjelasan alasan perubahan."""
    verdict = guard_request(f"{instruction} {text}", kind="parafrase")
    if not verdict.allowed:
        raise GuardrailError(verdict)

    system = prompts.render(prompts.PARAPHRASE)
    user = f"Teks yang diparafrase:\n{text}"
    if instruction:
        user += f"\n\nPermintaan tambahan pengguna: {instruction}"

    try:
        completion = _call("parafrase", system, user, temperature=0.5, billing=billing)
    except LLMUnavailable:
        return ServiceResult(
            text=_normalize_academic(text),
            source="deterministik",
            meta={
                "explanation": (
                    "Tanpa model bahasa, Recens hanya membakukan ejaan dan bentuk kata. "
                    "Parafrase yang mengubah struktur kalimat memerlukan kunci API."
                )
            },
        )

    body, _, reason = completion.text.partition("ALASAN:")
    cleaned, output_verdict = guard_output(body.strip(), kind="parafrase")
    return ServiceResult(
        text=cleaned,
        verdict=output_verdict,
        meta={
            "explanation": reason.strip()
            or "Struktur kalimat diubah dengan mempertahankan makna dan seluruh angka.",
            "reminder": (
                "Parafrase tidak menghapus kewajiban menyitasi. Bila gagasannya milik "
                "orang lain, sitasi tetap harus dicantumkan."
            ),
            "model": completion.model,
        },
    )


def academic_language(text: str, billing: Billing | None = None) -> ServiceResult:
    """Penyuntingan sesuai kaidah PUEBI/EYD."""
    findings = [f.to_dict() for f in check_text(text)]
    system = prompts.render(prompts.ACADEMIC_LANGUAGE)
    user = f"Teks:\n{text}"

    try:
        completion = _call("bahasa_akademik", system, user, temperature=0.2, billing=billing)
    except LLMUnavailable:
        return ServiceResult(
            text=_normalize_academic(text),
            source="deterministik",
            meta={
                "findings": findings,
                "note": (
                    f"{len(findings)} temuan kaidah bahasa diperbaiki secara otomatis "
                    f"berdasarkan daftar bentuk baku dan aturan penulisan."
                ),
            },
        )

    cleaned, verdict = guard_output(completion.text, kind="bahasa_akademik")
    return ServiceResult(
        text=cleaned, verdict=verdict, meta={"findings": findings, "model": completion.model}
    )


def _normalize_academic(text: str) -> str:
    """Pembakuan deterministik: bentuk tidak baku, ragam percakapan, dan spasi."""
    result = text
    for wrong, right in {**KATA_TIDAK_BAKU, **RAGAM_PERCAKAPAN}.items():
        result = re.sub(
            rf"\b{re.escape(wrong)}\b",
            lambda m, r=right: r.capitalize() if m.group(0)[0].isupper() else r,
            result,
            flags=re.IGNORECASE,
        )
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    result = re.sub(r"([,.;:!?])(?=[A-Za-z])", r"\1 ", result)
    return result.strip()


#: Template siap pakai untuk bagian standar (Bagian 4.1).
SECTION_TEMPLATES: dict[str, dict] = {
    "latar_belakang": {
        "label": "Latar Belakang",
        "outline": [
            "Kondisi ideal atau harapan tentang topik ini menurut teori dan kebijakan.",
            "Kenyataan di lapangan yang berbeda dari kondisi ideal, disertai data pendukung.",
            "Kesenjangan antara harapan dan kenyataan, serta dampaknya bila dibiarkan.",
            "Penelitian terdahulu yang sudah membahas dan apa yang belum terjawab.",
            "Alasan penelitian ini perlu dilakukan dan apa yang ditawarkannya.",
        ],
    },
    "rumusan_masalah": {
        "label": "Rumusan Masalah",
        "outline": [
            "Bagaimana gambaran [variabel X] pada [objek penelitian]?",
            "Apakah terdapat pengaruh [variabel X] terhadap [variabel Y] pada [objek]?",
            "Seberapa besar kontribusi [variabel X] terhadap [variabel Y]?",
        ],
    },
    "tujuan": {
        "label": "Tujuan Penelitian",
        "outline": [
            "Untuk mengetahui gambaran [variabel X] pada [objek penelitian].",
            "Untuk menganalisis pengaruh [variabel X] terhadap [variabel Y].",
            "Untuk mengukur besar kontribusi [variabel X] terhadap [variabel Y].",
        ],
    },
    "landasan_teori": {
        "label": "Kerangka Teori",
        "outline": [
            "Definisi [variabel] menurut beberapa ahli, ditutup sintesis penulis.",
            "Dimensi atau indikator [variabel] beserta dasar teoretisnya.",
            "Faktor yang memengaruhi [variabel].",
            "Teori utama (grand theory) yang menaungi hubungan antarvariabel.",
        ],
    },
    "hipotesis": {
        "label": "Hipotesis",
        "outline": [
            "H1: Terdapat pengaruh positif dan signifikan [variabel X] terhadap [variabel Y].",
            "H2: Terdapat pengaruh positif dan signifikan [variabel Z] terhadap [variabel Y].",
            "H3: [variabel X] dan [variabel Z] secara simultan berpengaruh terhadap "
            "[variabel Y].",
        ],
    },
    "abstrak": {
        "label": "Abstrak",
        "outline": [
            "Tujuan penelitian dalam satu kalimat.",
            "Metode: pendekatan, populasi dan sampel, teknik pengumpulan dan analisis data.",
            "Hasil utama beserta angka pendukungnya.",
            "Simpulan dan implikasinya dalam satu sampai dua kalimat.",
        ],
    },
    "metode": {
        "label": "Metode Penelitian",
        "outline": [
            "Jenis dan pendekatan penelitian beserta alasan pemilihannya.",
            "Populasi, teknik pengambilan sampel, dan ukuran sampel beserta perhitungannya.",
            "Teknik pengumpulan data dan instrumen yang dipakai.",
            "Uji instrumen: validitas dan reliabilitas.",
            "Teknik analisis data beserta uji asumsi yang mendahuluinya.",
        ],
    },
    "kerangka_berpikir": {
        "label": "Kerangka Berpikir",
        "outline": [
            "Ringkasan hubungan antar-variabel yang sudah dibangun di landasan teori.",
            "Alur logika: mengapa [variabel X] diduga memengaruhi [variabel Y], bukan sebaliknya.",
            "Peran variabel lain bila ada — mediasi, moderasi, atau kontrol.",
            "Kalimat penutup yang menyiapkan hipotesis pada sub-bab berikutnya.",
            "Bagan kerangka berpikir: kotak variabel dan panah arah pengaruh.",
        ],
    },
    "penelitian_terdahulu": {
        "label": "Penelitian Terdahulu",
        "outline": [
            "Penelitian yang meneliti hubungan serupa, beserta metode dan temuannya.",
            "Penelitian yang hasilnya berbeda atau bertentangan, dan dugaan penyebabnya.",
            "Persamaan penelitian ini dengan penelitian terdahulu.",
            "Perbedaannya — objek, variabel, periode, atau metode.",
            "Celah yang belum terjawab, yang menjadi ruang bagi penelitian ini.",
        ],
    },
    "manfaat": {
        "label": "Manfaat Penelitian",
        "outline": [
            "Manfaat teoretis: sumbangan bagi pengembangan teori [bidang ilmu].",
            "Manfaat praktis bagi [objek penelitian] dalam mengambil keputusan.",
            "Manfaat bagi peneliti berikutnya sebagai rujukan atau titik lanjut.",
        ],
    },
    "batasan": {
        "label": "Batasan Masalah",
        "outline": [
            "Variabel yang diteliti dan yang sengaja tidak diteliti.",
            "Batas objek, lokasi, dan periode pengambilan data.",
            "Alasan pembatasan — keterbatasan waktu, akses data, atau fokus kajian.",
        ],
    },
    "populasi_sampel": {
        "label": "Populasi dan Sampel",
        "outline": [
            "Populasi: siapa atau apa, berapa jumlahnya, dan dari mana angka itu diperoleh.",
            "Teknik sampling yang dipakai beserta alasannya.",
            "Perhitungan ukuran sampel — rumus yang dipakai dan hasilnya.",
            "Kriteria inklusi dan eksklusi responden bila ada.",
        ],
    },
    "instrumen": {
        "label": "Instrumen Penelitian",
        "outline": [
            "Bentuk instrumen: kuesioner, pedoman wawancara, atau lembar observasi.",
            "Kisi-kisi instrumen: variabel, indikator, dan nomor butir.",
            "Skala pengukuran yang dipakai beserta rentang nilainya.",
            "Uji validitas dan reliabilitas: cara pengujian dan kriteria kelulusannya.",
        ],
    },
    "teknik_analisis": {
        "label": "Teknik Analisis Data",
        "outline": [
            "Analisis deskriptif: apa yang digambarkan dan dengan ukuran apa.",
            "Uji asumsi klasik yang harus dipenuhi sebelum uji utama.",
            "Uji hipotesis yang dipakai beserta alasan pemilihannya.",
            "Kriteria pengambilan keputusan — taraf signifikansi dan pembanding tabelnya.",
            "Perangkat bantu yang dipakai untuk mengolah data.",
        ],
    },
    "hasil": {
        "label": "Hasil Penelitian",
        "outline": [
            "Gambaran umum objek penelitian dan karakteristik responden.",
            "Hasil uji instrumen: validitas dan reliabilitas tiap butir.",
            "Hasil uji asumsi klasik, disertai tabel dan keputusannya.",
            "Hasil uji hipotesis: tabel, angka, dan keputusan diterima atau ditolak.",
            "Sajikan apa adanya lebih dahulu — penafsiran maknanya di pembahasan.",
        ],
    },
    "pembahasan": {
        "label": "Pembahasan",
        "outline": [
            "Jawaban atas tiap rumusan masalah, berurutan sesuai urutannya di BAB I.",
            "Makna praktis angka yang diperoleh bagi [objek penelitian].",
            "Kesesuaian atau pertentangan dengan teori yang dipakai.",
            "Kesesuaian atau pertentangan dengan penelitian terdahulu, beserta dugaan penyebabnya.",
            "Hasil yang tidak signifikan tetap dibahas — mengapa hubungan itu tidak terbukti.",
        ],
    },
    "simpulan": {
        "label": "Simpulan",
        "outline": [
            "Jawaban ringkas atas tiap rumusan masalah, satu paragraf satu rumusan.",
            "Ditulis tanpa angka teknis dan tanpa istilah statistik yang belum dijelaskan.",
            "Tidak memuat hal baru yang belum dibahas pada bab sebelumnya.",
        ],
    },
    "saran": {
        "label": "Saran",
        "outline": [
            "Saran praktis bagi [objek penelitian], langsung mengikuti temuan.",
            "Saran bagi peneliti berikutnya: variabel, metode, atau objek yang layak ditambah.",
            "Keterbatasan penelitian ini yang perlu diperbaiki penelitian berikutnya.",
        ],
    },
}


def section_template(role: str) -> dict:
    """Template bagian standar agar pengguna baru langsung bisa bekerja."""
    template = SECTION_TEMPLATES.get(role)
    if template is None:
        raise ValueError(
            f"Template '{role}' belum tersedia. Pilihan: {', '.join(SECTION_TEMPLATES)}."
        )
    return {
        "role": role,
        "label": template["label"],
        "outline": template["outline"],
        "text": "\n".join(f"{i + 1}. {line}" for i, line in enumerate(template["outline"])),
        "note": (
            "Template ini kerangka isi, bukan teks jadi. Ganti bagian dalam kurung siku "
            "dengan variabel dan objek penelitian Anda, lalu kembangkan tiap butir menjadi "
            "paragraf."
        ),
    }


# --- Referensi & riset -------------------------------------------------------


def ask_journal(question: str, hits: list[Hit], billing: Billing | None = None) -> ServiceResult:
    """Tanya Jurnal — jawaban selalu disertai penunjuk halaman sumber."""
    if not hits:
        return ServiceResult(
            text="",
            source="deterministik",
            meta={
                "note": (
                    "Belum ada potongan sumber yang cocok. Unggah PDF jurnal ke pustaka "
                    "proyek lebih dahulu agar isinya bisa ditanyai."
                ),
                "sources": [],
            },
        )

    evidence = format_evidence(hits)
    system = prompts.render(prompts.JOURNAL_QA)
    user = f"Pertanyaan: {question}\n\nKutipan sumber:\n{evidence}"

    sources = [hit.as_dict() for hit in hits]
    try:
        completion = _call("tanya_jurnal", system, user, billing=billing)
    except LLMUnavailable:
        return ServiceResult(
            text="",
            source="deterministik",
            meta={
                "sources": sources,
                "note": (
                    "Tanpa model bahasa, Recens mengembalikan potongan sumber paling relevan "
                    "beserta halamannya. Kutipan di bawah bisa langsung dibaca dan dikutip."
                ),
            },
        )

    text, verdict = guard_output(completion.text, kind="tanya_jurnal")
    return ServiceResult(
        text=text, verdict=verdict, meta={"sources": sources, "model": completion.model}
    )


def synthesis_row(reference: dict, hits: list[Hit], billing: Billing | None = None) -> dict:
    """Satu baris matriks sintesis untuk satu artikel."""
    entry = reference.get("csl_json", {})
    from ..citations.styles import authors, family_name, title_of
    from ..citations.styles import year as csl_year

    author_list = authors(entry)
    base = {
        "citekey": reference.get("citekey"),
        "penulis": family_name(author_list[0]) if author_list else "—",
        "tahun": csl_year(entry),
        "judul": title_of(entry),
        "teori": "belum diisi",
        "metode": "belum diisi",
        "sampel": "belum diisi",
        "temuan": "belum diisi",
        "celah": "belum diisi",
    }
    if not hits:
        base["catatan"] = (
            "Unggah PDF artikel ini ke pustaka proyek agar kolom teori, metode, dan "
            "temuan bisa diisi dari isinya."
        )
        return base

    system = prompts.render(prompts.SYNTHESIS)
    user = f"Artikel: {base['judul']}\n\nKutipan sumber:\n{format_evidence(hits)}"
    try:
        completion = _call("matriks_sintesis", system, user, billing=billing)
        payload = _extract_json(completion.text)
        if isinstance(payload, dict):
            base.update({k: v for k, v in payload.items() if k in base})
    except (LLMUnavailable, ValueError):
        abstract = reference.get("abstract") or ""
        if abstract:
            base["temuan"] = abstract[:300].strip() + ("…" if len(abstract) > 300 else "")
            base["catatan"] = "Kolom diisi dari abstrak resmi; lengkapi setelah membaca penuh."
    return base


# --- Analisis ----------------------------------------------------------------


def narrative_for_analysis(result: AnalysisResult, context: str = "", billing: Billing | None = None) -> ServiceResult:
    """Susun narasi pembahasan di atas angka yang sudah dihitung mesin statistik.

    Bila narasi model memuat angka yang tidak ada di hasil perhitungan, narasi
    itu ditolak dan diganti draf deterministik. Angka tidak pernah datang dari
    model.
    """
    fallback = draft_narrative(result)
    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    system = prompts.render(prompts.NARRATIVE)
    user = (
        f"Konteks penelitian: {context or 'tidak disebutkan'}\n\n"
        f"Hasil perhitungan (satu-satunya sumber angka yang boleh dipakai):\n{payload}"
    )

    try:
        completion = _call("narasi_hasil", system, user, billing=billing)
    except LLMUnavailable:
        return ServiceResult(
            text=fallback,
            source="deterministik",
            meta={"note": "Narasi disusun dari temuan mesin statistik."},
        )

    text, verdict = guard_output(
        completion.text, kind="narasi_hasil", analysis_result=result
    )

    # Naik satu tingkat, sekali saja, bila penjaga menolak.
    #
    # Inilah cara menekan biaya tanpa menurunkan mutu: sebagian besar narasi
    # lolos di jenjang murah, dan hanya yang benar-benar gagal yang dibayar
    # mahal. Kebalikannya — semuanya di jenjang mahal supaya aman — membayar
    # penuh untuk pekerjaan yang model murah sudah sanggup.
    #
    # Sekali saja, dan hanya karena penolakannya berarti sesuatu: angkanya
    # diperiksa mesin, bukan dinilai perasaan. Tanpa batas itu, satu hasil
    # analisis yang aneh bisa memanggil model termahal berkali-kali.
    # Hanya bila ``_call`` belum menaikkannya sendiri. Tanpa syarat ini,
    # keluaran yang gagal lantai mutu *dan* gagal penelusuran angka akan
    # memanggil model termahal dua kali untuk satu permintaan — biaya berlipat
    # justru pada kasus yang paling sering gagal.
    if not verdict.allowed and not completion.escalated:
        try:
            naik = route(
                "narasi_hasil", system, user, billing=billing, escalated=True
            ).completion
        except (LLMUnavailable, BudgetExceeded):
            naik = None
        if naik is not None:
            text_naik, verdict_naik = guard_output(
                naik.text, kind="narasi_hasil", analysis_result=result
            )
            if verdict_naik.allowed:
                return ServiceResult(
                    text=text_naik,
                    verdict=verdict_naik,
                    meta={"model": naik.model, "naik_tingkat": True},
                )

    if not verdict.allowed:
        return ServiceResult(
            text=fallback,
            source="deterministik",
            verdict=verdict,
            meta={
                "rejected_draft": completion.text,
                "note": (
                    "Narasi model ditolak karena memuat angka di luar hasil perhitungan. "
                    "Yang ditampilkan adalah draf yang seluruh angkanya berasal dari mesin "
                    "statistik."
                ),
            },
        )
    return ServiceResult(text=text, verdict=verdict, meta={"model": completion.model})


# --- Sidang & publikasi ------------------------------------------------------


def defense_questions(manuscript: Manuscript, weak_points: list[dict], billing: Billing | None = None) -> ServiceResult:
    """Mode siap sidang: menyusun kemungkinan pertanyaan penguji."""
    deterministic = _rule_based_defense_questions(manuscript, weak_points)
    system = prompts.render(prompts.DEFENSE)
    excerpt = manuscript.text()[:12000]
    user = (
        f"Titik lemah yang sudah terdeteksi sistem:\n"
        f"{json.dumps(weak_points, ensure_ascii=False, indent=2)}\n\n"
        f"Naskah:\n{excerpt}"
    )
    try:
        completion = _call("mode_sidang", system, user, billing=billing)
        payload = _extract_json(completion.text)
        questions = payload if isinstance(payload, list) else deterministic
    except (LLMUnavailable, ValueError):
        return ServiceResult(
            text=json.dumps(deterministic, ensure_ascii=False),
            source="deterministik",
            meta={"questions": deterministic},
        )
    return ServiceResult(
        text=json.dumps(questions, ensure_ascii=False), meta={"questions": questions}
    )


def _rule_based_defense_questions(manuscript: Manuscript, weak_points: list[dict]) -> list[dict]:
    """Pertanyaan yang bisa diturunkan langsung dari temuan pemeriksaan.

    Penguji hampir selalu menyerang titik yang sama: sampel, asumsi statistik,
    keselarasan rumusan dengan simpulan, dan kebaruan. Semua itu sudah terdeteksi
    pemeriksaan naskah, jadi pertanyaannya bisa disusun tanpa model.
    """
    questions: list[dict] = []
    for point in weak_points:
        message = point.get("message", "")
        if "rumusan masalah" in message.lower():
            questions.append(
                {
                    "pertanyaan": "Coba jelaskan, rumusan masalah mana yang dijawab oleh "
                                  "simpulan nomor berapa?",
                    "sasaran": "Keselarasan rumusan masalah dan simpulan",
                    "kerangka_jawaban": message,
                    "tingkat_risiko": "tinggi",
                }
            )
        if "normal" in message.lower() or "asumsi" in message.lower():
            questions.append(
                {
                    "pertanyaan": "Asumsi klasik mana yang tidak terpenuhi, dan mengapa "
                                  "uji ini tetap Anda pakai?",
                    "sasaran": "Uji asumsi klasik",
                    "kerangka_jawaban": message,
                    "tingkat_risiko": "tinggi",
                }
            )
        if "sitasi" in message.lower() or "referensi" in message.lower():
            questions.append(
                {
                    "pertanyaan": "Dari mana sumber pernyataan ini? Boleh saya lihat "
                                  "referensi aslinya?",
                    "sasaran": "Kelengkapan dan ketertelusuran sitasi",
                    "kerangka_jawaban": message,
                    "tingkat_risiko": "tinggi",
                }
            )

    standard = [
        ("Apa kebaruan penelitian Anda dibandingkan penelitian terdahulu?",
         "Kebaruan penelitian", "sedang"),
        ("Mengapa Anda memilih teknik sampling ini, dan seberapa representatif sampelnya?",
         "Populasi dan sampel", "tinggi"),
        ("Mengapa memilih uji statistik ini dan bukan yang lain?",
         "Teknik analisis data", "tinggi"),
        ("Apa keterbatasan penelitian ini yang Anda sadari sendiri?",
         "Keterbatasan penelitian", "sedang"),
        ("Apa implikasi praktis temuan Anda bagi objek penelitian?",
         "Implikasi dan saran", "sedang"),
    ]
    for question, target, risk in standard:
        questions.append(
            {
                "pertanyaan": question,
                "sasaran": target,
                "kerangka_jawaban": (
                    "Siapkan jawaban berdasarkan isi naskah; tunjuk bagian dan halaman "
                    "yang mendukungnya."
                ),
                "tingkat_risiko": risk,
            }
        )
    return questions


def cover_letter(meta: dict, billing: Billing | None = None) -> ServiceResult:
    """Surat pengantar ke editor — berkas wajib yang jarang diajarkan."""
    deterministic = _cover_letter_template(meta)
    system = prompts.render(prompts.COVER_LETTER)
    user = json.dumps(meta, ensure_ascii=False, indent=2)
    try:
        completion = _call("cover_letter", system, user, billing=billing)
    except LLMUnavailable:
        return ServiceResult(text=deterministic, source="deterministik")
    text, verdict = guard_output(completion.text, kind="cover_letter")
    return ServiceResult(text=text, verdict=verdict, meta={"model": completion.model})


def _cover_letter_template(meta: dict) -> str:
    return f"""Kepada Yth.
Editor {meta.get('journal', '[Nama Jurnal]')}

Dengan hormat,

Bersama surat ini kami mengajukan naskah berjudul "{meta.get('title', '[Judul Naskah]')}"
untuk dipertimbangkan pemuatannya di {meta.get('journal', '[Nama Jurnal]')}.

Kebaruan naskah ini terletak pada {meta.get('novelty', '[jelaskan apa yang belum dikerjakan penelitian sebelumnya]')}.
Penelitian ini {meta.get('summary', '[ringkas tujuan, metode, dan temuan utama dalam dua hingga tiga kalimat]')}.

Naskah ini sesuai dengan ruang lingkup {meta.get('journal', '[Nama Jurnal]')} karena
{meta.get('scope_fit', '[jelaskan kaitan topik dengan fokus dan ruang lingkup jurnal]')}.

Kami menyatakan bahwa naskah ini merupakan karya asli, belum pernah dipublikasikan,
dan tidak sedang dipertimbangkan di jurnal lain. Seluruh penulis telah menyetujui
pengiriman naskah ini dan tidak terdapat konflik kepentingan.

Atas perhatian dan pertimbangan Bapak/Ibu, kami mengucapkan terima kasih.

Hormat kami,
{meta.get('author', '[Nama Penulis Korespondensi]')}
{meta.get('affiliation', '[Afiliasi]')}
{meta.get('email', '[Surel]')}
"""


def reviewer_response(comments: list[dict], meta: dict | None = None, billing: Billing | None = None) -> ServiceResult:
    """Tanggapan poin per poin — tahap yang menentukan diterima tidaknya artikel."""
    deterministic = _reviewer_response_template(comments)
    system = prompts.render(prompts.REVIEWER_RESPONSE)
    user = json.dumps(
        {"komentar": comments, "konteks": meta or {}}, ensure_ascii=False, indent=2
    )
    try:
        completion = _call("respon_reviewer", system, user, billing=billing)
    except LLMUnavailable:
        return ServiceResult(text=deterministic, source="deterministik")
    text, verdict = guard_output(completion.text, kind="respon_reviewer")
    return ServiceResult(text=text, verdict=verdict, meta={"model": completion.model})


def _reviewer_response_template(comments: list[dict]) -> str:
    lines = [
        "TANGGAPAN ATAS KOMENTAR REVIEWER",
        "",
        "Kami mengucapkan terima kasih kepada reviewer atas masukan yang membangun.",
        "Berikut tanggapan kami poin per poin.",
        "",
    ]
    for index, comment in enumerate(comments, start=1):
        lines += [
            f"Komentar {index}: {comment.get('text', '')}",
            f"Tanggapan: {comment.get('response', '[tuliskan tanggapan penulis]')}",
            f"Perubahan pada naskah: {comment.get('change', '[sebutkan bagian dan halaman yang berubah]')}",
            "",
        ]
    return "\n".join(lines)


def structured_abstract(
    manuscript: Manuscript,
    sections: list[str] | None = None,
    max_words: int = 250,
    billing: Billing | None = None,
) -> ServiceResult:
    """Abstrak terstruktur sesuai pola yang diminta jurnal."""
    sections = sections or ["Tujuan", "Metode", "Hasil", "Simpulan"]
    deterministic = _abstract_skeleton(manuscript, sections, max_words)

    system = prompts.render(prompts.STRUCTURED_ABSTRACT)
    role_text = {
        role: "\n".join(s.text() for s in manuscript.sections_by_role(role))
        for role in ("latar_belakang", "metode", "hasil", "pembahasan", "simpulan")
    }
    user = (
        f"Bagian abstrak yang diminta: {', '.join(sections)}\n"
        f"Batas kata: {max_words}\n\n"
        f"Isi naskah per bagian:\n{json.dumps(role_text, ensure_ascii=False)[:14000]}"
    )
    try:
        completion = _call("abstrak_terstruktur", system, user, billing=billing)
    except LLMUnavailable:
        return ServiceResult(text=deterministic, source="deterministik")

    text, verdict = guard_output(completion.text, kind="abstrak", max_words=max_words + 40)
    return ServiceResult(text=text, verdict=verdict, meta={"model": completion.model})


def _abstract_skeleton(manuscript: Manuscript, sections: list[str], max_words: int) -> str:
    role_for = {
        "tujuan": "tujuan", "latar belakang": "latar_belakang", "metode": "metode",
        "hasil": "hasil", "simpulan": "simpulan", "pembahasan": "pembahasan",
    }
    lines = []
    for label in sections:
        role = role_for.get(label.lower())
        found = manuscript.sections_by_role(role) if role else []
        first = ""
        if found:
            text = found[0].text()
            sentences = re.split(r"(?<=[.!?])\s+", text)
            first = " ".join(sentences[1:3]).strip()
        lines.append(f"{label}: {first or '[belum ada isi pada bagian ini]'}")
    lines.append("")
    lines.append(f"Batas kata abstrak: {max_words}.")
    return "\n".join(lines)


def translate(
    text: str, direction: str = "id-en", field_of_study: str | None = None,
    billing: Billing | None = None,
) -> ServiceResult:
    """Penerjemahan dwibahasa dengan konsistensi istilah teknis dijaga glosarium.

    Padanan istilah tidak diserahkan ke model: ia disodorkan sebagai daftar
    wajib, lalu hasil terjemahan diperiksa ulang terhadap daftar itu.
    """
    from ..glossary import check_translation, glossary_hint

    hint = glossary_hint(text, field_of_study)
    system = prompts.render(prompts.TRANSLATE)
    arah = "Indonesia ke Inggris" if direction == "id-en" else "Inggris ke Indonesia"
    user = f"Arah terjemahan: {arah}\n\n{hint}\n\nTeks:\n{text}"

    try:
        completion = _call("terjemahan", system, user, temperature=0.2, billing=billing)
    except LLMUnavailable:
        from ..glossary import apply_glossary

        pairs = apply_glossary(text, field_of_study)
        return ServiceResult(
            text="",
            source="deterministik",
            meta={
                "glossary": pairs,
                "note": (
                    "Penerjemahan kalimat memerlukan model bahasa. Yang bisa dipastikan "
                    "tanpa model adalah padanan istilah teknisnya, dan daftar itu ada di "
                    "bawah — pakai sebagai acuan saat menyusun abstrak bahasa Inggris."
                ),
            },
        )

    translated, verdict = guard_output(completion.text, kind="terjemahan")
    check = (
        check_translation(text, translated, field_of_study)
        if direction == "id-en"
        else check_translation(translated, text, field_of_study)
    )
    return ServiceResult(
        text=translated,
        verdict=verdict,
        meta={
            "model": completion.model,
            "terminology": check,
            "note": (
                "Seluruh istilah teknis konsisten dengan glosarium."
                if check["passed"]
                else f"{len(check['issues'])} istilah teknis belum memakai padanan baku."
            ),
        },
    )


def condense_section(
    text: str, section_name: str, budget_words: int, source_section: str = "",
    billing: Billing | None = None,
) -> ServiceResult:
    """Padatkan satu bagian tugas akhir menjadi bagian artikel."""
    verdict = guard_request(text, kind="konversi")
    if not verdict.allowed:
        raise GuardrailError(verdict)

    system = prompts.render(prompts.CONDENSE)
    user = (
        f"Bagian artikel yang dituju: {section_name}\n"
        f"Asal bagian pada naskah: {source_section or 'tidak disebutkan'}\n"
        f"Anggaran kata: {budget_words}\n\nTeks sumber:\n{text}"
    )
    try:
        completion = _call("konversi_naskah", system, user, billing=billing)
    except LLMUnavailable:
        return ServiceResult(
            text="",
            source="deterministik",
            meta={
                "source_words": len(text.split()),
                "budget_words": budget_words,
                "note": (
                    "Pemadatan kalimat memerlukan model bahasa. Rencana konversi, "
                    "anggaran kata tiap bagian, serta pemindahan isi dan pustaka sudah "
                    "dikerjakan tanpa model."
                ),
            },
        )

    condensed, output_verdict = guard_output(
        completion.text, kind="konversi", max_words=int(budget_words * 1.2)
    )
    return ServiceResult(
        text=condensed,
        verdict=output_verdict,
        meta={
            "source_words": len(text.split()),
            "result_words": len(condensed.split()),
            "budget_words": budget_words,
            "model": completion.model,
        },
    )


def _extract_json(text: str):
    """Ambil JSON dari keluaran model yang mungkin dibungkus blok kode."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Keluaran model bukan JSON yang sah.")
