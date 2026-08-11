import * as React from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, DataTable, Metric, MetricRow, Progress } from "@/components/ui/display";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { num } from "@/lib/utils";
import type { OutlineRow } from "@/lib/types";
import { PageHeader } from "@/views/shared";

interface Dashboard {
  word_count: number;
  target_words: number;
  progress: number;
  remaining_words: number;
  days_left: number | null;
  words_per_day_needed: number | null;
  chapters: OutlineRow[];
  revisions: Record<string, number>;
}

export function DashboardView() {
  const { project } = useApp();
  const { run } = useActions();
  const [data, setData] = React.useState<Dashboard | null>(null);

  React.useEffect(() => {
    void run(async () => setData(await api.get(`/projects/${project!.id}/dashboard`)));
  }, [project, run]);

  if (!data) return null;

  return (
    <>
      <PageHeader title="Dashboard progres">
        Status tiap bab, jumlah kata, dan sisa waktu menuju target sidang.
      </PageHeader>

      <Card className="mb-3.5">
        <CardContent className="pt-5">
          <MetricRow>
            <Metric value={num(data.word_count)} label="kata tertulis" />
            <Metric value={`${Math.round(data.progress * 100)}%`} label="dari target" />
            <Metric value={num(data.remaining_words)} label="kata tersisa" />
            <Metric value={data.days_left ?? "—"} label="hari menuju target" />
            <Metric value={data.words_per_day_needed ?? "—"} label="kata/hari dibutuhkan" />
          </MetricRow>
        </CardContent>
      </Card>

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
              <Badge key="s" variant={chapter.status === "selesai" ? "success" : "default"}>
                {chapter.status}
              </Badge>,
            ])}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Revisi</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-1.5">
          {Object.keys(data.revisions).length ? (
            Object.entries(data.revisions).map(([status, count]) => (
              <Badge key={status} variant={status === "selesai" ? "success" : "warning"}>
                {status}: {count}
              </Badge>
            ))
          ) : (
            <p className="text-[13px] text-muted-foreground">Belum ada revisi tercatat.</p>
          )}
        </CardContent>
      </Card>
    </>
  );
}
