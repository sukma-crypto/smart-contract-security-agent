"""Langkah 6: olah data penelitian.

Seluruh angka dihitung mesin statistik di sini. Model bahasa hanya dipanggil
untuk menyusun kalimat penjelas, dan hasilnya diverifikasi ulang terhadap angka
yang sudah dihitung.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from .. import db
from ..core.llm import services
from ..core.stats import engine, methodology, narrative, qualitative, readers
from .deps import (
    charge_for,
    current_account,
    get_conn,
    get_project,
    owned_analysis,
    owned_section,
    upload_path,
)

router = APIRouter(tags=["analisis"])

#: Uji yang tersedia beserta parameter yang diminta.
#: Nama parameter ditulis dalam bahasa Inggris di mesin statistik, tetapi yang
#: memakainya adalah mahasiswa yang sedang mengerjakan Bab 4. "predictors" dan
#: "dependent" di layar tidak menolong siapa pun; yang dikenal di ruang sidang
#: adalah "variabel bebas" dan "variabel terikat".
PARAM_LABELS = {
    "columns": "Variabel yang dianalisis",
    "column": "Variabel",
    "row": "Variabel baris",
    "items": "Butir kuesioner",
    "predictors": "Variabel bebas (X)",
    "dependent": "Variabel terikat (Y)",
    "value": "Variabel yang diukur",
    "group": "Variabel pengelompok",
    "before": "Skor sebelum (pretest)",
    "after": "Skor sesudah (posttest)",
    "second": "Pengukuran kedua",
    "pretest": "Skor pretest",
    "posttest": "Skor posttest",
    "ideal_score": "Skor maksimum instrumen",
    "ratings": "Penilaian para ahli",
    "loadings": "Outer loading per konstruk",
    "paths": "Koefisien jalur antar-konstruk",
}

#: Parameter berupa angka, bukan nama kolom. Antarmuka perlu tahu bedanya agar
#: tidak menyodorkan daftar kolom untuk isian yang seharusnya diketik.
NUMBER_PARAMS = {"ideal_score"}

#: Parameter yang boleh dikosongkan.
OPTIONAL_PARAMS = {"ideal_score"}

PARAM_HINTS = {
    "ideal_score": (
        "Skor tertinggi yang mungkin dicapai instrumen — 100 untuk tes berskala "
        "seratus, 5 untuk angket Likert lima titik. Bila dikosongkan, nilainya "
        "diterka dari skala data dan hasilnya diberi peringatan."
    ),
    "items": "Butir pembentuk satu variabel, misalnya X1.1 sampai X1.5.",
    "predictors": "Boleh lebih dari satu; pisahkan dengan koma.",
}

METHODS = {
    "descriptive": {"label": "Statistik deskriptif", "params": ["columns"]},
    "frequency": {"label": "Distribusi frekuensi", "params": ["column"]},
    "crosstab": {"label": "Tabulasi silang", "params": ["row", "column"]},
    "categorize": {"label": "Kategorisasi jawaban", "params": ["columns"]},
    "validity": {"label": "Uji validitas", "params": ["items"]},
    "reliability": {"label": "Uji reliabilitas", "params": ["items"]},
    "normality": {"label": "Uji normalitas", "params": ["columns"]},
    "multicollinearity": {"label": "Uji multikolinearitas", "params": ["predictors"]},
    "heteroscedasticity": {
        "label": "Uji heteroskedastisitas", "params": ["dependent", "predictors"]
    },
    "correlation": {"label": "Analisis korelasi", "params": ["columns"]},
    "regression": {"label": "Analisis regresi", "params": ["dependent", "predictors"]},
    "ttest_independent": {"label": "Uji t sampel bebas", "params": ["value", "group"]},
    "ttest_paired": {"label": "Uji t berpasangan", "params": ["before", "after"]},
    "anova_oneway": {"label": "ANOVA satu jalur", "params": ["value", "group"]},
    "mann_whitney": {"label": "Uji Mann-Whitney U", "params": ["value", "group"]},
    "wilcoxon": {"label": "Uji Wilcoxon", "params": ["value", "second"]},
    "kruskal": {"label": "Uji Kruskal-Wallis", "params": ["value", "group"]},
    "ngain": {"label": "Uji N-Gain", "params": ["pretest", "posttest", "ideal_score"]},
    "aiken_v": {"label": "Validasi ahli (Aiken's V)", "params": ["ratings"]},
    "pls_measurement": {"label": "Model pengukuran PLS", "params": ["loadings"]},
    "pls_structural": {"label": "Model struktural PLS", "params": ["paths"]},
}


class RunAnalysis(BaseModel):
    method: str
    dataset_id: int | None = None
    params: dict = Field(default_factory=dict)
    narrate: bool = True


class MethodologyRequest(BaseModel):
    purpose: str
    dependent_scale: str = "interval"
    n_independent: int = 1
    n_groups: int = 2
    paired: bool = False
    normal: bool | None = None
    sample_size: int | None = None
    latent_variables: bool = False


class SampleSizeRequest(BaseModel):
    population: int | None = None
    margin_of_error: float = 0.05
    n_predictors: int | None = None


class InsertRequest(BaseModel):
    #: Boleh dikosongkan — Recens mencarikan bagian hasilnya sendiri.
    section_id: int | None = None
    include_narrative: bool = True


class PastedOutput(BaseModel):
    text: str
    label: str = "Output tertempel"


class CodeSuggestRequest(BaseModel):
    dataset_id: int
    top_k: int = 20


class ApplyCodeRequest(BaseModel):
    dataset_id: int
    codes: list[str]


class ThemeRequest(BaseModel):
    theme_map: dict[str, str]


# --- Dataset -----------------------------------------------------------------


@router.get("/analysis/methods")
def list_methods() -> dict:
    return {
        "methods": [
            {
                "key": key,
                **spec,
                "param_labels": {p: PARAM_LABELS.get(p, p) for p in spec["params"]},
                "param_hints": {p: PARAM_HINTS[p] for p in spec["params"] if p in PARAM_HINTS},
                "number_params": [p for p in spec["params"] if p in NUMBER_PARAMS],
                "optional_params": [p for p in spec["params"] if p in OPTIONAL_PARAMS],
            }
            for key, spec in METHODS.items()
        ],
        "boundary": (
            "Recens mengolah dan menjelaskan data yang benar-benar diunggah pengguna. "
            "Sistem tidak mengarang data, tidak memanipulasi hasil agar hipotesis "
            "diterima, dan selalu menampilkan langkah serta angka aslinya. Hasil yang "
            "tidak signifikan tetap dilaporkan apa adanya."
        ),
        "accepted_files": sorted(readers.READERS),
    }


@router.post("/projects/{project_id}/datasets", status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    kind: str = Form(""),
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Unggah data penelitian: SPSS, Excel, CSV, atau transkrip wawancara."""
    project_id = project["id"]
    filename = file.filename or "data.csv"
    destination = upload_path(project_id, filename, "data")
    destination.write_bytes(await file.read())

    try:
        loaded = readers.load(destination)
    except (readers.UnsupportedDataFile, ValueError) as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, str(exc)) from exc

    detected = kind or readers.detect_kind(destination)
    dataset_id = db.insert(
        conn,
        "datasets",
        project_id=project_id,
        filename=filename,
        path=str(destination),
        kind=detected,
        meta_json=json.dumps(
            {
                "columns": [str(c) for c in loaded.frame.columns],
                "n_rows": int(loaded.frame.shape[0]),
                "notes": loaded.notes,
            },
            ensure_ascii=False,
        ),
        created_at=db.now(),
    )
    return {"id": dataset_id, "kind": detected, **loaded.preview()}


@router.get("/projects/{project_id}/datasets")
def list_datasets(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> list[dict]:
    rows = db.fetch_all(
        conn, "SELECT * FROM datasets WHERE project_id = ? ORDER BY id DESC", (project["id"],)
    )
    return db.rows_to_dicts(rows, ("meta_json",))


@router.get("/datasets/{dataset_id}/preview")
def preview_dataset(
    dataset_id: int,
    rows: int = 10,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    row = db.fetch_one(
        conn,
        "SELECT d.* FROM datasets d JOIN projects p ON p.id = d.project_id "
        "WHERE d.id = ? AND p.account_id = ?",
        (dataset_id, account["id"]),
    )
    if row is None:
        raise HTTPException(404, f"Data {dataset_id} tidak ditemukan.")
    dataset = _existing_file(dict(row))
    loaded = readers.load(dataset["path"])
    return loaded.preview(rows)


def _get_dataset(conn: sqlite3.Connection, project_id: int, dataset_id: int) -> dict:
    """Data hanya bisa diambil dari dalam proyeknya sendiri.

    Menerima ``dataset_id`` apa adanya berarti satu proyek bisa menjalankan uji
    statistik atas data penelitian proyek lain — dan hasilnya ikut terbaca.
    """
    row = db.fetch_one(
        conn,
        "SELECT * FROM datasets WHERE id = ? AND project_id = ?",
        (dataset_id, project_id),
    )
    if row is None:
        raise HTTPException(404, f"Data {dataset_id} tidak ditemukan di proyek ini.")
    return _existing_file(dict(row))


def _existing_file(dataset: dict) -> dict:
    if not Path(dataset["path"]).exists():
        raise HTTPException(410, f"Berkas data '{dataset['filename']}' sudah tidak ada di disk.")
    return dataset


# --- Menjalankan analisis ----------------------------------------------------


@router.post("/projects/{project_id}/analyses", status_code=201)
def run_analysis(
    payload: RunAnalysis,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Jalankan satu uji dan simpan jejaknya agar dapat ditelusuri ulang."""
    project_id = project["id"]
    if payload.method not in METHODS:
        raise HTTPException(
            400, f"Uji '{payload.method}' tidak dikenal. Pilihan: {', '.join(METHODS)}."
        )

    try:
        result = _dispatch(conn, project_id, payload)
    except engine.AnalysisError as exc:
        raise HTTPException(400, str(exc)) from exc
    except (KeyError, TypeError) as exc:
        raise HTTPException(400, f"Parameter uji tidak lengkap atau keliru: {exc}") from exc

    narrative_text = narrative.draft_narrative(result)
    narrative_source = "deterministik"
    verdict = None
    if payload.narrate:
        service_result = services.narrative_for_analysis(
            result, context=project.get("field_of_study") or ""
        )
        narrative_text = service_result.text
        narrative_source = service_result.source
        verdict = service_result.verdict.to_dict() if service_result.verdict else None
        if service_result.source == "model":
            charge_for(conn, project, "narasi_hasil")

    analysis_id = db.insert(
        conn,
        "analyses",
        project_id=project_id,
        dataset_id=payload.dataset_id,
        method=payload.method,
        params_json=json.dumps(payload.params, ensure_ascii=False),
        result_json=json.dumps(result.to_dict(), ensure_ascii=False),
        narrative=narrative_text,
        engine="python",
        created_at=db.now(),
    )
    return {
        "id": analysis_id,
        "result": result.to_dict(),
        "narrative": narrative_text,
        "narrative_source": narrative_source,
        "guardrail": verdict,
    }


def _dispatch(
    conn: sqlite3.Connection, project_id: int, payload: RunAnalysis
) -> engine.AnalysisResult:
    # Isian pilihan yang dibiarkan kosong dikirim antarmuka sebagai string
    # kosong atau null. Diteruskan apa adanya, keduanya akan menabrak
    # perhitungan; yang dimaksud pengguna adalah "tidak diisi".
    params = {
        key: value
        for key, value in payload.params.items()
        if not (key in OPTIONAL_PARAMS and value in (None, ""))
    }
    method = payload.method

    # Uji yang bekerja atas nilai yang ditempel, bukan berkas data.
    if method == "aiken_v":
        return engine.aiken_v(**params)
    if method == "pls_measurement":
        return engine.pls_measurement_model(**params)
    if method == "pls_structural":
        return engine.pls_structural_model(**params)

    if payload.dataset_id is None:
        raise HTTPException(400, f"Uji '{method}' memerlukan dataset_id.")
    dataset = _get_dataset(conn, project_id, payload.dataset_id)
    frame = readers.load(dataset["path"]).frame

    dispatch = {
        "descriptive": engine.descriptive,
        "frequency": engine.frequency,
        "crosstab": engine.crosstab,
        "categorize": engine.categorize,
        "validity": engine.validity_test,
        "reliability": engine.reliability_test,
        "normality": engine.normality,
        "multicollinearity": engine.multicollinearity,
        "heteroscedasticity": engine.heteroscedasticity,
        "correlation": engine.correlation,
        "regression": engine.regression,
        "ttest_independent": engine.ttest_independent,
        "ttest_paired": engine.ttest_paired,
        "anova_oneway": engine.anova_oneway,
        "ngain": engine.ngain,
    }
    if method in ("mann_whitney", "wilcoxon", "kruskal"):
        return engine.nonparametric(frame, test=method, **params)
    return dispatch[method](frame, **params)


@router.get("/projects/{project_id}/analyses")
def list_analyses(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> list[dict]:
    """Jejak analisis: data, langkah, parameter, dan hasil setiap uji."""
    rows = db.fetch_all(
        conn, "SELECT * FROM analyses WHERE project_id = ? ORDER BY id DESC", (project["id"],)
    )
    return db.rows_to_dicts(rows, ("params_json", "result_json"))


@router.post("/analyses/{analysis_id}/insert")
def insert_analysis(
    analysis_id: int,
    payload: InsertRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    account: dict = Depends(current_account),
) -> dict:
    """Sisipkan tabel dan narasi hasil ke bagian naskah.

    Dua ID datang dari luar sekaligus, dan keduanya harus ditelusuri: analisis
    ke pemiliknya, bagian ke pemiliknya, lalu keduanya dipastikan berada di
    proyek yang sama. Tanpa langkah ketiga, hasil uji proyek sendiri masih bisa
    disisipkan ke naskah proyek orang lain.
    """
    row = owned_analysis(conn, account["id"], analysis_id)
    if payload.section_id is None:
        section_id = _results_section(conn, row["project_id"])
    else:
        section = owned_section(conn, account["id"], payload.section_id)
        if section["project_id"] != row["project_id"]:
            raise HTTPException(
                400,
                "Bagian tujuan berada di proyek lain. Sisipkan ke bagian dalam proyek yang sama.",
            )
        section_id = payload.section_id

    data = json.loads(row["result_json"])
    result = engine.AnalysisResult(
        method=data["method"],
        label=data["label"],
        params=data.get("params", {}),
        tables=[engine.Table(**t) for t in data.get("tables", [])],
        values=data.get("values", {}),
        findings=data.get("findings", []),
        assumptions=data.get("assumptions", []),
        warnings=data.get("warnings", []),
    )
    blocks = narrative.result_to_blocks(result, include_narrative=False)
    if payload.include_narrative and row["narrative"]:
        blocks.append(
            {
                "kind": "paragraph",
                "content": row["narrative"],
                "meta": {"source": "analisis", "analysis_id": analysis_id},
            }
        )

    start = db.fetch_one(
        conn,
        "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM blocks WHERE section_id = ?",
        (section_id,),
    )["p"]
    created = []
    for offset, block in enumerate(blocks):
        created.append(
            db.insert(
                conn,
                "blocks",
                section_id=section_id,
                position=start + offset,
                kind=block["kind"],
                content=block["content"],
                meta_json=json.dumps(block.get("meta", {}), ensure_ascii=False),
                updated_at=db.now(),
            )
        )
    return {"inserted": len(created), "block_ids": created, "section_id": section_id}


def _results_section(conn: sqlite3.Connection, project_id: int) -> int:
    """Bagian tempat hasil analisis semestinya mendarat.

    Tanpa ini antarmuka menebak dengan mengambil bagian terdaun pertama, dan
    bagian terdaun pertama sebuah skripsi adalah Latar Belakang. Tabel regresi
    yang tersisip di latar belakang bukan sekadar salah tempat — mahasiswa yang
    fokusnya memang hanya BAB IV akan menyimpulkan fiturnya rusak.
    """
    row = db.fetch_one(
        conn,
        "SELECT id FROM sections WHERE project_id = ? AND role = 'hasil' "
        "ORDER BY position LIMIT 1",
        (project_id,),
    )
    if row is not None:
        return int(row["id"])

    row = db.fetch_one(
        conn,
        "SELECT id FROM sections WHERE project_id = ? AND LOWER(title) LIKE 'hasil%' "
        "ORDER BY position LIMIT 1",
        (project_id,),
    )
    if row is not None:
        return int(row["id"])

    # Proyek yang kerangkanya sudah dirombak sendiri bisa saja tidak punya
    # bagian hasil sama sekali. Dibuatkan, daripada menolak menyisipkan.
    position = db.fetch_one(
        conn,
        "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM sections "
        "WHERE project_id = ? AND parent_id IS NULL",
        (project_id,),
    )["p"]
    return db.insert(
        conn,
        "sections",
        project_id=project_id,
        parent_id=None,
        position=position,
        title="Hasil Penelitian",
        role="hasil",
        target_words=0,
        status="draf",
        created_at=db.now(),
    )


@router.post("/projects/{project_id}/analyses/pasted", status_code=201)
def parse_pasted(
    payload: PastedOutput,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Baca tabel output yang ditempel dari SPSS, SmartPLS, Lisrel, atau R.

    Untuk berkas .spv dan tangkapan layar, jalur inilah yang dipakai: angkanya
    distrukturkan lalu dinarasikan, tanpa diubah.
    """
    table = readers.parse_pasted_table(payload.text)
    if not table["rows"]:
        raise HTTPException(400, "Tidak ada baris tabel yang bisa dibaca dari teks tersebut.")
    return {
        "label": payload.label,
        "table": table,
        "note": (
            "Angka dibaca apa adanya dari output yang Anda tempel. Recens tidak "
            "menghitung ulang maupun mengubahnya."
        ),
    }


# --- Pemandu metodologi ------------------------------------------------------


@router.post("/methodology/recommend")
def recommend_method(payload: MethodologyRequest) -> dict:
    try:
        recommendation = methodology.recommend(**payload.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return recommendation.to_dict()


@router.get("/methodology/options")
def methodology_options() -> dict:
    return {
        "purposes": [
            {"key": p.value, "label": methodology.PURPOSE_LABELS[p]} for p in methodology.Purpose
        ],
        "scales": [s.value for s in methodology.Scale],
        "sampling": methodology.SAMPLING_TECHNIQUES,
    }


@router.post("/methodology/sample-size")
def sample_size(payload: SampleSizeRequest) -> dict:
    result = {}
    if payload.population:
        try:
            result["slovin"] = methodology.slovin(payload.population, payload.margin_of_error)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    if payload.n_predictors:
        result["regression"] = methodology.sample_size_for_regression(payload.n_predictors)
    if not result:
        raise HTTPException(400, "Isi 'population' atau 'n_predictors'.")
    return result


# --- Analisis kualitatif -----------------------------------------------------


@router.post("/projects/{project_id}/qualitative/suggest")
def suggest_codes(
    payload: CodeSuggestRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Usulkan kode awal dari pola yang benar-benar berulang di transkrip."""
    dataset = _get_dataset(conn, project["id"], payload.dataset_id)
    frame = readers.load(dataset["path"]).frame
    try:
        candidates = qualitative.suggest_codes(frame, top_k=payload.top_k)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "candidates": candidates,
        "n_utterances": int(frame.shape[0]),
        "note": (
            "Yang diusulkan adalah pola yang muncul berulang di transkrip Anda. "
            "Peneliti tetap memutuskan kode mana yang bermakna."
        ),
    }


@router.post("/projects/{project_id}/qualitative/apply")
def apply_codes(
    payload: ApplyCodeRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Tandai giliran bicara yang memuat tiap kode, lalu verifikasi kutipannya."""
    project_id = project["id"]
    dataset = _get_dataset(conn, project_id, payload.dataset_id)
    loaded = readers.load(dataset["path"])
    transcript = "\n".join(str(v) for v in loaded.frame.get("ucapan", []))

    segments = []
    for code in payload.codes:
        segments.extend(qualitative.apply_code(loaded.frame, code))

    verified, rejected = qualitative.verify_segments(segments, transcript)
    saved = qualitative.save_segments(conn, project_id, payload.dataset_id, verified)
    return {
        "saved": saved,
        "rejected": len(rejected),
        "segments": [s.to_dict() for s in verified],
        "note": (
            "Setiap kutipan diverifikasi ada di transkrip. Kutipan yang tidak ditemukan "
            "tidak disimpan."
        ),
    }


@router.post("/projects/{project_id}/qualitative/themes")
def build_themes(
    payload: ThemeRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    project: dict = Depends(get_project),
) -> dict:
    """Susun tema dari kode, lengkap dengan matriks triangulasi sumber."""
    segments = qualitative.load_segments(conn, project["id"])
    if not segments:
        raise HTTPException(400, "Belum ada segmen berkode. Jalankan pengodean lebih dahulu.")
    themes = qualitative.build_themes(segments, payload.theme_map)
    return {
        **themes,
        "triangulation": qualitative.triangulation_matrix(segments),
        "reduction": qualitative.reduce_data(segments),
    }


@router.get("/projects/{project_id}/qualitative/segments")
def list_segments(
    conn: sqlite3.Connection = Depends(get_conn), project: dict = Depends(get_project)
) -> dict:
    segments = qualitative.load_segments(conn, project["id"])
    return {"count": len(segments), "segments": [s.to_dict() for s in segments]}
