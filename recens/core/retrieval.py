"""Pencarian semantik-leksikal atas dokumen proyek.

Fitur Tanya Jurnal harus menjawab disertai penunjuk halaman sumber. Karena
jawaban wajib bisa ditelusuri, pengambilan potongan dilakukan lokal dengan BM25
di atas potongan yang menyimpan nomor halamannya — bukan diserahkan ke ingatan
model. Bila layanan embedding tersedia, peringkat BM25 dipakai sebagai
pengambilan tahap pertama.
"""

from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass

from .. import db

#: Kata tugas bahasa Indonesia dan Inggris yang tidak membedakan makna.
STOPWORDS = {
    "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "adalah", "ini",
    "itu", "atau", "dalam", "tidak", "akan", "dapat", "oleh", "sebagai", "juga",
    "telah", "bahwa", "karena", "agar", "para", "suatu", "serta", "antara", "lebih",
    "the", "a", "an", "of", "and", "or", "to", "in", "is", "are", "was", "were",
    "for", "on", "with", "that", "this", "by", "as", "at", "be", "from", "it",
}

TOKEN_RE = re.compile(r"[a-zA-ZÀ-ɏ]+|\d+(?:[.,]\d+)?")


def tokenize(text: str) -> list[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text or "")]
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


@dataclass
class Chunk:
    ref_id: int
    citekey: str
    page: int | None
    text: str
    title: str = ""


@dataclass
class Hit:
    chunk: Chunk
    score: float

    def as_dict(self) -> dict:
        return {
            "citekey": self.chunk.citekey,
            "ref_id": self.chunk.ref_id,
            "page": self.chunk.page,
            "title": self.chunk.title,
            "text": self.chunk.text,
            "score": round(self.score, 4),
        }


class BM25:
    """BM25 Okapi — cukup untuk korpus satu proyek dan berjalan tanpa jaringan."""

    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.doc_len = [len(d) for d in documents]
        self.avgdl = (sum(self.doc_len) / len(documents)) if documents else 0.0
        self.freqs = [Counter(d) for d in documents]
        self.df: Counter[str] = Counter()
        for freq in self.freqs:
            self.df.update(freq.keys())
        self.n = len(documents)

    def idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query_tokens: list[str], index: int) -> float:
        if not self.avgdl:
            return 0.0
        freq = self.freqs[index]
        length = self.doc_len[index]
        total = 0.0
        for term in query_tokens:
            tf = freq.get(term, 0)
            if not tf:
                continue
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * length / self.avgdl)
            total += self.idf(term) * numerator / denominator
        return total

    def rank(self, query_tokens: list[str], top_k: int = 5) -> list[tuple[int, float]]:
        scored = [(i, self.score(query_tokens, i)) for i in range(self.n)]
        scored = [(i, s) for i, s in scored if s > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


def load_chunks(
    conn: sqlite3.Connection, project_id: int, ref_ids: list[int] | None = None
) -> list[Chunk]:
    sql = (
        "SELECT c.ref_id, c.page, c.text, r.citekey, r.csl_json "
        "FROM ref_chunks c JOIN refs r ON r.id = c.ref_id "
        "WHERE r.project_id = ?"
    )
    params: list = [project_id]
    if ref_ids:
        placeholders = ",".join("?" for _ in ref_ids)
        sql += f" AND c.ref_id IN ({placeholders})"
        params.extend(ref_ids)
    sql += " ORDER BY c.ref_id, c.ordinal"

    chunks = []
    for row in db.fetch_all(conn, sql, params):
        import json

        try:
            entry = json.loads(row["csl_json"])
        except (json.JSONDecodeError, TypeError):
            entry = {}
        title = entry.get("title", "")
        if isinstance(title, list):
            title = title[0] if title else ""
        chunks.append(
            Chunk(
                ref_id=row["ref_id"],
                citekey=row["citekey"],
                page=row["page"],
                text=row["text"],
                title=str(title),
            )
        )
    return chunks


def search_chunks(
    conn: sqlite3.Connection,
    project_id: int,
    question: str,
    top_k: int = 5,
    ref_ids: list[int] | None = None,
) -> list[Hit]:
    chunks = load_chunks(conn, project_id, ref_ids)
    if not chunks:
        return []
    index = BM25([tokenize(c.text) for c in chunks])
    query_tokens = tokenize(question)
    if not query_tokens:
        return []
    return [Hit(chunk=chunks[i], score=score) for i, score in index.rank(query_tokens, top_k)]


def format_evidence(hits: list[Hit]) -> str:
    """Susun kutipan sumber dengan penunjuk halaman untuk dibaca model."""
    lines = []
    for position, hit in enumerate(hits, start=1):
        page = f"hlm. {hit.chunk.page}" if hit.chunk.page else "halaman tidak diketahui"
        lines.append(
            f"[{position}] ({hit.chunk.citekey}, {page}) {hit.chunk.title}\n{hit.chunk.text}"
        )
    return "\n\n".join(lines)
