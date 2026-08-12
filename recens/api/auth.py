"""Pendaftaran, masuk, dan pengelolaan akun.

Kuki sesi diberi ``httponly`` supaya tidak terbaca JavaScript, dan
``samesite=lax`` supaya tidak ikut terkirim pada permintaan lintas situs —
dua penutup yang membuat pencurian sesi lewat XSS dan CSRF jauh lebih sulit.
Tanda ``secure`` menyala bila ``RECENS_HTTPS=1``; di ``localhost`` ia harus
mati, karena peramban membuang kuki ``secure`` pada koneksi biasa.
"""

from __future__ import annotations

import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import db
from ..core import auth, credits
from .deps import SESSION_COOKIE, current_account, current_session, get_conn

router = APIRouter(tags=["akun"])


def _https_only() -> bool:
    return os.environ.get("RECENS_HTTPS", "").strip().lower() in {"1", "true", "yes", "on"}


def _set_cookie(response: Response, session: auth.Session) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session.token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=_https_only(),
        path="/",
    )


class Register(BaseModel):
    email: str
    password: str
    display_name: str = ""
    plan: str = "coba"


class Login(BaseModel):
    email: str
    password: str


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    email: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    logout_other_sessions: bool = True


class AccountDelete(BaseModel):
    password: str
    confirm: str = ""


def _public(account: dict) -> dict:
    """Bentuk akun yang aman dikirim ke klien."""
    return {
        key: value
        for key, value in account.items()
        if key not in {"password_hash"}
    }


# --- Masuk & keluar ----------------------------------------------------------


@router.post("/auth/register", status_code=201)
def register(
    payload: Register,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Buat akun sekaligus membuka sesinya."""
    try:
        email = auth.normalize_email(payload.email)
    except auth.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc

    display_name = payload.display_name.strip() or email.split("@")[0]
    problem = auth.password_problem(payload.password, email=email, display_name=display_name)
    if problem:
        raise HTTPException(400, problem)

    if auth.find_account_by_email(conn, email) is not None:
        raise HTTPException(409, f"Surel {email} sudah terdaftar. Masuk saja, atau pakai surel lain.")

    try:
        account = credits.create_account(
            conn, email=email, plan_key=payload.plan, display_name=display_name
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except sqlite3.IntegrityError as exc:  # balapan antar-permintaan
        raise HTTPException(409, f"Surel {email} sudah terdaftar.") from exc

    auth.set_password(conn, account["id"], payload.password)
    session = auth.create_session(
        conn,
        account["id"],
        user_agent=request.headers.get("user-agent", ""),
        ip=request.client.host if request.client else "",
    )
    _set_cookie(response, session)
    return {"account": _public(credits.get_account(conn, account["id"])), "token": session.token}


@router.post("/auth/login")
def login(
    payload: Login,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    try:
        account = auth.authenticate(conn, payload.email, payload.password)
    except auth.AuthError as exc:
        raise HTTPException(401, str(exc)) from exc

    session = auth.create_session(
        conn,
        account["id"],
        user_agent=request.headers.get("user-agent", ""),
        ip=request.client.host if request.client else "",
    )
    _set_cookie(response, session)
    auth.purge_expired_sessions(conn)
    return {"account": _public(credits.get_account(conn, account["id"])), "token": session.token}


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    session: dict = Depends(current_session),
) -> None:
    auth.revoke_session(conn, session["id"], session["account_id"])
    response.delete_cookie(SESSION_COOKIE, path="/")


# --- Akun sendiri (CRUD) -----------------------------------------------------


@router.get("/auth/me")
def me(account: dict = Depends(current_account)) -> dict:
    """Siapa yang sedang masuk. Dipakai antarmuka saat memuat halaman."""
    return _public(account)


@router.patch("/auth/me")
def update_me(
    payload: ProfileUpdate,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    values: dict = {}
    if payload.display_name is not None:
        name = payload.display_name.strip()
        if not name:
            raise HTTPException(400, "Nama tampilan tidak boleh kosong.")
        values["display_name"] = name
    if payload.email is not None:
        try:
            email = auth.normalize_email(payload.email)
        except auth.AuthError as exc:
            raise HTTPException(400, str(exc)) from exc
        existing = auth.find_account_by_email(conn, email)
        if existing and existing["id"] != account["id"]:
            raise HTTPException(409, f"Surel {email} sudah dipakai akun lain.")
        values["email"] = email

    if values:
        db.update(conn, "accounts", account["id"], **values)
    return _public(credits.get_account(conn, account["id"]))


@router.post("/auth/me/password")
def change_password(
    payload: PasswordChange,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
    session: dict = Depends(current_session),
) -> dict:
    """Ganti kata sandi.

    Kata sandi lama tetap diminta meski sesinya sudah sah: tanpa itu, peramban
    yang ditinggal terbuka di komputer perpustakaan cukup untuk mengambil alih
    akun secara permanen.
    """
    row = db.fetch_one(conn, "SELECT password_hash FROM accounts WHERE id = ?", (account["id"],))
    if not auth.verify_password(payload.current_password, row["password_hash"] if row else None):
        raise HTTPException(403, "Kata sandi saat ini salah.")

    problem = auth.password_problem(
        payload.new_password,
        email=account.get("email") or "",
        display_name=account.get("display_name") or "",
    )
    if problem:
        raise HTTPException(400, problem)

    auth.set_password(conn, account["id"], payload.new_password)
    revoked = 0
    if payload.logout_other_sessions:
        revoked = auth.revoke_all_sessions(conn, account["id"], keep_session_id=session["id"])
    return {
        "changed": True,
        "sessions_revoked": revoked,
        "note": (
            "Kata sandi diganti. Perangkat lain yang sedang masuk sudah dikeluarkan."
            if revoked
            else "Kata sandi diganti."
        ),
    }


@router.delete("/auth/me", status_code=204)
def delete_me(
    payload: AccountDelete,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> None:
    """Hapus akun beserta seluruh proyek di dalamnya.

    Dua pagar sebelum penghapusan: kata sandi, dan pengetikan ulang surel.
    Yang hilang di sini adalah naskah berbulan-bulan, dan tidak ada cadangan
    yang bisa memulihkannya.
    """
    row = db.fetch_one(conn, "SELECT password_hash FROM accounts WHERE id = ?", (account["id"],))
    if not auth.verify_password(payload.password, row["password_hash"] if row else None):
        raise HTTPException(403, "Kata sandi salah.")
    if payload.confirm.strip().casefold() != (account.get("email") or "").casefold():
        raise HTTPException(
            400,
            "Ketik ulang surel akun ini untuk memastikan penghapusan memang disengaja.",
        )

    conn.execute("DELETE FROM accounts WHERE id = ?", (account["id"],))
    conn.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


# --- Sesi aktif --------------------------------------------------------------


@router.get("/auth/sessions")
def list_sessions(
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
    session: dict = Depends(current_session),
) -> list[dict]:
    """Perangkat yang sedang masuk. Sesi yang sedang dipakai ditandai."""
    return [
        {**item, "current": item["id"] == session["id"]}
        for item in auth.list_sessions(conn, account["id"])
    ]


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke(
    session_id: int,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
    session: dict = Depends(current_session),
) -> None:
    if not auth.revoke_session(conn, session_id, account["id"]):
        raise HTTPException(404, f"Sesi {session_id} tidak ditemukan.")
    if session_id == session["id"]:
        response.delete_cookie(SESSION_COOKIE, path="/")
