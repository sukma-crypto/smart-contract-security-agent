import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Badge,
  Callout,
  DataTable,
  Empty,
  Finding,
  Metric,
  MetricRow,
} from "@/components/ui/display";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { num } from "@/lib/utils";
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
      <PageHeader title="Periksa naskah">
        Keselarasan rumusan masalah sampai kesimpulan, kelengkapan silang sitasi, kaidah PUEBI,
        serta indikasi kemiripan — sebelum naskah masuk sistem kampus.
      </PageHeader>

      <Card className="mb-3.5">
        <CardContent className="flex flex-wrap items-center gap-3 pt-5">
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
            Jalankan seluruh pemeriksaan
          </Button>
          <span className="text-[11.5px] text-muted-foreground">
            Berjalan lokal, tidak menagih kredit.
          </span>
        </CardContent>
      </Card>

      {!data ? <Empty>Belum ada pemeriksaan.</Empty> : <Results data={data} />}
    </>
  );
}

function Results({ data }: { data: ChecksResponse }) {
  const { summary, checks } = data;

  return (
    <div className="flex flex-col gap-3.5">
      <Card>
        <CardHeader>
          <CardTitle>Ringkasan</CardTitle>
        </CardHeader>
        <CardContent>
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
          <MetricRow>
            {summary.areas.map((area) => (
              <Metric
                key={area.kind}
                value={area.percent !== undefined ? `${area.percent}%` : area.count}
                label={area.kind}
                hint={
                  <Badge variant={area.passed ? "success" : "warning"}>
                    {area.passed ? "lolos" : "periksa"}
                  </Badge>
                }
              />
            ))}
          </MetricRow>
        </CardContent>
      </Card>

      {checks.bahasa ? (
        <Card>
          <CardHeader>
            <CardTitle>Bahasa akademik Indonesia — {checks.bahasa.total} temuan</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      ) : null}

      {checks.sitasi ? (
        <Card>
          <CardHeader>
            <CardTitle>Cek silang sitasi</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricRow>
              <Metric value={checks.sitasi.n_references} label="referensi" />
              <Metric value={checks.sitasi.n_citations_in_text} label="sitasi dalam teks" />
              <Metric value={checks.sitasi.dangling.length} label="sitasi menggantung" />
              <Metric value={checks.sitasi.uncited.length} label="referensi tak dikutip" />
              <Metric
                value={checks.sitasi.recency.recent}
                label={`terbit ≤ ${checks.sitasi.recency.window_years} thn`}
              />
            </MetricRow>
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
          </CardContent>
        </Card>
      ) : null}

      {checks.konsistensi ? (
        <Card>
          <CardHeader>
            <CardTitle>Cek konsistensi</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      ) : null}

      {checks.kemiripan ? (
        <Card>
          <CardHeader>
            <CardTitle>
              Cek kemiripan mandiri — {checks.kemiripan.similarity_percent}%
            </CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      ) : null}

      {checks.batas ? (
        <Card>
          <CardHeader>
            <CardTitle>Cek batas panjang</CardTitle>
          </CardHeader>
          <CardContent>
            <MetricRow>
              <Metric value={num(checks.batas.total_words)} label="kata" />
              <Metric value={checks.batas.estimated_pages} label="perkiraan halaman" />
              <Metric
                value={checks.batas.max_words ? num(checks.batas.max_words) : "—"}
                label="batas kata"
              />
              <Metric value={checks.batas.max_pages ?? "—"} label="batas halaman" />
            </MetricRow>
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
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
