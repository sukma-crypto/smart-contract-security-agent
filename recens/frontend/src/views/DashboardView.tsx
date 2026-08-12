import * as React from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, DataTable, Metric, MetricRow, Progress, StatusBadge } from "@/components/ui/display";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { cn, num } from "@/lib/utils";
import type { OutlineRow } from "@/lib/types";
import { QuoteRotator } from "@/components/ui/quote";
import { PageHeader } from "@/views/shared";

interface WorkItem {
  step: string;
  key: string;
  label: string;
  count: number;
  total?: number;
  hint: string;
}

interface Dashboard {
  word_count: number;
  target_words: number;
  progress: number;
  remaining_words: number;
  days_left: number | null;
  words_per_day_needed: number | null;
  chapters: OutlineRow[];
  revisions: Record<string, number>;
  focus: string[];
  focus_label: string;
  writing_in_focus: boolean;
  tracks_word_target: boolean;
  work_done: WorkItem[];
}

export function DashboardView() {
  const { project } = useApp();
  const { run } = useActions();
  const [data, setData] = React.useState<Dashboard | null>(null);

  React.useEffect(() => {
    void run(async () => setData(await api.get(`/projects/${project!.id}/dashboard`)));
  }, [project, run]);

  if (!data) return null;

  const percent = Math.round(data.progress * 100);
  // Tenggat yang mepet adalah satu-satunya angka di halaman ini yang perlu
  // berteriak. Sisanya cukup terbaca.
  const urgent = data.days_left !== null && data.days_left <= 30;
  // Jumlah kata hanya diukur bila menulis memang termasuk yang dikerjakan dan
  // targetnya memang ada. Selain itu, cincin yang menunjuk 0% cuma mengabarkan
  // kegagalan pada pekerjaan yang tidak pernah diambil orangnya.
  const measureWords = data.tracks_word_target && data.target_words > 0;
  const showChapters = data.tracks_word_target && data.chapters.length > 0;

  return (
    <>
      <PageHeader title="Ringkasan pekerjaan">
        {measureWords
          ? "Status tiap bab, jumlah kata, dan sisa waktu menuju target sidang."
          : `Yang sudah dikerjakan pada fokus "${data.focus_label}". Ubah fokusnya di sidebar bila cakupannya berubah.`}
      </PageHeader>

      {/* Cincin kemajuan sebagai jangkar visual. Angka persen di dalam tabel
          gampang terlewat; bentuk melingkar terbaca sebelum dibaca. */}
      {measureWords ? (
        <Card className="mb-3.5">
          <CardContent className="flex flex-wrap items-center gap-x-10 gap-y-6 pt-5">
            <ProgressRing percent={percent} />
            <MetricRow>
              <Metric value={num(data.word_count)} label="kata tertulis" tone="lagoon" />
              <Metric value={num(data.remaining_words)} label="kata tersisa" tone="violet" />
              {/* Hitung mundur hanya muncul bila tenggatnya memang diisi
                  sendiri. Tanda pisah di tempat angka bukan informasi, dan
                  tenggat karangan adalah tekanan yang tidak diminta siapa pun. */}
              {data.days_left !== null ? (
                <Metric
                  value={data.days_left}
                  label="hari menuju target"
                  tone={urgent ? "clay" : "default"}
                />
              ) : null}
              {data.words_per_day_needed !== null ? (
                <Metric
                  value={data.words_per_day_needed}
                  label="kata/hari dibutuhkan"
                  tone="amber"
                />
              ) : null}
            </MetricRow>
          </CardContent>
        </Card>
      ) : null}

      {data.work_done.length ? (
        <Card className="mb-3.5">
          <CardHeader>
            <CardTitle>Yang sudah dikerjakan</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.work_done.map((item) => (
                <div key={item.key}>
                  <p className="tabular font-serif text-[25px] font-semibold leading-none">
                    {num(item.count)}
                    {item.total !== undefined ? (
                      <span className="text-[15px] font-normal text-faint">
                        {" "}
                        / {num(item.total)}
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-1.5 text-[12.5px] font-medium">{item.label}</p>
                  <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">
                    {item.hint}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {showChapters ? (
        <Card className="mb-3.5">
          <CardHeader>
            <CardTitle>Kemajuan per bab</CardTitle>
          </CardHeader>
          <CardContent>
            <DataTable
              columns={["Bab", "Kata", "Target", "Kemajuan", "Status"]}
              rows={data.chapters.map((chapter) => [
                `${chapter.number} ${chapter.title}`,
                num(chapter.word_count),
                num(chapter.target_words),
                <Progress key="p" value={Math.min(chapter.progress * 100, 100)} />,
                <StatusBadge key="s" status={chapter.status} />,
              ])}
            />
          </CardContent>
        </Card>
      ) : null}

      {Object.keys(data.revisions).length ? (
        <Card>
          <CardHeader>
            <CardTitle>Revisi</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {Object.entries(data.revisions).map(([status, count]) => (
              <Badge key={status} variant={status === "selesai" ? "success" : "warning"}>
                {status}: {count}
              </Badge>
            ))}
          </CardContent>
        </Card>
      ) : null}

      {/* Ruang di bawah dashboard memang kosong dan akan tetap kosong — isinya
          bergantung pada panjang naskah. Diisi kutipan, bukan dibiarkan
          menganga: halaman ini paling sering dibuka orang yang sedang menakar
          sisa pekerjaannya, dan itu saat yang tepat untuk sedikit dorongan. */}
      <QuoteRotator tema="ketekunan" className="mt-14 pb-6" />
    </>
  );
}

/** Cincin kemajuan. Warnanya mengikuti aturan yang sama dengan bilah progres. */
function ProgressRing({ percent }: { percent: number }) {
  const size = 112;
  const stroke = 9;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.min(Math.max(percent, 0), 100) / 100) * circumference;
  const tone =
    percent >= 85 ? "text-success" : percent >= 40 ? "text-amber" : percent > 0 ? "text-clay" : "text-border-strong";

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-border/70"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          className={cn("stroke-current transition-all duration-1000", tone)}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
        <span className="tabular font-serif text-[27px] font-semibold leading-none">
          {percent}%
        </span>
        <span className="text-[10.5px] leading-none text-muted-foreground">dari target</span>
      </div>
    </div>
  );
}
