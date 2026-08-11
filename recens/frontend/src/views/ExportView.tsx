import * as React from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Badge,
  Callout,
  DataTable,
  Empty,
  Finding,
  Metric,
  MetricRow,
  Pre,
} from "@/components/ui/display";
import { Field, FileInput, Input, SimpleSelect, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { flattenSections, useActions, useApp } from "@/lib/store";
import { num } from "@/lib/utils";
import type { Revision, Section } from "@/lib/types";
import { PageHeader, Row, useBusy } from "@/views/shared";

const STATUSES = ["terbuka", "dikerjakan", "selesai", "ditolak"];
const SOURCES = [
  { value: "pembimbing", label: "Pembimbing" },
  { value: "penguji", label: "Penguji" },
  { value: "reviewer", label: "Reviewer" },
  { value: "mandiri", label: "Mandiri" },
];

interface ConversionPlan {
  source_words: number;
  target_words: number;
  overall_compression: number;
  citekeys: string[];
  warnings: string[];
  sections: {
    target: string;
    target_words: number;
    source_words: number;
    sources: { number: string; title: string }[];
  }[];
  dropped: { title: string; word_count: number; reason: string }[];
}

export function ExportView() {
  const { project, manuscript } = useApp();
  const { run, refreshProject, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const detail = project!.work_type_detail;

  const [meta, setMeta] = React.useState({
    author: "",
    student_id: "",
    institution: "",
    faculty: "",
  });
  const [exportInfo, setExportInfo] = React.useState<React.ReactNode>(null);
  const [revisions, setRevisions] = React.useState<{
    revisions: Revision[];
    total: number;
  } | null>(null);

  const loadRevisions = React.useCallback(async () => {
    const result = await run(() =>
      api.get<{ revisions: Revision[]; total: number }>(`/projects/${project!.id}/revisions`),
    );
    if (result) setRevisions(result);
  }, [project, run]);

  React.useEffect(() => {
    void loadRevisions();
  }, [loadRevisions]);

  const doExport = (format: string) =>
    withBusy(format, async () => {
      const result = await run(() =>
        api.post<{
          format: string;
          size_bytes: number;
          download_url: string;
          applied_rules: Record<string, never> & {
            font: string;
            line_spacing: number;
            citation_style: string;
            front_matter_numbering: string;
            body_numbering: string;
            margins: { top_cm: number; right_cm: number; bottom_cm: number; left_cm: number };
          };
          assumed_rules: string[];
        }>(`/projects/${project!.id}/export`, { format, meta }),
      );
      if (!result) return;
      const rules = result.applied_rules;
      setExportInfo(
        <Callout
          variant="success"
          title={`${result.format.toUpperCase()} dirakit — ${num(result.size_bytes / 1024, 1)} KB`}
        >
          <p>
            Aturan yang diterapkan: {rules.font}, spasi {rules.line_spacing}, margin{" "}
            {rules.margins.top_cm}/{rules.margins.right_cm}/{rules.margins.bottom_cm}/
            {rules.margins.left_cm} cm, {rules.citation_style}, halaman awal{" "}
            {rules.front_matter_numbering} → isi {rules.body_numbering}.
          </p>
          {result.assumed_rules?.length ? (
            <p className="mt-1.5 text-muted-foreground">
              Memakai bawaan: {result.assumed_rules.join(", ")}
            </p>
          ) : null}
          <Button asChild size="sm" className="mt-2.5">
            <a href={result.download_url}>
              <Download /> Unduh berkas
            </a>
          </Button>
        </Callout>,
      );
    });

  return (
    <>
      <PageHeader title="Ekspor & kelola revisi">
        Naskah diekspor dalam keadaan sudah terformat penuh. Catatan dosen maupun reviewer
        dicatat sebagai daftar tugas berstatus.
      </PageHeader>

      <div className="flex flex-col gap-3.5">
        <Card>
          <CardHeader>
            <CardTitle>Ekspor naskah</CardTitle>
          </CardHeader>
          <CardContent>
            <Row>
              <Field label="Penulis" className="min-w-48 flex-1">
                <Input
                  value={meta.author}
                  onChange={(e) => setMeta({ ...meta, author: e.target.value })}
                  placeholder="Nama lengkap"
                />
              </Field>
              <Field label="NIM">
                <Input
                  className="w-32"
                  value={meta.student_id}
                  onChange={(e) => setMeta({ ...meta, student_id: e.target.value })}
                />
              </Field>
              <Field label="Institusi" className="min-w-48 flex-1">
                <Input
                  value={meta.institution}
                  onChange={(e) => setMeta({ ...meta, institution: e.target.value })}
                  placeholder="Universitas …"
                />
              </Field>
              <Field label="Fakultas / Program studi" className="min-w-48 flex-1">
                <Input
                  value={meta.faculty}
                  onChange={(e) => setMeta({ ...meta, faculty: e.target.value })}
                />
              </Field>
            </Row>
            <Row className="mt-3">
              {detail.export_formats.map((format) => (
                <Button
                  key={format}
                  loading={isBusy(format)}
                  onClick={() => doExport(format)}
                >
                  Ekspor {format.toUpperCase()}
                </Button>
              ))}
            </Row>
            {exportInfo ? <div className="mt-3.5">{exportInfo}</div> : null}
          </CardContent>
        </Card>

        <RevisionsCard
          revisions={revisions}
          reload={loadRevisions}
          sections={flattenSections<Section>(manuscript?.sections ?? [])}
        />

        {detail.supervision_tracking ? <SupervisionCard /> : null}
        {detail.defense_mode ? <DefenseCard /> : null}
        {detail.family !== "artikel_publikasi" ? (
          <ConversionCard onCreated={refreshProject} toast={toast} />
        ) : null}
        <JournalCard />
        <TranslationCard />
      </div>
    </>
  );
}

function RevisionsCard({
  revisions,
  reload,
  sections,
}: {
  revisions: { revisions: Revision[]; total: number } | null;
  reload: () => Promise<void>;
  sections: Section[];
}) {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [source, setSource] = React.useState("pembimbing");
  const [text, setText] = React.useState("");
  const [sectionId, setSectionId] = React.useState("");
  const [imported, setImported] = React.useState<{
    count: number;
    linked: number;
    created: number;
    notes: string[];
    comments: {
      kind: string;
      page: number | null;
      section_title: string;
      text: string;
      anchor: string;
    }[];
  } | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pelacak bimbingan — {revisions?.total ?? 0} revisi</CardTitle>
        <CardDescription>
          Coretan dosen — komentar PDF atau dokumen Word bertanda — diubah menjadi daftar revisi
          berstatus yang terhubung ke lokasinya di naskah.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Row>
          <Field label="Impor berkas bertanda (.pdf / .docx)" className="min-w-56 flex-1">
            <FileInput ref={fileRef} accept=".pdf,.docx" />
          </Field>
          <Field label="Sumber">
            <SimpleSelect
              className="w-40"
              value={source}
              onValueChange={setSource}
              options={SOURCES.slice(0, 3)}
            />
          </Field>
          <Button
            variant="outline"
            loading={isBusy("import")}
            onClick={() =>
              withBusy("import", async () => {
                const file = fileRef.current?.files?.[0];
                if (!file) return toast("Pilih berkas bertanda lebih dahulu.", "error");
                const form = new FormData();
                form.append("file", file);
                form.append("source", source);
                const result = await run(() =>
                  api.upload<typeof imported>(
                    `/projects/${project!.id}/revisions/import`,
                    form,
                  ),
                );
                if (result) {
                  setImported(result);
                  await reload();
                }
              })
            }
          >
            Impor komentar
          </Button>
        </Row>

        {imported ? (
          <div className="mt-3">
            <Callout
              variant={imported.count ? "success" : "warning"}
              title={`${imported.count} komentar terbaca — ${imported.linked} tertaut ke bagian naskah, ${imported.created} dicatat sebagai revisi`}
            >
              {imported.notes.map((note, index) => (
                <p key={index}>{note}</p>
              ))}
            </Callout>
            <div className="mt-2.5 flex flex-col gap-2">
              {imported.comments.map((comment, index) => (
                <div
                  key={index}
                  className="rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
                >
                  <div className="flex flex-wrap items-center gap-1.5">
                    <Badge>{comment.kind}</Badge>
                    {comment.page ? <Badge>hlm. {comment.page}</Badge> : null}
                    {comment.section_title ? (
                      <Badge variant="success">{comment.section_title}</Badge>
                    ) : (
                      <Badge variant="warning">tanpa lokasi</Badge>
                    )}
                  </div>
                  <p className="mt-1.5 text-[13px]">{comment.text}</p>
                  {comment.anchor ? (
                    <p className="mt-1 text-[11.5px] text-muted-foreground">
                      menyorot: “{comment.anchor.slice(0, 140)}”
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <Row className="mt-3.5">
          <Field label="Catatan pembimbing / reviewer" className="min-w-56 flex-1">
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Perbaiki rumusan masalah nomor 2 agar sejalan dengan tujuan"
            />
          </Field>
          <Field label="Sumber">
            <SimpleSelect
              className="w-36"
              value={source}
              onValueChange={setSource}
              options={SOURCES}
            />
          </Field>
          <Field label="Bagian">
            <SimpleSelect
              className="w-56"
              value={sectionId}
              onValueChange={setSectionId}
              placeholder="— tidak spesifik —"
              options={sections.map((s) => ({
                value: String(s.id),
                label: `${s.number} ${s.title}`,
              }))}
            />
          </Field>
          <Button
            loading={isBusy("add")}
            onClick={() =>
              withBusy("add", async () => {
                if (!text.trim()) return toast("Catatan masih kosong.", "error");
                await run(() =>
                  api.post(`/projects/${project!.id}/revisions`, {
                    text,
                    source,
                    section_id: sectionId ? Number(sectionId) : null,
                  }),
                );
                setText("");
                await reload();
              })
            }
          >
            Catat
          </Button>
        </Row>

        <div className="mt-3 flex flex-col gap-2">
          {!revisions?.revisions.length ? (
            <Empty>Belum ada revisi tercatat.</Empty>
          ) : (
            revisions.revisions.map((revision) => (
              <div
                key={revision.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
              >
                <div className="min-w-56 flex-1">
                  <p className="text-[13px] font-medium">{revision.text}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5">
                    <Badge>{revision.source}</Badge>
                    <span className="text-[11.5px] text-muted-foreground">
                      {revision.section_title ?? "tanpa bagian"} · {revision.created_at}
                    </span>
                  </div>
                </div>
                <SimpleSelect
                  className="w-36"
                  value={revision.status}
                  onValueChange={(value) =>
                    run(async () => {
                      await api.patch(`/revisions/${revision.id}`, { status: value });
                      await reload();
                    })
                  }
                  options={STATUSES.map((s) => ({ value: s, label: s }))}
                />
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SupervisionCard() {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [sessions, setSessions] = React.useState<
    { id: number; met_on: string; supervisor: string | null; notes: string }[]
  >([]);
  const [form, setForm] = React.useState({ met_on: "", supervisor: "", notes: "" });

  const load = React.useCallback(async () => {
    const result = await run(() => api.get<typeof sessions>(`/projects/${project!.id}/supervision`));
    if (result) setSessions(result);
  }, [project, run]);

  React.useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Riwayat bimbingan</CardTitle>
      </CardHeader>
      <CardContent>
        <Row>
          <Field label="Tanggal">
            <Input
              className="w-40"
              type="date"
              value={form.met_on}
              onChange={(e) => setForm({ ...form, met_on: e.target.value })}
            />
          </Field>
          <Field label="Pembimbing">
            <Input
              className="w-44"
              value={form.supervisor}
              onChange={(e) => setForm({ ...form, supervisor: e.target.value })}
            />
          </Field>
          <Field label="Catatan & capaian" className="min-w-56 flex-1">
            <Input
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </Field>
          <Button
            variant="outline"
            loading={isBusy("sv")}
            onClick={() =>
              withBusy("sv", async () => {
                if (!form.met_on) return toast("Tanggal bimbingan belum diisi.", "error");
                await run(() => api.post(`/projects/${project!.id}/supervision`, form));
                setForm({ met_on: "", supervisor: "", notes: "" });
                await load();
              })
            }
          >
            Catat sesi
          </Button>
        </Row>

        <div className="mt-3 flex flex-col gap-2">
          {sessions.length === 0 ? (
            <Empty>Belum ada sesi bimbingan.</Empty>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                className="rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
              >
                <p className="text-[13px] font-medium">
                  {session.met_on} {session.supervisor ? `· ${session.supervisor}` : ""}
                </p>
                <p className="text-[11.5px] text-muted-foreground">{session.notes}</p>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function DefenseCard() {
  const { project } = useApp();
  const { run } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [result, setResult] = React.useState<{
    questions: {
      pertanyaan: string;
      sasaran: string;
      kerangka_jawaban: string;
      tingkat_risiko: string;
    }[];
    weak_points: { message: string }[];
  } | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mode siap sidang</CardTitle>
        <CardDescription>
          Pertanyaan penguji disusun dari titik yang benar-benar rawan pada naskah.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          loading={isBusy("df")}
          onClick={() =>
            withBusy("df", async () => {
              const response = await run(() =>
                api.post<typeof result>(`/projects/${project!.id}/defense`),
              );
              if (response) setResult(response);
            })
          }
        >
          Susun kemungkinan pertanyaan
        </Button>

        {result ? (
          <div className="mt-3.5">
            {result.weak_points.length ? (
              <Callout
                variant="warning"
                className="mb-3"
                title={`${result.weak_points.length} titik rawan terdeteksi pada naskah`}
              >
                {result.weak_points.slice(0, 5).map((point, index) => (
                  <p key={index}>{point.message}</p>
                ))}
              </Callout>
            ) : null}
            <div className="flex flex-col gap-2">
              {result.questions.map((question, index) => (
                <div
                  key={index}
                  className="rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-medium">{question.pertanyaan}</span>
                    <Badge variant={question.tingkat_risiko === "tinggi" ? "danger" : "warning"}>
                      {question.tingkat_risiko}
                    </Badge>
                  </div>
                  <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                    Sasaran: {question.sasaran}
                  </p>
                  <p className="mt-1 text-[12.5px]">{question.kerangka_jawaban}</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ConversionCard({
  onCreated,
  toast,
}: {
  onCreated: () => Promise<void>;
  toast: (message: string) => void;
}) {
  const { project } = useApp();
  const { run, reloadProjects, openProject, setView } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [target, setTarget] = React.useState(6000);
  const [plan, setPlan] = React.useState<ConversionPlan | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Konversi naskah menjadi artikel</CardTitle>
        <CardDescription>
          Memadatkan tugas akhir menjadi artikel berstruktur IMRAD tanpa kehilangan temuan
          utamanya. Rencananya ditampilkan lebih dahulu.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Row>
          <Field label="Target kata artikel">
            <Input
              className="w-32"
              type="number"
              value={target}
              onChange={(e) => setTarget(Number(e.target.value))}
            />
          </Field>
          <Button
            variant="outline"
            loading={isBusy("plan")}
            onClick={() =>
              withBusy("plan", async () => {
                const result = await run(() =>
                  api.post<ConversionPlan>(`/projects/${project!.id}/conversion/plan`, {
                    target_words: target,
                  }),
                );
                if (result) setPlan(result);
              })
            }
          >
            Lihat rencana
          </Button>
          <Button
            loading={isBusy("apply")}
            onClick={() =>
              withBusy("apply", async () => {
                if (
                  !window.confirm(
                    "Bangun proyek artikel baru dari naskah ini? Naskah asli tidak diubah.",
                  )
                )
                  return;
                const result = await run(() =>
                  api.post<{ project_id: number; plan: ConversionPlan; note: string }>(
                    `/projects/${project!.id}/conversion/apply`,
                    { target_words: target },
                  ),
                );
                if (result) {
                  setPlan(result.plan);
                  await reloadProjects();
                  await onCreated();
                  toast("Proyek artikel dibuat. Buka lewat pemilih proyek di atas.");
                  await openProject(result.project_id);
                  setView("menulis");
                }
              })
            }
          >
            Bangun proyek artikel
          </Button>
        </Row>

        {plan ? (
          <div className="mt-3.5">
            <MetricRow>
              <Metric value={num(plan.source_words)} label="kata naskah asal" />
              <Metric value={num(plan.target_words)} label="target artikel" />
              <Metric
                value={
                  plan.overall_compression <= 1
                    ? `${Math.round(plan.overall_compression * 100)}%`
                    : "—"
                }
                label={
                  plan.overall_compression <= 1
                    ? "tersisa setelah dipadatkan"
                    : "naskah lebih pendek dari target"
                }
              />
              <Metric value={plan.citekeys.length} label="sitasi ikut" />
            </MetricRow>

            <div className="mt-3">
              {plan.warnings.map((warning, index) => (
                <Finding key={index} severity="sedang">
                  {warning}
                </Finding>
              ))}
            </div>

            <DataTable
              className="mt-2"
              columns={["Bagian artikel", "Anggaran", "Dari", "Bahan dari naskah"]}
              rows={plan.sections.map((section) => [
                <span key="t" className="font-semibold">
                  {section.target}
                </span>,
                `${num(section.target_words)} kata`,
                `${num(section.source_words)} kata`,
                section.sources.length ? (
                  <div key="s" className="flex flex-wrap gap-1">
                    {section.sources.map((source, index) => (
                      <Badge key={index}>
                        {source.number} {source.title}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <span key="s" className="text-muted-foreground">
                    belum ada bahan
                  </span>
                ),
              ])}
            />

            {plan.dropped.length ? (
              <Callout variant="warning" className="mt-3" title="Tidak dibawa ke artikel">
                {plan.dropped.map((item, index) => (
                  <p key={index}>
                    {item.title} ({item.word_count} kata) — {item.reason}
                  </p>
                ))}
              </Callout>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function JournalCard() {
  const { project } = useApp();
  const { run, refreshProject } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [profiles, setProfiles] = React.useState<{ key: string; name: string }[]>([]);
  const [profile, setProfile] = React.useState("");
  const [report, setReport] = React.useState<{
    ready: boolean;
    word_count: number;
    matched_sections: string[];
    missing_sections: string[];
    extra_sections: string[];
    issues: { severity: string; message: string }[];
    profile_detail: {
      citation_style: string;
      max_words: number | null;
      abstract_max_words: number | null;
      notes: string[];
    };
  } | null>(null);
  const [applied, setApplied] = React.useState<string | null>(null);

  React.useEffect(() => {
    void run(async () => {
      const result = await api.get<{ profiles: { key: string; name: string }[] }>("/journals");
      setProfiles(result.profiles);
      if (result.profiles.length) setProfile(result.profiles[0].key);
    });
  }, [run]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Jurnal tujuan</CardTitle>
        <CardDescription>
          Naskah tidak ditolak di meja editor hanya karena salah format.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Row>
          <Field label="Profil jurnal" className="min-w-56 flex-1">
            <SimpleSelect
              value={profile}
              onValueChange={setProfile}
              options={profiles.map((p) => ({ value: p.key, label: p.name }))}
            />
          </Field>
          <Button
            variant="outline"
            loading={isBusy("check")}
            onClick={() =>
              withBusy("check", async () => {
                const result = await run(() =>
                  api.post<typeof report>(`/projects/${project!.id}/journal/readiness`, {
                    profile,
                  }),
                );
                if (result) setReport(result);
              })
            }
          >
            Periksa kesiapan
          </Button>
          <Button
            variant="outline"
            loading={isBusy("apply")}
            onClick={() =>
              withBusy("apply", async () => {
                const result = await run(() =>
                  api.post<{ note: string }>(`/projects/${project!.id}/journal/apply`, {
                    profile,
                  }),
                );
                if (result) {
                  setApplied(result.note);
                  await refreshProject();
                }
              })
            }
          >
            Jadikan aturan naskah
          </Button>
        </Row>

        {applied ? (
          <Callout variant="success" className="mt-3" title="Aturan naskah diperbarui">
            {applied}
          </Callout>
        ) : null}

        {report ? (
          <div className="mt-3.5">
            <Callout
              variant={report.ready ? "success" : "warning"}
              title={
                report.ready
                  ? "Struktur dan batas panjang sudah sesuai"
                  : "Belum siap dikirim"
              }
            >
              {report.word_count} kata
              {report.profile_detail.max_words
                ? ` dari batas ${num(report.profile_detail.max_words)}`
                : ""}{" "}
              · gaya sitasi {report.profile_detail.citation_style.toUpperCase()}
              {report.profile_detail.abstract_max_words
                ? ` · abstrak maks. ${report.profile_detail.abstract_max_words} kata`
                : ""}
            </Callout>

            <div className="my-3 flex flex-wrap gap-1.5">
              {report.matched_sections.map((section) => (
                <Badge key={section} variant="success">
                  {section}
                </Badge>
              ))}
              {report.missing_sections.map((section) => (
                <Badge key={section} variant="danger">
                  kurang: {section}
                </Badge>
              ))}
              {report.extra_sections.map((section) => (
                <Badge key={section} variant="warning">
                  lebih: {section}
                </Badge>
              ))}
            </div>

            {report.issues.map((issue, index) => (
              <Finding key={index} severity={issue.severity}>
                {issue.message}
              </Finding>
            ))}

            {report.profile_detail.notes.length ? (
              <Callout className="mt-3">
                {report.profile_detail.notes.map((note, index) => (
                  <p key={index}>{note}</p>
                ))}
              </Callout>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TranslationCard() {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [indonesian, setIndonesian] = React.useState("");
  const [english, setEnglish] = React.useState("");
  const [output, setOutput] = React.useState<React.ReactNode>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Dua bahasa</CardTitle>
        <CardDescription>
          Penerjemahan yang menjaga konsistensi istilah teknis per bidang ilmu — menjawab
          kewajiban abstrak dwibahasa.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Field label="Teks bahasa Indonesia">
          <Textarea
            value={indonesian}
            onChange={(e) => setIndonesian(e.target.value)}
            placeholder="Penelitian ini menguji pengaruh motivasi kerja terhadap kinerja karyawan…"
          />
        </Field>

        <Row className="mt-2.5">
          <Button
            variant="outline"
            loading={isBusy("tr")}
            onClick={() =>
              withBusy("tr", async () => {
                if (!indonesian.trim()) return toast("Teks masih kosong.", "error");
                const result = await run(() =>
                  api.post<{
                    text: string;
                    source: string;
                    meta: { note?: string; glossary?: string };
                  }>(`/projects/${project!.id}/translate`, {
                    text: indonesian,
                    direction: "id-en",
                  }),
                );
                if (!result) return;
                if (result.text) {
                  setEnglish(result.text);
                  setOutput(
                    <Callout variant="success" title={`Terjemahan (${result.source})`}>
                      <p>{result.text}</p>
                      {result.meta.note ? (
                        <p className="mt-1.5 text-muted-foreground">{result.meta.note}</p>
                      ) : null}
                    </Callout>,
                  );
                } else {
                  setOutput(
                    <Callout variant="warning" title={result.meta.note}>
                      <Pre>{result.meta.glossary ?? ""}</Pre>
                    </Callout>,
                  );
                }
              })
            }
          >
            Terjemahkan ke Inggris
          </Button>
          <Button
            variant="outline"
            loading={isBusy("gl")}
            onClick={() =>
              withBusy("gl", async () => {
                const result = await run(() =>
                  api.get<{
                    count: number;
                    terms: Record<string, string>;
                    fields_available: string[];
                  }>(
                    `/glossary?field_of_study=${encodeURIComponent(project!.field_of_study ?? "")}`,
                  ),
                );
                if (!result) return;
                setOutput(
                  <div>
                    <Callout title={`${result.count} padanan istilah`}>
                      Bidang tersedia: {result.fields_available.join(", ")}
                    </Callout>
                    <div className="mt-2.5 max-h-72 overflow-y-auto">
                      <DataTable
                        columns={["Indonesia", "Inggris"]}
                        rows={Object.entries(result.terms).map(([k, v]) => [k, v])}
                      />
                    </div>
                  </div>,
                );
              })
            }
          >
            Lihat padanan istilah
          </Button>
        </Row>

        <Field label="Versi bahasa Inggris (untuk diperiksa)" className="mt-3">
          <Textarea
            value={english}
            onChange={(e) => setEnglish(e.target.value)}
            placeholder="This study examines the effect of work motivation on employee performance…"
          />
        </Field>
        <Button
          variant="outline"
          className="mt-2.5"
          loading={isBusy("chk")}
          onClick={() =>
            withBusy("chk", async () => {
              if (!indonesian.trim() || !english.trim())
                return toast("Isi kedua versi teks lebih dahulu.", "error");
              const result = await run(() =>
                api.post<{
                  passed: boolean;
                  terms_detected: number;
                  terms_consistent: number;
                  issues: { message: string }[];
                }>(`/projects/${project!.id}/terminology`, { indonesian, english }),
              );
              if (!result) return;
              setOutput(
                <div>
                  <Callout
                    variant={result.passed ? "success" : "warning"}
                    title={`${result.terms_consistent} dari ${result.terms_detected} istilah teknis konsisten`}
                  >
                    {result.passed
                      ? "Seluruh padanan sudah sesuai glosarium."
                      : "Istilah di bawah perlu disamakan agar tidak terbaca sebagai ketidakcermatan."}
                  </Callout>
                  <div className="mt-2.5">
                    {result.issues.map((issue, index) => (
                      <Finding key={index} severity="sedang">
                        {issue.message}
                      </Finding>
                    ))}
                  </div>
                </div>,
              );
            })
          }
        >
          Periksa konsistensi istilah
        </Button>

        {output ? <div className="mt-3.5">{output}</div> : null}
      </CardContent>
    </Card>
  );
}
