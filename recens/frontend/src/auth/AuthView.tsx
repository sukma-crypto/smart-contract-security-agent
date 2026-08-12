import * as React from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  ShieldCheck,
  User,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { UnauthorizedError } from "@/lib/api";
import { MIN_PASSWORD, passwordStrength, useAuth } from "@/lib/auth";
import { Bookshelf, Diploma, Mark, OpenBook, PaperRules } from "@/auth/illustrations";
import { CoffeeCup, DotGrid, GradCap, PaperStack, Pen } from "@/landing/illustrations";

export type AuthMode = "masuk" | "daftar";

/* Delapan langkah, dipakai panel kanan sebagai penanda apa yang akan dimasuki.
   Isinya sama dengan alur produk, bukan hiasan yang dikarang untuk halaman ini. */
const STEPS = [
  "Buat proyek — jenis karya menentukan strukturnya",
  "Muat pedoman kampus jadi aturan yang mengikat",
  "Kumpulkan referensi dari basis data resmi",
  "Susun kerangka lengkap dengan target kata",
  "Menulis dengan sitasi yang tersisip sendiri",
  "Olah data: uji instrumen sampai SEM-PLS",
  "Periksa naskah: PUEBI, sitasi, konsistensi",
  "Ekspor DOCX yang formatnya sudah benar",
];

export function AuthView({
  mode,
  onModeChange,
  onDone,
  onHome,
}: {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  onDone: () => void;
  onHome: () => void;
}) {
  return (
    <div className="min-h-full bg-paper lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <FormSide mode={mode} onModeChange={onModeChange} onDone={onDone} onHome={onHome} />
      <ShowcaseSide mode={mode} />
    </div>
  );
}

/* --- Sisi formulir ---------------------------------------------------------- */

function FormSide({
  mode,
  onModeChange,
  onDone,
  onHome,
}: {
  mode: AuthMode;
  onModeChange: (mode: AuthMode) => void;
  onDone: () => void;
  onHome: () => void;
}) {
  const { login, register } = useAuth();
  const daftar = mode === "daftar";

  const [email, setEmail] = React.useState("");
  const [name, setName] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [visible, setVisible] = React.useState(false);
  const [capsLock, setCapsLock] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const strength = React.useMemo(
    () => (daftar ? passwordStrength(password, email, name) : null),
    [daftar, password, email, name],
  );

  // Pesan galat dari percobaan sebelumnya tidak boleh menempel saat orang
  // berpindah antara masuk dan daftar — isinya sudah tidak relevan.
  React.useEffect(() => {
    setError(null);
  }, [mode]);

  const blocked = daftar && Boolean(strength?.problem);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || blocked) return;
    setBusy(true);
    setError(null);
    try {
      if (daftar) await register({ email, password, display_name: name });
      else await login(email, password);
      onDone();
    } catch (caught) {
      // 401 di sini normal — kata sandi salah — jadi jangan sampai ia memicu
      // penanganan "sesi berakhir" yang dipakai di dalam ruang kerja.
      setError(
        caught instanceof UnauthorizedError || caught instanceof Error
          ? caught.message
          : "Permintaan gagal.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative isolate flex min-h-svh flex-col px-6 py-8 sm:px-10 lg:px-14">
      <PaperRules className="-z-10" />
      <DotGrid className="-z-10 absolute -left-24 top-24 hidden size-64 text-lagoon/10 lg:block" />

      <header className="flex items-center justify-between">
        <button
          onClick={onHome}
          className="flex items-center gap-2.5 rounded transition-opacity hover:opacity-70"
        >
          <Mark />
          <span className="font-serif text-[19px] font-semibold tracking-tight">Recens</span>
        </button>
        <button
          onClick={onHome}
          className="flex items-center gap-1.5 text-[12.5px] text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> Halaman depan
        </button>
      </header>

      <main className="flex flex-1 items-center py-10">
        <div className="w-full max-w-[27rem]">
          <h1 className="animate-rise font-serif text-[32px] font-semibold leading-[1.1] tracking-tight sm:text-[38px]">
            {daftar ? (
              <>
                Mulai naskah <span className="text-sheen">pertama</span> Anda.
              </>
            ) : (
              <>
                Lanjutkan dari <span className="text-sheen">tempat berhenti</span>.
              </>
            )}
          </h1>
          <p
            className="animate-rise mt-3 text-[14px] leading-relaxed text-muted-foreground"
            style={{ animationDelay: "70ms" }}
          >
            {daftar
              ? "Paket coba berisi 200 kredit dan berlaku 14 hari. Seluruh fitur terbuka — yang membedakan paket hanya kuota dan durasinya."
              : "Naskah, referensi, dan jejak analisis Anda tersimpan utuh sejak kunjungan terakhir."}
          </p>

          <form
            onSubmit={submit}
            className="animate-rise mt-8 space-y-4"
            style={{ animationDelay: "140ms" }}
          >
            {daftar ? (
              <FieldRow
                icon={User}
                label="Nama"
                hint="Boleh dikosongkan"
                id="nama"
                value={name}
                onChange={setName}
                autoComplete="name"
                placeholder="Bayu Saputra"
              />
            ) : null}

            <FieldRow
              icon={Mail}
              label="Surel"
              id="surel"
              type="email"
              required
              value={email}
              onChange={setEmail}
              autoComplete="email"
              placeholder="nama@kampus.ac.id"
            />

            <div>
              <FieldRow
                icon={Lock}
                label="Kata sandi"
                id="sandi"
                required
                type={visible ? "text" : "password"}
                value={password}
                onChange={setPassword}
                autoComplete={daftar ? "new-password" : "current-password"}
                placeholder={daftar ? `Minimal ${MIN_PASSWORD} karakter` : "••••••••••"}
                onKeyUp={(event) =>
                  setCapsLock(event.getModifierState?.("CapsLock") ?? false)
                }
                trailing={
                  <button
                    type="button"
                    onClick={() => setVisible((v) => !v)}
                    aria-label={visible ? "Sembunyikan kata sandi" : "Tampilkan kata sandi"}
                    className="grid size-7 place-items-center rounded text-faint transition-colors hover:bg-muted hover:text-foreground"
                  >
                    {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                }
              />
              {capsLock ? (
                <p className="mt-1.5 text-[11.5px] text-warning">Caps Lock sedang menyala.</p>
              ) : null}
              {daftar && strength ? <StrengthMeter strength={strength} /> : null}
            </div>

            {error ? (
              <p
                role="alert"
                className="rule-left border-destructive text-[12.5px] leading-relaxed text-destructive"
              >
                {error}
              </p>
            ) : null}

            <Button type="submit" size="lg" className="w-full" disabled={busy || blocked}>
              {busy ? <Loader2 className="animate-spin" /> : null}
              {daftar ? "Buat akun" : "Masuk"}
              {!busy ? <ArrowRight /> : null}
            </Button>
          </form>

          <p
            className="animate-rise mt-6 text-[13px] text-muted-foreground"
            style={{ animationDelay: "210ms" }}
          >
            {daftar ? "Sudah punya akun? " : "Belum punya akun? "}
            <button
              onClick={() => onModeChange(daftar ? "masuk" : "daftar")}
              className="font-medium text-foreground underline underline-offset-4 transition-colors hover:text-lagoon"
            >
              {daftar ? "Masuk" : "Buat akun"}
            </button>
          </p>

          <p
            className="animate-rise mt-8 flex items-start gap-2 text-[11.5px] leading-relaxed text-faint"
            style={{ animationDelay: "260ms" }}
          >
            <ShieldCheck className="mt-px size-3.5 shrink-0" />
            <span>
              Naskah Anda hanya bisa dibuka oleh akun ini. Kata sandi disimpan dalam bentuk
              teracak dan tidak pernah dapat dibaca kembali — termasuk oleh kami.
            </span>
          </p>
        </div>
      </main>
    </div>
  );
}

/* --- Kolom isian ------------------------------------------------------------ */

function FieldRow({
  icon: Icon,
  label,
  hint,
  id,
  value,
  onChange,
  trailing,
  ...props
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  hint?: string;
  id: string;
  value: string;
  onChange: (value: string) => void;
  trailing?: React.ReactNode;
} & Omit<React.ComponentProps<"input">, "onChange" | "value" | "id">) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-[12.5px] font-medium">
          {label}
        </label>
        {hint ? <span className="text-[11px] text-faint">{hint}</span> : null}
      </div>
      <div className="group relative flex items-center rounded-md border border-input bg-card transition-colors focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/25">
        <Icon className="pointer-events-none absolute left-3 size-4 text-faint transition-colors group-focus-within:text-lagoon" />
        <input
          id={id}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className={cn(
            "h-11 w-full bg-transparent pl-9 text-[14px] outline-none placeholder:text-faint/70",
            trailing ? "pr-11" : "pr-3",
          )}
          {...props}
        />
        {trailing ? <span className="absolute right-2">{trailing}</span> : null}
      </div>
    </div>
  );
}

/* --- Penunjuk kekuatan kata sandi -------------------------------------------
   Empat ruas, bukan angka persen: yang perlu dijawab hanyalah "sudah cukup
   atau belum", dan bila belum, kenapa. */

function StrengthMeter({ strength }: { strength: ReturnType<typeof passwordStrength> }) {
  // Kolom kosong tidak perlu penunjuk: empat ruas abu-abu yang muncul sebelum
  // orang mengetik apa pun hanya terbaca sebagai elemen yang tercecer.
  if (!strength.label) return null;

  const tone = ["bg-destructive", "bg-warning", "bg-amber", "bg-success"][strength.score];
  const filled = Math.max(strength.score, 1);
  return (
    <div className="mt-2.5">
      <div className="flex items-center gap-1.5">
        {[0, 1, 2, 3].map((index) => (
          <span
            key={index}
            className={cn(
              "h-1 flex-1 rounded-full transition-colors duration-300",
              index < filled ? tone : "bg-border",
            )}
          />
        ))}
        <span
          className={cn(
            "ml-1.5 w-[7.5rem] shrink-0 whitespace-nowrap text-right text-[11px] font-medium",
            strength.score === 0 ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {strength.label}
        </span>
      </div>
      {strength.problem ? (
        <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
          {strength.problem}
        </p>
      ) : null}
    </div>
  );
}

/* --- Sisi kanan --------------------------------------------------------------
   Panel gelap berisi meja baca. Ia menjawab satu pertanyaan yang selalu ada di
   halaman masuk: "saya sedang mendaftar ke apa, sebenarnya?" — karena itu
   isinya delapan langkah produk, bukan gambar tanpa keterangan. */

function ShowcaseSide({ mode }: { mode: AuthMode }) {
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return;
    const timer = setInterval(() => setActive((n) => (n + 1) % STEPS.length), 2600);
    return () => clearInterval(timer);
  }, []);

  return (
    <aside
      className="relative isolate hidden overflow-hidden bg-ink px-12 py-14 text-white/90 lg:flex lg:flex-col lg:justify-center"
      /* Panel ini gelap pada kedua tema, sementara ilustrasi memakai
         `hsl(var(--card))` untuk bidang kertasnya. Tanpa penimpaan ini,
         halaman buku ikut menggelap di mode gelap dan bukunya lenyap ditelan
         latar. Menimpa satu variabel di sini lebih baik daripada membuat
         varian gelap untuk tiap ilustrasi. */
      style={{ "--card": "42 30% 97%" } as React.CSSProperties}
    >
      {/* Cahaya latar yang bergeser pelan */}
      <div
        aria-hidden
        className="animate-drift pointer-events-none absolute -right-24 -top-24 -z-10 size-[30rem] rounded-full bg-lagoon/25 blur-3xl"
      />
      <div
        aria-hidden
        className="animate-drift pointer-events-none absolute -bottom-32 -left-20 -z-10 size-[26rem] rounded-full bg-violet/20 blur-3xl"
        style={{ animationDelay: "-7s" }}
      />
      <DotGrid className="-z-10 absolute inset-x-0 top-0 h-40 w-full text-white/10" />

      <div className="mx-auto w-full max-w-[30rem]">
        {/* Meja baca.
            Benda-bendanya berdiri pada satu garis meja agar terbaca sebagai
            satu pemandangan. Susunan sebelumnya menaruh rak di kiri dan
            perkakas di kanan, dan lubang di tengahnya membuat keduanya tampak
            seperti dua gambar yang kebetulan bertetangga. */}
        <div className="relative pb-3">
          {/* Ijazah tergantung di dinding, di belakang segalanya. */}
          <Diploma className="absolute right-0 top-0 w-24 rotate-[7deg] opacity-90" />

          <OpenBook className="relative mx-auto w-[19rem] drop-shadow-[0_20px_46px_rgba(0,0,0,0.5)]" />

          <div className="mt-2 flex items-end justify-between gap-2 px-1">
            <Bookshelf className="w-[11.5rem] shrink-0 opacity-95" />
            <PaperStack className="w-[3.4rem] shrink-0 rotate-3 opacity-90" />
            {/* Tiga benda ini digambar dengan garis tinta gelap. Di atas panel
                gelap garis itu lenyap, jadi warnanya ditimpa di sini — bidang
                datarnya tetap gelap sehingga topi wisuda dan cangkir justru
                terbaca sebagai bentuk padat, bukan sekadar bayangan. */}
            <Pen className="mb-1 w-10 shrink-0 -rotate-12 text-white/75" />
            <CoffeeCup className="w-12 shrink-0 text-white/75" />
            <GradCap className="w-14 shrink-0 text-white/75" />
          </div>
          <div aria-hidden className="mt-1 h-px bg-white/20" />
        </div>

        <p className="mt-9 font-serif text-[22px] leading-snug text-white">
          {mode === "daftar"
            ? "Delapan langkah, dari halaman kosong sampai berkas siap serah."
            : "Ruang kerja Anda menunggu, beserta seluruh jejaknya."}
        </p>

        <ol className="mt-6 space-y-0.5">
          {STEPS.map((step, index) => {
            const current = index === active;
            return (
              <li
                key={step}
                className={cn(
                  "flex items-baseline gap-3 rounded px-2 py-1.5 text-[13px] transition-all duration-500",
                  current ? "bg-white/10 text-white" : "text-white/45",
                )}
              >
                <span
                  className={cn(
                    "tabular grid size-[18px] shrink-0 translate-y-px place-items-center rounded-full text-[10px] font-semibold transition-colors duration-500",
                    current ? "bg-amber text-ink" : "border border-white/25 text-white/50",
                  )}
                >
                  {index < active ? <Check className="size-2.5" strokeWidth={3} /> : index + 1}
                </span>
                <span className="leading-snug">{step}</span>
              </li>
            );
          })}
        </ol>

        <p className="mt-8 border-t border-white/15 pt-5 text-[12px] leading-relaxed text-white/55">
          Recens tidak mengarang data, tidak menulis bab utuh sekali jalan, dan tidak menyusun
          referensi yang tidak ada. Batas itu melekat pada produk dan tidak dapat dimatikan.
        </p>
      </div>
    </aside>
  );
}
