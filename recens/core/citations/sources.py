"""Sumber metadata sitasi — hanya basis data ilmiah resmi.

Kesalahan paling fatal pada karya ilmiah adalah referensi karangan. Recens
menutup jalannya secara arsitektural: metadata sitasi tidak pernah disusun oleh
model bahasa, melainkan ditarik dari Crossref, OpenAlex, Semantic Scholar, atau
Garuda/SINTA, lalu disimpan apa adanya sebagai CSL-JSON.

Referensi yang diunggah pengguna sendiri tetap boleh masuk pustaka, tetapi
ditandai belum terverifikasi sampai metadatanya cocok dengan salah satu basis
data di atas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from ...config import get_settings

CSL = dict[str, Any]

#: Basis data yang diakui sebagai sumber kebenaran metadata.
OFFICIAL_SOURCES = ("crossref", "openalex", "semantic_scholar", "garuda")


class SourceUnavailable(RuntimeError):
    """Layanan literatur tidak dapat dihubungi atau belum dikonfigurasi."""


@dataclass
class SearchResult:
    entry: CSL
    source_db: str
    external_id: str
    abstract: str = ""
    verified: bool = True

    def as_dict(self) -> dict:
        return {
            "entry": self.entry,
            "source_db": self.source_db,
            "external_id": self.external_id,
            "abstract": self.abstract,
            "verified": self.verified,
            "citekey": suggest_citekey(self.entry),
        }


def _client() -> httpx.Client:
    settings = get_settings()
    if not settings.network_enabled:
        raise SourceUnavailable(
            "Akses jaringan dimatikan (RECENS_NETWORK=0). Pencarian literatur daring "
            "tidak tersedia; referensi masih bisa ditambahkan lewat unggahan PDF."
        )
    headers = {"User-Agent": "Recens/0.1 (academic writing tool)"}
    if settings.crossref_mailto:
        headers["User-Agent"] += f" mailto:{settings.crossref_mailto}"
    return httpx.Client(timeout=settings.http_timeout, headers=headers, follow_redirects=True)


def suggest_citekey(entry: CSL) -> str:
    """Citekey ringkas: nama belakang penulis pertama + tahun."""
    from .styles import authors, family_name, year

    author_list = authors(entry)
    base = family_name(author_list[0]) if author_list else (entry.get("container-title") or "anon")
    if isinstance(base, list):
        base = base[0] if base else "anon"
    slug = re.sub(r"[^a-z0-9]", "", str(base).lower())[:20] or "anon"
    return f"{slug}{year(entry)}"


def _date_parts(*values) -> dict:
    parts = [int(v) for v in values if v not in (None, "")]
    return {"date-parts": [parts or [0]]}


# --- Crossref ----------------------------------------------------------------


def _from_crossref_item(item: dict) -> SearchResult:
    issued = item.get("issued", {}).get("date-parts", [[None]])
    entry: CSL = {
        "id": "",
        "type": _map_crossref_type(item.get("type", "")),
        "title": (item.get("title") or [""])[0],
        "author": [
            {"family": a.get("family", ""), "given": a.get("given", "")}
            for a in item.get("author", [])
            if a.get("family") or a.get("given")
        ],
        "issued": {"date-parts": issued},
        "container-title": (item.get("container-title") or [""])[0],
        "volume": item.get("volume", ""),
        "issue": item.get("issue", ""),
        "page": item.get("page", ""),
        "DOI": item.get("DOI", ""),
        "publisher": item.get("publisher", ""),
        "URL": item.get("URL", ""),
        "ISSN": (item.get("ISSN") or [None])[0],
    }
    entry["id"] = suggest_citekey(entry)
    abstract = re.sub(r"<[^>]+>", "", item.get("abstract", "") or "").strip()
    return SearchResult(
        entry=entry, source_db="crossref", external_id=item.get("DOI", ""), abstract=abstract
    )


def _map_crossref_type(value: str) -> str:
    return {
        "journal-article": "article-journal",
        "proceedings-article": "paper-conference",
        "book": "book",
        "book-chapter": "chapter",
        "dissertation": "thesis",
        "posted-content": "article",
        "report": "report",
    }.get(value, "article-journal")


def search_crossref(query: str, rows: int = 10) -> list[SearchResult]:
    with _client() as client:
        response = client.get(
            "https://api.crossref.org/works",
            params={"query.bibliographic": query, "rows": rows, "select": (
                "DOI,title,author,issued,container-title,volume,issue,page,type,publisher,URL,"
                "abstract,ISSN"
            )},
        )
        response.raise_for_status()
        items = response.json().get("message", {}).get("items", [])
    return [_from_crossref_item(item) for item in items]


def fetch_doi(doi: str) -> SearchResult:
    """Sumber kebenaran metadata DOI: penulis, tahun, jurnal, volume, halaman."""
    doi = doi.strip().replace("https://doi.org/", "").replace("http://doi.org/", "")
    with _client() as client:
        response = client.get(f"https://api.crossref.org/works/{doi}")
        if response.status_code == 404:
            raise SourceUnavailable(f"DOI {doi} tidak ditemukan di Crossref.")
        response.raise_for_status()
        item = response.json().get("message", {})
    return _from_crossref_item(item)


# --- OpenAlex ----------------------------------------------------------------


def _decode_inverted_abstract(index: dict | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, spots in index.items():
        positions.extend((spot, word) for spot in spots)
    return " ".join(word for _, word in sorted(positions))


def _from_openalex_item(item: dict) -> SearchResult:
    biblio = item.get("biblio") or {}
    first, last = biblio.get("first_page"), biblio.get("last_page")
    pages = f"{first}-{last}" if first and last else (first or "")
    source = (item.get("primary_location") or {}).get("source") or {}
    entry: CSL = {
        "id": "",
        "type": "article-journal",
        "title": item.get("title") or item.get("display_name") or "",
        "author": [
            _split_display_name((a.get("author") or {}).get("display_name", ""))
            for a in item.get("authorships", [])
        ],
        "issued": _date_parts(item.get("publication_year")),
        "container-title": source.get("display_name", ""),
        "volume": biblio.get("volume") or "",
        "issue": biblio.get("issue") or "",
        "page": pages,
        "DOI": (item.get("doi") or "").replace("https://doi.org/", ""),
        "URL": item.get("id", ""),
    }
    entry["id"] = suggest_citekey(entry)
    return SearchResult(
        entry=entry,
        source_db="openalex",
        external_id=item.get("id", ""),
        abstract=_decode_inverted_abstract(item.get("abstract_inverted_index")),
    )


def _split_display_name(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        return {"family": "", "given": ""}
    parts = name.split()
    if len(parts) == 1:
        return {"family": parts[0], "given": ""}
    return {"family": parts[-1], "given": " ".join(parts[:-1])}


def search_openalex(query: str, rows: int = 10) -> list[SearchResult]:
    settings = get_settings()
    if not settings.openalex_enabled:
        raise SourceUnavailable("OpenAlex dimatikan lewat konfigurasi.")
    params = {"search": query, "per_page": rows}
    if settings.crossref_mailto:
        params["mailto"] = settings.crossref_mailto
    with _client() as client:
        response = client.get("https://api.openalex.org/works", params=params)
        response.raise_for_status()
        items = response.json().get("results", [])
    return [_from_openalex_item(item) for item in items]


# --- Semantic Scholar --------------------------------------------------------


def _from_semantic_scholar_item(item: dict) -> SearchResult:
    external = item.get("externalIds") or {}
    entry: CSL = {
        "id": "",
        "type": "article-journal",
        "title": item.get("title", ""),
        "author": [_split_display_name(a.get("name", "")) for a in item.get("authors", [])],
        "issued": _date_parts(item.get("year")),
        "container-title": item.get("venue", ""),
        "DOI": external.get("DOI", ""),
        "URL": item.get("url", ""),
    }
    entry["id"] = suggest_citekey(entry)
    return SearchResult(
        entry=entry,
        source_db="semantic_scholar",
        external_id=item.get("paperId", ""),
        abstract=item.get("abstract") or "",
    )


def search_semantic_scholar(query: str, rows: int = 10) -> list[SearchResult]:
    settings = get_settings()
    headers = {"x-api-key": settings.semantic_scholar_key} if settings.semantic_scholar_key else {}
    with _client() as client:
        response = client.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={
                "query": query,
                "limit": rows,
                "fields": "title,year,authors,abstract,venue,externalIds,url",
            },
            headers=headers,
        )
        response.raise_for_status()
        items = response.json().get("data", []) or []
    return [_from_semantic_scholar_item(item) for item in items]


# --- Garuda / SINTA ----------------------------------------------------------


def search_garuda(query: str, rows: int = 10) -> list[SearchResult]:
    """Jurnal nasional terakreditasi.

    Garuda/SINTA tidak menyediakan API publik yang stabil, sehingga adaptor ini
    menunjuk ke endpoint yang dikonfigurasi lembaga (``RECENS_GARUDA_BASE_URL``)
    dan mengharapkan keluaran berbentuk CSL-JSON. Bila belum dikonfigurasi,
    Recens mengatakannya apa adanya alih-alih mengarang hasil pencarian.
    """
    settings = get_settings()
    if not settings.garuda_base_url:
        raise SourceUnavailable(
            "Sumber Garuda/SINTA belum dikonfigurasi. Isi RECENS_GARUDA_BASE_URL dengan "
            "endpoint yang menyediakan metadata CSL-JSON."
        )
    with _client() as client:
        response = client.get(
            settings.garuda_base_url.rstrip("/") + "/search",
            params={"q": query, "limit": rows},
        )
        response.raise_for_status()
        payload = response.json()
    items = payload.get("results", payload if isinstance(payload, list) else [])
    results = []
    for item in items[:rows]:
        entry = dict(item)
        entry.setdefault("type", "article-journal")
        entry["id"] = suggest_citekey(entry)
        results.append(
            SearchResult(
                entry=entry,
                source_db="garuda",
                external_id=str(item.get("id", "")),
                abstract=item.get("abstract", ""),
            )
        )
    return results


# --- Pencarian serentak ------------------------------------------------------

PROVIDERS = {
    "crossref": search_crossref,
    "openalex": search_openalex,
    "semantic_scholar": search_semantic_scholar,
    "garuda": search_garuda,
}


def search_all(
    query: str, rows: int = 10, providers: list[str] | None = None
) -> dict[str, Any]:
    """Penelusuran serentak ke jurnal nasional dan basis data internasional.

    Kegagalan satu sumber tidak menjatuhkan pencarian; sumber yang gagal
    dilaporkan agar pengguna tahu cakupan hasil yang sedang dilihatnya.
    """
    chosen = providers or list(PROVIDERS)
    results: list[SearchResult] = []
    errors: dict[str, str] = {}
    for name in chosen:
        provider = PROVIDERS.get(name)
        if provider is None:
            errors[name] = "sumber tidak dikenal"
            continue
        try:
            results.extend(provider(query, rows=rows))
        except SourceUnavailable as exc:
            errors[name] = str(exc)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"

    deduped = _dedupe(results)
    return {
        "query": query,
        "count": len(deduped),
        "results": [r.as_dict() for r in deduped],
        "sources_searched": [n for n in chosen if n not in errors],
        "sources_failed": errors,
    }


def _dedupe(results: list[SearchResult]) -> list[SearchResult]:
    """Satu karya bisa muncul di beberapa basis data; DOI jadi kunci utama."""
    by_doi: dict[str, SearchResult] = {}
    by_title: dict[str, SearchResult] = {}
    ordered: list[SearchResult] = []
    for result in results:
        doi = str(result.entry.get("DOI", "")).lower().strip()
        title_key = re.sub(r"[^a-z0-9]", "", str(result.entry.get("title", "")).lower())[:80]
        if doi and doi in by_doi:
            continue
        if not doi and title_key and title_key in by_title:
            continue
        if doi:
            by_doi[doi] = result
        if title_key:
            by_title[title_key] = result
        ordered.append(result)
    return ordered
