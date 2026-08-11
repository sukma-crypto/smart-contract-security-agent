import * as React from "react";
import {
  ArrowRight,
  BookOpenCheck,
  Check,
  FileCheck2,
  FlaskConical,
  ListTree,
  PenLine,
  ScrollText,
  Search,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useCountUp, useReveal, useTypewriter, type Segment } from "@/landing/hooks";

/* Naskah yang diketik di hero. Sengaja memakai kalimat akademik Indonesia
   sungguhan, lengkap dengan sitasi yang muncul utuh — bukan diketik — karena
   begitulah cara kerja produknya. */
const DEMO: Segment[] = [
  { text: "Kinerja karyawan dipengaruhi oleh motivasi kerja ", pause: 90 },
  { chip: "(Sugiyono & Hasibuan, 2021)", pause: 620 },
  { text: ". Temuan serupa dilaporkan pada sektor jasa ", pause: 90 },
  { chip: "(Ghozali dkk., 2020)", pause: 620 },
  {
    text: ". Uji regresi pada 154 responden menghasilkan koefisien determinasi sebesar 0,816.",
    pause: 400,
  },
];

const PROBLEMS = [
  {
    n: "01",
    title: "Buta struktur",
    old: "Mencontek karya orang lain tanpa memahami logika hubungan antarbagiannya.",
    now: "Kerangka dibangun mengikuti aturan yang berlaku pada jenis karya tersebut.",
    Icon: ListTree,
    tint: "text-lagoon",
  },
  {
    n: "02",
    title: "Sitasi tidak valid",
    old: "Referensi diketik manual, sering tidak konsisten dan tidak sinkron dengan daftar pustaka.",
    now: "Sitasi ditarik dari metadata resmi dan selalu sinkron dengan daftar pustaka.",
    Icon: BookOpenCheck,
    tint: "text-violet",
  },
  {
    n: "03",
    title: "Format manual",
    old: "Berhari-hari mengatur margin, penomoran, dan daftar isi secara manual.",
    now: "Dokumen dirakit otomatis sesuai aturan tujuan dan siap serah.",
    Icon: FileCheck2,
    tint: "text-amber",
  },
  {
    n: "04",
    title: "Buntu di olah data",
    old: "Bingung memilih uji statistik, menjalankannya, dan membaca output perangkat analisis.",
    now: "Pemandu metode, pengolahan data, dan pembacaan hasil menjadi tabel serta narasi.",
    Icon: FlaskConical,
    tint: "text-clay",
  },
  {
    n: "05",
    title: "Revisi tercecer",
    old: "Catatan dosen atau reviewer tersebar di pesan, coretan, dan berkas berbeda.",
    now: "Seluruh revisi tercatat berstatus dan terhubung ke lokasinya di naskah.",
    Icon: ScrollText,
    tint: "text-lagoon",
  },
];

const STEPS = [
  { n: 1, title: "Buat proyek", body: "Pilih jenis karya; struktur dan batasnya mengikuti.", Icon: ListTree },
  { n: 2, title: "Muat aturan", body: "Pedoman kampus dibaca jadi aturan yang mengikat.", Icon: ShieldCheck },
  { n: 3, title: "Kumpulkan referensi", body: "Crossref, OpenAlex, Semantic Scholar, Garuda.", Icon: Search },
  { n: 4, title: "Susun outline", body: "Kerangka bab lengkap dengan target kata.", Icon: ListTree },
  { n: 5, title: "Menulis", body: "Lanjutan kalimat, parafrase, sitasi tersisip.", Icon: PenLine },
  { n: 6, title: "Olah data", body: "Uji instrumen sampai regresi dan SEM-PLS.", Icon: FlaskConical },
  { n: 7, title: "Periksa naskah", body: "PUEBI, silang sitasi, konsistensi, kemiripan.", Icon: FileCheck2 },
  { n: 8, title: "Ekspor & revisi", body: "DOCX terformat penuh, pelacak bimbingan.", Icon: Send },
];

const WORK_TYPES = [
  "Makalah kuliah",
  "Laporan praktikum",
  "Laporan magang",
  "Karya tulis lomba",
  "Esai ilmiah",
  "Proposal penelitian",
  "Skripsi",
  "Tesis",
  "Disertasi",
  "Artikel jurnal",
  "Artikel prosiding",
  "Tinjauan pustaka",
];

const LIMITS = [
  ["Menyusun kerangka dan struktur bab", "Menghasilkan bab utuh sekali jalan"],
  ["Melanjutkan kalimat yang sedang diketik", "Mengarang data, hasil uji, atau temuan"],
  ["Menyarankan sitasi dari sumber terverifikasi", "Menghasilkan referensi tak terlacak"],
  ["Mengolah data dan menampilkan langkahnya", "Memanipulasi hasil agar hipotesis diterima"],
  ["Memparafrase disertai alasan perubahan", "Memparafrase untuk mengelabui deteksi"],
];

export function Landing({ onEnter }: { onEnter: () => void }) {
  return (
    <div className="min-h-full bg-paper text-foreground">
      <Nav onEnter={onEnter} />
      <Hero onEnter={onEnter} />
      <Marquee />
      <Problems />
      <Workflow />
      <Engine />
      <Limits />
      <Closing onEnter={onEnter} />
      <Footer />
    </div>
  );
}

/* --- Navigasi --- */

function Nav({ onEnter }: { onEnter: () => void }) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-paper/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-5">
        <span className="font-serif text-[20px] font-semibold tracking-tight">Recens</span>
        <nav className="hidden gap-6 text-[13px] text-muted-foreground md:flex">
          <a href="#masalah" className="transition-colors hover:text-foreground">Masalah</a>
          <a href="#alur" className="transition-colors hover:text-foreground">Alur kerja</a>
          <a href="#mesin" className="transition-colors hover:text-foreground">Mesinnya</a>
          <a href="#batas" className="transition-colors hover:text-foreground">Batas produk</a>
        </nav>
        <div className="flex-1" />
        <Button size="sm" onClick={onEnter}>
          Buka ruang kerja <ArrowRight />
        </Button>
      </div>
    </header>
  );
}

/* --- Hero --- */

function Hero({ onEnter }: { onEnter: () => void }) {
  const { parts, finished } = useTypewriter(DEMO);

  return (
    <section className="relative isolate overflow-hidden px-5 pb-14 pt-14 md:pt-20">
      {/* Latar gradien yang bergerak sangat pelan. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-gradient-to-b from-lagoon/[0.07] via-amber/[0.05] to-transparent" />
        <div className="animate-drift absolute -left-40 -top-52 size-[42rem] rounded-full bg-lagoon/35 blur-[130px]" />
        <div
          className="animate-drift absolute -right-32 -top-10 size-[34rem] rounded-full bg-amber/30 blur-[120px]"
          style={{ animationDelay: "-7s" }}
        />
        <div
          className="animate-drift absolute -bottom-32 left-1/3 size-[30rem] rounded-full bg-violet/24 blur-[120px]"
          style={{ animationDelay: "-14s" }}
        />
        <div
          className="animate-drift absolute bottom-0 right-1/4 size-[22rem] rounded-full bg-clay/20 blur-[110px]"
          style={{ animationDelay: "-4s" }}
        />
      </div>

      <div className="mx-auto max-w-6xl">
        <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_1fr]">
          <div>
            <p className="animate-rise inline-flex items-center gap-2 rounded-full border border-lagoon/25 bg-lagoon/8 px-3 py-1 text-[12px] font-medium text-lagoon">
              <span className="relative flex size-1.5">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-lagoon opacity-70" />
                <span className="relative inline-flex size-1.5 rounded-full bg-lagoon" />
              </span>
              Untuk mahasiswa, peneliti, dan dosen
            </p>

            <h1
              className="animate-rise mt-5 font-serif text-[42px] font-semibold leading-[1.06] tracking-tight sm:text-[54px]"
              style={{ animationDelay: "80ms" }}
            >
              Menulis karya ilmiah,
              <br />
              <span className="text-sheen">dari halaman kosong</span>
              <br />
              sampai siap serah.
            </h1>

            <p
              className="animate-rise mt-5 max-w-[52ch] text-[15px] leading-relaxed text-muted-foreground"
              style={{ animationDelay: "160ms" }}
            >
              Satu ruang kerja untuk makalah, laporan, proposal, skripsi, tesis, disertasi,
              sampai artikel jurnal — mengumpulkan referensi, menulis, mengolah data, memeriksa
              naskah, hingga mengekspor dokumen yang formatnya sudah benar.
            </p>

            <div
              className="animate-rise mt-7 flex flex-wrap items-center gap-3"
              style={{ animationDelay: "240ms" }}
            >
              <Button size="lg" onClick={onEnter}>
                Mulai menulis <ArrowRight />
              </Button>
              <a
                href="#alur"
                className="text-[13px] font-medium text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
              >
                Lihat delapan langkahnya
              </a>
            </div>

            <dl
              className="animate-rise mt-9 flex flex-wrap gap-x-8 gap-y-3"
              style={{ animationDelay: "320ms" }}
            >
              <Stat value={37} label="fitur" />
              <Stat value={12} label="jenis karya" />
              <Stat value={20} label="uji statistik" />
              <Stat value={4} label="gaya sitasi" />
            </dl>
          </div>

          {/* Demo mengetik */}
          <div className="animate-rise" style={{ animationDelay: "180ms" }}>
            <div className="relative rounded-xl border border-border bg-card shadow-[0_24px_60px_-28px_rgba(20,40,35,0.4)]">
              <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
                <span className="size-2 rounded-full bg-clay/60" />
                <span className="size-2 rounded-full bg-amber/60" />
                <span className="size-2 rounded-full bg-lagoon/50" />
                <span className="ml-2 truncate text-[11px] text-muted-foreground">
                  BAB II · Landasan Teori
                </span>
                <span className="ml-auto shrink-0 rounded bg-lagoon/10 px-1.5 py-0.5 text-[10px] font-medium text-lagoon">
                  menulis…
                </span>
              </div>

              <div className="px-5 py-6">
                <p className="prose-manuscript min-h-[7.5rem] text-[15.5px]">
                  {parts.map((part, index) =>
                    part.kind === "chip" ? (
                      <span
                        key={index}
                        className="animate-pop mx-0.5 inline-block rounded bg-lagoon/12 px-1.5 py-0.5 text-[13.5px] font-medium text-lagoon"
                      >
                        {part.value}
                      </span>
                    ) : (
                      <span key={index}>{part.value}</span>
                    ),
                  )}
                  {!finished ? (
                    <span className="animate-caret ml-0.5 inline-block h-[1.1em] w-[2px] translate-y-[0.15em] bg-lagoon" />
                  ) : null}
                </p>

                <div
                  className={cn(
                    "mt-5 space-y-2 border-t border-border pt-4 transition-opacity duration-700",
                    finished ? "opacity-100" : "opacity-0",
                  )}
                >
                  <Verified
                    label="Sitasi ditarik dari Crossref"
                    detail="doi:10.1234/jmi.2021.12"
                  />
                  <Verified
                    label="0,816 dihitung mesin statistik"
                    detail="bukan diperkirakan model"
                  />
                </div>
              </div>
            </div>

            <p className="mt-3 text-center text-[11.5px] text-muted-foreground">
              Sitasi tidak diketik — ia disisipkan dari pustaka proyek yang sudah terverifikasi.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Verified({ label, detail }: { label: string; detail: string }) {
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <span className="grid size-4 shrink-0 place-items-center rounded-full bg-lagoon/15">
        <Check className="size-2.5 text-lagoon" strokeWidth={3} />
      </span>
      <span className="font-medium">{label}</span>
      <span className="truncate font-mono text-[10.5px] text-muted-foreground">{detail}</span>
    </div>
  );
}

function Stat({ value, label }: { value: number; label: string }) {
  const { ref, shown } = useReveal<HTMLDivElement>();
  const count = useCountUp(value, shown);
  return (
    <div ref={ref} className="flex items-baseline gap-1.5">
      <dd className="tabular font-serif text-[26px] font-semibold leading-none">{count}</dd>
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
    </div>
  );
}

/* --- Marquee jenis karya --- */

function Marquee() {
  const items = [...WORK_TYPES, ...WORK_TYPES];
  return (
    <section className="overflow-hidden border-y border-border bg-card/50 py-4">
      <div className="relative flex">
        <div className="animate-marquee flex shrink-0 gap-3 pr-3">
          {items.map((item, index) => (
            <span
              key={index}
              className="whitespace-nowrap rounded-full border border-border bg-paper px-3.5 py-1.5 text-[12.5px] text-muted-foreground"
            >
              {item}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* --- Bagian bisa direveal --- */

function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const { ref, shown } = useReveal();
  return (
    <div
      ref={ref}
      className={cn("reveal", shown && "revealed", className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

function SectionHead({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <Reveal className="mx-auto mb-12 max-w-2xl text-center">
      <p className="text-[12px] font-semibold text-lagoon">{eyebrow}</p>
      <h2 className="mt-2 font-serif text-[32px] font-semibold leading-tight tracking-tight sm:text-[38px]">
        {title}
      </h2>
      {children ? (
        <p className="mt-3 text-[14px] leading-relaxed text-muted-foreground">{children}</p>
      ) : null}
    </Reveal>
  );
}

/* --- Masalah --- */

function Problems() {
  return (
    <section id="masalah" className="relative isolate px-5 py-24">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-72 bg-gradient-to-b from-violet/[0.06] to-transparent" />
      <div className="mx-auto max-w-6xl">
        <SectionHead eyebrow="Masalah yang diselesaikan" title="Menulis hanyalah gejala terakhir">
          Mayoritas penulis karya ilmiah tidak tersendat karena tidak bisa menulis. Mereka
          tersendat karena tidak tahu struktur apa yang benar, format apa yang diminta, metode
          apa yang tepat, dan referensi mana yang layak dikutip.
        </SectionHead>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PROBLEMS.map((problem, index) => (
            <Reveal key={problem.n} delay={index * 70}>
              <article className="group h-full rounded-xl border border-border bg-card p-5 transition-all duration-300 hover:-translate-y-1 hover:border-lagoon/35 hover:shadow-[0_18px_44px_-24px_rgba(20,40,35,0.35)]">
                <div className="flex items-center gap-2.5">
                  <problem.Icon className={cn("size-4.5", problem.tint)} />
                  <span className="tabular text-[11px] font-semibold text-muted-foreground">
                    {problem.n}
                  </span>
                </div>
                <h3 className="mt-3 font-serif text-[19px] font-semibold">{problem.title}</h3>
                <p className="mt-2.5 text-[12.5px] leading-relaxed text-muted-foreground line-through decoration-clay/40">
                  {problem.old}
                </p>
                <p className="mt-2.5 flex gap-2 text-[13px] leading-relaxed">
                  <ArrowRight className="mt-1 size-3.5 shrink-0 text-lagoon" />
                  <span>{problem.now}</span>
                </p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* --- Alur kerja --- */

function Workflow() {
  return (
    <section id="alur" className="border-y border-border bg-card/40 px-5 py-24">
      <div className="mx-auto max-w-6xl">
        <SectionHead eyebrow="Alur kerja" title="Delapan langkah, satu alur">
          Yang menyesuaikan hanyalah panjang, struktur, dan sumber aturannya — makalah mingguan
          dan disertasi berjalan di jalur yang sama.
        </SectionHead>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <Reveal key={step.n} delay={index * 55}>
              <div className="relative h-full rounded-xl border border-border bg-paper p-5 transition-colors hover:border-lagoon/35">
                <div className="flex items-center justify-between">
                  <span className="grid size-7 place-items-center rounded-full bg-lagoon/12 text-[12px] font-semibold text-lagoon">
                    {step.n}
                  </span>
                  <step.Icon className="size-4 text-muted-foreground" />
                </div>
                <h3 className="mt-3.5 text-[14px] font-semibold">{step.title}</h3>
                <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                  {step.body}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* --- Mesin --- */

function Engine() {
  const items = [
    {
      title: "Angka dihitung, bukan ditaksir",
      body: "Uji validitas, reliabilitas, asumsi klasik, regresi, uji beda, sampai pembacaan output SEM-PLS dijalankan mesin statistik. Nilai r, t, dan F tabel dihitung dari distribusinya — bukan disalin dari lampiran.",
      accent: "from-lagoon/16 to-transparent",
      Icon: FlaskConical,
    },
    {
      title: "Sitasi tertelusur ke sumbernya",
      body: "Metadata hanya diterima dari Crossref, OpenAlex, Semantic Scholar, dan jurnal nasional terakreditasi. Referensi hasil unggahan ditandai jelas sampai berhasil ditelusuri.",
      accent: "from-violet/16 to-transparent",
      Icon: BookOpenCheck,
    },
    {
      title: "Pedoman kampus jadi aturan",
      body: "PDF pedoman dibaca menjadi aturan yang mengikat outline, penomoran, gaya sitasi, dan batas panjang — lengkap dengan kutipan kalimat asal setiap aturan.",
      accent: "from-amber/16 to-transparent",
      Icon: ShieldCheck,
    },
  ];

  return (
    <section id="mesin" className="relative isolate px-5 py-24">
        <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-72 bg-gradient-to-t from-lagoon/[0.07] to-transparent" />
      <div className="mx-auto max-w-6xl">
        <SectionHead eyebrow="Di balik layar" title="Yang bisa dipertanggungjawabkan di sidang">
          Model bahasa menyusun kalimat. Angka, sitasi, dan format datang dari mesin yang bisa
          diperiksa — dan setiap angka pada narasi ditelusuri balik ke hasil perhitungannya.
        </SectionHead>

        <div className="grid gap-4 md:grid-cols-3">
          {items.map((item, index) => (
            <Reveal key={item.title} delay={index * 80}>
              <article className="relative h-full overflow-hidden rounded-xl border border-border bg-card p-6">
                <div
                  aria-hidden
                  className={cn(
                    "pointer-events-none absolute inset-x-0 top-0 h-28 bg-gradient-to-b",
                    item.accent,
                  )}
                />
                <item.Icon className="relative size-5 text-lagoon" />
                <h3 className="relative mt-4 font-serif text-[19px] font-semibold leading-snug">
                  {item.title}
                </h3>
                <p className="relative mt-2.5 text-[13px] leading-relaxed text-muted-foreground">
                  {item.body}
                </p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* --- Batas produk --- */

function Limits() {
  return (
    <section id="batas" className="border-y border-border bg-ink px-5 py-24 text-paper">
      <div className="mx-auto max-w-5xl">
        <Reveal className="mx-auto mb-12 max-w-2xl text-center">
          <p className="text-[12px] font-semibold text-amber">Batas produk</p>
          <h2 className="mt-2 font-serif text-[32px] font-semibold leading-tight tracking-tight sm:text-[38px]">
            Yang tidak akan Recens lakukan
          </h2>
          <p className="mt-3 text-[14px] leading-relaxed text-paper/70">
            Batasan ini melekat pada produk dan tidak dapat dimatikan. Yang ditulis sistem tanpa
            Anda baca tidak akan bisa Anda pertahankan di hadapan penguji.
          </p>
        </Reveal>

        <div className="overflow-hidden rounded-xl border border-paper/15">
          {LIMITS.map(([does, doesNot], index) => (
            <Reveal key={does} delay={index * 60}>
              <div
                className={cn(
                  "grid gap-px sm:grid-cols-2",
                  index > 0 && "border-t border-paper/10",
                )}
              >
                <p className="flex items-start gap-2.5 px-5 py-4 text-[13.5px] leading-relaxed">
                  <Check className="mt-0.5 size-4 shrink-0 text-lagoon" strokeWidth={2.5} />
                  {does}
                </p>
                <p className="flex items-start gap-2.5 border-t border-paper/10 px-5 py-4 text-[13.5px] leading-relaxed text-paper/60 sm:border-l sm:border-t-0">
                  <X className="mt-0.5 size-4 shrink-0 text-clay" strokeWidth={2.5} />
                  {doesNot}
                </p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={200}>
          <p className="mx-auto mt-8 max-w-2xl text-center text-[13px] leading-relaxed text-paper/60">
            Setiap penolakan disertai jalan keluar yang sah — karena di balik permintaan yang
            melanggar biasanya ada kebutuhan yang wajar.
          </p>
        </Reveal>
      </div>
    </section>
  );
}

/* --- Penutup --- */

function Closing({ onEnter }: { onEnter: () => void }) {
  return (
    <section className="relative isolate overflow-hidden px-5 py-28">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="animate-drift absolute left-1/4 top-0 size-[34rem] rounded-full bg-lagoon/28 blur-[120px]" />
        <div
          className="animate-drift absolute right-1/4 bottom-0 size-[28rem] rounded-full bg-amber/26 blur-[120px]"
          style={{ animationDelay: "-9s" }}
        />
      </div>

      <Reveal className="mx-auto max-w-2xl text-center">
        <h2 className="font-serif text-[34px] font-semibold leading-tight tracking-tight sm:text-[42px]">
          Muat aturannya. Kerjakan karyamu.
          <br />
          <span className="text-sheen">Unduh yang formatnya sudah benar.</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-[14px] leading-relaxed text-muted-foreground">
          Berjalan penuh tanpa kunci API: perhitungan statistik, pemeriksaan naskah, perenderan
          sitasi, dan perakitan format semuanya lokal.
        </p>
        <Button size="lg" className="mt-7" onClick={onEnter}>
          Buka ruang kerja <ArrowRight />
        </Button>
      </Reveal>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border px-5 py-8">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 text-[12px] text-muted-foreground">
        <span className="font-serif text-[15px] font-semibold text-foreground">Recens</span>
        <span>AI writing tool untuk seluruh karya tulis ilmiah.</span>
      </div>
    </footer>
  );
}
