import * as React from "react";
import { Copy, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, Callout, DataTable, Empty, Finding } from "@/components/ui/display";
import { Field, SimpleSelect, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { flattenSections, useActions, useApp } from "@/lib/store";
import { cn, num } from "@/lib/utils";
import type { Block, Reference, Section } from "@/lib/types";
import { PageHeader, Row, cellText, titleOf, useBusy } from "@/views/shared";

interface ServiceResult {
  text: string;
  source: string;
  verdict: { adjustments: string[] } | null;
  meta: Record<string, unknown> & {
    findings?: { rule: string; severity: string; message: string; excerpt: string; suggestion: string }[];
    explanation?: string;
    reminder?: string;
    note?: string;
    hint?: string;
    unavailable?: string;
  };
}

const KIND_LABEL: Record<string, string> = {
  paragraph: "Paragraf",
  quote: "Kutipan langsung",
  list: "Daftar",
  table: "Tabel",
  figure: "Gambar",
  equation: "Persamaan",
};

export function EditorView() {
  const { manuscript, project } = useApp();
  const { run, refreshProject, toast } = useActions();
  const { withBusy, isBusy } = useBusy();

  const flat = React.useMemo(
    () => flattenSections<Section>(manuscript?.sections ?? []),
    [manuscript],
  );
  const [sectionId, setSectionId] = React.useState<number | null>(null);
  const active = flat.find((s) => s.id === sectionId) ?? flat.find((s) => !s.children.length) ?? flat[0];

  React.useEffect(() => {
    if (active && sectionId !== active.id) setSectionId(active.id);
  }, [active, sectionId]);

  const [panel, setPanel] = React.useState<React.ReactNode>(null);
  const [references, setReferences] = React.useState<Reference[]>([]);
  const [citekey, setCitekey] = React.useState("");

  React.useEffect(() => {
    void run(async () => {
      const result = await api.get<{ references: Reference[] }>(
        `/projects/${project!.id}/references`,
      );
      setReferences(result.references);
    });
  }, [project, run]);

  const addBlock = (kind: string) =>
    run(async () => {
      await api.post(`/sections/${active!.id}/blocks`, { kind, content: "" });
      await refreshProject();
    });

  return (
    <>
      <PageHeader title="Menulis di editor">
        Editor mengenali bab, sub-bab, kutipan, tabel, gambar, dan caption sebagai bagian
        terpisah — dasar bagi format otomatis dan pemeriksaan menyeluruh.
      </PageHeader>

      <div className="grid gap-3.5 lg:grid-cols-[15rem_1fr] lg:items-start">
        <Card className="lg:sticky lg:top-0">
          <CardHeader>
            <CardTitle>Kerangka</CardTitle>
          </CardHeader>
          <CardContent className="scrollbar-slim max-h-[65vh] overflow-y-auto px-2 pb-3">
            {flat.map((section) => (
              <button
                key={section.id}
                onClick={() => setSectionId(section.id)}
                style={{ paddingLeft: `${8 + (section.level - 1) * 12}px` }}
                className={cn(
                  "flex w-full items-baseline gap-2 rounded-md py-1.5 pr-2 text-left text-[12.5px] transition-colors",
                  section.id === active?.id
                    ? "bg-accent font-semibold text-accent-foreground"
                    : "text-muted-foreground hover:bg-muted",
                )}
              >
                <span className="min-w-0 flex-1 truncate">
                  {section.number} {section.title}
                </span>
                <span className="tabular shrink-0 text-[10.5px] opacity-70">
                  {num(section.word_count)}
                </span>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="flex min-w-0 flex-col gap-3.5">
          <Card>
            <CardHeader>
              <CardTitle>
                {active ? `${active.number} ${active.title}` : "Tidak ada bagian"}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Row className="mb-3">
                {["paragraph", "quote", "list"].map((kind) => (
                  <Button key={kind} size="sm" variant="outline" onClick={() => addBlock(kind)}>
                    <Plus /> {KIND_LABEL[kind]}
                  </Button>
                ))}
                <span className="pb-2 text-[11.5px] text-muted-foreground">
                  {num(active?.word_count ?? 0)} / {num(active?.target_words ?? 0)} kata target
                </span>
              </Row>

              {!active?.blocks.length ? (
                <Empty>Bagian ini masih kosong. Tambahkan paragraf untuk mulai menulis.</Empty>
              ) : (
                <div className="flex flex-col gap-2.5">
                  {active.blocks.map((block) => (
                    <BlockEditor
                      key={block.id}
                      block={block}
                      sectionId={active.id}
                      onPanel={setPanel}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Bantuan menulis</CardTitle>
            </CardHeader>
            <CardContent>
              <Row>
                <Field label="Sisipkan sitasi">
                  <SimpleSelect
                    className="w-64"
                    value={citekey}
                    onValueChange={setCitekey}
                    placeholder="— pilih dari pustaka —"
                    options={references.map((r) => ({
                      value: r.citekey,
                      label: `${r.citekey} — ${titleOf(r.csl_json).slice(0, 46)}`,
                    }))}
                  />
                </Field>
                <Button
                  variant="outline"
                  loading={isBusy("cite")}
                  onClick={() =>
                    withBusy("cite", async () => {
                      if (!citekey) return toast("Pilih referensi lebih dahulu.", "error");
                      const marker = `[[cite:${citekey}]]`;
                      await navigator.clipboard?.writeText(marker).catch(() => undefined);
                      setPanel(
                        <Callout variant="success" title="Penanda disalin">
                          <code className="rounded bg-accent px-1 py-0.5 font-mono text-[12px]">
                            {marker}
                          </code>{" "}
                          — tempelkan di posisi kutipan dalam paragraf.
                        </Callout>,
                      );
                    })
                  }
                >
                  <Copy /> Salin penanda
                </Button>
              </Row>

              <p className="mt-2.5 text-[11.5px] text-muted-foreground">
                Sitasi dalam teks memakai penanda{" "}
                <code className="rounded bg-accent px-1 font-mono text-accent-foreground">
                  [[cite:citekey]]
                </code>{" "}
                sehingga selalu sinkron dengan daftar pustaka apa pun gaya sitasinya.
              </p>
              {manuscript?.citekeys.length ? (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <span className="text-[11.5px] text-muted-foreground">Dipakai di naskah:</span>
                  {manuscript.citekeys.map((key) => (
                    <Badge key={key} variant="mono">
                      {key}
                    </Badge>
                  ))}
                </div>
              ) : null}

              {panel ? <div className="mt-3.5">{panel}</div> : null}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}

function BlockEditor({
  block,
  sectionId,
  onPanel,
}: {
  block: Block;
  sectionId: number;
  onPanel: (node: React.ReactNode) => void;
}) {
  const { project } = useApp();
  const { run, refreshProject } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [value, setValue] = React.useState(block.content);

  React.useEffect(() => setValue(block.content), [block.content]);

  const save = (content: string) =>
    run(async () => {
      await api.patch(`/blocks/${block.id}`, { content });
      await refreshProject();
    });

  if (block.kind === "table") {
    const meta = block.meta;
    return (
      <div className="rounded-md border border-border">
        <div className="flex items-center gap-2 border-b border-border bg-muted/70 px-3 py-1.5 text-[11.5px] text-muted-foreground">
          <span className="font-semibold">{KIND_LABEL.table}</span>
          <span className="min-w-0 flex-1 truncate">{meta.caption}</span>
          <Button
            size="sm"
            variant="ghost"
            aria-label="Hapus"
            onClick={() =>
              run(async () => {
                await api.del(`/blocks/${block.id}`);
                await refreshProject();
              })
            }
          >
            <Trash2 />
          </Button>
        </div>
        <div className="p-3">
          <DataTable
            columns={(meta.columns ?? []).map(cellText)}
            rows={(meta.rows ?? []).slice(0, 12).map((row) => (row as unknown[]).map(cellText))}
            note={meta.note}
          />
        </div>
      </div>
    );
  }

  const action = (key: string, path: string, body: object, handle: (r: ServiceResult) => void) =>
    withBusy(key, async () => {
      const result = await run(() => api.post<ServiceResult>(path, body));
      if (result) handle(result);
    });

  return (
    <div className="rounded-md border border-border">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-border bg-muted/70 px-3 py-1.5 text-[11.5px] text-muted-foreground">
        <span className="font-semibold">{KIND_LABEL[block.kind] ?? block.kind}</span>
        <span>{num(block.word_count)} kata</span>
        <span className="flex-1" />
        <Button
          size="sm"
          variant="ghost"
          loading={isBusy("continue")}
          onClick={() =>
            action(
              "continue",
              `/projects/${project!.id}/continue`,
              { context: value, section_id: sectionId },
              (result) => {
                if (!result.text) {
                  onPanel(
                    <Callout variant="warning">
                      {result.meta.hint ?? result.meta.unavailable ?? "Model belum tersedia."}
                    </Callout>,
                  );
                  return;
                }
                const next = `${value.trimEnd()} ${result.text}`;
                setValue(next);
                void save(next);
                if (result.verdict?.adjustments.length) {
                  onPanel(
                    <Callout variant="warning" title="Penyesuaian otomatis">
                      {result.verdict.adjustments.map((a, i) => (
                        <p key={i}>{a}</p>
                      ))}
                    </Callout>,
                  );
                }
              },
            )
          }
        >
          Lanjutkan kalimat
        </Button>
        <Button
          size="sm"
          variant="ghost"
          loading={isBusy("lang")}
          onClick={() =>
            action("lang", `/projects/${project!.id}/language`, { text: value }, (result) => {
              setValue(result.text);
              void save(result.text);
              const findings = result.meta.findings ?? [];
              onPanel(
                <div>
                  <Callout
                    variant={findings.length ? "warning" : "success"}
                    title={`${findings.length} temuan kaidah bahasa`}
                  >
                    {result.meta.note}
                  </Callout>
                  <div className="mt-2.5">
                    {findings.slice(0, 8).map((finding, index) => (
                      <Finding
                        key={index}
                        severity={finding.severity}
                        title={
                          <>
                            <span className="font-semibold">{finding.rule}</span> —{" "}
                            {finding.message}
                          </>
                        }
                        excerpt={finding.excerpt}
                        suggestion={finding.suggestion}
                      />
                    ))}
                  </div>
                </div>,
              );
            })
          }
        >
          Perbaiki bahasa
        </Button>
        <Button
          size="sm"
          variant="ghost"
          loading={isBusy("para")}
          onClick={() =>
            action("para", `/projects/${project!.id}/paraphrase`, { text: value }, (result) =>
              onPanel(
                <Callout title="Usulan parafrase">
                  <p>{result.text}</p>
                  {result.meta.explanation ? (
                    <p className="mt-2">
                      <span className="font-semibold">Alasan perubahan: </span>
                      {result.meta.explanation}
                    </p>
                  ) : null}
                  {result.meta.reminder ? (
                    <p className="mt-1.5 text-muted-foreground">{result.meta.reminder}</p>
                  ) : null}
                  <Button
                    size="sm"
                    className="mt-2.5"
                    onClick={() => {
                      setValue(result.text);
                      void save(result.text);
                      onPanel(null);
                    }}
                  >
                    Pakai usulan ini
                  </Button>
                </Callout>,
              ),
            )
          }
        >
          Parafrase
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Hapus"
          onClick={() =>
            run(async () => {
              await api.del(`/blocks/${block.id}`);
              await refreshProject();
            })
          }
        >
          <Trash2 />
        </Button>
      </div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => value !== block.content && save(value)}
        className="min-h-24 rounded-none rounded-b-md border-0 text-[13.5px] leading-[1.75] focus-visible:ring-inset"
      />
    </div>
  );
}
