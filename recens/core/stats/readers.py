"""Pembaca berkas data penelitian (Bagian 5.2).

Recens hanya mengolah data yang benar-benar diunggah pengguna. Tidak ada jalur
kode yang membangkitkan baris data baru; pembersihan yang dilakukan hanya
bersifat pembacaan — konversi tipe, pengenalan desimal koma, dan penandaan
nilai hilang — dan setiap tindakannya dilaporkan.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

MISSING_TOKENS = {"", "na", "n/a", "-", "--", ".", "null", "none", "nan", "tidak ada"}


class UnsupportedDataFile(ValueError):
    pass


@dataclass
class LoadedData:
    frame: pd.DataFrame
    source: str
    #: Catatan tindakan pembacaan, ditampilkan apa adanya ke pengguna.
    notes: list[str] = field(default_factory=list)
    value_labels: dict = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        return self.frame.shape

    def preview(self, rows: int = 8) -> dict:
        head = self.frame.head(rows)
        return {
            "columns": [str(c) for c in self.frame.columns],
            "rows": head.astype(object).where(pd.notna(head), None).values.tolist(),
            "n_rows": int(self.frame.shape[0]),
            "n_cols": int(self.frame.shape[1]),
            "dtypes": {str(c): str(t) for c, t in self.frame.dtypes.items()},
            "notes": self.notes,
        }


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ";" if sample.count(";") > sample.count(",") else ","


def read_csv(path: Path | str) -> LoadedData:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 selalu berhasil
        text = raw.decode("utf-8", errors="replace")

    sample = text[:8192]
    delimiter = _sniff_delimiter(sample)
    notes = [f"Pemisah kolom terdeteksi: '{delimiter}'."]

    # Desimal koma lazim pada ekspor Excel berlokal Indonesia.
    decimal = ","
    if delimiter == ",":
        decimal = "."
    elif re.search(r"\d+,\d+", sample) and not re.search(r"\d+\.\d+", sample):
        notes.append("Angka desimal memakai koma; dibaca sebagai desimal.")
    else:
        decimal = "."

    frame = pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        decimal=decimal,
        na_values=sorted(MISSING_TOKENS),
        keep_default_na=True,
    )
    return _finalize(frame, str(path), notes)


def read_excel(path: Path | str, sheet: str | int = 0) -> LoadedData:
    frame = pd.read_excel(path, sheet_name=sheet, na_values=sorted(MISSING_TOKENS))
    if isinstance(frame, dict):  # beberapa lembar
        first = next(iter(frame))
        return _finalize(frame[first], str(path), [f"Lembar dibaca: '{first}'."])
    return _finalize(frame, str(path), [])


def read_spss(path: Path | str) -> LoadedData:
    """Baca berkas SPSS .sav lengkap dengan label variabel dan label nilai."""
    try:
        import pyreadstat
    except ImportError as exc:  # pragma: no cover
        raise UnsupportedDataFile(
            "Membaca berkas SPSS (.sav) memerlukan pyreadstat. "
            "Jalankan: pip install pyreadstat"
        ) from exc

    frame, meta = pyreadstat.read_sav(str(path))
    notes = ["Berkas SPSS dibaca langsung beserta label variabelnya."]
    labels = dict(getattr(meta, "variable_value_labels", {}) or {})
    loaded = _finalize(frame, str(path), notes)
    loaded.value_labels = labels
    if getattr(meta, "column_names_to_labels", None):
        loaded.notes.append(
            "Label variabel tersedia dan dipakai sebagai judul kolom pada tabel hasil."
        )
    return loaded


def read_transcript(path: Path | str) -> LoadedData:
    """Transkrip wawancara yang sudah diketik pengguna, dipecah per giliran bicara."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    rows = []
    speaker_re = re.compile(r"^\s*([A-Z][\w .'-]{0,40})\s*:\s*(.+)$")
    current_speaker, buffer = None, []
    line_start = 1
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = speaker_re.match(line)
        if match:
            if current_speaker is not None and buffer:
                rows.append((current_speaker, " ".join(buffer).strip(), line_start))
            current_speaker = match.group(1).strip()
            buffer = [match.group(2).strip()]
            line_start = line_no
        elif line.strip():
            buffer.append(line.strip())
    if current_speaker is not None and buffer:
        rows.append((current_speaker, " ".join(buffer).strip(), line_start))
    if not rows:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        rows = [("informan", p, i + 1) for i, p in enumerate(paragraphs)]

    frame = pd.DataFrame(rows, columns=["informan", "ucapan", "baris"])
    return _finalize(frame, str(path), [f"{len(rows)} giliran bicara terbaca dari transkrip."])


def _finalize(frame: pd.DataFrame, source: str, notes: list[str]) -> LoadedData:
    frame = frame.copy()
    frame.columns = [str(c).strip() for c in frame.columns]

    empty_cols = [c for c in frame.columns if frame[c].isna().all()]
    if empty_cols:
        frame = frame.drop(columns=empty_cols)
        notes.append(f"{len(empty_cols)} kolom kosong dilewati: {', '.join(empty_cols)}.")

    before = len(frame)
    frame = frame.dropna(how="all")
    if len(frame) != before:
        notes.append(f"{before - len(frame)} baris kosong dilewati.")

    converted = []
    for column in frame.columns:
        if frame[column].dtype == object:
            candidate = pd.to_numeric(
                frame[column].astype(str).str.strip().str.replace(",", ".", regex=False),
                errors="coerce",
            )
            if candidate.notna().sum() >= max(1, int(0.9 * frame[column].notna().sum())):
                frame[column] = candidate
                converted.append(column)
    if converted:
        notes.append(f"{len(converted)} kolom dibaca sebagai angka: {', '.join(converted)}.")

    missing = int(frame.isna().sum().sum())
    if missing:
        notes.append(f"Terdapat {missing} sel kosong; uji dijalankan pada data yang tersedia.")

    return LoadedData(frame=frame, source=source, notes=notes)


READERS = {
    ".csv": read_csv,
    ".tsv": read_csv,
    ".txt": read_transcript,
    ".xlsx": read_excel,
    ".xls": read_excel,
    ".xlsm": read_excel,
    ".sav": read_spss,
}


def detect_kind(path: Path | str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".csv": "csv", ".tsv": "csv", ".xlsx": "xlsx", ".xls": "xlsx", ".xlsm": "xlsx",
        ".sav": "sav", ".txt": "transcript", ".docx": "transcript",
    }.get(suffix, "unknown")


#: Berkas yang tidak bisa dibaca langsung, tetapi isinya tetap bisa diolah
#: lewat jalur tempel. Tanpa petunjuk ini, mahasiswa yang mengunggah
#: ``output.spv`` hanya melihat penolakan dan menyimpulkan Recens tidak bisa
#: menangani hasil SPSS-nya — padahal bisa, hanya lewat pintu yang berbeda.
JALUR_TEMPEL: dict[str, str] = {
    ".spv": (
        "Berkas .spv adalah format keluaran SPSS yang tertutup dan tidak bisa dibaca "
        "langsung. Buka berkasnya di SPSS, salin tabel yang Anda butuhkan, lalu tempel "
        "lewat 'Baca output tertempel' — angkanya dibaca apa adanya lalu dinarasikan. "
        "Untuk mengolah datanya dari nol, ekspor dulu ke .sav atau .xlsx."
    ),
    ".spo": (
        "Berkas .spo adalah keluaran SPSS versi lama. Salin tabelnya lalu tempel lewat "
        "'Baca output tertempel'."
    ),
    ".r": (
        "Berkas .R berisi skrip, bukan data. Tempel keluaran konsolnya lewat 'Baca "
        "output tertempel' agar tabelnya distrukturkan dan dinarasikan, atau unggah "
        "data mentahnya sebagai .csv untuk diolah dari nol."
    ),
    ".rdata": (
        "Berkas .RData belum bisa dibaca langsung. Dari R, jalankan "
        "write.csv(data, 'data.csv') lalu unggah berkas .csv-nya."
    ),
    ".rds": (
        "Berkas .rds belum bisa dibaca langsung. Dari R, jalankan "
        "write.csv(readRDS('berkas.rds'), 'data.csv') lalu unggah berkas .csv-nya."
    ),
    ".png": (
        "Tangkapan layar belum bisa dibaca karena OCR belum tersambung. Salin tabelnya "
        "sebagai teks lalu tempel lewat 'Baca output tertempel'."
    ),
    ".jpg": (
        "Tangkapan layar belum bisa dibaca karena OCR belum tersambung. Salin tabelnya "
        "sebagai teks lalu tempel lewat 'Baca output tertempel'."
    ),
    ".jpeg": (
        "Tangkapan layar belum bisa dibaca karena OCR belum tersambung. Salin tabelnya "
        "sebagai teks lalu tempel lewat 'Baca output tertempel'."
    ),
    ".dta": (
        "Berkas Stata .dta belum didukung. Ekspor ke .csv dari Stata lalu unggah kembali."
    ),
    ".json": (
        "Data dalam bentuk JSON belum dibaca langsung. Ubah ke .csv lebih dahulu."
    ),
}


def load(path: Path | str) -> LoadedData:
    suffix = Path(path).suffix.lower()
    reader = READERS.get(suffix)
    if reader is None:
        petunjuk = JALUR_TEMPEL.get(suffix)
        if petunjuk:
            raise UnsupportedDataFile(petunjuk)
        raise UnsupportedDataFile(
            f"Format '{suffix}' belum didukung. Format yang diterima: "
            f"{', '.join(sorted(READERS))}. Bila yang Anda punya adalah output jadi "
            f"dari SPSS, SmartPLS, atau R, salin tabelnya lalu tempel lewat 'Baca "
            f"output tertempel'."
        )
    return reader(path)


# --- Pembacaan output jadi ---------------------------------------------------

NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def parse_pasted_table(text: str) -> dict:
    """Baca tabel output yang ditempel pengguna (SPSS, SmartPLS, Lisrel, R).

    Untuk berkas .spv dan tangkapan layar, jalur yang dipakai adalah menempelkan
    tabel outputnya; Recens menstrukturkan angkanya lalu menyusun narasi di
    atasnya. Angka tidak diubah, hanya dibaca.
    """
    lines = [line.rstrip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return {"columns": [], "rows": []}

    def split_row(line: str) -> list[str]:
        if "\t" in line:
            return [c.strip() for c in line.split("\t")]
        if line.count("|") >= 2:
            return [c.strip() for c in line.strip("|").split("|")]
        return re.split(r"\s{2,}", line.strip())

    rows = [split_row(line) for line in lines]
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    header, body = rows[0], rows[1:]
    numeric_in_header = sum(bool(NUMBER_RE.fullmatch(c.replace(" ", ""))) for c in header)
    if numeric_in_header > width / 2:
        header = [f"kolom_{i + 1}" for i in range(width)]
        body = rows

    parsed_rows = []
    for row in body:
        parsed = []
        for cell in row:
            match = NUMBER_RE.fullmatch(cell.replace(" ", ""))
            parsed.append(float(match.group().replace(",", ".")) if match else cell)
        parsed_rows.append(parsed)

    return {"columns": header, "rows": parsed_rows}
