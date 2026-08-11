"""Perenderan penanda internal menjadi teks akhir.

Penanda sitasi dan acuan silang disimpan sebagai penanda, bukan teks jadi,
supaya satu naskah bisa dikeluarkan dalam gaya sitasi apa pun tanpa menyunting
ulang isinya — dan supaya sitasi tidak pernah lepas sinkron dari daftar pustaka.
"""

from __future__ import annotations

import re

from .citations.styles import CitationStyle
from .manuscript import CITE_PATTERN, XREF_PATTERN

#: Penanda yang sengaja mencolok bila sebuah sitasi tidak ada di pustaka.
MISSING_TEMPLATE = "[SITASI TIDAK DITEMUKAN: {key}]"


def render_citations(
    text: str,
    entries: dict[str, dict],
    style: CitationStyle,
    index_map: dict[str, int] | None = None,
) -> str:
    """Ganti penanda sitasi dengan bentuk akhir sesuai gaya yang berlaku.

    Sitasi yang citekey-nya tidak ada di pustaka tidak dihapus diam-diam,
    melainkan diganti penanda yang terlihat jelas di naskah hasil ekspor.
    """
    index_map = index_map or {}

    def replace(match: re.Match) -> str:
        citekey, locator = match.group(1), match.group(2)
        entry = entries.get(citekey)
        if entry is None:
            return MISSING_TEMPLATE.format(key=citekey)
        return style.in_text(entry, locator=locator, index=index_map.get(citekey))

    return CITE_PATTERN.sub(replace, text)


def render_xrefs(text: str, captions: dict[str, dict]) -> str:
    """Ganti acuan silang dengan nomor tabel atau gambar yang sudah terhitung."""

    def replace(match: re.Match) -> str:
        kind, label = match.group(1), match.group(2)
        caption = captions.get(label)
        if caption is None:
            return f"[{kind.upper()} TIDAK DITEMUKAN: {label}]"
        return f"{caption['kind']} {caption['number']}"

    return XREF_PATTERN.sub(replace, text)


def render_block(
    text: str,
    entries: dict[str, dict],
    style: CitationStyle,
    captions: dict[str, dict],
    index_map: dict[str, int] | None = None,
) -> str:
    return render_xrefs(render_citations(text, entries, style, index_map), captions)
