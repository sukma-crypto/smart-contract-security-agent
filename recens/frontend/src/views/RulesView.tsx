import * as React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge, Callout } from "@/components/ui/display";
import { Field, FileInput, Input, SimpleSelect, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import { num } from "@/lib/utils";
import type { RuleSet } from "@/lib/types";
import { PageHeader, Row, useBusy } from "@/views/shared";

const KINDS = [
  { value: "fakultas", label: "Pedoman fakultas" },
  { value: "dosen", label: "Instruksi dosen" },
  { value: "panitia", label: "Ketentuan panitia" },
  { value: "jurnal", label: "Pedoman jurnal" },
];

const POSITION_LABEL: Record<string, string> = { above: "atas", below: "bawah" };

interface GuidelineResponse {
  active: RuleSet;
  history: { id: number; name: string; kind: string; active: number; created_at: string }[];
}

export function RulesView() {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();

  const [data, setData] = React.useState<GuidelineResponse | null>(null);
  const [text, setText] = React.useState("");
  const [name, setName] = React.useState("Pedoman penulisan");
  const [kind, setKind] = React.useState("fakultas");
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = React.useCallback(async () => {
    const result = await run(() =>
      api.get<GuidelineResponse>(`/projects/${project!.id}/guidelines`),
    );
    if (result) setData(result);
  }, [project, run]);

  React.useEffect(() => {
    void load();
  }, [load]);

  const upload = () =>
    withBusy("upload", async () => {
      const file = fileRef.current?.files?.[0];
      if (!file) {
        toast("Pilih berkas pedoman lebih dahulu.", "error");
        return;
      }
      const form = new FormData();
      form.append("file", file);
      form.append("name", name);
      form.append("kind", kind);
      const result = await run(() =>
        api.upload<{ pages_read: number }>(`/projects/${project!.id}/guidelines/upload`, form),
      );
      if (result) {
        toast(`Pedoman terbaca dari ${result.pages_read} halaman.`);
        await load();
      }
    });

  const parse = () =>
    withBusy("parse", async () => {
      if (!text.trim()) {
        toast("Teks pedoman masih kosong.", "error");
        return;
      }
      const result = await run(() =>
        api.post(`/projects/${project!.id}/guidelines/text`, { text, name, kind }),
      );
      if (result) {
        toast("Aturan diperbarui.");
        setText("");
        await load();
      }
    });

  const rules = data?.active;

  return (
    <>
      <PageHeader title="Muat aturan penulisan">
        Pedoman dibaca menjadi aturan yang mengikat seluruh keluaran: struktur, gaya sitasi,
        margin, huruf, spasi, penomoran, dan batas panjang.
      </PageHeader>

      <Card className="mb-3.5">
        <CardHeader>
          <CardTitle>Unggah atau tempel pedoman</CardTitle>
          <CardDescription>
            Pedoman fakultas, instruksi dosen, ketentuan panitia lomba, atau pedoman penulis
            jurnal tujuan.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Row>
            <Field label="Berkas PDF / DOCX" className="min-w-56 flex-1">
              <FileInput ref={fileRef} accept=".pdf,.docx,.txt" />
            </Field>
            <Field label="Nama">
              <Input className="w-48" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Jenis">
              <SimpleSelect className="w-44" value={kind} onValueChange={setKind} options={KINDS} />
            </Field>
            <Button onClick={upload} loading={isBusy("upload")}>
              Baca berkas
            </Button>
          </Row>

          <Field label="Atau tempel teks pedoman" className="mt-3.5">
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Naskah diketik pada kertas A4 dengan huruf Times New Roman ukuran 12 pt, jarak 2 spasi, margin atas 4 cm…"
            />
          </Field>
          <Button variant="outline" className="mt-2.5" onClick={parse} loading={isBusy("parse")}>
            Baca teks
          </Button>
        </CardContent>
      </Card>

      {rules ? (
        <Card className="mb-3.5">
          <CardHeader>
            <CardTitle>Aturan yang berlaku — {rules.name}</CardTitle>
          </CardHeader>
          <CardContent>
            {rules.assumed?.length ? (
              <Callout
                variant="warning"
                className="mb-3.5"
                title={`${rules.assumed.length} aturan memakai nilai bawaan`}
              >
                Tidak ditemukan di pedoman: {rules.assumed.join(", ")}. Periksa dan perbaiki
                sebelum naskah dirakit.
              </Callout>
            ) : null}

            <dl className="divide-y divide-border border-t border-border text-[13px]">
              <RuleRow label="Ukuran kertas">{rules.page_size}</RuleRow>
              <RuleRow label="Huruf" evidence={[rules.evidence.font_family, rules.evidence.font_size_pt]}>
                {rules.font_family}, {rules.font_size_pt} pt
              </RuleRow>
              <RuleRow label="Jarak baris" evidence={[rules.evidence.line_spacing]}>
                {rules.line_spacing} spasi
              </RuleRow>
              <RuleRow label="Margin (atas/kanan/bawah/kiri)">
                {rules.margins.top_cm} / {rules.margins.right_cm} / {rules.margins.bottom_cm} /{" "}
                {rules.margins.left_cm} cm
              </RuleRow>
              <RuleRow label="Gaya sitasi" evidence={[rules.evidence.citation_style]}>
                <span className="inline-flex items-center gap-1.5">
                  {rules.citation_style.toUpperCase()}
                  {rules.citation_options?.et_al_term ? (
                    <Badge>{rules.citation_options.et_al_term}</Badge>
                  ) : null}
                </span>
              </RuleRow>
              <RuleRow label="Penomoran halaman">
                Bagian awal {rules.front_matter_numbering}, bagian isi {rules.body_numbering}
              </RuleRow>
              <RuleRow label="Caption">
                Judul tabel di {POSITION_LABEL[rules.table_caption_position] ?? rules.table_caption_position},
                judul gambar di{" "}
                {POSITION_LABEL[rules.figure_caption_position] ?? rules.figure_caption_position},
                penomoran {rules.caption_numbering}
              </RuleRow>
              <RuleRow
                label="Batas panjang"
                evidence={[rules.evidence.max_pages, rules.evidence.abstract_max_words]}
              >
                {rules.max_words ? `${num(rules.max_words)} kata` : "kata tidak dibatasi"} ·{" "}
                {rules.max_pages ? `${num(rules.max_pages)} halaman` : "halaman tidak dibatasi"} ·
                abstrak{" "}
                {rules.abstract_max_words ? `${num(rules.abstract_max_words)} kata` : "tidak dibatasi"}
              </RuleRow>
              <RuleRow label="Bab wajib">
                {rules.required_sections?.length ? (
                  <div className="flex flex-wrap gap-1">
                    {rules.required_sections.map((section) => (
                      <Badge key={section}>{section}</Badge>
                    ))}
                  </div>
                ) : (
                  <span className="text-muted-foreground">tidak terbaca dari pedoman</span>
                )}
              </RuleRow>
            </dl>
          </CardContent>
        </Card>
      ) : null}

      {data && data.history.length > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle>Riwayat pedoman</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {data.history.map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/50 px-3 py-2 text-[13px]"
              >
                <span className="font-medium">{item.name}</span>
                <Badge>{item.kind}</Badge>
                {item.active ? <Badge variant="success">aktif</Badge> : null}
                <span className="text-[11.5px] text-muted-foreground">{item.created_at}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </>
  );
}

function RuleRow({
  label,
  children,
  evidence = [],
}: {
  label: string;
  children: React.ReactNode;
  evidence?: (string | undefined)[];
}) {
  const quotes = evidence.filter(Boolean) as string[];
  return (
    <div className="grid gap-1 py-2 sm:grid-cols-[13rem_1fr] sm:gap-4">
      <dt className="text-[11.5px] font-semibold text-muted-foreground sm:text-[13px]">{label}</dt>
      <dd className="min-w-0">
        {children}
        {quotes.map((quote, index) => (
          <p key={index} className="mt-1 text-[11.5px] italic text-muted-foreground">
            “{quote}”
          </p>
        ))}
      </dd>
    </div>
  );
}
