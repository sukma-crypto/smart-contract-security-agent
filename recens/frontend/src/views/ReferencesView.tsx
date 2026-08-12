import * as React from "react";
import { Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Badge,
  Callout,
  DataTable,
  Empty,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/display";
import { Field, FileInput, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { useActions, useApp } from "@/lib/store";
import type { Reference, SearchResultItem } from "@/lib/types";
import {
  PageHeader,
  Row,
  authorsOf,
  cellText,
  containerOf,
  titleOf,
  useBusy,
  yearOf,
} from "@/views/shared";

interface LibraryResponse {
  count: number;
  verified: number;
  references: Reference[];
}

export function ReferencesView() {
  const { project } = useApp();
  const { run } = useActions();
  const [library, setLibrary] = React.useState<LibraryResponse | null>(null);

  const load = React.useCallback(async () => {
    const result = await run(() =>
      api.get<LibraryResponse>(`/projects/${project!.id}/references`),
    );
    if (result) setLibrary(result);
  }, [project, run]);

  React.useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader title="Kumpulkan referensi">
        Metadata sitasi hanya berasal dari basis data ilmiah resmi. Referensi unggahan sendiri
        ditandai jelas sampai berhasil ditelusuri.
      </PageHeader>

      <Tabs defaultValue="cari">
        <TabsList className="mb-3.5">
          <TabsTrigger value="cari">Pencarian literatur</TabsTrigger>
          <TabsTrigger value="pustaka">Pustaka proyek ({library?.count ?? 0})</TabsTrigger>
          <TabsTrigger value="tanya">Tanya jurnal</TabsTrigger>
          <TabsTrigger value="sintesis">Matriks sintesis</TabsTrigger>
        </TabsList>

        <TabsContent value="cari">
          <SearchPanel onAdded={load} />
        </TabsContent>
        <TabsContent value="pustaka">
          <LibraryPanel library={library} reload={load} />
        </TabsContent>
        <TabsContent value="tanya">
          <AskPanel />
        </TabsContent>
        <TabsContent value="sintesis">
          <SynthesisPanel />
        </TabsContent>
      </Tabs>
    </>
  );
}

function SearchPanel({ onAdded }: { onAdded: () => Promise<void> }) {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();

  const [query, setQuery] = React.useState("");
  const [doi, setDoi] = React.useState("");
  const [results, setResults] = React.useState<{
    count: number;
    results: SearchResultItem[];
    sources_searched: string[];
    sources_failed: Record<string, string>;
  } | null>(null);
  const pdfRef = React.useRef<HTMLInputElement>(null);

  const search = () =>
    withBusy("search", async () => {
      if (!query.trim()) {
        toast("Kata kunci masih kosong.", "error");
        return;
      }
      const result = await run(() =>
        api.get<typeof results>(
          `/references/search?q=${encodeURIComponent(query)}&rows=10&project_id=${project!.id}`,
        ),
      );
      if (result) setResults(result);
    });

  const failed = Object.entries(results?.sources_failed ?? {});

  return (
    <Card>
      <CardHeader>
        <CardTitle>Penelusuran serentak</CardTitle>
        <CardDescription>
          Crossref, OpenAlex, Semantic Scholar, dan Garuda/SINTA dicari sekaligus.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <Row>
          <Field label="Kata kunci" className="min-w-56 flex-1">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              placeholder="motivasi kerja kinerja karyawan"
            />
          </Field>
          <Button onClick={search} loading={isBusy("search")}>
            Cari
          </Button>
        </Row>

        <Row>
          <Field label="Atau tambah lewat DOI" className="min-w-56 flex-1">
            <Input
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
              placeholder="10.1016/j.jbusres.2020.01.001"
            />
          </Field>
          <Button
            variant="outline"
            loading={isBusy("doi")}
            onClick={() =>
              withBusy("doi", async () => {
                if (!doi.trim()) return toast("DOI masih kosong.", "error");
                const added = await run(() =>
                  api.post<Reference>(`/projects/${project!.id}/references/doi`, { doi }),
                );
                if (added) {
                  toast(`Ditambahkan: ${added.citekey}`);
                  setDoi("");
                  await onAdded();
                }
              })
            }
          >
            Tarik metadata
          </Button>
        </Row>

        <Row>
          <Field label="Atau unggah PDF sendiri" className="min-w-56 flex-1">
            <FileInput ref={pdfRef} accept=".pdf" />
          </Field>
          <Button
            variant="outline"
            loading={isBusy("pdf")}
            onClick={() =>
              withBusy("pdf", async () => {
                const file = pdfRef.current?.files?.[0];
                if (!file) return toast("Pilih berkas PDF lebih dahulu.", "error");
                const form = new FormData();
                form.append("file", file);
                const added = await run(() =>
                  api.upload<{ pages: number; chunks: number; note: string }>(
                    `/projects/${project!.id}/references/upload`,
                    form,
                  ),
                );
                if (added) {
                  toast(`${added.pages} halaman terindeks jadi ${added.chunks} potongan.`);
                  await onAdded();
                }
              })
            }
          >
            Unggah &amp; indeks
          </Button>
        </Row>

        {failed.length ? (
          <Callout variant="warning" title="Sebagian sumber tidak terjangkau">
            {failed.map(([key, value]) => (
              <p key={key}>
                {key}: {value}
              </p>
            ))}
          </Callout>
        ) : null}

        {results ? (
          <div>
            <p className="mb-2 text-[11.5px] text-muted-foreground">
              {results.count} hasil dari{" "}
              {results.sources_searched.join(", ") || "tidak ada sumber"}.
            </p>
            <div className="flex flex-col gap-2">
              {results.results.map((item, index) => (
                <div
                  key={index}
                  className="rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
                >
                  <p className="text-[13px] font-medium">{titleOf(item.entry)}</p>
                  <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                    {authorsOf(item.entry)} ({yearOf(item.entry)}) · {containerOf(item.entry)}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <Badge variant="success">{item.source_db}</Badge>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        run(async () => {
                          await api.post(`/projects/${project!.id}/references`, {
                            entry: item.entry,
                            source_db: item.source_db,
                            external_id: item.external_id,
                            abstract: item.abstract,
                          });
                          toast("Referensi masuk pustaka proyek.");
                          await onAdded();
                        })
                      }
                    >
                      Tambah ke pustaka
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <SumberResmi />
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Keempat basis data yang ditelusuri, sebelum pencarian pertama dijalankan.
 *
 * Kolom kosong di bawah kotak pencarian menyembunyikan hal yang justru
 * menjadi alasan fitur ini ada: metadata tidak diketik dan tidak dikarang,
 * melainkan ditarik dari basis data resmi. Mahasiswa yang tidak tahu itu akan
 * mengira Recens "mencari di internet" — dan pertanyaan pertama pembimbing
 * atas daftar pustaka selalu dari mana sumbernya.
 */
function SumberResmi() {
  return (
    <div>
      <p className="mb-2.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-faint">
        Yang ditelusuri
      </p>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {SUMBER.map((item) => (
          <div key={item.nama} className="rounded-lg border border-border bg-muted/40 p-3">
            <p className="text-[12.5px] font-semibold">{item.nama}</p>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
              {item.isi}
            </p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
        Metadata sitasi hanya diterima dari keempat sumber di atas atau dari PDF yang Anda
        unggah sendiri. Recens tidak pernah menyusun entri pustaka dari ingatan model.
      </p>
    </div>
  );
}

const SUMBER = [
  {
    nama: "Crossref",
    isi: "Rujukan resmi DOI. Paling lengkap untuk jurnal internasional bereputasi.",
  },
  {
    nama: "OpenAlex",
    isi: "Katalog terbuka lintas bidang, termasuk terbitan yang belum ber-DOI.",
  },
  {
    nama: "Semantic Scholar",
    isi: "Kuat pada ilmu komputer, kedokteran, dan bidang yang cepat berubah.",
  },
  {
    nama: "Garuda / SINTA",
    isi: "Jurnal nasional terakreditasi — yang paling sering diminta pembimbing.",
  },
] as const;

function LibraryPanel({
  library,
  reload,
}: {
  library: LibraryResponse | null;
  reload: () => Promise<void>;
}) {
  const { run, toast } = useActions();

  return (
    <Card>
      <CardHeader>
        <CardTitle>Pustaka proyek</CardTitle>
      </CardHeader>
      <CardContent>
        {!library?.references.length ? (
          <Empty>Pustaka masih kosong.</Empty>
        ) : (
          <div className="flex flex-col gap-2">
            {library.references.map((reference) => (
              <div
                key={reference.id}
                className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-border bg-muted/50 px-3.5 py-2.5"
              >
                <div className="min-w-56 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="mono">{reference.citekey}</Badge>
                    <span className="text-[13px] font-medium">
                      {titleOf(reference.csl_json)}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                    {authorsOf(reference.csl_json)} ({yearOf(reference.csl_json)}) ·{" "}
                    {containerOf(reference.csl_json)}
                    {reference.csl_json.DOI ? ` · doi:${reference.csl_json.DOI}` : ""}
                  </p>
                  <div className="mt-1.5">
                    {reference.verified ? (
                      <Badge variant="success">terverifikasi · {reference.source_db}</Badge>
                    ) : (
                      <Badge variant="warning">belum terverifikasi</Badge>
                    )}
                  </div>
                </div>
                <div className="flex gap-1.5">
                  {!reference.verified ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        run(async () => {
                          const result = await api.post<Reference & { note?: string }>(
                            `/references/${reference.id}/verify`,
                          );
                          toast(
                            result.verified
                              ? "Terverifikasi ke basis data resmi."
                              : (result.note ?? "Belum cocok."),
                          );
                          await reload();
                        })
                      }
                    >
                      Telusuri
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Hapus"
                    onClick={() =>
                      run(async () => {
                        await api.del(`/references/${reference.id}`);
                        await reload();
                      })
                    }
                  >
                    <Trash2 />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AskPanel() {
  const { project } = useApp();
  const { run, toast } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [question, setQuestion] = React.useState("");
  const [answer, setAnswer] = React.useState<{
    text: string;
    meta: { note?: string; sources?: { citekey: string; page: number | null; text: string }[] };
  } | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tanya jurnal</CardTitle>
        <CardDescription>
          Jawaban disertai penunjuk halaman sumber. Berlaku untuk PDF yang sudah diunggah dan
          diindeks.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3.5">
        <Row>
          <Field label="Pertanyaan" className="min-w-56 flex-1">
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Apa metode dan ukuran sampel penelitian ini?"
            />
          </Field>
          <Button
            loading={isBusy("ask")}
            onClick={() =>
              withBusy("ask", async () => {
                if (!question.trim()) return toast("Pertanyaan masih kosong.", "error");
                const result = await run(() =>
                  api.post<typeof answer>(`/projects/${project!.id}/ask`, { question }),
                );
                if (result) setAnswer(result);
              })
            }
          >
            Tanya
          </Button>
        </Row>

        {answer?.text ? <Callout variant="success">{answer.text}</Callout> : null}
        {answer?.meta.note ? <Callout>{answer.meta.note}</Callout> : null}
        {answer?.meta.sources?.map((source, index) => (
          <div key={index} className="rounded-md border border-border bg-muted/50 px-3.5 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="mono">{source.citekey}</Badge>
              <Badge>hlm. {source.page ?? "?"}</Badge>
            </div>
            <p className="mt-1.5 text-[13px] leading-relaxed">{source.text.slice(0, 420)}…</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function SynthesisPanel() {
  const { project } = useApp();
  const { run } = useActions();
  const { withBusy, isBusy } = useBusy();
  const [matrix, setMatrix] = React.useState<{
    columns: string[];
    rows: Record<string, unknown>[];
  } | null>(null);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Matriks sintesis</CardTitle>
        <CardDescription>
          Mengubah tumpukan bacaan menjadi tabel perbandingan: penulis, tahun, teori, metode,
          temuan, dan celah penelitian.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button
          loading={isBusy("syn")}
          onClick={() =>
            withBusy("syn", async () => {
              const result = await run(() =>
                api.post<typeof matrix>(`/projects/${project!.id}/synthesis`, {}),
              );
              if (result) setMatrix(result);
            })
          }
        >
          Susun matriks
        </Button>
        {matrix ? (
          <DataTable
            className="mt-3.5"
            columns={matrix.columns}
            rows={matrix.rows.map((row) => matrix.columns.map((column) => cellText(row[column])))}
            emptyLabel="Pustaka masih kosong."
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
