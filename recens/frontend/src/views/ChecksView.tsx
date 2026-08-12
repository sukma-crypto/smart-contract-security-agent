import * as React from "react";

import { Button } from "@/components/ui/button";
import { Section } from "@/components/ui/card";
import { Badge, Callout, DataTable, Finding, StatLine } from "@/components/ui/display";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { cn, num } from "@/lib/utils";
import { PageHeader, useBusy } from "@/views/shared";

interface Issue {
  severity: string;
  message: string;
  detail?: string;
}

interface ChecksResponse {
  summary: {
    ready_to_submit: boolean;
    areas: { kind: string; count: number; critical: number; passed: boolean; percent?: number }[];
  };
  checks: {
    bahasa?: {
      total: number;
      word_count: number;
      sentence_count: number;
      by_severity: Record<string, number>;
      findings: {
        rule: string;
        severity: string;
        message: string;
        excerpt: string;
        suggestion: string;
        section_title: string;
      }[];
    };
    sitasi?: {
      n_references: number;
      n_citations_in_text: number;
      dangling: unknown[];
      uncited: unknown[];
      recency: { recent: number; window_years: number };
      issues: Issue[];
    };
    konsistensi?: { counts: Record<string, number>; issues: Issue[] };
    kemiripan?: {
      similarity_percent: number;
      n_matches: number;
      scope_note: string;
      matches: {
        n_words: number;
        citekey: string;
        page: number | null;
        section_title: string;
        text: string;
        guidance: string;
      }[];
    };
    batas?: {
      total_words: number;
      estimated_pages: number;
      max_words: number | null;
      max_pages: number | null;
      issues: Issue[];
      sections: {
        number: string;
        title: string;
        word_count: number;
        target_words: number;
        estimated_pages: number;
        status: string;
      }[];
    };
  };
}

export function ChecksView() {
  const { project } = useApp();
  const { run } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [data, setData] = React.useState<ChecksResponse | null>(null);

  return (
    <>
      <PageHeader
        title="Periksa naskah"
        action={
          <div className="text-right">
            <Button
              loading={isBusy("run")}
              onClick={() =>
                withBusy("run", async () => {
                  const result = await run(() =>
                    api.post<ChecksResponse>(`/projects/${project!.id}/checks`),
                  );
                  if (result) setData(result);
                })
              }
            >
              {data ? "Periksa ulang" : "Jalankan pemeriksaan"}
            </Button>
            <p className="mt-1.5 text-[11px] text-faint">Berjalan lokal, tanpa kredit.</p>
          </div>
        }
      >
        Keselarasan rumusan masalah sampai kesimpulan, kelengkapan silang sitasi, kaidah PUEBI,
        serta indikasi kemiripan — sebelum naskah masuk sistem kampus.
      </PageHeader>

      {!data ? (
        <BelumDiperiksa />
      ) : (
        <Results data={data} />
      )}
    </>
  );
}

function Results({ data }: { data: ChecksResponse }) {
  const { summary, checks } = data;

  return (
    <div>
      <Section title="Ringkasan">
          <Callout
            variant={summary.ready_to_submit ? "success" : "warning"}
            className="mb-3"
            title={
              summary.ready_to_submit
                ? "Naskah lolos seluruh pemeriksaan"
                : "Masih ada yang perlu dibereskan"
            }
          >
            {summary.areas
              .map((a) => `${a.kind}: ${a.count} temuan${a.critical ? ` (${a.critical} berat)` : ""}`)
              .join(" · ")}
          </Callout>
          <div className="flex flex-wrap gap-x-7 gap-y-3">
            {summary.areas.map((area) => (
              <div key={area.kind} className="flex items-baseline gap-2">
                <span
                  className={cn(
                    "tabular text-[17px] font-semibold leading-none",
                    area.passed ? "text-muted-foreground" : "text-warning",
                  )}
                >
                  {area.percent !== undefined ? `${area.percent}%` : area.count}
                </span>
                <span className="text-[11.5px] text-muted-foreground">{area.kind}</span>
                {area.passed ? (
                  <Badge variant="success">lolos</Badge>
                ) : (
                  <Badge variant="warning">periksa</Badge>
                )}
              </div>
            ))}
        </div>
      </Section>

      {checks.bahasa ? (
        <Section
          title={`Bahasa akademik Indonesia — ${checks.bahasa.total} temuan`}
        >
            <p className="mb-2.5 text-[11.5px] text-muted-foreground">
              {num(checks.bahasa.word_count)} kata, {num(checks.bahasa.sentence_count)} kalimat.
            </p>
            {checks.bahasa.findings.slice(0, 25).map((finding, index) => (
              <Finding
                key={index}
                severity={finding.severity}
                title={
                  <>
                    <span className="font-semibold">{finding.rule}</span> · {finding.section_title}{" "}
                    — {finding.message}
                  </>
                }
                excerpt={finding.excerpt}
                suggestion={finding.suggestion}
              />
            ))}
            {checks.bahasa.total > 25 ? (
              <p className="text-[11.5px] text-muted-foreground">
                …dan {checks.bahasa.total - 25} temuan lain.
              </p>
            ) : null}
        </Section>
      ) : null}

      {checks.sitasi ? (
        <Section title="Cek silang sitasi">
            <StatLine
              items={[
                { label: "referensi", value: checks.sitasi.n_references },
                { label: "sitasi dalam teks", value: checks.sitasi.n_citations_in_text },
                {
                  label: "menggantung",
                  value: checks.sitasi.dangling.length,
                  tone: checks.sitasi.dangling.length ? "danger" : "default",
                },
                { label: "tak dikutip", value: checks.sitasi.uncited.length },
                {
                  label: `terbit ≤ ${checks.sitasi.recency.window_years} thn`,
                  value: checks.sitasi.recency.recent,
                },
              ]}
            />
            <div className="mt-3">
              {checks.sitasi.issues.length ? (
                checks.sitasi.issues.map((issue, index) => (
                  <Finding key={index} severity={issue.severity}>
                    {issue.message}
                  </Finding>
                ))
              ) : (
                <Callout variant="success">
                  Seluruh sitasi sinkron dengan daftar pustaka.
                </Callout>
              )}
            </div>
        </Section>
      ) : null}

      {checks.konsistensi ? (
        <Section title="Cek konsistensi">
            <p className="mb-2.5 text-[11.5px] text-muted-foreground">
              Butir terbaca:{" "}
              {Object.entries(checks.konsistensi.counts)
                .map(([key, value]) => `${key} ${value}`)
                .join(" · ") || "—"}
            </p>
            {checks.konsistensi.issues.length ? (
              checks.konsistensi.issues.map((issue, index) => (
                <Finding key={index} severity={issue.severity} excerpt={issue.detail}>
                  {issue.message}
                </Finding>
              ))
            ) : (
              <Callout variant="success">
                Rumusan masalah, tujuan, dan simpulan sudah selaras.
              </Callout>
            )}
        </Section>
      ) : null}

      {checks.kemiripan ? (
        <Section
          title={`Cek kemiripan mandiri — ${checks.kemiripan.similarity_percent}%`}
        >
            <Callout className="mb-3">{checks.kemiripan.scope_note}</Callout>
            {checks.kemiripan.matches.length ? (
              checks.kemiripan.matches.slice(0, 10).map((match, index) => (
                <Finding
                  key={index}
                  severity="sedang"
                  title={
                    <span className="flex flex-wrap items-center gap-1.5">
                      <span className="font-semibold">{match.n_words} kata mirip</span> dengan
                      <Badge variant="mono">{match.citekey}</Badge>
                      {match.page ? <span>hlm. {match.page}</span> : null}
                      <span>· {match.section_title}</span>
                    </span>
                  }
                  excerpt={`${match.text.slice(0, 220)}…`}
                  suggestion={match.guidance}
                />
              ))
            ) : (
              <Callout variant="success">
                Tidak ditemukan rentang yang mirip dengan sumber di pustaka.
              </Callout>
            )}
        </Section>
      ) : null}

      {checks.batas ? (
        <Section title="Cek batas panjang">
            <StatLine
              items={[
                { label: "kata", value: num(checks.batas.total_words) },
                { label: "perkiraan halaman", value: checks.batas.estimated_pages },
                {
                  label: "batas kata",
                  value: checks.batas.max_words ? num(checks.batas.max_words) : "—",
                },
                { label: "batas halaman", value: checks.batas.max_pages ?? "—" },
              ]}
            />
            <div className="my-3">
              {checks.batas.issues.length ? (
                checks.batas.issues.map((issue, index) => (
                  <Finding key={index} severity={issue.severity}>
                    {issue.message}
                  </Finding>
                ))
              ) : (
                <Callout variant="success">Panjang naskah masih dalam batas.</Callout>
              )}
            </div>
            <DataTable
              columns={["Bagian", "Kata", "Target", "Halaman", "Status"]}
              rows={checks.batas.sections
                .filter((s) => s.word_count)
                .map((s) => [
                  `${s.number} ${s.title}`,
                  num(s.word_count),
                  num(s.target_words),
                  s.estimated_pages,
                  <Badge key="b" variant={s.status === "sesuai" ? "success" : "warning"}>
                    {s.status}
                  </Badge>,
                ])}
            />
        </Section>
      ) : null}
    </div>
  );
}


/**
 * Keadaan sebelum pemeriksaan pertama dijalankan.
 *
 * Satu baris "Belum ada pemeriksaan dijalankan" di atas layar yang kosong
 * sebenarnya menyembunyikan hal yang paling ingin diketahui orangnya: apa
 * yang akan diperiksa. Tanpa itu, tombol "Jalankan pemeriksaan" adalah ajakan
 * membeli kucing dalam karung — dan mahasiswa yang naskahnya dipertaruhkan
 * tidak menekan tombol yang tidak ia mengerti.
 *
 * Jadi ruang kosongnya diisi daftar apa yang akan dikerjakan, bukan hiasan.
 */
function BelumDiperiksa() {
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {PEMERIKSAAN.map((item) => (
          <div
            key={item.kind}
            className="sheet flex flex-col gap-2 p-4 transition-shadow hover:shadow-[0_1px_2px_hsl(30_20%_20%/0.05),0_14px_34px_-16px_hsl(30_24%_18%/0.26)]"
          >
            <span
              aria-hidden
              className={cn("h-[3px] w-8 rounded-full", item.warna)}
            />
            <p className="font-serif text-[16px] font-semibold leading-snug">{item.judul}</p>
            <p className="text-[12px] leading-relaxed text-muted-foreground">{item.isi}</p>
            <p className="mt-auto pt-1 text-[11px] leading-relaxed text-faint">
              Menangkap: {item.contoh}
            </p>
          </div>
        ))}
      </div>

      <Callout className="mt-5" title="Seluruhnya berjalan di komputer ini">
        Kelima pemeriksaan tidak memanggil model bahasa dan tidak menagih kredit. Naskah Anda
        tidak dikirim ke mana pun untuk diperiksa.
      </Callout>
    </>
  );
}

/** Kelima pemeriksaan, dijelaskan dengan contoh yang benar-benar ditangkapnya. */
const PEMERIKSAAN = [
  {
    kind: "konsistensi",
    judul: "Keselarasan bab",
    warna: "bg-lagoon",
    isi: "Rumusan masalah, tujuan, hipotesis, dan simpulan dibandingkan satu per satu.",
    contoh: "rumusan masalah nomor 3 yang tidak pernah dijawab di simpulan.",
  },
  {
    kind: "sitasi",
    judul: "Silang sitasi",
    warna: "bg-violet",
    isi: "Tiap sitasi dalam teks dicocokkan dengan daftar pustaka, dan sebaliknya.",
    contoh: "pustaka yang tercantum tetapi tidak pernah dikutip di naskah.",
  },
  {
    kind: "bahasa",
    judul: "Kaidah PUEBI",
    warna: "bg-amber",
    isi: "Ejaan, bentuk tidak baku, dan ragam percakapan yang lolos ke naskah ilmiah.",
    contoh: '"analisa", "dimana" sebagai penghubung, "produktifitas".',
  },
  {
    kind: "kemiripan",
    judul: "Indikasi kemiripan",
    warna: "bg-clay",
    isi: "Kemiripan antarbagian naskah sendiri dan terhadap kutipan yang tersimpan.",
    contoh: "paragraf yang tersalin dua kali di bab berbeda.",
  },
  {
    kind: "batas",
    judul: "Batas pedoman",
    warna: "bg-lagoon",
    isi: "Jumlah kata, panjang abstrak, dan bagian wajib menurut pedoman yang aktif.",
    contoh: "abstrak 320 kata pada pedoman yang membatasi 250.",
  },
] as const;
