"""Kredit & langganan.

Yang membedakan paket adalah kuota dan durasi, bukan fitur.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..core import credits
from .deps import get_conn

router = APIRouter(tags=["langganan"])


class AccountCreate(BaseModel):
    email: str
    display_name: str = ""
    plan: str = "coba"


class PlanChange(BaseModel):
    plan: str


class TopUp(BaseModel):
    amount: int
    reason: str = "Pembelian kredit"


@router.get("/plans")
def list_plans() -> dict:
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


@router.post("/accounts", status_code=201)
def create_account(payload: AccountCreate, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        return credits.create_account(
            conn, email=payload.email, plan_key=payload.plan, display_name=payload.display_name
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, f"Akun dengan surel {payload.email} sudah ada.") from exc


@router.get("/accounts/{account_id}")
def get_account(account_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    account = credits.get_account(conn, account_id)
    if account is None:
        raise HTTPException(404, f"Akun {account_id} tidak ditemukan.")
    return account


@router.post("/accounts/{account_id}/plan")
def change_plan(
    account_id: int, payload: PlanChange, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    try:
        return credits.change_plan(conn, account_id, payload.plan)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/accounts/{account_id}/topup")
def top_up(
    account_id: int, payload: TopUp, conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    if payload.amount <= 0:
        raise HTTPException(400, "Jumlah kredit harus lebih besar dari nol.")
    try:
        return credits.top_up(conn, account_id, payload.amount, payload.reason)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/accounts/{account_id}/ledger")
def ledger(account_id: int, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    if credits.get_account(conn, account_id) is None:
        raise HTTPException(404, f"Akun {account_id} tidak ditemukan.")
    return credits.ledger(conn, account_id)
