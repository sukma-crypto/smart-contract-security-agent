"""Perute panggilan model: memilih yang termurah yang sanggup, lalu mencatatnya.

Modul ini memegang satu tanggung jawab yang tidak boleh bocor ke tempat lain:
**tidak ada panggilan model yang terjadi tanpa melewati sini.** Sebabnya bukan
kerapian melainkan uang. Panggilan yang menyelinap lewat jalur lain adalah
pengeluaran tanpa nama, tanpa batas keluaran, dan tanpa catatan — dan
pengeluaran yang tidak tercatat tidak bisa ditekan karena tidak ada yang tahu
ia ada.

Enam kebocoran yang ditutup di sini, masing-masing pernah membuat tagihan orang
membengkak tanpa ada satu pun keputusan yang bisa ditunjuk sebagai penyebabnya:

1. **Masukan tak terbatas.** Perintah yang menyertakan naskah utuh dibayar per
   token, tiap kali. Masukan dipotong ke anggaran modelnya dan pemotongannya
   dilaporkan, bukan didiamkan.
2. **Keluaran tak terbatas.** Tanpa pagar, satu perintah yang salah bentuk
   menghasilkan keluaran sepanjang batas teknis model — dan itu dibayar penuh.
   Batasnya diambil dari katalog tugas, bukan dari pemanggil.
3. **Cadangan yang naik harga.** Sistem yang diam-diam pindah ke model mahal
   ketika yang murah sedang mati adalah cara paling umum tagihan berlipat: yang
   berubah cuma cuaca jaringan, bukan keputusan siapa pun.
4. **Percobaan ulang berlipat.** Tiap jenjang dicoba paling banyak sekali.
5. **Pengeluaran tanpa pagar.** Batas harian dan bulanan per akun diperiksa
   *sebelum* memanggil. Pagar yang menyala setelah uangnya keluar bukan pagar.
6. **Biaya tak terlihat.** Tiap panggilan dicatat lengkap dengan token
   sebenarnya dari penyedia dan biayanya, berhasil maupun gagal.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from ... import db
from ...config import get_settings
from .base import Completion, LLMUnavailable
from .catalog import MODELS, RANTAI, Model, Task, estimate_tokens, task_for, truncate_to_tokens
from .providers import get_providers


@dataclass
class Billing:
    """Kepada siapa biaya panggilan ini dibebankan.

    Diteruskan terang-terangan lewat parameter, bukan lewat variabel konteks
    tersembunyi. Panggilan tanpa ``Billing`` tetap berjalan tetapi tidak
    tercatat — dan itu memang hanya boleh terjadi di pengujian dan di jalur
    yang tidak punya pemilik, sehingga bentuknya yang mencolok justru berguna:
    panggilan tak berpemilik jadi kelihatan di kode, bukan tersembunyi di
    dalam kerangka kerja.
    """

    conn: sqlite3.Connection | None = None
    account_id: int | None = None
    project_id: int | None = None

    @classmethod
    def dari_proyek(cls, conn: sqlite3.Connection, project: dict) -> "Billing":
        return cls(
            conn=conn,
            account_id=project.get("account_id"),
            project_id=project.get("id"),
        )


class BudgetExceeded(RuntimeError):
    """Batas belanja API terlampaui; pemanggil harus memakai jalur deterministik."""

    def __init__(self, message: str, spent_cents: int, limit_cents: int, window: str):
        super().__init__(message)
        self.spent_cents = spent_cents
        self.limit_cents = limit_cents
        self.window = window


@dataclass
class RouteResult:
    completion: Completion
    model: Model
    task: Task
    #: Jenjang yang benar-benar dipakai bila berbeda dari jenjang bawaan tugas.
    escalated: bool = False
    attempts: list[str] = field(default_factory=list)


# --- Catatan pengeluaran -----------------------------------------------------


def record_call(
    conn: sqlite3.Connection,
    *,
    account_id: int | None,
    project_id: int | None,
    task: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_micros: int,
    outcome: str,
    detail: str = "",
) -> int:
    """Catat satu panggilan model, berhasil maupun gagal.

    Yang gagal ikut dicatat dengan sengaja. Panggilan yang ditolak penjaga
    tetap sudah dibayar, dan pola kegagalan yang mahal hanya terlihat bila ia
    tercatat — jenjang yang sering ditolak adalah jenjang yang salah pilih.
    """
    return db.insert(
        conn,
        "llm_calls",
        account_id=account_id,
        project_id=project_id,
        task=task,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_micros=cost_micros,
        outcome=outcome,
        detail=detail[:500],
        created_at=db.now(),
    )


def spend_micros(
    conn: sqlite3.Connection, account_id: int | None, since: str | None = None
) -> int:
    """Total pengeluaran satu akun sejak waktu tertentu, dalam mikro-dolar."""
    if account_id is None:
        return 0
    sql = "SELECT COALESCE(SUM(cost_micros), 0) AS total FROM llm_calls WHERE account_id = ?"
    args: list = [account_id]
    if since:
        sql += " AND created_at >= ?"
        args.append(since)
    return int(db.fetch_one(conn, sql, tuple(args))["total"])


def _awal_hari() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _awal_bulan() -> str:
    today = date.today()
    return datetime(today.year, today.month, 1, tzinfo=timezone.utc).isoformat()


def check_budget(conn: sqlite3.Connection, account_id: int | None) -> None:
    """Tolak panggilan bila akun sudah melewati pagar belanjanya.

    Diperiksa sebelum memanggil. Nol berarti tanpa batas, dan itu sengaja bukan
    nilai bawaan: pagar yang harus dinyalakan sendiri adalah pagar yang lupa
    dinyalakan.
    """
    if account_id is None:
        return
    settings = get_settings()

    for batas_cents, sejak, nama in (
        (settings.budget_daily_cents, _awal_hari(), "hari ini"),
        (settings.budget_monthly_cents, _awal_bulan(), "bulan ini"),
    ):
        if batas_cents <= 0:
            continue
        terpakai = spend_micros(conn, account_id, sejak)
        batas_micros = batas_cents * 10_000
        if terpakai >= batas_micros:
            raise BudgetExceeded(
                f"Batas pemakaian model untuk {nama} sudah tercapai "
                f"(${terpakai / 1_000_000:.2f} dari ${batas_micros / 1_000_000:.2f}). "
                f"Penyusunan kalimat memakai jalur deterministik sampai batasnya "
                f"disegarkan; fitur lain tetap berjalan penuh.",
                spent_cents=terpakai // 10_000,
                limit_cents=batas_cents,
                window=nama,
            )


# --- Pemilihan model ---------------------------------------------------------


def candidates_for(task: Task, escalated: bool = False) -> list[Model]:
    """Model yang boleh dipakai tugas ini, dari yang termurah.

    Hanya penyedia yang kuncinya benar-benar terpasang yang masuk daftar.
    Melewatinya di sini, bukan setelah panggilan gagal, menghemat satu bolak-
    balik jaringan pada tiap permintaan — dan pada sebagian penyedia, panggilan
    yang gagal pun tetap ditagih.
    """
    tersedia = set(get_providers())
    tier = task.tier
    if escalated:
        urutan = list(RANTAI)
        posisi = urutan.index(task.tier)
        tier = urutan[min(posisi + 1, len(urutan) - 1)]

    dipilih = [
        MODELS[key]
        for key in RANTAI[tier]
        if key in MODELS and MODELS[key].provider in tersedia
    ]
    if dipilih:
        return dipilih

    # Jenjang yang diminta tidak punya penyedia yang terpasang. Turun ke
    # jenjang yang lebih murah, tidak pernah naik: kalau yang mahal yang hidup,
    # ia dipakai hanya bila memang tidak ada pilihan lain sama sekali.
    urutan = list(RANTAI)
    for lain in reversed(urutan[: urutan.index(tier)]):
        turun = [
            MODELS[key]
            for key in RANTAI[lain]
            if key in MODELS and MODELS[key].provider in tersedia
        ]
        if turun:
            return turun
    for lain in urutan[urutan.index(tier) + 1 :]:
        naik = [
            MODELS[key]
            for key in RANTAI[lain]
            if key in MODELS and MODELS[key].provider in tersedia
        ]
        if naik:
            return naik
    return []


def route(
    task_key: str,
    system: str,
    user: str,
    *,
    billing: Billing | None = None,
    temperature: float = 0.3,
    escalated: bool = False,
) -> RouteResult:
    """Jalankan satu tugas pada model termurah yang tersedia untuk jenjangnya."""
    task = task_for(task_key)
    billing = billing or Billing()
    conn, account_id, project_id = billing.conn, billing.account_id, billing.project_id
    if conn is not None:
        check_budget(conn, account_id)

    pilihan = candidates_for(task, escalated=escalated)
    if not pilihan:
        raise LLMUnavailable(
            "Belum ada penyedia model yang dikonfigurasi. Setel salah satu dari "
            "DEEPSEEK_API_KEY, OPENAI_API_KEY, atau ANTHROPIC_API_KEY."
        )

    penyedia = get_providers()
    dicoba: list[str] = []
    kegagalan: list[str] = []

    for model in pilihan:
        # Anggaran masukan milik modelnya, bukan milik pemanggil. Perintah yang
        # menyertakan naskah utuh dipotong di sini, dan pemotongannya dilaporkan
        # supaya tidak ada hasil yang tampak utuh padahal dasarnya terpangkas.
        sisa = model.max_input_tokens - estimate_tokens(system) - task.max_output_tokens
        isi, terpotong = truncate_to_tokens(user, max(sisa, 500))
        dicoba.append(model.key)

        try:
            completion = penyedia[model.provider].complete(
                system=system,
                user=isi,
                model_id=model.model_id,
                max_tokens=task.max_output_tokens,
                temperature=temperature,
            )
        except LLMUnavailable as exc:
            kegagalan.append(f"{model.key}: {exc}")
            if conn is not None:
                record_call(
                    conn,
                    account_id=account_id,
                    project_id=project_id,
                    task=task.key,
                    provider=model.provider,
                    model=model.model_id,
                    input_tokens=0,
                    output_tokens=0,
                    cost_micros=0,
                    outcome="gagal",
                    detail=str(exc),
                )
            continue

        completion.truncated = terpotong
        completion.cost_micros = model.cost_micros(
            completion.input_tokens, completion.output_tokens
        )
        if conn is not None:
            record_call(
                conn,
                account_id=account_id,
                project_id=project_id,
                task=task.key,
                provider=model.provider,
                model=model.model_id,
                input_tokens=completion.input_tokens,
                output_tokens=completion.output_tokens,
                cost_micros=completion.cost_micros,
                outcome="naik_tingkat" if escalated else "berhasil",
            )
        return RouteResult(
            completion=completion, model=model, task=task, escalated=escalated, attempts=dicoba
        )

    raise LLMUnavailable(
        "Seluruh model untuk tugas ini gagal dipanggil. " + " | ".join(kegagalan)
    )


def usage_summary(conn: sqlite3.Connection, account_id: int | None) -> dict:
    """Ringkasan pemakaian dan sisa pagar anggaran satu akun."""
    settings = get_settings()
    harian = spend_micros(conn, account_id, _awal_hari())
    bulanan = spend_micros(conn, account_id, _awal_bulan())
    seluruhnya = spend_micros(conn, account_id)

    per_model = db.fetch_all(
        conn,
        "SELECT provider, model, COUNT(*) AS panggilan, "
        "COALESCE(SUM(input_tokens), 0) AS token_masuk, "
        "COALESCE(SUM(output_tokens), 0) AS token_keluar, "
        "COALESCE(SUM(cost_micros), 0) AS biaya "
        "FROM llm_calls WHERE account_id = ? AND created_at >= ? "
        "GROUP BY provider, model ORDER BY biaya DESC",
        (account_id, _awal_bulan()),
    )
    per_tugas = db.fetch_all(
        conn,
        "SELECT task, COUNT(*) AS panggilan, COALESCE(SUM(cost_micros), 0) AS biaya "
        "FROM llm_calls WHERE account_id = ? AND created_at >= ? "
        "GROUP BY task ORDER BY biaya DESC",
        (account_id, _awal_bulan()),
    )
    gagal = db.fetch_one(
        conn,
        "SELECT COUNT(*) AS n FROM llm_calls WHERE account_id = ? AND outcome != 'berhasil' "
        "AND created_at >= ?",
        (account_id, _awal_bulan()),
    )["n"]

    return {
        "hari_ini_usd": round(harian / 1_000_000, 4),
        "bulan_ini_usd": round(bulanan / 1_000_000, 4),
        "seluruhnya_usd": round(seluruhnya / 1_000_000, 4),
        "batas_harian_usd": round(settings.budget_daily_cents / 100, 2),
        "batas_bulanan_usd": round(settings.budget_monthly_cents / 100, 2),
        "sisa_harian_usd": round(
            max(settings.budget_daily_cents * 10_000 - harian, 0) / 1_000_000, 4
        )
        if settings.budget_daily_cents > 0
        else None,
        "sisa_bulanan_usd": round(
            max(settings.budget_monthly_cents * 10_000 - bulanan, 0) / 1_000_000, 4
        )
        if settings.budget_monthly_cents > 0
        else None,
        "per_model": [
            {
                "provider": row["provider"],
                "model": row["model"],
                "panggilan": row["panggilan"],
                "token_masuk": row["token_masuk"],
                "token_keluar": row["token_keluar"],
                "biaya_usd": round(row["biaya"] / 1_000_000, 4),
            }
            for row in per_model
        ],
        "per_tugas": [
            {
                "task": row["task"],
                "panggilan": row["panggilan"],
                "biaya_usd": round(row["biaya"] / 1_000_000, 4),
            }
            for row in per_tugas
        ],
        "panggilan_gagal_bulan_ini": gagal,
    }
