"""Pembaca keluaran perangkat statistik lain: SPSS, R, SmartPLS, Lisrel.

Ini pintu masuk bagi mahasiswa yang datanya sudah diolah di tempat lain. Yang
mereka bawa bukan data mentah melainkan hasil jadi — tabel *Model Summary*,
blok *Coefficients*, matriks *outer loading* — dalam bentuk yang tidak bisa
disalin begitu saja ke naskah: angkanya sudah benar, tetapi terpisah dari
maknanya, dan yang ditanya penguji justru maknanya.

Modul ini hanya **membaca**. Tidak ada satu pun angka yang dihitung ulang di
sini. Tugasnya tiga: memotong tempelan menjadi blok-blok tabel, mengenali
pemisah desimal yang dipakai perangkat asalnya, dan mengubah selnya menjadi
bilangan tanpa mengubah nilainya. Penafsirannya dikerjakan ``translate``.

Bentuk angka yang harus ditangani lebih beragam daripada yang terlihat:

* ``.659`` — SPSS membuang nol di depan. Inilah bentuk paling lazim pada
  keluaran SPSS, dan pembaca yang mensyaratkan digit di depan titik akan
  membaca *seluruh* nilai R Square, korelasi, dan signifikansi sebagai teks.
* ``,874`` — SPSS berlokal Indonesia memakai koma, dan sebagian besar kampus
  memasangnya begitu.
* ``.812a`` — penanda catatan kaki menempel pada angkanya.
* ``0.523***`` — kode signifikansi R menempel pada koefisiennya.
* ``1.53e-06`` dan ``< 2.2e-16`` — notasi ilmiah R.
* ``<,001`` — pelaporan p pada SPSS versi baru.
* ``.`` sendirian — sel kosong pada SPSS.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .engine import Table

# --- Pembacaan angka ---------------------------------------------------------

#: Tanda minus yang bukan hyphen-minus ASCII. Salinan dari Word dan dari panel
#: keluaran SmartPLS kerap membawa en-dash sebagai tanda negatif.
_MINUS = {"−": "-", "–": "-", "—": "-", "­": ""}

#: Kode signifikansi R dan tanda bintang SPSS pada matriks korelasi.
_JEJAK_BINTANG = re.compile(r"[*†‡·]+\s*$")

#: Penanda catatan kaki SPSS: satu huruf, kadang beberapa dipisah koma —
#: ``.200c,d`` pada tabel Kolmogorov-Smirnov. Hanya dilucuti bila menempel
#: langsung pada digit, sehingga kata seperti "Beta" tidak ikut terpotong.
_PENANDA_KAKI = re.compile(r"(?<=[\d.,])\s*[a-h](?:\s*,\s*[a-h])*\s*$")

_ILMIAH = re.compile(r"^[-+]?\d*[.,]?\d+\s*[eE]\s*[-+]?\d+$")

#: Judul dan nama kolom baku SPSS. Dipakai untuk melucuti huruf catatan kaki
#: yang menempel pada teks — "ANOVAa", "Coefficientsa", "Kolmogorov-Smirnova" —
#: yang tidak bisa dikenali aturan umum tanpa ikut memotong kata seperti "Beta".
_LABEL_BAKU = (
    "Model Summary", "ANOVA", "Coefficients", "Correlations", "Residuals Statistics",
    "Kolmogorov-Smirnov", "Shapiro-Wilk", "Tests of Normality", "Collinearity Diagnostics",
    "Descriptive Statistics", "Group Statistics", "Independent Samples Test",
    "Paired Samples Test", "Paired Samples Statistics", "Paired Samples Correlations",
    "Item-Total Statistics", "Reliability Statistics", "Test Statistics",
)


def strip_footnote_letter(text: str) -> str:
    """Buang huruf catatan kaki yang menempel pada judul atau nama kolom."""
    bersih = (text or "").strip()
    for label in _LABEL_BAKU:
        if (
            len(bersih) == len(label) + 1
            and bersih[-1].isalpha()
            and bersih[-1].islower()
            and bersih[:-1].lower() == label.lower()
        ):
            return bersih[:-1]
    return bersih

#: Bukti pemisah desimal yang tidak bisa dibaca sebagai pemisah ribuan:
#: tidak ada bagian bulat sama sekali, atau bagian pecahannya bukan tiga digit.
_BUKTI_KOMA = re.compile(r"^[-+]?(?:\d*,\d{1,2}|\d*,\d{4,}|,\d+)$")
_BUKTI_TITIK = re.compile(r"^[-+]?(?:\d*\.\d{1,2}|\d*\.\d{4,}|\.\d+)$")

#: Sel yang berarti "tidak ada nilai" pada keluaran SPSS dan SmartPLS.
KOSONG = {"", ".", ",", "-", "--", "—", "–", "n/a", "na", "nan", "null"}


def _bersihkan(text: Any) -> tuple[str, bool]:
    """Lucuti hiasan dari satu sel, kembalikan isinya dan apakah bertanda '<'."""
    raw = str(text if text is not None else "").strip()
    for asing, ganti in _MINUS.items():
        raw = raw.replace(asing, ganti)
    raw = _JEJAK_BINTANG.sub("", raw).strip()
    kurang = raw.startswith("<")
    if kurang:
        raw = raw[1:].strip()
    raw = raw.rstrip("%").strip()
    if not _ILMIAH.match(raw):
        raw = _PENANDA_KAKI.sub("", raw).strip()
    return raw, kurang


def decimal_hint(cells: list[str]) -> str:
    """Tentukan pemisah desimal yang dipakai tempelan, dari buktinya sendiri.

    Menebak salah di sini berakibat fatal dan senyap: ``2,145`` yang dibaca
    sebagai pemisah ribuan menjadi 2145, dan mahasiswa menulis koefisien yang
    keliru seribu kali lipat di naskahnya. Karena itu yang dihitung hanya bukti
    yang tidak bisa dibaca dua cara — angka tanpa bagian bulat, atau yang
    pecahannya bukan tiga digit.
    """
    koma = titik = 0
    for cell in cells:
        raw, _ = _bersihkan(cell)
        if _ILMIAH.match(raw):
            continue
        if _BUKTI_KOMA.match(raw):
            koma += 1
        elif _BUKTI_TITIK.match(raw):
            titik += 1
    if koma and koma > titik:
        return ","
    return "."


def parse_number(text: Any, decimal: str = ".") -> float | None:
    """Baca satu sel menjadi bilangan, atau ``None`` bila ia bukan bilangan."""
    if isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return float(text)

    raw, _ = _bersihkan(text)
    if raw.lower() in KOSONG:
        return None

    if _ILMIAH.match(raw):
        raw = raw.replace(" ", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None

    # Sebuah nilai yang dibuka koma tidak mungkin memakai koma sebagai pemisah
    # ribuan, berapa pun tebakan untuk sisa tempelannya.
    if re.fullmatch(r"[-+]?,\d+", raw):
        return float(raw.replace(",", "."))
    if re.fullmatch(r"[-+]?\.\d+", raw):
        return float(raw)

    if decimal == ",":
        candidate = raw.replace(".", "").replace(" ", "").replace(",", ".")
    else:
        candidate = raw.replace(",", "").replace(" ", "")

    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", candidate):
        return None
    try:
        return float(candidate)
    except ValueError:
        return None


def is_upper_bound(text: Any) -> bool:
    """Benar bila sel ditulis sebagai batas atas, mis. ``<,001``."""
    _, kurang = _bersihkan(text)
    return kurang


# --- Pemotongan tempelan menjadi blok ---------------------------------------

#: Baris keterangan di bawah tabel SPSS dan kode signifikansi R. Disimpan, tidak
#: dibuang: "a. Dependent Variable: Y" adalah satu-satunya tempat nama variabel
#: terikat muncul pada keluaran regresi, dan narasinya butuh nama itu.
_CATATAN = re.compile(
    r"^\s*(?:[a-h]\.\s|\*+\.\s|---\s*$|Signif\.\s*codes|Note[:.]|Catatan[:.]|"
    r"Dependent Variable|Predictors\s*[:(]|Weighted Least Squares|"
    r"Lilliefors|This is a lower bound|Test distribution|Listwise|"
    r"Correlation is significant|\*\*?\s*Correlation)",
    re.IGNORECASE,
)

_JUDUL_DIKENAL = re.compile(
    r"^\s*(?:Model Summary|ANOVA|Coefficients?|Correlations?|Reliability Statistics|"
    r"Item[- ]Total Statistics|Item Statistics|Scale Statistics|Case Processing Summary|"
    r"Tests? of Normality|One[- ]Sample Kolmogorov|Descriptive Statistics|Descriptives|"
    r"Statistics|Group Statistics|Independent Samples Test|Paired Samples|"
    r"Test Statistics|Ranks|Frequencies|Crosstab|Multiple Comparisons|"
    r"Outer Loadings?|Outer Weights?|Path Coefficients?|Construct Reliability|"
    r"R Square|f Square|Fornell|Heterotrait|Discriminant Validity|"
    r"Collinearity Statistics|Total Effects|Specific Indirect Effects|"
    r"Latent Variable|Cross Loadings)",
    re.IGNORECASE,
)


def _split_cells(line: str) -> list[str]:
    """Potong satu baris menjadi sel.

    Tiga bentuk tempelan yang benar-benar muncul: bertab (salin dari pivot table
    SPSS dan dari Excel), berpipa (salin dari Markdown atau dari R
    ``knitr::kable``), dan berspasi ganda (salin dari panel teks). Urutannya
    penting — ``Pr(>|t|)`` di keluaran R memuat pipa tetapi bukan pemisah kolom,
    karena itu pipa hanya diakui bila diapit spasi atau membuka baris.
    """
    if "\t" in line:
        return [c.strip() for c in line.split("\t")]
    stripped = line.strip()
    if stripped.startswith("|") and stripped.count("|") >= 2:
        return [c.strip() for c in stripped.strip("|").split("|")]
    if len(re.findall(r"\s\|\s", line)) >= 2:
        return [c.strip() for c in re.split(r"\s\|\s", stripped)]
    return [c.strip() for c in re.split(r"\s{2,}", stripped)]


def _is_title(cells: list[str]) -> bool:
    isi = [c for c in cells if c]
    return len(isi) == 1 and not re.fullmatch(r"[-+]?[\d.,]+", isi[0])


@dataclass
class Block:
    """Satu tabel keluaran yang sudah dipisahkan dari tetangganya."""

    title: str
    columns: list[str]
    #: Sel yang sudah menjadi bilangan bila memang bilangan, selebihnya teks.
    rows: list[list[Any]]
    #: Sel apa adanya — dibutuhkan untuk mengenali penulisan ``<,001``.
    raw: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    decimal: str = "."

    @property
    def headers(self) -> list[str]:
        return self.columns

    def column_at(self, index: int) -> list[Any]:
        return [row[index] if index < len(row) else None for row in self.rows]

    def to_table(self, title: str | None = None, note: str = "") -> Table:
        return Table(
            title=title or self.title or "Tabel keluaran",
            columns=list(self.columns),
            rows=[list(row) for row in self.rows],
            note=note or "  ".join(self.notes),
        )


def _pad(rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        return rows
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def _merge_headers(header_rows: list[list[str]]) -> list[str]:
    """Gabungkan judul kolom yang tersebar di beberapa baris.

    Tabel *Coefficients* SPSS menulis "Unstandardized Coefficients" sekali di
    baris atas untuk dua kolom di bawahnya, lalu "B" dan "Std. Error" di baris
    berikutnya. Baris atas disebarkan ke kanan mengisi selnya yang kosong;
    baris terakhir dibiarkan apa adanya, sebab menyebarkannya justru akan
    menempelkan "Beta" pada kolom t dan Sig.
    """
    if not header_rows:
        return []
    if len(header_rows) == 1:
        return list(header_rows[0])

    disebar = []
    for row in header_rows[:-1]:
        terisi, terakhir = [], ""
        for cell in row:
            terakhir = cell or terakhir
            terisi.append(terakhir)
        disebar.append(terisi)
    disebar.append(header_rows[-1])

    merged = []
    for index in range(len(header_rows[0])):
        bagian: list[str] = []
        for row in disebar:
            cell = row[index] if index < len(row) else ""
            if cell and (not bagian or bagian[-1] != cell):
                bagian.append(cell)
        merged.append(" ".join(bagian).strip())

    # Judul yang sama persis dengan tetangga kirinya adalah sisa penyebaran,
    # bukan nama kolom. SPSS sendiri menampilkannya kosong.
    for index in range(len(merged) - 1, 0, -1):
        if merged[index] and merged[index] == merged[index - 1]:
            merged[index] = ""
    return merged


def _assemble(title: str, lines: list[list[str]], notes: list[str], decimal: str) -> Block | None:
    lines = _pad([line for line in lines if any(c for c in line)])
    if not lines:
        return None

    width = max(len(line) for line in lines)

    def numeric_count(row: list[str]) -> int:
        return sum(1 for cell in row if parse_number(cell, decimal) is not None)

    # Baris judul kolom adalah baris pembuka yang tidak memuat satu pun angka.
    header_rows: list[list[str]] = []
    for line in lines:
        if numeric_count(line) == 0 and any(c for c in line):
            header_rows.append(line)
        else:
            break
    body = lines[len(header_rows) :]

    if not body:
        # Seluruh tempelan tidak beangka: perlakukan baris pertama sebagai judul
        # kolom dan sisanya sebagai isi, daripada mengembalikan tabel kosong.
        header_rows, body = lines[:1], lines[1:]
        if not body:
            header_rows, body = [], lines

    columns = _merge_headers(header_rows)

    # Matriks tanpa sel sudut: baris judulnya satu kolom lebih pendek karena
    # kolom nama indikator tidak diberi nama. Bentuk ini dipakai SmartPLS pada
    # outer loading, Fornell-Larcker, dan HTMT.
    if columns and len(columns) == width - 1 and body:
        columns = [""] + columns
    while len(columns) < width:
        columns.append("")
    columns = columns[:width]
    # Kolom tanpa nama dibiarkan tanpa nama. SPSS sendiri menampilkannya
    # kosong — kolom yang memuat nama variabel pada tabel Coefficients memang
    # tidak berjudul — dan nama pengganti seperti "Kolom 2" ikut tercetak di
    # tabel BAB IV mahasiswa, tempat ia tidak punya arti apa pun.
    columns = [strip_footnote_letter(c) for c in columns]

    rows: list[list[Any]] = []
    for line in body:
        parsed: list[Any] = []
        for cell in line:
            number = parse_number(cell, decimal)
            parsed.append(number if number is not None else cell)
        rows.append(parsed)

    return Block(
        title=strip_footnote_letter(title),
        columns=columns,
        rows=rows,
        raw=body,
        notes=notes,
        decimal=decimal,
    )


def split_blocks(text: str) -> list[Block]:
    """Potong satu tempelan menjadi tabel-tabel yang berdiri sendiri.

    Mahasiswa jarang menempel satu tabel. Yang disalin biasanya seluruh
    keluaran regresi sekaligus — Model Summary, ANOVA, dan Coefficients — dan
    ketiganya harus terbaca terpisah agar masing-masing bisa dinarasikan pada
    subbab yang tepat.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    semua_sel = [cell for line in lines for cell in _split_cells(line)]
    decimal = decimal_hint(semua_sel)

    blocks: list[Block] = []
    judul, kumpulan, catatan = "", [], []
    jeda = False

    def tutup() -> None:
        nonlocal judul, kumpulan, catatan
        if kumpulan:
            block = _assemble(judul, kumpulan, catatan, decimal)
            if block is not None:
                blocks.append(block)
        judul, kumpulan, catatan = "", [], []

    for line in lines:
        if not line.strip():
            jeda = True
            continue

        if _CATATAN.match(line.strip()):
            catatan.append(line.strip())
            continue

        cells = _split_cells(line)

        if _is_title(cells):
            isi = next(c for c in cells if c)
            # Sebuah baris tunggal hanya dianggap judul tabel baru bila ia
            # memang berbentuk judul; kalau bukan, ia baris isi bertepi.
            if _JUDUL_DIKENAL.match(isi) or (jeda and len(isi) <= 80) or not kumpulan:
                tutup()
                judul = isi
                jeda = False
                continue

        if jeda and kumpulan:
            lebar_baru = len([c for c in cells if c])
            lebar_lama = len([c for c in kumpulan[-1] if c])
            if lebar_baru != lebar_lama:
                tutup()
        jeda = False
        kumpulan.append(cells)

    tutup()
    return blocks


# --- Keluaran konsol R -------------------------------------------------------

_R_PENANDA = re.compile(
    r"^\s*(?:Call:|Coefficients:|lm\(formula|glm\(formula|Signif\.\s*codes|"
    r"Multiple R-squared|Residual standard error|F-statistic:|"
    r"data:\s|alternative hypothesis|sample estimates)",
    re.MULTILINE,
)


def looks_like_r(text: str) -> bool:
    """Benar bila tempelan berasal dari konsol R, bukan dari tabel."""
    return bool(_R_PENANDA.search(text or ""))


def _angka_r(token: str) -> float | None:
    return parse_number(token, ".")


def read_r_lm(text: str) -> dict | None:
    """Bongkar ``summary(lm(...))`` menjadi bagian-bagiannya.

    Keluaran konsol R tidak bertab dan kolomnya dirapikan dengan spasi tunggal,
    sehingga pemotong tabel biasa merusaknya. Bentuknya tetap, jadi yang dipakai
    di sini adalah pembacaan per bagian: rumus model, blok koefisien, lalu tiga
    baris ringkasan di bawahnya.
    """
    if not text or "Coefficients" not in text:
        return None

    hasil: dict[str, Any] = {"coefficients": []}

    rumus = re.search(r"formula\s*=\s*([^,\n]+?)\s*(?:,\s*data\s*=|\))", text)
    if rumus:
        hasil["formula"] = rumus.group(1).strip()
        sisi = hasil["formula"].split("~")
        if len(sisi) == 2:
            hasil["dependent"] = sisi[0].strip()

    lines = text.replace("\r\n", "\n").split("\n")
    mulai = None
    for index, line in enumerate(lines):
        if re.match(r"^\s*Coefficients:", line):
            mulai = index + 1
            break
    if mulai is None:
        return None

    # Baris judul kolom blok koefisien diloncati bila ada; sebagian keluaran
    # (mis. ``coef(summary(model))``) tidak menyertakannya.
    if mulai < len(lines) and "Estimate" in lines[mulai]:
        mulai += 1

    for line in lines[mulai:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("---") or stripped.startswith("Signif"):
            break
        tokens = stripped.split()
        angka_pertama = next(
            (i for i, tok in enumerate(tokens) if i > 0 and _angka_r(tok) is not None), None
        )
        if angka_pertama is None:
            break
        term = " ".join(tokens[:angka_pertama])
        nilai = [_angka_r(tok) for tok in tokens[angka_pertama:]]
        nilai = [v for v in nilai if v is not None]
        if len(nilai) < 2:
            continue
        # R menuliskan p sebagai "< 2e-16" — dua token, dan yang bermakna
        # angkanya. Batas atas ini dilaporkan apa adanya oleh penerjemah.
        p_kurang = bool(re.search(r"<\s*2?[.,]?\d*e?-?\d*\s*(?:\*|$)", stripped[-14:]))
        hasil["coefficients"].append(
            {
                "term": term,
                "estimate": nilai[0],
                "std_error": nilai[1] if len(nilai) > 1 else None,
                "t": nilai[2] if len(nilai) > 2 else None,
                "p_value": nilai[3] if len(nilai) > 3 else None,
                "p_upper_bound": p_kurang,
            }
        )

    if not hasil["coefficients"]:
        return None

    sisa = re.search(
        r"Residual standard error:\s*([\d.eE+-]+)\s*on\s*(\d+)\s*degrees of freedom", text
    )
    if sisa:
        hasil["sigma"] = _angka_r(sisa.group(1))
        hasil["df_residual"] = int(sisa.group(2))

    r2 = re.search(r"Multiple R-squared:\s*([\d.eE+-]+)", text)
    if r2:
        hasil["r_squared"] = _angka_r(r2.group(1))
    adj = re.search(r"Adjusted R-squared:\s*([\d.eE+-]+)", text)
    if adj:
        hasil["adj_r_squared"] = _angka_r(adj.group(1))

    fstat = re.search(
        r"F-statistic:\s*([\d.eE+-]+)\s*on\s*(\d+)\s*and\s*(\d+)\s*DF,\s*"
        r"p-value:\s*(<?\s*[\d.eE+-]+)",
        text,
    )
    if fstat:
        hasil["f_statistic"] = _angka_r(fstat.group(1))
        hasil["df_model"] = int(fstat.group(2))
        hasil["df_residual"] = int(fstat.group(3))
        hasil["f_p_value"] = _angka_r(fstat.group(4).lstrip("< ").strip())
        hasil["f_p_upper_bound"] = fstat.group(4).strip().startswith("<")

    return hasil


#: Uji ringkas R yang keluarannya satu baris statistik di bawah nama ujinya.
_R_UJI = [
    (
        "t",
        re.compile(
            r"\bt\s*=\s*(?P<t>[-\d.eE+]+),\s*df\s*=\s*(?P<df>[-\d.eE+]+),\s*"
            r"p-value\s*(?P<kurang><)?\s*=?\s*(?P<p>[-\d.eE+]+)"
        ),
    ),
    (
        "shapiro",
        re.compile(r"\bW\s*=\s*(?P<w>[\d.eE+-]+),\s*p-value\s*(?P<kurang><)?\s*=?\s*(?P<p>[\d.eE+-]+)"),
    ),
    (
        "ks",
        re.compile(r"\bD\s*=\s*(?P<d>[\d.eE+-]+),\s*p-value\s*(?P<kurang><)?\s*=?\s*(?P<p>[\d.eE+-]+)"),
    ),
    (
        "chisq",
        re.compile(
            r"(?:Kruskal-Wallis\s+)?chi-squared\s*=\s*(?P<chi>[\d.eE+-]+),\s*df\s*=\s*(?P<df>\d+),"
            r"\s*p-value\s*(?P<kurang><)?\s*=?\s*(?P<p>[\d.eE+-]+)"
        ),
    ),
    (
        "wilcox",
        re.compile(r"\b[VW]\s*=\s*(?P<stat>[\d.eE+-]+),\s*p-value\s*(?P<kurang><)?\s*=?\s*(?P<p>[\d.eE+-]+)"),
    ),
]


def read_r_tests(text: str) -> list[dict]:
    """Baca uji ringkas R: t.test, shapiro.test, cor.test, kruskal.test, wilcox.test."""
    if not text:
        return []
    lines = text.replace("\r\n", "\n").split("\n")
    hasil: list[dict] = []

    for index, line in enumerate(lines):
        for jenis, pola in _R_UJI:
            match = pola.search(line)
            if not match:
                continue
            # Nama uji ditulis R sebagai baris berindentasi di atas blok, dan
            # nama itulah yang menentukan bagaimana angkanya dibaca.
            nama = ""
            for sebelum in reversed(lines[max(0, index - 6) : index]):
                bersih = sebelum.strip()
                if bersih and not bersih.startswith("data:") and "=" not in bersih:
                    nama = bersih
                    break
            data = ""
            for sekitar in lines[max(0, index - 4) : index + 4]:
                if sekitar.strip().startswith("data:"):
                    data = sekitar.split(":", 1)[1].strip()
                    break
            estimasi = _estimasi_r(lines, index)
            hasil.append(
                {
                    "jenis": jenis,
                    "nama": nama,
                    "data": data,
                    "stats": {
                        key: parse_number(value, ".")
                        for key, value in match.groupdict().items()
                        if key != "kurang" and value is not None
                    },
                    "p_upper_bound": bool(match.groupdict().get("kurang")),
                    "estimasi": estimasi,
                }
            )
            break
    return hasil


def _estimasi_r(lines: list[str], index: int) -> dict[str, float]:
    """Ambil blok ``sample estimates:`` yang mengikuti sebuah uji R."""
    for offset in range(index, min(index + 10, len(lines))):
        if lines[offset].strip().startswith("sample estimates"):
            nama = lines[offset + 1].split() if offset + 1 < len(lines) else []
            nilai = lines[offset + 2].split() if offset + 2 < len(lines) else []
            angka = [parse_number(v, ".") for v in nilai]
            if len(nama) == len(angka) and all(v is not None for v in angka):
                return {n: float(v) for n, v in zip(nama, angka)}
            # ``cor`` dan ``mean of x`` tercetak dengan nama berspasi; ambil
            # angkanya saja bila pasangannya tidak seimbang.
            bersih = [float(v) for v in angka if v is not None]
            if bersih:
                return {f"estimasi_{i + 1}": v for i, v in enumerate(bersih)}
    return {}
