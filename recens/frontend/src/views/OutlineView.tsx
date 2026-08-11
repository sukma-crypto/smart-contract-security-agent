import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, DataTable, Progress, StatusBadge } from "@/components/ui/display";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { num } from "@/lib/utils";
import type { OutlineRow } from "@/lib/types";
import { PageHeader, Row, useBusy } from "@/views/shared";

interface OutlineResponse {
  sections: OutlineRow[];
  word_count: number;
  target_words: number;
}

export function OutlineView() {
  const { project } = useApp();
  const { run, refreshProject, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [data, setData] = React.useState<OutlineResponse | null>(null);
  const [target, setTarget] = React.useState(0);

  const load = React.useCallback(async () => {
    const result = await run(() => api.get<OutlineResponse>(`/projects/${project!.id}/outline`));
    if (result) {
      setData(result);
      setTarget(result.target_words);
    }
  }, [project, run]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const regenerate = () =>
    withBusy("regen", async () => {
      if (!window.confirm("Bangun ulang kerangka? Seluruh isi bagian akan terhapus.")) return;
      await run(async () => {
        await api.post(`/projects/${project!.id}/versions`, {
          label: "Sebelum bangun ulang kerangka",
        });
        await api.post(`/projects/${project!.id}/outline/generate`, {
          reset: true,
          target_words: target,
        });
      });
      await refreshProject();
      await load();
      toast("Kerangka dibangun ulang. Versi sebelumnya tersimpan.");
    });

  return (
    <>
      <PageHeader title="Susun outline">
        Kerangka dibangun mengikuti struktur yang berlaku pada jenis karya ini, lengkap dengan
        target jumlah kata tiap bagian.
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>
            Kerangka — {num(data?.word_count ?? 0)} dari {num(data?.target_words ?? 0)} kata
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Row className="mb-3.5">
            <Field label="Target kata">
              <Input
                className="w-32"
                type="number"
                value={target}
                onChange={(e) => setTarget(Number(e.target.value))}
              />
            </Field>
            <Button variant="outline" onClick={regenerate} loading={isBusy("regen")}>
              Bangun ulang kerangka
            </Button>
            <p className="pb-2 text-[11.5px] text-muted-foreground">
              Membangun ulang menghapus isi yang sudah ditulis.
            </p>
          </Row>

          <DataTable
            columns={["Bagian", "Kata", "Target", "Kemajuan", "Status"]}
            rows={(data?.sections ?? []).map((section) => [
              <span
                key="t"
                style={{ paddingLeft: `${(section.level - 1) * 16}px` }}
                className="flex flex-wrap items-center gap-1.5"
              >
                <span className={section.level === 1 ? "font-semibold" : ""}>
                  {section.number} {section.title}
                </span>
                {section.role ? <Badge>{section.role}</Badge> : null}
              </span>,
              num(section.word_count),
              num(section.target_words),
              <Progress key="p" value={Math.min(section.progress * 100, 100)} />,
              <StatusBadge key="s" status={section.status} />,
            ])}
          />
        </CardContent>
      </Card>
    </>
  );
}
