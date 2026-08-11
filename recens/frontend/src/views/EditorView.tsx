import * as React from "react";
import { Check, Plus, Quote, Trash2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge, Callout, DataTable, Finding } from "@/components/ui/display";
import { SimpleSelect } from "@/components/ui/form";
import { api } from "@/lib/api";
import { flattenSections, useActions, useApp } from "@/lib/store";
import { cn, num } from "@/lib/utils";
import type { Block, Reference, Section } from "@/lib/types";
import { cellText, titleOf, useBusy } from "@/views/shared";

interface ServiceResult {
  text: string;
  source: string;
  verdict: { adjustments: string[] } | null;
  meta: Record<string, unknown> & {
    findings?: {
      rule: string;
      severity: string;
      message: string;
      excerpt: string;
      suggestion: string;
    }[];
    explanation?: string;
    reminder?: string;
    note?: string;
    hint?: string;
    unavailable?: string;
  };
}

export function EditorView() {
  const { manuscript, project } = useApp();
  const { run, refreshProject, toast } = useActions();

  const flat = React.useMemo(
    () => flattenSections<Section>(manuscript?.sections ?? []),
    [manuscript],
  );
  const [sectionId, setSectionId] = React.useState<number | null>(null);
  const active =
    flat.find((s) => s.id === sectionId) ?? flat.find((s) => !s.children.length) ?? flat[0];

  React.useEffect(() => {
    if (active && sectionId !== active.id) setSectionId(active.id);
  }, [active, sectionId]);

  const [aside, setAside] = React.useState<React.ReactNode>(null);
  const [references, setReferences] = React.useState<Reference[]>([]);

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

  const progress = active?.target_words
    ? Math.min((active.word_count / active.target_words) * 100, 100)
    : 0;

  return (
    <div className="grid gap-x-10 gap-y-6 lg:grid-cols-[13.5rem_minmax(0,1fr)] xl:grid-cols-[13.5rem_minmax(0,1fr)_16rem]">
      {/* Tulang punggung kerangka */}
      <aside className="lg:sticky lg:top-0 lg:max-h-[calc(100vh-5rem)] lg:self-start">
        <p className="mb-2 text-[11px] font-semibold text-faint">Kerangka</p>
        <nav className="scrollbar-slim -ml-px max-h-[70vh] overflow-y-auto border-l border-border">
          {flat.map((section) => {
            const current = section.id === active?.id;
            const written = section.word_count > 0;
            return (
              <button
                key={section.id}
                onClick={() => setSectionId(section.id)}
                style={{ paddingLeft: `${12 + (section.level - 1) * 11}px` }}
                className={cn(
                  "-ml-px flex w-full items-baseline gap-2 border-l-2 py-1 pr-1 text-left transition-colors",
                  current
                    ? "border-primary font-semibold text-foreground"
                    : written
                      ? "border-transparent text-muted-foreground hover:border-border-strong"
                      : "border-transparent text-faint hover:border-border-strong",
                )}
              >
                <span className="min-w-0 flex-1 truncate text-[12px] leading-snug">
                  <span className="tabular mr-1.5 text-[10.5px] text-faint">{section.number}</span>
                  {section.title}
                </span>
                {written ? (
                  <span className="tabular shrink-0 text-[10px] text-faint">
                    {num(section.word_count)}
                  </span>
                ) : null}
              </button>
            );
          })}
        </nav>
      </aside>

      {/* Permukaan menulis: satu lembar kertas di atas meja.
          Naskahnya sendiri tetap tenang — tidak ada warna di antara barisnya —
          tetapi lembarnya kini benar-benar terangkat dan punya marginnya
          sendiri, sehingga terbaca sebagai halaman yang sedang digarap, bukan
          sebagai kolom teks yang menempel pada latar. */}
      <div className="min-w-0">
        <div className="sheet px-7 py-8 sm:px-10 sm:py-10">
          <header className="measure mb-7">
            <p className="tabular text-[11px] font-medium text-violet">{active?.number}</p>
            <h2 className="mt-1 font-serif text-[27px] font-semibold leading-tight">
              {active?.title ?? "Tidak ada bagian"}
            </h2>
            <div className="mt-3 flex items-center gap-3">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-border/70">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-700",
                    progress >= 85 ? "bg-success" : progress >= 40 ? "bg-amber" : "bg-clay",
                  )}
                  style={{ width: `${Math.max(progress, progress > 0 ? 3 : 0)}%` }}
                />
              </div>
              <span className="tabular shrink-0 text-[11px] text-muted-foreground">
                {num(active?.word_count ?? 0)}
                {active?.target_words ? ` / ${num(active.target_words)}` : ""} kata
              </span>
            </div>
          </header>

          <div className="measure">
          {!active?.blocks.length ? (
            <button
              onClick={() => addBlock("paragraph")}
              className="w-full rounded-md border border-dashed border-border py-10 text-center text-[12.5px] text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
            >
              Bagian ini masih kosong — klik untuk mulai menulis.
            </button>
          ) : (
            <>
              {active.blocks.map((block) => (
                <BlockEditor key={block.id} block={block} sectionId={active.id} onAside={setAside} />
              ))}
              <InsertBar onAdd={addBlock} />
            </>
          )}
          </div>
        </div>
      </div>

      {/* Rel kanan: sitasi dan hasil bantuan menulis */}
      <aside className="min-w-0 xl:sticky xl:top-0 xl:self-start">
        <p className="mb-2 text-[11px] font-semibold text-faint">Sitasi</p>
        <SimpleSelect
          className="w-full"
          value=""
          placeholder="Salin penanda…"
          onValueChange={(key) => {
            const marker = `[[cite:${key}]]`;
            void navigator.clipboard?.writeText(marker).catch(() => undefined);
            toast(`Penanda ${marker} disalin.`);
          }}
          options={references.map((r) => ({
            value: r.citekey,
            label: `${r.citekey} — ${titleOf(r.csl_json).slice(0, 40)}`,
          }))}
        />
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          Tempelkan{" "}
          <code className="rounded bg-accent px-1 font-mono text-[10.5px] text-accent-foreground">
            [[cite:kunci]]
          </code>{" "}
          di posisi kutipan. Bentuk akhirnya menyesuaikan gaya sitasi saat diekspor.
        </p>

        {manuscript?.citekeys.length ? (
          <div className="mt-3 flex flex-wrap gap-1">
            {manuscript.citekeys.map((key) => (
              <Badge key={key} variant="mono">
                {key}
              </Badge>
            ))}
          </div>
        ) : null}

        {aside ? (
          <div className="mt-6">
            <div className="mb-2 flex items-baseline justify-between">
              <p className="text-[11px] font-semibold text-faint">Hasil bantuan</p>
              <button
                onClick={() => setAside(null)}
                className="text-faint transition-colors hover:text-foreground"
                aria-label="Tutup"
              >
                <X className="size-3.5" />
              </button>
            </div>
            <div className="scrollbar-slim max-h-[60vh] overflow-y-auto pr-1">{aside}</div>
          </div>
        ) : null}
      </aside>
    </div>
  );
}

/** Sisipan blok baru yang hanya muncul saat didekati. */
function InsertBar({ onAdd }: { onAdd: (kind: string) => void }) {
  return (
    <div className="group relative py-3">
      <div className="h-px bg-transparent transition-colors group-hover:bg-border" />
      <div className="mt-2 flex gap-1 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
        <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => onAdd("paragraph")}>
          <Plus /> Paragraf
        </Button>
        <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => onAdd("quote")}>
          <Quote /> Kutipan
        </Button>
      </div>
    </div>
  );
}

function BlockEditor({
  block,
  sectionId,
  onAside,
}: {
  block: Block;
  sectionId: number;
  onAside: (node: React.ReactNode) => void;
}) {
  const { project } = useApp();
  const { run, refreshProject } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [value, setValue] = React.useState(block.content);
  const [focused, setFocused] = React.useState(false);
  const areaRef = React.useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => setValue(block.content), [block.content]);

  // Tinggi mengikuti isi, supaya naskah terbaca sebagai dokumen mengalir
  // dan bukan sebagai kotak isian bergulir sendiri.
  React.useLayoutEffect(() => {
    const node = areaRef.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${node.scrollHeight}px`;
  }, [value]);

  const save = (content: string) =>
    run(async () => {
      await api.patch(`/blocks/${block.id}`, { content });
      await refreshProject();
    });

  const remove = () =>
    run(async () => {
      await api.del(`/blocks/${block.id}`);
      await refreshProject();
    });

  if (block.kind === "table") {
    const meta = block.meta;
    return (
      <figure className="my-6">
        <figcaption className="mb-2 flex items-baseline justify-between gap-2">
          <span className="font-serif text-[13px] font-semibold">{meta.caption}</span>
          <button onClick={remove} className="text-faint hover:text-destructive" aria-label="Hapus">
            <Trash2 className="size-3.5" />
          </button>
        </figcaption>
        <DataTable
          columns={(meta.columns ?? []).map(cellText)}
          rows={(meta.rows ?? []).slice(0, 12).map((row) => (row as unknown[]).map(cellText))}
          note={meta.note}
        />
      </figure>
    );
  }

  const call = (key: string, path: string, body: object, handle: (r: ServiceResult) => void) =>
    withBusy(key, async () => {
      const result = await run(() => api.post<ServiceResult>(path, body));
      if (result) handle(result);
    });

  const isQuote = block.kind === "quote";

  return (
    <div
      className={cn(
        "group relative -ml-4 border-l-2 pl-4 transition-colors",
        focused ? "border-primary/40" : "border-transparent",
      )}
    >
      <textarea
        ref={areaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => {
          setFocused(false);
          if (value !== block.content) void save(value);
        }}
        rows={1}
        placeholder="Tulis di sini…"
        className={cn(
          "prose-manuscript w-full resize-none border-0 bg-transparent p-0 outline-none placeholder:text-faint",
          isQuote && "border-l-2 border-border py-0.5 pl-4 text-[15px] italic",
        )}
      />

      {/* Perkakas muncul hanya saat blok sedang dikerjakan. */}
      <div
        className={cn(
          "mt-1 flex flex-wrap items-center gap-0.5 transition-opacity",
          focused || isBusy("continue") || isBusy("lang") || isBusy("para")
            ? "opacity-100"
            : "opacity-0 group-hover:opacity-60",
        )}
      >
        <ToolButton
          label="Lanjutkan"
          busy={isBusy("continue")}
          onClick={() =>
            call(
              "continue",
              `/projects/${project!.id}/continue`,
              { context: value, section_id: sectionId },
              (result) => {
                if (!result.text) {
                  onAside(
                    <Callout variant="warning" title="Model belum tersedia">
                      {result.meta.hint ?? result.meta.unavailable}
                    </Callout>,
                  );
                  return;
                }
                const next = `${value.trimEnd()} ${result.text}`;
                setValue(next);
                void save(next);
                if (result.verdict?.adjustments.length) {
                  onAside(
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
        />
        <ToolButton
          label="Perbaiki bahasa"
          busy={isBusy("lang")}
          onClick={() =>
            call("lang", `/projects/${project!.id}/language`, { text: value }, (result) => {
              setValue(result.text);
              void save(result.text);
              const findings = result.meta.findings ?? [];
              onAside(
                <div>
                  <Callout
                    variant={findings.length ? "warning" : "success"}
                    title={`${findings.length} temuan kaidah bahasa`}
                  >
                    {result.meta.note}
                  </Callout>
                  <div className="mt-2">
                    {findings.slice(0, 10).map((finding, index) => (
                      <Finding
                        key={index}
                        severity={finding.severity}
                        title={finding.message}
                        suggestion={finding.suggestion}
                      />
                    ))}
                  </div>
                </div>,
              );
            })
          }
        />
        <ToolButton
          label="Parafrase"
          busy={isBusy("para")}
          onClick={() =>
            call("para", `/projects/${project!.id}/paraphrase`, { text: value }, (result) =>
              onAside(
                <div>
                  <Callout title="Usulan parafrase">
                    <p className="prose-manuscript !text-[13.5px] !leading-relaxed text-foreground">
                      {result.text}
                    </p>
                  </Callout>
                  {result.meta.explanation ? (
                    <Callout className="mt-3" title="Alasan perubahan">
                      {result.meta.explanation}
                    </Callout>
                  ) : null}
                  {result.meta.reminder ? (
                    <p className="mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
                      {result.meta.reminder}
                    </p>
                  ) : null}
                  <Button
                    size="sm"
                    className="mt-3"
                    onClick={() => {
                      setValue(result.text);
                      void save(result.text);
                      onAside(null);
                    }}
                  >
                    <Check /> Pakai usulan ini
                  </Button>
                </div>,
              ),
            )
          }
        />
        <span className="flex-1" />
        <button
          onClick={remove}
          className="rounded px-1.5 py-1 text-[11.5px] text-faint transition-colors hover:text-destructive"
          aria-label="Hapus"
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>
    </div>
  );
}

function ToolButton({
  label,
  onClick,
  busy,
}: {
  label: string;
  onClick: () => void;
  busy: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="rounded px-1.5 py-1 text-[11.5px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
    >
      {busy ? "…" : label}
    </button>
  );
}
