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
from .deps import current_account, get_conn

router = APIRouter(tags=["langganan"])


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
