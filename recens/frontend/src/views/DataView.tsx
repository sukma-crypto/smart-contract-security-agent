import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Badge,
  Callout,
  DataTable,
  Empty,
  Metric,
  MetricRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/display";
import { Field, FileInput, Input, SimpleSelect, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { flattenSections, useActions, useApp } from "@/lib/store";
import type { AnalysisResponse, Dataset, Section } from "@/lib/types";
import { PageHeader, Row, cellText, useBusy } from "@/views/shared";

const LIST_PARAMS = ["columns", "items", "predictors"];
const JSON_PARAMS = ["ratings", "loadings", "paths"];

interface MethodInfo {
  key: string;
  label: string;
  params: string[];
}

interface MethodsResponse {
  methods: MethodInfo[];
  boundary: string;
  accepted_files: string[];
}

export function DataView() {
  const { project } = useApp();
  const { run } = useActions();
  const [methods, setMethods] = React.useState<MethodsResponse | null>(null);
  const [datasets, setDatasets] = React.useState<Dataset[]>([]);
  const [analyses, setAnalyses] = React.useState<{ id: number; method: string; narrative: string; created_at: string; result_json: { label: string }; params_json: unknown }[]>([]);

  const load = React.useCallback(async () => {
    await run(async () => {
      const [m, d, a] = await Promise.all([
        api.get<MethodsResponse>("/analysis/methods"),
        api.get<Dataset[]>(`/projects/${project!.id}/datasets`),
        api.get<typeof analyses>(`/projects/${project!.id}/analyses`),
      ]);
      setMethods(m);
      setDatasets(d);
      setAnalyses(a);
    });
  }, [project, run]);

  React.useEffect(() => {
    void load();
  }, [load]);

  if (!methods) return null;

  return (
    <>
      <PageHeader title="Olah data penelitian">{methods.boundary}</PageHeader>

      <Tabs defaultValue="uji">
        <TabsList className="mb-3.5">
          <TabsTrigger value="uji">Menjalankan uji</TabsTrigger>
          <TabsTrigger value="pemandu">Pemandu metodologi</TabsTrigger>
          <TabsTrigger value="kualitatif">Analisis kualitatif</TabsTrigger>
          <TabsTrigger value="jejak">Jejak analisis ({analyses.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="uji" className="flex flex-col gap-3.5">
          <UploadPanel accepted={methods.accepted_files} datasets={datasets} reload={load} />
          <RunPanel methods={methods.methods} datasets={datasets} reload={load} />
        </TabsContent>
        <TabsContent value="pemandu" className="flex flex-col gap-3.5">
          <MethodologyPanel />
        </TabsContent>
        <TabsContent value="kualitatif">
          <QualitativePanel datasets={datasets} />
        </TabsContent>
        <TabsContent value="jejak">
          <TrailPanel analyses={analyses} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function UploadPanel({
  accepted,
  datasets,
  reload,
}: {
  accepted: string[];
  datasets: Dataset[];
  reload: () => Promise<void>;
}) {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const fileRef = React.useRef<HTMLInputElement>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Unggah data</CardTitle>
        <CardDescription>
          Diterima: {accepted.join(", ")} — SPSS, Excel, CSV, dan transkrip wawancara.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Row>
          <Field className="min-w-56 flex-1">
            <FileInput ref={fileRef} />
          </Field>
          <Button
            loading={isBusy("up")}
            onClick={() =>
              withBusy("up", async () => {
                const file = fileRef.current?.files?.[0];
                if (!file) return toast("Pilih berkas data lebih dahulu.", "error");
                const form = new FormData();
                form.append("file", file);
                const result = await run(() =>
                  api.upload<{ n_rows: number; n_cols: number }>(
                    `/projects/${project!.id}/datasets`,
                    form,
                  ),
                );
                if (result) {
                  toast(`${result.n_rows} baris × ${result.n_cols} kolom terbaca.`);
                  await reload();
                }
              })
            }
          >
            Unggah
          </Button>
        </Row>

        <div className="mt-3 flex flex-col gap-2">
          {datasets.length === 0 ? (
            <Empty>Belum ada data.</Empty>
          ) : (
            datasets.map((dataset) => (
              <div
                key={dataset.id}
                className="rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-medium">{dataset.filename}</span>
                  <Badge>{dataset.kind}</Badge>
                </div>
                <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                  {dataset.meta_json.n_rows} baris · {dataset.meta_json.columns.length} kolom
                </p>
                {dataset.meta_json.notes?.map((note, index) => (
                  <p key={index} className="text-[11.5px] text-muted-foreground">
                    • {note}
                  </p>
                ))}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function RunPanel({
  methods,
  datasets,
  reload,
}: {
  methods: MethodInfo[];
  datasets: Dataset[];
  reload: () => Promise<void>;
}) {
  const { project } = useApp();
  const { run } = useActions();
  const { withBusy, isBusy } = useBusy();

  const [datasetId, setDatasetId] = React.useState("");
  const [method, setMethod] = React.useState("descriptive");
  const [params, setParams] = React.useState<Record<string, string>>({});
  const [result, setResult] = React.useState<AnalysisResponse | null>(null);

  React.useEffect(() => {
    if (!datasetId && datasets.length) setDatasetId(String(datasets[0].id));
  }, [datasets, datasetId]);

  const info = methods.find((m) => m.key === method)!;
  const columns = datasets.find((d) => d.id === Number(datasetId))?.meta_json.columns ?? [];

  const execute = () =>
    withBusy("run", async () => {
      const payload: Record<string, unknown> = {};
      for (const key of info.params) {
        const raw = params[key] ?? "";
        if (LIST_PARAMS.includes(key)) {
          payload[key] = raw.split(",").map((v) => v.trim()).filter(Boolean);
        } else if (JSON_PARAMS.includes(key)) {
          try {
            payload[key] = JSON.parse(raw || (key === "loadings" ? "{}" : "[]"));
          } catch {
            payload[key] = key === "loadings" ? {} : [];
          }
        } else {
          payload[key] = raw || columns[0];
        }
      }
      const response = await run(() =>
        api.post<AnalysisResponse>(`/projects/${project!.id}/analyses`, {
          method,
          dataset_id: datasetId ? Number(datasetId) : null,
          params: payload,
        }),
      );
      if (response) {
        setResult(response);
        await reload();
      }
    });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Jalankan uji</CardTitle>
      </CardHeader>
      <CardContent>
        <Row>
          <Field label="Data">
            <SimpleSelect
              className="w-52"
              value={datasetId}
              onValueChange={setDatasetId}
              options={datasets.map((d) => ({ value: String(d.id), label: d.filename }))}
            />
          </Field>
          <Field label="Uji">
            <SimpleSelect
              className="w-60"
              value={method}
              onValueChange={(value) => {
                setMethod(value);
                setParams({});
              }}
              options={methods.map((m) => ({ value: m.key, label: m.label }))}
            />
          </Field>
        </Row>

        <Row className="mt-3">
          {info.params.map((param) => {
            if (LIST_PARAMS.includes(param)) {
              return (
                <Field
                  key={param}
                  label={`${param} (pisahkan dengan koma)`}
                  className="min-w-56 flex-1"
                >
                  <Input
                    value={params[param] ?? ""}
                    onChange={(e) => setParams({ ...params, [param]: e.target.value })}
                    placeholder={columns.slice(0, 3).join(", ")}
                  />
                </Field>
              );
            }
            if (JSON_PARAMS.includes(param)) {
              return (
                <Field key={param} label={`${param} (JSON dari output perangkat)`} className="w-full">
                  <Textarea
                    value={params[param] ?? ""}
                    onChange={(e) => setParams({ ...params, [param]: e.target.value })}
                    placeholder={
                      param === "loadings"
                        ? '{"Kepuasan": {"X1": 0.82, "X2": 0.79}}'
                        : "[[4,5,4],[3,4,4]]"
                    }
                  />
                </Field>
              );
            }
            return (
              <Field key={param} label={param}>
                <SimpleSelect
                  className="w-44"
                  value={params[param] ?? columns[0] ?? ""}
                  onValueChange={(value) => setParams({ ...params, [param]: value })}
                  options={columns.map((c) => ({ value: c, label: c }))}
                />
              </Field>
            );
          })}
        </Row>

        <Button className="mt-3" onClick={execute} loading={isBusy("run")}>
          Jalankan
        </Button>

        {result ? <AnalysisOutput response={result} /> : null}
      </CardContent>
    </Card>
  );
}

export function AnalysisOutput({ response }: { response: AnalysisResponse }) {
  return (
    <div className="mt-4 flex flex-col gap-3.5">
      {response.guardrail && !response.guardrail.allowed ? (
        <Callout variant="danger" title="Narasi model ditolak">
          {response.guardrail.reason}
        </Callout>
      ) : null}

      {response.result.tables.map((table, index) => (
        <div key={index}>
          <p className="mb-1.5 text-[13px] font-semibold">{table.title}</p>
          <DataTable
            columns={table.columns}
            rows={table.rows.map((row) => row.map(cellText))}
            note={table.note}
          />
        </div>
      ))}

      {response.result.warnings.length ? (
        <Callout variant="warning" title="Catatan">
          {response.result.warnings.map((warning, index) => (
            <p key={index}>{warning}</p>
          ))}
        </Callout>
      ) : null}

      <Callout title={`Narasi hasil (${response.narrative_source})`}>
        {response.narrative}
      </Callout>
    </div>
  );
}

function MethodologyPanel() {
  const { run } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [options, setOptions] = React.useState<{
    purposes: { key: string; label: string }[];
    scales: string[];
  } | null>(null);
  const [form, setForm] = React.useState({
    purpose: "pengaruh",
    dependent_scale: "interval",
    n_independent: 1,
    n_groups: 2,
    paired: "false",
  });
  const [recommendation, setRecommendation] = React.useState<{
    design: string;
    approach: string;
    tests: string[];
    prerequisites: string[];
    instrument: string;
    sampling: string;
    reasoning: string[];
    cautions: string[];
  } | null>(null);
  const [sample, setSample] = React.useState<Record<string, { formula: string; narrative: string }> | null>(null);
  const [population, setPopulation] = React.useState("");
  const [predictors, setPredictors] = React.useState("");
  const [error, setError] = React.useState("0.05");

  React.useEffect(() => {
    void run(async () => setOptions(await api.get("/methodology/options")));
  }, [run]);

  if (!options) return null;

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Pemandu metodologi</CardTitle>
          <CardDescription>
            Pemilihan uji mengikuti pertanyaan penelitian, skala data, jumlah kelompok, dan
            sebaran data.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Row>
            <Field label="Tujuan">
              <SimpleSelect
                className="w-72"
                value={form.purpose}
                onValueChange={(value) => setForm({ ...form, purpose: value })}
                options={options.purposes.map((p) => ({ value: p.key, label: p.label }))}
              />
            </Field>
            <Field label="Skala variabel terikat">
              <SimpleSelect
                className="w-36"
                value={form.dependent_scale}
                onValueChange={(value) => setForm({ ...form, dependent_scale: value })}
                options={options.scales.map((s) => ({ value: s, label: s }))}
              />
            </Field>
            <Field label="Variabel bebas">
              <Input
                className="w-24"
                type="number"
                value={form.n_independent}
                onChange={(e) => setForm({ ...form, n_independent: Number(e.target.value) })}
              />
            </Field>
            <Field label="Jumlah kelompok">
              <Input
                className="w-24"
                type="number"
                value={form.n_groups}
                onChange={(e) => setForm({ ...form, n_groups: Number(e.target.value) })}
              />
            </Field>
            <Field label="Berpasangan">
              <SimpleSelect
                className="w-28"
                value={form.paired}
                onValueChange={(value) => setForm({ ...form, paired: value })}
                options={[
                  { value: "false", label: "tidak" },
                  { value: "true", label: "ya" },
                ]}
              />
            </Field>
            <Button
              loading={isBusy("rec")}
              onClick={() =>
                withBusy("rec", async () => {
                  const result = await run(() =>
                    api.post<typeof recommendation>("/methodology/recommend", {
                      ...form,
                      paired: form.paired === "true",
                    }),
                  );
                  if (result) setRecommendation(result);
                })
              }
            >
              Susun rekomendasi
            </Button>
          </Row>

          {recommendation ? (
            <div className="mt-3.5">
              <Callout variant="success" title={recommendation.design}>
                Pendekatan {recommendation.approach}
              </Callout>
              <dl className="mt-3 divide-y divide-border border-t border-border text-[13px]">
                <InfoRow label="Uji yang dijalankan">
                  <div className="flex flex-wrap gap-1">
                    {recommendation.tests.map((test) => (
                      <Badge key={test}>{test}</Badge>
                    ))}
                  </div>
                </InfoRow>
                <InfoRow label="Prasyarat">
                  {recommendation.prerequisites.map((item, index) => (
                    <p key={index}>{item}</p>
                  ))}
                </InfoRow>
                <InfoRow label="Instrumen">{recommendation.instrument}</InfoRow>
                <InfoRow label="Teknik sampling">{recommendation.sampling}</InfoRow>
                <InfoRow label="Dasar pemilihan">
                  {recommendation.reasoning.map((item, index) => (
                    <p key={index}>{item}</p>
                  ))}
                </InfoRow>
                {recommendation.cautions.length ? (
                  <InfoRow label="Perhatian">
                    {recommendation.cautions.map((item, index) => (
                      <p key={index}>{item}</p>
                    ))}
                  </InfoRow>
                ) : null}
              </dl>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Ukuran sampel</CardTitle>
        </CardHeader>
        <CardContent>
          <Row>
            <Field label="Jumlah populasi">
              <Input
                className="w-32"
                type="number"
                value={population}
                onChange={(e) => setPopulation(e.target.value)}
                placeholder="250"
              />
            </Field>
            <Field label="Taraf kesalahan">
              <SimpleSelect
                className="w-28"
                value={error}
                onValueChange={setError}
                options={[
                  { value: "0.05", label: "5%" },
                  { value: "0.1", label: "10%" },
                  { value: "0.01", label: "1%" },
                ]}
              />
            </Field>
            <Field label="Variabel bebas">
              <Input
                className="w-28"
                type="number"
                value={predictors}
                onChange={(e) => setPredictors(e.target.value)}
                placeholder="3"
              />
            </Field>
            <Button
              variant="outline"
              loading={isBusy("ss")}
              onClick={() =>
                withBusy("ss", async () => {
                  const body: Record<string, number> = { margin_of_error: Number(error) };
                  if (population) body.population = Number(population);
                  if (predictors) body.n_predictors = Number(predictors);
                  const result = await run(() =>
                    api.post<typeof sample>("/methodology/sample-size", body),
                  );
                  if (result) setSample(result);
                })
              }
            >
              Hitung
            </Button>
          </Row>

          {sample
            ? Object.values(sample).map((item, index) => (
                <Callout key={index} variant="success" className="mt-2.5" title={item.formula}>
                  {item.narrative}
                </Callout>
              ))
            : null}
        </CardContent>
      </Card>
    </>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-2 sm:grid-cols-[11rem_1fr] sm:gap-4">
      <dt className="text-[11.5px] font-semibold text-muted-foreground sm:text-[13px]">{label}</dt>
      <dd className="min-w-0">{children}</dd>
    </div>
  );
}

function QualitativePanel({ datasets }: { datasets: Dataset[] }) {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const transcripts = datasets.filter((d) => d.kind === "transcript");

  const [datasetId, setDatasetId] = React.useState("");
  const [codes, setCodes] = React.useState("");
  const [candidates, setCandidates] = React.useState<
    { code: string; count: number; kind: string }[] | null
  >(null);
  const [themes, setThemes] = React.useState<{
    n_codes: number;
    n_segments: number;
    themes: unknown[];
    reduction: { n_after: number };
    triangulation: { columns: string[]; rows: unknown[][]; single_source_codes: string[]; note: string };
  } | null>(null);

  React.useEffect(() => {
    if (!datasetId && transcripts.length) setDatasetId(String(transcripts[0].id));
  }, [transcripts, datasetId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pengodean transkrip</CardTitle>
        <CardDescription>
          Setiap kutipan diverifikasi benar-benar ada di transkrip yang Anda ketik. Kutipan yang
          tidak ditemukan tidak disimpan.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Row>
          <Field label="Transkrip">
            <SimpleSelect
              className="w-56"
              value={datasetId}
              onValueChange={setDatasetId}
              placeholder="— unggah transkrip .txt —"
              options={transcripts.map((d) => ({ value: String(d.id), label: d.filename }))}
            />
          </Field>
          <Button
            loading={isBusy("sug")}
            onClick={() =>
              withBusy("sug", async () => {
                if (!datasetId) return toast("Unggah transkrip .txt lebih dahulu.", "error");
                const result = await run(() =>
                  api.post<{ candidates: typeof candidates; note: string }>(
                    `/projects/${project!.id}/qualitative/suggest`,
                    { dataset_id: Number(datasetId) },
                  ),
                );
                if (result?.candidates) {
                  setCandidates(result.candidates);
                  setCodes(result.candidates.slice(0, 6).map((c) => c.code).join(", "));
                }
              })
            }
          >
            Usulkan kode awal
          </Button>
          <Button
            variant="outline"
            loading={isBusy("themes")}
            onClick={() =>
              withBusy("themes", async () => {
                const segments = await run(() =>
                  api.get<{ count: number; segments: { code: string; theme: string }[] }>(
                    `/projects/${project!.id}/qualitative/segments`,
                  ),
                );
                if (!segments?.count) return toast("Belum ada segmen berkode.", "error");
                const map: Record<string, string> = {};
                segments.segments.forEach((s) => {
                  map[s.code] = s.theme || `Tema: ${s.code}`;
                });
                const result = await run(() =>
                  api.post<typeof themes>(`/projects/${project!.id}/qualitative/themes`, {
                    theme_map: map,
                  }),
                );
                if (result) setThemes(result);
              })
            }
          >
            Susun tema &amp; triangulasi
          </Button>
        </Row>

        {candidates ? (
          <div className="mt-3.5">
            <Row>
              <Field label="Kode yang dipakai (pisahkan dengan koma)" className="min-w-56 flex-1">
                <Input value={codes} onChange={(e) => setCodes(e.target.value)} />
              </Field>
              <Button
                loading={isBusy("apply")}
                onClick={() =>
                  withBusy("apply", async () => {
                    const result = await run(() =>
                      api.post<{ saved: number; rejected: number }>(
                        `/projects/${project!.id}/qualitative/apply`,
                        {
                          dataset_id: Number(datasetId),
                          codes: codes.split(",").map((c) => c.trim()).filter(Boolean),
                        },
                      ),
                    );
                    if (result) {
                      toast(
                        `${result.saved} segmen tersimpan, ${result.rejected} ditolak karena tidak ditemukan di transkrip.`,
                      );
                    }
                  })
                }
              >
                Terapkan pengodean
              </Button>
            </Row>
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {candidates.map((candidate) => (
                <Badge key={candidate.code}>
                  {candidate.code} · {candidate.count}×
                </Badge>
              ))}
            </div>
          </div>
        ) : null}

        {themes ? (
          <div className="mt-4">
            <MetricRow>
              <Metric value={themes.n_codes} label="kode" />
              <Metric value={themes.n_segments} label="segmen" />
              <Metric value={themes.themes.length} label="tema" />
              <Metric value={themes.reduction.n_after} label="setelah reduksi" />
            </MetricRow>
            {themes.triangulation.single_source_codes.length ? (
              <Callout
                variant="warning"
                className="mt-3"
                title="Kode yang hanya didukung satu informan"
              >
                {themes.triangulation.single_source_codes.join(", ")} — {themes.triangulation.note}
              </Callout>
            ) : null}
            <DataTable
              className="mt-3"
              columns={themes.triangulation.columns}
              rows={themes.triangulation.rows.map((row) => (row as unknown[]).map(cellText))}
            />
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TrailPanel({
  analyses,
}: {
  analyses: { id: number; method: string; narrative: string; created_at: string; result_json: { label: string }; params_json: unknown }[];
}) {
  const { project, manuscript } = useApp();
  const { run, refreshProject, toast } = useActions();
  const leaves = flattenSections<Section>(manuscript?.sections ?? []).filter(
    (s) => !s.children.length,
  );
  const [targets, setTargets] = React.useState<Record<number, string>>({});

  return (
    <Card>
      <CardHeader>
        <CardTitle>Jejak analisis</CardTitle>
        <CardDescription>
          Data, langkah, parameter, dan hasil setiap analisis tersimpan agar dapat ditelusuri
          ulang saat ditanya penguji.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-2.5">
        {analyses.length === 0 ? (
          <Empty>Belum ada analisis.</Empty>
        ) : (
          analyses.map((analysis) => (
            <div
              key={analysis.id}
              className="rounded-md border border-border bg-muted/50 px-3.5 py-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[13px] font-semibold">{analysis.result_json.label}</span>
                <Badge>{analysis.method}</Badge>
                <span className="text-[11.5px] text-muted-foreground">{analysis.created_at}</span>
              </div>
              <p className="mt-1.5 text-[12.5px] leading-relaxed">
                {(analysis.narrative ?? "").slice(0, 320)}…
              </p>
              <Row className="mt-2.5">
                <SimpleSelect
                  className="w-64"
                  value={targets[analysis.id] ?? String(leaves[0]?.id ?? "")}
                  onValueChange={(value) => setTargets({ ...targets, [analysis.id]: value })}
                  options={leaves.map((s) => ({
                    value: String(s.id),
                    label: `${s.number} ${s.title}`,
                  }))}
                />
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    run(async () => {
                      const sectionId = Number(targets[analysis.id] ?? leaves[0]?.id);
                      const result = await api.post<{ inserted: number }>(
                        `/analyses/${analysis.id}/insert`,
                        { section_id: sectionId },
                      );
                      toast(`${result.inserted} blok disisipkan ke naskah.`);
                      await refreshProject();
                    })
                  }
                >
                  Sisipkan ke naskah
                </Button>
              </Row>
            </div>
          ))
        )}
        {project ? null : null}
      </CardContent>
    </Card>
  );
}
