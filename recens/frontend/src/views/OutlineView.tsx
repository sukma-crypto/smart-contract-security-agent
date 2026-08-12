import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge, Callout, DataTable, Progress, StatusBadge } from "@/components/ui/display";
import { Field, FileInput, Input } from "@/components/ui/form";
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

      <ImportPanel reload={load} />

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


/**
 * Impor naskah yang sudah ditulis sendiri.
 *
 * Berdiri di atas kerangka, bukan di bawahnya, karena inilah yang pertama
 * dicari orang yang datang membawa BAB I sampai III: sebelum ia percaya pada
 * kerangka bawaan yang belum tentu cocok dengan pedoman kampusnya, ia ingin
 * tahu apakah tulisannya sendiri bisa masuk.
 */
function ImportPanel({ reload }: { reload: () => Promise<void> }) {
  const { project } = useApp();
  const { run, refreshProject, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const fileRef = React.useRef<HTMLInputElement>(null);
  const [catatan, setCatatan] = React.useState<string[]>([]);

  const impor = (ganti: boolean) =>
    withBusy("impor", async () => {
      const file = fileRef.current?.files?.[0];
      if (!file) return toast("Pilih berkas naskah .docx lebih dahulu.", "error");
      const form = new FormData();
      form.append("file", file);
      form.append("replace", ganti ? "true" : "false");
      const hasil = await run(() =>
        api.upload<{ sections_created: number; word_count: number; notes: string[] }>(
          `/projects/${project!.id}/manuscript/import`,
          form,
        ),
      );
      if (!hasil) return;
      setCatatan(hasil.notes);
      toast(
        `${hasil.sections_created} bagian terbaca, ${hasil.word_count.toLocaleString("id-ID")} kata masuk ke naskah.`,
      );
      await reload();
      await refreshProject();
    });

  return (
    <Card className="mb-3.5">
      <CardHeader>
        <CardTitle>Sudah punya naskah sendiri?</CardTitle>
        <CardDescription>
          Unggah berkas .docx yang sudah Anda tulis — BAB I sampai III atau seluruhnya. Judul
          bab dikenali dari penomorannya, jadi naskah yang ditulis mengikuti pedoman kampus
          tetap terbaca meski tidak memakai gaya Heading di Word.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Row>
          <Field className="min-w-56 flex-1">
            <FileInput ref={fileRef} accept=".docx" />
          </Field>
          <Button loading={isBusy("impor")} onClick={() => impor(false)}>
            Impor naskah
          </Button>
        </Row>

        {catatan.length ? (
          <Callout className="mt-3" title="Hasil pembacaan">
            {catatan.map((baris, index) => (
              <p key={index} className={index ? "mt-1" : ""}>
                {baris}
              </p>
            ))}
          </Callout>
        ) : null}

        <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          Bila naskah proyek ini sudah berisi tulisan, impor akan ditolak lebih dulu — dan bila
          Anda memang bermaksud menggantinya,{" "}
          <button
            className="underline underline-offset-2 hover:text-foreground"
            onClick={() => impor(true)}
          >
            ganti naskah yang ada
          </button>
          . Naskah lamanya disimpan sebagai versi dan bisa dipulihkan kapan saja.
        </p>
      </CardContent>
    </Card>
  );
}
