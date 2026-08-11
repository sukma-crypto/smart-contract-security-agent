"""Akun, kata sandi, dan sesi.

Modul ini menyimpan dua rahasia, dan keduanya sengaja tidak pernah disimpan
apa adanya:

* **Kata sandi** disimpan sebagai turunan PBKDF2-HMAC-SHA256 dengan garam acak
  per akun. Jumlah iterasinya ikut disimpan di dalam string hash, sehingga
  angka itu bisa dinaikkan di kemudian hari tanpa membatalkan kata sandi yang
  sudah ada — verifikasi memakai jumlah iterasi milik hash, bukan milik kode.
* **Token sesi** dikirim ke peramban dalam bentuk aslinya, tetapi yang tersimpan
  di basis data hanyalah SHA-256 dari token itu. Bocornya salinan basis data
  karena itu tidak langsung menyerahkan sesi siapa pun.

PBKDF2 dipilih karena tersedia di pustaka standar. Ia lebih lemah dari Argon2id
terhadap serangan perangkat keras khusus; bila nanti dipasang ``argon2-cffi``,
tambahkan skema baru di ``_SCHEMES`` dan biarkan hash lama tetap terverifikasi —
``needs_rehash`` sudah menyiapkan jalan pindahnya.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import sqlite3
import unicodedata
from base64 import urlsafe_b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .. import db

#: Iterasi PBKDF2 untuk hash baru. Mengikuti anjuran OWASP untuk SHA-256.
PBKDF2_ITERATIONS = 600_000
_ALGORITHM = "pbkdf2_sha256"

#: Umur sesi. Diperpanjang sendiri selama dipakai (lihat ``touch_session``).
SESSION_DAYS = 30

#: Batas panjang kata sandi. Batas atas ada supaya PBKDF2 tidak bisa dijadikan
#: alat menghabiskan CPU lewat kiriman kata sandi sepanjang megabyte.
MIN_PASSWORD = 10
MAX_PASSWORD = 256

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

#: Kata sandi yang paling sering dipakai di Indonesia beserta turunan jelasnya.
#: Daftar pendek ini bukan pengganti pemeriksaan kebocoran, tetapi menahan
#: pilihan terburuk tanpa perlu memanggil layanan luar.
_COMMON_PASSWORDS = {
    "password", "password123", "qwerty123", "12345678", "123456789", "1234567890",
    "indonesia", "indonesia1", "adminadmin", "administrator", "iloveyou",
    "sayangkamu", "namasaya", "rahasia123", "kataSandi", "katasandi",
    "skripsi123", "mahasiswa", "mahasiswa123", "universitas", "recens123",
}


class AuthError(Exception):
    """Kegagalan yang aman ditunjukkan kepada pengguna."""


# --- Kata sandi --------------------------------------------------------------


def _b64(raw: bytes) -> str:
    return urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _normalize(password: str) -> bytes:
    """Samakan bentuk Unicode agar kata sandi ber-aksen tetap cocok.

    Tanpa ini, kata sandi yang mengandung "é" bisa gagal saat diketik dari
    papan ketik yang menghasilkan bentuk terurai, padahal hurufnya sama.
    """
    return unicodedata.normalize("NFKC", password).encode("utf-8")


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", _normalize(password), salt, iterations)
    return f"{_ALGORITHM}${iterations}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Cocokkan kata sandi dengan hash tersimpan, tanpa membocorkan lewat waktu.

    Akun tanpa kata sandi (peninggalan sebelum autentikasi ada) tetap dijalankan
    lewat satu perhitungan tiruan, supaya lamanya jawaban tidak memberi tahu
    penyerang bahwa akun tersebut ada tetapi belum berkata sandi.
    """
    if not stored:
        hashlib.pbkdf2_hmac("sha256", _normalize(password), b"garam-tiruan", 1_000)
        return False
    try:
        algorithm, raw_iterations, salt_b64, hash_b64 = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", _normalize(password), _unb64(salt_b64), int(raw_iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, _unb64(hash_b64))


def needs_rehash(stored: str | None) -> bool:
    """Benar bila hash dibuat dengan parameter yang kini dianggap terlalu lemah."""
    if not stored:
        return True
    try:
        algorithm, raw_iterations, _, _ = stored.split("$")
    except ValueError:
        return True
    return algorithm != _ALGORITHM or int(raw_iterations) < PBKDF2_ITERATIONS


def password_problem(password: str, email: str = "", display_name: str = "") -> str | None:
    """Kembalikan alasan penolakan, atau ``None`` bila kata sandi diterima.

    Aturannya sengaja tidak menuntut campuran simbol dan angka. Syarat semacam
    itu mendorong orang membuat "Skripsi2024!" — panjang di atas kertas, mudah
    ditebak pada praktiknya. Yang ditagih di sini adalah panjang, ditambah
    penolakan atas kata sandi yang isinya nama atau surel pemiliknya sendiri.
    """
    if len(password) < MIN_PASSWORD:
        return (
            f"Kata sandi minimal {MIN_PASSWORD} karakter. Kalimat pendek yang mudah "
            f"Anda ingat — misalnya tiga kata yang tidak berhubungan — lebih aman "
            f"daripada satu kata dengan angka di ujungnya."
        )
    if len(password) > MAX_PASSWORD:
        return f"Kata sandi maksimal {MAX_PASSWORD} karakter."

    folded = password.casefold()
    if folded in _COMMON_PASSWORDS:
        return "Kata sandi ini termasuk yang paling sering dipakai. Pilih yang lain."
    if len(set(folded)) <= 3:
        return "Kata sandi terlalu berulang. Tambahkan kata lain."

    local_part = email.split("@")[0].casefold() if email else ""
    for piece in (local_part, display_name.casefold()):
        if piece and len(piece) >= 4 and piece in folded:
            return "Kata sandi sebaiknya tidak memuat nama atau surel Anda sendiri."
    return None


def normalize_email(email: str) -> str:
    cleaned = email.strip().casefold()
    if not _EMAIL_RE.match(cleaned):
        raise AuthError(f"Surel '{email.strip()}' tidak berbentuk alamat yang sah.")
    return cleaned


# --- Sesi --------------------------------------------------------------------


@dataclass(frozen=True)
class Session:
    id: int
    account_id: int
    token: str
    expires_at: str


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _expiry(days: int = SESSION_DAYS) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(timespec="seconds")


def create_session(
    conn: sqlite3.Connection, account_id: int, user_agent: str = "", ip: str = ""
) -> Session:
    token = secrets.token_urlsafe(32)
    expires_at = _expiry()
    session_id = db.insert(
        conn,
        "sessions",
        account_id=account_id,
        token_hash=_hash_token(token),
        user_agent=user_agent[:300],
        ip=ip[:60],
        created_at=db.now(),
        last_seen_at=db.now(),
        expires_at=expires_at,
    )
    return Session(id=session_id, account_id=account_id, token=token, expires_at=expires_at)


def resolve_session(conn: sqlite3.Connection, token: str | None) -> dict | None:
    """Terjemahkan token menjadi baris sesi yang masih berlaku, atau ``None``."""
    if not token:
        return None
    row = db.fetch_one(
        conn, "SELECT * FROM sessions WHERE token_hash = ?", (_hash_token(token),)
    )
    if row is None:
        return None
    session = dict(row)
    if session["expires_at"] <= db.now():
        conn.execute("DELETE FROM sessions WHERE id = ?", (session["id"],))
        conn.commit()
        return None
    return session


def touch_session(conn: sqlite3.Connection, session_id: int) -> None:
    """Tandai sesi masih dipakai dan geser kedaluwarsanya ke depan.

    Sesi yang dipakai tiap hari tidak akan memutus orang di tengah menulis;
    sesi yang ditinggalkan tetap mati sendiri setelah ``SESSION_DAYS``.
    """
    db.update(conn, "sessions", session_id, last_seen_at=db.now(), expires_at=_expiry())


def revoke_session(conn: sqlite3.Connection, session_id: int, account_id: int) -> bool:
    cur = conn.execute(
        "DELETE FROM sessions WHERE id = ? AND account_id = ?", (session_id, account_id)
    )
    conn.commit()
    return cur.rowcount > 0


def revoke_all_sessions(
    conn: sqlite3.Connection, account_id: int, keep_session_id: int | None = None
) -> int:
    sql = "DELETE FROM sessions WHERE account_id = ?"
    params: tuple = (account_id,)
    if keep_session_id is not None:
        sql += " AND id != ?"
        params += (keep_session_id,)
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.rowcount


def list_sessions(conn: sqlite3.Connection, account_id: int) -> list[dict]:
    """Sesi aktif milik satu akun. Token tidak pernah ikut keluar dari sini."""
    rows = db.fetch_all(
        conn,
        "SELECT id, user_agent, ip, created_at, last_seen_at, expires_at FROM sessions "
        "WHERE account_id = ? AND expires_at > ? ORDER BY last_seen_at DESC",
        (account_id, db.now()),
    )
    return [dict(row) for row in rows]


def purge_expired_sessions(conn: sqlite3.Connection) -> int:
    cur = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (db.now(),))
    conn.commit()
    return cur.rowcount


# --- Akun --------------------------------------------------------------------


def find_account_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = db.fetch_one(conn, "SELECT * FROM accounts WHERE email = ?", (normalize_email(email),))
    return dict(row) if row else None


def set_password(conn: sqlite3.Connection, account_id: int, password: str) -> None:
    db.update(conn, "accounts", account_id, password_hash=hash_password(password))


def authenticate(conn: sqlite3.Connection, email: str, password: str) -> dict:
    """Kembalikan akun bila surel dan kata sandinya cocok.

    Pesan galatnya sengaja sama untuk surel yang tidak terdaftar dan kata sandi
    yang salah, supaya halaman masuk tidak bisa dipakai memetakan siapa saja
    yang punya akun di sini.
    """
    try:
        normalized = normalize_email(email)
    except AuthError:
        normalized = email.strip().casefold()

    row = db.fetch_one(conn, "SELECT * FROM accounts WHERE email = ?", (normalized,))
    account = dict(row) if row else None
    stored = account["password_hash"] if account else None

    if not verify_password(password, stored) or account is None:
        raise AuthError("Surel atau kata sandi salah.")

    # Kesempatan alami menaikkan biaya hash: kata sandinya ada di tangan kita
    # dalam bentuk asli hanya pada saat ini.
    if needs_rehash(stored):
        set_password(conn, account["id"], password)
    return account
