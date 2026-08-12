import * as React from "react";
import { FolderOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, Callout, Empty, StatLine } from "@/components/ui/display";
import { Field, Input, SimpleSelect } from "@/components/ui/form";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { cn, num } from "@/lib/utils";
import type { Project } from "@/lib/types";
import { PageHeader, Row, useBusy } from "@/views/shared";

export function ProjectView() {
  const { catalog, project, projects } = useApp();
  const { run, setView, openProject, reloadProjects, toast } = useActions();
  const { withBusy, isBusy } = useBusy();

  const [name, setName] = React.useState("");
  const [workType, setWorkType] = React.useState(catalog!.work_types[0].key);
  const [researchType, setResearchType] = React.useState(catalog!.research_types[0].key);
  const [field, setField] = React.useState("");
  const [deadline, setDeadline] = React.useState("");
  const [focus, setFocus] = React.useState("lengkap");

  const selected = catalog!.work_types.find((w) => w.key === workType)!;
  const presets = catalog!.focus_presets ?? [];

  const create = () =>
    withBusy("create", async () => {
      if (!name.trim()) {
        toast("Judul karya belum diisi.", "error");
        return;
      }
      const created = await run(() =>
        api.post<Project>("/projects", {
          name: name.trim(),
          work_type: workType,
          research_type: researchType,
          field_of_study: field || null,
          deadline: deadline || null,
          focus,
        }),
      );
      if (!created) return;
      await reloadProjects();
      await openProject(created.id);
      setName("");
      toast("Proyek dibuat lengkap dengan kerangka bawaannya.");
      // Mendarat di langkah yang memang dituju orangnya. Melempar semua orang
      // ke "Muat aturan" hanya benar bagi yang mengerjakan naskah utuh; bagi
      // yang datang untuk BAB IV, itu satu layar yang harus dilewati dulu
      // sebelum sampai ke pekerjaannya.
      const preset = presets.find((p) => p.key === focus);
      const first = preset?.steps[0];
      setView(!first || first === "buat_proyek" ? "muat_aturan" : first);
    });

  return (
    <>
      <PageHeader title="Buat proyek">
        Pilihan jenis karya menentukan struktur bawaan, batas panjang, dan langkah mana yang
        dipakai.
      </PageHeader>

      <Card className="mb-3.5">
        <CardHeader>
          <CardTitle>Proyek baru</CardTitle>
        </CardHeader>
        <CardContent>
          <Row>
            <Field label="Judul karya" className="min-w-56 flex-1">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Pengaruh … terhadap …"
                onKeyDown={(e) => e.key === "Enter" && create()}
              />
            </Field>
            <Field label="Jenis karya">
              <SimpleSelect
                className="w-56"
                value={workType}
                onValueChange={setWorkType}
                options={catalog!.work_types.map((w) => ({ value: w.key, label: w.label }))}
              />
            </Field>
            <Field label="Jenis penelitian">
              <SimpleSelect
                className="w-52"
                value={researchType}
                onValueChange={setResearchType}
                options={catalog!.research_types.map((r) => ({ value: r.key, label: r.label }))}
              />
            </Field>
            <Field label="Bidang ilmu">
              <Input
                className="w-36"
                value={field}
                onChange={(e) => setField(e.target.value)}
                placeholder="Manajemen"
              />
            </Field>
            <Field label="Target sidang">
              <Input
                className="w-40"
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </Field>
            <Button onClick={create} loading={isBusy("create")}>
              Buat proyek
            </Button>
          </Row>

          {/* Pertanyaan yang menentukan bentuk seluruh ruang kerja, jadi ia
              ditanyakan di sini dan bukan disembunyikan di pengaturan. Tidak
              ada pilihan yang mengunci apa pun — yang berubah hanya langkah
              mana yang berdiri di depan. */}
          {presets.length ? (
            <div className="mt-5">
              <p className="text-[12.5px] font-medium">Apa yang ingin Anda kerjakan?</p>
              <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                Menentukan langkah mana yang ditonjolkan. Seluruh langkah lain tetap
                terbuka dan bisa dipakai kapan saja.
              </p>
              <div className="mt-2.5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {presets.map((preset) => {
                  const active = focus === preset.key;
                  return (
                    <button
                      key={preset.key}
                      type="button"
                      onClick={() => setFocus(preset.key)}
                      className={cn(
                        "rounded-lg border p-3 text-left transition-colors",
                        active
                          ? "border-lagoon/50 bg-lagoon/8"
                          : "border-border hover:border-border-strong hover:bg-muted/50",
                      )}
                    >
                      <span
                        className={cn(
                          "block text-[12.5px] font-medium",
                          active && "text-foreground",
                        )}
                      >
                        {preset.label}
                      </span>
                      <span className="mt-1 block text-[11px] leading-snug text-muted-foreground">
                        {preset.summary}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}

          <Callout className="mt-3.5" title={selected.label}>
            <p>{selected.ciri_khas}</p>
            <p className="mt-1.5 text-muted-foreground">
              Struktur bawaan: {selected.structure.join(" · ")}
            </p>
            <p className="mt-1 text-muted-foreground">
              Target {num(selected.default_target_words)} kata
              {selected.hard_word_limit
                ? ` · batas keras ${num(selected.hard_word_limit)} kata`
                : ""}{" "}
              · gaya sitasi {selected.citation_style.toUpperCase()} · ekspor{" "}
              {selected.export_formats.join(", ")}
            </p>
          </Callout>
        </CardContent>
      </Card>

      {project ? <ActiveProject project={project} /> : null}

      <Card>
        <CardHeader>
          <CardTitle>Proyek tersimpan</CardTitle>
        </CardHeader>
        <CardContent>
          {projects.length === 0 ? (
            <Empty>Belum ada proyek.</Empty>
          ) : (
            <div className="flex flex-col gap-2">
              {projects.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium">{item.name}</p>
                    <p className="text-[11.5px] text-muted-foreground">
                      {item.work_type_label} · {num(item.word_count)} dari{" "}
                      {num(item.target_words)} kata
                    </p>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => openProject(item.id)}>
                    <FolderOpen /> Buka
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function ActiveProject({ project }: { project: Project }) {
  const detail = project.work_type_detail;
  const rows: [string, React.ReactNode][] = [
    ["Jenis karya", `${project.work_type_label} — ${detail.ciri_khas}`],
    [
      "Jenis penelitian",
      <>
        {project.research_type_label}
        <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
          {project.research_needs}
        </span>
      </>,
    ],
    ["Sumber aturan", project.treatment.sumber_aturan],
    ["Struktur", project.treatment.struktur],
    ["Batas panjang", project.treatment.batas_panjang],
    ["Gaya sitasi", project.treatment.gaya_sitasi],
    ["Siklus revisi", project.treatment.siklus_revisi],
    ["Keluaran", project.treatment.keluaran],
    [
      "Fitur paling berperan",
      <div className="flex flex-wrap gap-1">
        {detail.fitur_utama.map((f) => (
          <Badge key={f}>{f}</Badge>
        ))}
      </div>,
    ],
  ];

  return (
    <Card className="mb-3.5">
      <CardHeader>
        <CardTitle>Proyek aktif</CardTitle>
      </CardHeader>
      <CardContent>
        <StatLine
          items={[
            { label: "kata tertulis", value: num(project.word_count) },
            { label: "target", value: num(project.target_words) },
            {
              label: `referensi · ${project.counts.references_verified} terverifikasi`,
              value: project.counts.references,
            },
            { label: "analisis", value: project.counts.analyses },
            {
              label: "revisi terbuka",
              value: project.counts.revisions_open,
              tone: project.counts.revisions_open ? "warning" : "default",
            },
          ]}
        />

        <dl className="mt-5 divide-y divide-border border-t border-border text-[13px]">
          {rows.map(([label, value]) => (
            <div key={label} className="grid gap-1 py-2 sm:grid-cols-[11rem_1fr] sm:gap-4">
              <dt className="text-[11.5px] font-semibold text-muted-foreground sm:text-[13px]">
                {label}
              </dt>
              <dd className="min-w-0">{value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
