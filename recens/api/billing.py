"""Kredit & langganan.

Yang membedakan paket adalah kuota dan durasi, bukan fitur.

Seluruh rute di sini bekerja pada akun yang sedang masuk, dan **tidak menerima
nomor akun dari luar**. Selama ``/accounts/{id}/topup`` masih ada, siapa pun
yang bisa menebak sebuah angka bisa menambah kredit ke akun orang lain — atau,
lewat ``/ledger``, membaca riwayat pemakaian mereka.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core import credits
from ..core.llm.catalog import MODELS, RANTAI, TASKS, Tier
from ..core.llm.router import candidates_for, quality_report, usage_summary
from .deps import current_account, get_conn

router = APIRouter(tags=["langganan"])

#: Satu tugas mewakili tiap jenjang, dipakai memperlihatkan hasil perutean.
_CONTOH_PER_JENJANG = {
    Tier.RINGAN: "lanjutan_kalimat",
    Tier.SEDANG: "outline",
    Tier.BERAT: "mode_sidang",
}


class PlanChange(BaseModel):
    plan: str


class TopUp(BaseModel):
    amount: int
    reason: str = "Pembelian kredit"


@router.get("/plans")
def list_plans() -> dict:
    """Katalog paket. Terbuka, karena halaman harga perlu dibaca sebelum masuk."""
    return {
        "plans": [plan.to_dict() for plan in credits.PLANS.values()],
        "principle": (
            "Tidak ada fitur yang dikunci berdasarkan jenjang pendidikan atau jenis karya. "
            "Skripsi S1 juga menuntut uji validitas dan regresi; tesis S2 juga bisa "
            "sepenuhnya kualitatif. Yang menentukan fitur mana dipakai adalah kebutuhan "
            "karyanya, bukan tingkat pendidikan penulisnya."
        ),
        "costs": credits.COSTS,
        "free_actions": [action for action, cost in credits.COSTS.items() if cost == 0],
    }


@router.get("/account")
def my_account(account: dict = Depends(current_account)) -> dict:
    """Akun sendiri, beserta paket, sisa kredit, dan jumlah proyek."""
    return account


@router.post("/account/plan")
def change_plan(
    payload: PlanChange,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    try:
        return credits.change_plan(conn, account["id"], payload.plan)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/account/topup")
def top_up(
    payload: TopUp,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    """Penambahan kredit.

    Belum ada gerbang pembayaran: yang tercatat di sini adalah pembukuan
    internal, dan pemanggilnya harus sudah masuk sebagai pemilik akun.
    """
    if payload.amount <= 0:
        raise HTTPException(400, "Jumlah kredit harus lebih besar dari nol.")
    try:
        return credits.top_up(conn, account["id"], payload.amount, payload.reason)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/account/ledger")
def ledger(
    conn: sqlite3.Connection = Depends(get_conn), account: dict = Depends(current_account)
) -> list[dict]:
    """Riwayat pemakaian kredit — tiap tindakan yang menagih dan berapa besarnya."""
    return credits.ledger(conn, account["id"])


@router.get("/account/usage")
def account_usage(
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    """Pemakaian model bahasa dan sisa pagar anggaran akun ini.

    Rincian per model dan per tugas ikut disertakan, sebab total saja tidak
    menolong siapa pun menekan biaya: yang bisa ditindaklanjuti adalah "narasi
    hasil menghabiskan separuh anggaran bulan ini", bukan "bulan ini habis dua
    dolar".

    Hanya akun yang sedang masuk. Nomor akun tidak diterima dari luar — riwayat
    pemakaian adalah catatan siapa mengerjakan apa dan kapan.
    """
    return usage_summary(conn, account["id"])


@router.get("/account/quality")
def account_quality(
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    """Angka penolakan mutu per tugas dan model.

    Inilah yang membuat penjenjangan bisa disetel dari bukti alih-alih tebakan.
    Tugas dengan angka penolakan tinggi di jenjang murah adalah tugas yang
    salah ditempatkan — dan itu terlihat di sini sebelum ada yang mengeluh,
    bukan sesudah.
    """
    baris = quality_report(conn, account["id"])
    perlu_ditinjau = [r for r in baris if r["panggilan"] >= 5 and r["angka_penolakan"] > 0.2]
    return {
        "rincian": baris,
        "perlu_ditinjau": perlu_ditinjau,
        "catatan": (
            "Keluaran diperiksa dengan aturan yang bisa dibuktikan salah — kalimat "
            "terputus, jawaban berpindah bahasa, sitasi di luar pustaka, keluaran yang "
            "merosot jadi pengulangan. Yang tidak lolos dinaikkan satu tingkat, sekali."
        ),
    }


@router.get("/models")
def model_catalog() -> dict:
    """Katalog model, harganya, dan jenjang mana memakai apa.

    Terbuka supaya keputusan perutean bisa diperiksa tanpa membaca kode —
    termasuk oleh yang membayar tagihannya.
    """
    return {
        "models": [
            {
                "key": m.key,
                "provider": m.provider,
                "label": m.label,
                "tier": m.tier.value,
                "harga_input_usd_per_juta_token": round(m.input_micros_per_mtok / 1_000_000, 3),
                "harga_output_usd_per_juta_token": round(m.output_micros_per_mtok / 1_000_000, 3),
                "batas_token_masukan": m.max_input_tokens,
            }
            for m in MODELS.values()
        ],
        "rantai": {tier.value: list(keys) for tier, keys in RANTAI.items()},
        # Yang benar-benar akan dipakai hari ini, setelah penyedia yang
        # kuncinya belum dipasang dicoret. Kosong berarti tidak ada penyedia
        # yang terpasang sama sekali, dan seluruh penyusunan kalimat memakai
        # jalur deterministik.
        "aktif": {
            tier.value: [m.key for m in candidates_for(TASKS[contoh])]
            for tier, contoh in _CONTOH_PER_JENJANG.items()
        },
        "tugas": [
            {
                "key": t.key,
                "label": t.label,
                "tier": t.tier.value,
                "batas_keluaran_token": t.max_output_tokens,
                "naik_tingkat_bila_ditolak": t.escalate_on_reject,
            }
            for t in TASKS.values()
        ],
        "catatan": (
            "Model dipilih berdasarkan berat tugasnya, bukan jenjang pendidikan "
            "penggunanya. Cadangan tidak pernah berpindah ke model yang lebih mahal."
        ),
    }
