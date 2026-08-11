"""Kredit & langganan (Bagian 4.7 dan Bagian 06).

Prinsip yang menentukan bentuk modul ini: **tidak ada fitur yang dikunci
berdasarkan paket, jenjang pendidikan, atau jenis karya.** Yang membedakan paket
hanyalah kuota dan durasi.

Karena itu tidak ada fungsi ``is_feature_allowed(plan, feature)`` di sini, dan
tidak boleh ada. Yang ada hanya pemeriksaan kuota. Skripsi S1 sama menuntutnya
dengan tesis S2, dan mengunci analisis data untuk jenjang tertentu akan membuat
produk gagal di segmen terbesarnya.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .. import db


@dataclass(frozen=True)
class Plan:
    key: str
    label: str
    suitable_for: str
    credits: int
    duration_days: int | None
    project_limit: int | None
    watermark: bool = False

    @property
    def feature_access(self) -> str:
        return (
            "Seluruh fitur bisa dicoba dengan batas pemakaian."
            if self.watermark
            else "Seluruh fitur terbuka."
        )

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "suitable_for": self.suitable_for,
            "credits": self.credits,
            "duration_days": self.duration_days,
            "project_limit": self.project_limit,
            "watermark": self.watermark,
            "feature_access": self.feature_access,
        }


PLANS: dict[str, Plan] = {
    "coba": Plan(
        key="coba",
        label="Coba",
        suitable_for="Menjajal alur kerja",
        credits=200,
        duration_days=14,
        project_limit=1,
        watermark=True,
    ),
    "bulanan": Plan(
        key="bulanan",
        label="Bulanan",
        suitable_for="Makalah, laporan, esai, dan karya pendek lain",
        credits=3_000,
        duration_days=30,
        project_limit=None,
    ),
    "semester": Plan(
        key="semester",
        label="Semester",
        suitable_for="Satu siklus tugas akhir atau proposal",
        credits=20_000,
        duration_days=182,
        project_limit=None,
    ),
    "tahunan": Plan(
        key="tahunan",
        label="Tahunan",
        suitable_for="Disertasi, riset panjang, dan kebutuhan publikasi berkala",
        credits=50_000,
        duration_days=365,
        project_limit=None,
    ),
}

#: Biaya kredit per tindakan. Tindakan yang tidak memanggil model berbiaya nol.
COSTS: dict[str, int] = {
    "lanjutan_kalimat": 1,
    "parafrase": 2,
    "bahasa_akademik": 2,
    "outline": 5,
    "tanya_jurnal": 3,
    "matriks_sintesis": 4,
    "narasi_hasil": 4,
    "mode_sidang": 10,
    "cover_letter": 5,
    "respon_reviewer": 6,
    "abstrak_terstruktur": 4,
    "pencarian_literatur": 1,
    "terjemahan": 3,
    "konversi_naskah": 8,
    # Berjalan lokal, tidak menagih kredit:
    "analisis_data": 0,
    "uji_instrumen": 0,
    "cek_naskah": 0,
    "cek_kemiripan": 0,
    "auto_format": 0,
    "ekspor": 0,
    "sitasi": 0,
    "impor_komentar": 0,
    "rencana_konversi": 0,
    "cek_jurnal": 0,
    "glosarium": 0,
}


class QuotaExceeded(RuntimeError):
    def __init__(self, message: str, needed: int, available: int):
        super().__init__(message)
        self.needed = needed
        self.available = available


class SubscriptionExpired(RuntimeError):
    pass


def create_account(
    conn: sqlite3.Connection, email: str, plan_key: str = "coba", display_name: str = ""
) -> dict:
    plan = PLANS.get(plan_key)
    if plan is None:
        raise ValueError(f"Paket '{plan_key}' tidak dikenal. Pilihan: {', '.join(PLANS)}.")

    valid_until = (
        (datetime.now(timezone.utc) + timedelta(days=plan.duration_days)).date().isoformat()
        if plan.duration_days
        else None
    )
    account_id = db.insert(
        conn,
        "accounts",
        email=email,
        display_name=display_name or email.split("@")[0],
        plan=plan.key,
        credits=plan.credits,
        valid_until=valid_until,
        created_at=db.now(),
    )
    db.insert(
        conn,
        "credit_ledger",
        account_id=account_id,
        project_id=None,
        delta=plan.credits,
        reason=f"Pembukaan paket {plan.label}",
        created_at=db.now(),
    )
    return get_account(conn, account_id)


def get_account(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = db.fetch_one(conn, "SELECT * FROM accounts WHERE id = ?", (account_id,))
    if row is None:
        return None
    account = dict(row)
    plan = PLANS.get(account["plan"], PLANS["coba"])
    account["plan_detail"] = plan.to_dict()
    account["expired"] = is_expired(account)
    account["project_count"] = db.fetch_one(
        conn, "SELECT COUNT(*) AS n FROM projects WHERE account_id = ?", (account_id,)
    )["n"]
    return account


def is_expired(account: dict) -> bool:
    if not account.get("valid_until"):
        return False
    return date.fromisoformat(account["valid_until"]) < date.today()


def ensure_active(account: dict) -> None:
    if is_expired(account):
        raise SubscriptionExpired(
            f"Masa berlaku paket {account['plan']} berakhir pada {account['valid_until']}. "
            f"Naskah dan data Anda tetap tersimpan dan bisa diekspor; perpanjang paket "
            f"untuk melanjutkan fitur yang memakai kredit."
        )


def cost_of(action: str) -> int:
    return COSTS.get(action, 1)


def can_afford(account: dict, action: str) -> bool:
    return account["credits"] >= cost_of(action)


def charge(
    conn: sqlite3.Connection, account_id: int, action: str, project_id: int | None = None
) -> dict:
    """Tagih kredit untuk satu tindakan.

    Tindakan yang berjalan lokal berbiaya nol dan tetap dicatat sebagai nol
    supaya pengguna bisa melihat bahwa fitur tersebut memang tidak menagih.
    """
    account = get_account(conn, account_id)
    if account is None:
        raise ValueError(f"Akun {account_id} tidak ditemukan.")

    amount = cost_of(action)
    if amount == 0:
        return {"charged": 0, "credits_left": account["credits"], "action": action}

    ensure_active(account)
    if account["credits"] < amount:
        raise QuotaExceeded(
            f"Kredit tidak mencukupi untuk '{action}': dibutuhkan {amount}, tersisa "
            f"{account['credits']}. Fitur yang berjalan lokal — analisis data, pemeriksaan "
            f"naskah, auto-format, dan ekspor — tetap bisa dipakai tanpa kredit.",
            needed=amount,
            available=account["credits"],
        )

    db.update(conn, "accounts", account_id, credits=account["credits"] - amount)
    db.insert(
        conn,
        "credit_ledger",
        account_id=account_id,
        project_id=project_id,
        delta=-amount,
        reason=action,
        created_at=db.now(),
    )
    return {
        "charged": amount,
        "credits_left": account["credits"] - amount,
        "action": action,
    }


def top_up(conn: sqlite3.Connection, account_id: int, amount: int, reason: str) -> dict:
    account = get_account(conn, account_id)
    if account is None:
        raise ValueError(f"Akun {account_id} tidak ditemukan.")
    db.update(conn, "accounts", account_id, credits=account["credits"] + amount)
    db.insert(
        conn,
        "credit_ledger",
        account_id=account_id,
        project_id=None,
        delta=amount,
        reason=reason,
        created_at=db.now(),
    )
    return get_account(conn, account_id)


def change_plan(conn: sqlite3.Connection, account_id: int, plan_key: str) -> dict:
    plan = PLANS.get(plan_key)
    if plan is None:
        raise ValueError(f"Paket '{plan_key}' tidak dikenal.")
    valid_until = (
        (datetime.now(timezone.utc) + timedelta(days=plan.duration_days)).date().isoformat()
        if plan.duration_days
        else None
    )
    account = get_account(conn, account_id)
    db.update(
        conn,
        "accounts",
        account_id,
        plan=plan.key,
        credits=account["credits"] + plan.credits,
        valid_until=valid_until,
    )
    db.insert(
        conn,
        "credit_ledger",
        account_id=account_id,
        project_id=None,
        delta=plan.credits,
        reason=f"Perubahan ke paket {plan.label}",
        created_at=db.now(),
    )
    return get_account(conn, account_id)


def check_project_quota(conn: sqlite3.Connection, account_id: int) -> None:
    account = get_account(conn, account_id)
    if account is None:
        raise ValueError(f"Akun {account_id} tidak ditemukan.")
    limit = PLANS.get(account["plan"], PLANS["coba"]).project_limit
    if limit is not None and account["project_count"] >= limit:
        raise QuotaExceeded(
            f"Paket {account['plan']} dibatasi {limit} proyek. Paket berbayar memberi "
            f"proyek tak terbatas — seluruh fiturnya sama, yang berbeda kuota dan durasinya.",
            needed=1,
            available=0,
        )


def ledger(conn: sqlite3.Connection, account_id: int, limit: int = 50) -> list[dict]:
    rows = db.fetch_all(
        conn,
        "SELECT * FROM credit_ledger WHERE account_id = ? ORDER BY id DESC LIMIT ?",
        (account_id, limit),
    )
    return [dict(row) for row in rows]
