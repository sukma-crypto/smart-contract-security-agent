import * as React from "react";
import { Check, Gauge, LogOut, Moon, ShieldCheck, Sun, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/display";
import { SimpleSelect } from "@/components/ui/form";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { BookStack } from "@/landing/illustrations";
import { QuoteRotator } from "@/components/ui/quote";
import { useActions, useApp } from "@/lib/store";

import { ProjectView } from "@/views/ProjectView";
import { RulesView } from "@/views/RulesView";
import { ReferencesView } from "@/views/ReferencesView";
import { OutlineView } from "@/views/OutlineView";
import { EditorView } from "@/views/EditorView";
import { DataView } from "@/views/DataView";
import { ChecksView } from "@/views/ChecksView";
import { ExportView } from "@/views/ExportView";
import { DashboardView } from "@/views/DashboardView";
import { LimitsView } from "@/views/LimitsView";
import { AccountView } from "@/views/AccountView";

/**
 * Delapan langkah dikelompokkan menjadi empat fase, dan tiap fase punya
 * warnanya sendiri.
 *
 * Warna di sini bukan hiasan: ia menjawab pertanyaan yang paling sering
 * muncul di kepala orang yang menggarap skripsi berbulan-bulan — "saya
 * sekarang sebenarnya sedang di tahap apa". Empat fase, bukan delapan warna,
 * karena delapan warna berbeda berhenti menjadi informasi dan berubah menjadi
 * pelangi.
 */
const PHASES = [
  { steps: ["buat_proyek", "muat_aturan", "kumpulkan_referensi"], name: "Persiapan", tint: "lagoon" },
  { steps: ["susun_outline", "menulis"], name: "Menyusun naskah", tint: "violet" },
  { steps: ["olah_data", "periksa_naskah"], name: "Data & pemeriksaan", tint: "amber" },
  { steps: ["ekspor_revisi"], name: "Penyelesaian", tint: "clay" },
] as const;

type Tint = (typeof PHASES)[number]["tint"];

const TINT: Record<Tint, { text: string; bg: string; ring: string; solid: string; soft: string }> = {
  lagoon: {
    text: "text-lagoon", bg: "bg-lagoon", ring: "ring-lagoon/30",
    solid: "bg-lagoon text-white", soft: "bg-lagoon/10",
  },
  violet: {
    text: "text-violet", bg: "bg-violet", ring: "ring-violet/30",
    solid: "bg-violet text-white", soft: "bg-violet/10",
  },
  amber: {
    text: "text-amber", bg: "bg-amber", ring: "ring-amber/35",
    solid: "bg-amber text-ink", soft: "bg-amber/12",
  },
  clay: {
    text: "text-clay", bg: "bg-clay", ring: "ring-clay/30",
    solid: "bg-clay text-white", soft: "bg-clay/10",
  },
};

/** Halaman di luar delapan langkah — tidak berada di fase mana pun. */
const SIDE_PAGES: Record<string, { name: string; tint: Tint }> = {
  dashboard: { name: "Ringkasan", tint: "lagoon" },
  limits: { name: "Ketentuan produk", tint: "clay" },
  akun: { name: "Pengaturan", tint: "violet" },
};

export function phaseOf(stepKey: string): { name: string; tint: Tint } {
  const phase = PHASES.find((p) => (p.steps as readonly string[]).includes(stepKey));
  if (phase) return { name: phase.name, tint: phase.tint };
  return SIDE_PAGES[stepKey] ?? { name: PHASES[0].name, tint: PHASES[0].tint };
}

/** Warna langkah yang sedang dibuka — dipakai tampilan lain agar seragam. */
export function tintOf(stepKey: string) {
  return TINT[phaseOf(stepKey).tint];
}

const STEP_VIEWS = [
  "buat_proyek",
  "muat_aturan",
  "kumpulkan_referensi",
  "susun_outline",
  "menulis",
  "olah_data",
  "periksa_naskah",
  "ekspor_revisi",
];

const VIEWS: Record<string, React.ComponentType> = {
  buat_proyek: ProjectView,
  muat_aturan: RulesView,
  kumpulkan_referensi: ReferencesView,
  susun_outline: OutlineView,
  menulis: EditorView,
  olah_data: DataView,
  periksa_naskah: ChecksView,
  ekspor_revisi: ExportView,
  dashboard: DashboardView,
  limits: LimitsView,
  akun: AccountView,
};

/** Langkah mana yang sudah punya isi — dipakai menandai kemajuan di sidebar. */
function useStepState() {
  const { project, manuscript } = useApp();
  return React.useMemo(() => {
    if (!project) return {} as Record<string, boolean>;
    return {
      buat_proyek: true,
      muat_aturan: Boolean(project.active_ruleset),
      kumpulkan_referensi: project.counts.references > 0,
      susun_outline: (manuscript?.sections.length ?? 0) > 0,
      menulis: project.word_count > 0,
      olah_data: project.counts.analyses > 0,
      periksa_naskah: false,
      ekspor_revisi: false,
    };
  }, [project, manuscript]);
}

function useTheme() {
  const [dark, setDark] = React.useState(
    () =>
      localStorage.getItem("recens-theme") === "dark" ||
      (!localStorage.getItem("recens-theme") &&
        window.matchMedia("(prefers-color-scheme: dark)").matches),
  );
  React.useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("recens-theme", dark ? "dark" : "light");
  }, [dark]);
  return { dark, toggle: () => setDark((value) => !value) };
}

export default function App({
  onExit,
  onSignedOut,
}: {
  onExit?: () => void;
  onSignedOut?: () => void;
}) {
  const { catalog, project, projects, view, loading, bootError, toasts, verdict, health } =
    useApp();
  const { setView, openProject, closeProject, dismissToast, dismissVerdict } = useActions();
  const { dark, toggle } = useTheme();
  const done = useStepState();

  if (loading) {
    return (
      <div className="grid h-full place-items-center text-[13px] text-muted-foreground">
        Memuat ruang kerja…
      </div>
    );
  }

  if (bootError || !catalog) {
    return (
      <div className="grid h-full place-items-center p-6">
        <Callout variant="danger" title="Gagal memuat aplikasi" className="max-w-lg">
          {bootError}
        </Callout>
      </div>
    );
  }

  const steps = project?.steps ?? catalog.steps.map((s) => ({ ...s, active: true, note: null }));
  const ViewComponent = VIEWS[view] ?? ProjectView;
  const needsProject = STEP_VIEWS.indexOf(view) > 0 || view === "dashboard";
  const llm = health?.language_model;

  const phase = phaseOf(view);
  const tint = TINT[phase.tint];
  const progress = project?.target_words
    ? Math.min(100, Math.round((project.word_count / project.target_words) * 100))
    : 0;

  return (
    <div className="desk grain flex h-full flex-col bg-background">
      <header className="relative z-10 flex shrink-0 items-center gap-3 px-5 py-3">
        <button
          onClick={onExit}
          className="flex items-baseline gap-2.5 rounded transition-opacity hover:opacity-70"
        >
          <span className="font-serif text-[19px] font-semibold leading-none tracking-tight">
            Recens
          </span>
          <span className="hidden text-[11px] text-faint lg:inline">
            alat menulis karya ilmiah
          </span>
        </button>

        {/* Jumlah kata selalu terlihat. Yang membuat orang bertahan menulis
            berbulan-bulan adalah melihat angkanya bergerak. */}
        {project ? (
          <div className="ml-4 hidden items-center gap-2.5 lg:flex">
            <div className="h-1.5 w-24 overflow-hidden rounded-full bg-border">
              <div
                className={cn("h-full rounded-full transition-all duration-700", tint.bg)}
                style={{ width: `${Math.max(progress, 2)}%` }}
              />
            </div>
            <span className="tabular text-[11.5px] text-muted-foreground">
              {project.word_count.toLocaleString("id-ID")} kata
              {project.target_words ? ` · ${progress}%` : ""}
            </span>
          </div>
        ) : null}

        <div className="flex-1" />
        <SimpleSelect
          className="h-8 w-[min(19rem,44vw)] border-transparent bg-transparent hover:border-input"
          value={project ? String(project.id) : ""}
          placeholder="— pilih proyek —"
          onValueChange={(value) => (value ? openProject(Number(value)) : closeProject())}
          options={projects.map((p) => ({ value: String(p.id), label: p.name }))}
        />
        <span
          title={llm?.note}
          className={cn(
            "hidden text-[11px] md:inline",
            llm?.available ? "text-success" : "text-faint",
          )}
        >
          {llm?.available ? llm.fast_model : "jalur deterministik"}
        </span>
        <button
          onClick={toggle}
          aria-label="Ganti tema"
          className="rounded p-1.5 text-faint transition-colors hover:bg-muted hover:text-foreground"
        >
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
        <AccountMenu onOpenAccount={() => setView("akun")} onSignedOut={onSignedOut} />
      </header>

      <div className="relative z-10 flex min-h-0 flex-1 flex-col md:flex-row">
        {/* Delapan langkah sebagai satu perjalanan bergaris tulang punggung.
            Garisnya menyambungkan penanda satu ke penanda berikutnya, sehingga
            sidebar terbaca sebagai rute, bukan sebagai daftar menu. */}
        <nav className="scrollbar-slim relative flex shrink-0 gap-3 overflow-x-auto px-5 pb-3 md:w-[14.5rem] md:flex-col md:gap-0 md:overflow-y-auto md:px-4 md:pb-8">
          {steps.map((step, index) => {
            const current = view === step.key;
            const complete = done[step.key];
            const stepPhase = phaseOf(step.key);
            const stepTint = TINT[stepPhase.tint];
            const first = index === 0 || phaseOf(steps[index - 1].key).name !== stepPhase.name;

            return (
              <React.Fragment key={step.key}>
                {first ? (
                  <p className="mt-4 hidden pl-[30px] text-[10px] font-medium uppercase tracking-[0.14em] text-faint first:mt-0 md:block">
                    {stepPhase.name}
                  </p>
                ) : null}
                <button
                  onClick={() => setView(step.key)}
                  className={cn(
                    "group relative flex shrink-0 items-start gap-2.5 rounded-lg py-1.5 pl-2 pr-2.5 text-left transition-colors md:w-full",
                    current
                      ? cn(stepTint.soft, "text-foreground")
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    step.active === false && "opacity-45",
                  )}
                >
                  {/* Tulang punggung antar-penanda */}
                  <span
                    aria-hidden
                    className={cn(
                      "absolute left-[15px] top-[26px] hidden h-[calc(100%-18px)] w-px md:block",
                      complete ? stepTint.bg : "bg-border",
                      index === steps.length - 1 && "hidden md:hidden",
                    )}
                  />
                  <span
                    className={cn(
                      "tabular relative z-10 grid size-[18px] shrink-0 translate-y-px place-items-center rounded-full text-[9.5px] font-semibold ring-2 ring-background transition-all",
                      current
                        ? stepTint.solid
                        : complete
                          ? cn(stepTint.solid, "opacity-85")
                          : "border border-border-strong bg-card text-faint",
                    )}
                  >
                    {complete && !current ? (
                      <Check className="size-2.5" strokeWidth={3} />
                    ) : (
                      step.number
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span
                      className={cn(
                        "block whitespace-nowrap text-[12.5px] leading-snug md:whitespace-normal",
                        current && "font-semibold",
                      )}
                    >
                      {step.title}
                    </span>
                    {step.note && current ? (
                      <span className="hidden text-[10.5px] leading-snug text-faint md:block">
                        {step.note}
                      </span>
                    ) : null}
                  </span>
                </button>
              </React.Fragment>
            );
          })}

          <div className="mt-4 hidden h-px bg-border md:mx-2 md:mb-2 md:block" />

          {[
            { key: "dashboard", title: "Progres", Icon: Gauge },
            { key: "limits", title: "Batas produk", Icon: ShieldCheck },
            { key: "akun", title: "Akun", Icon: UserRound },
          ].map(({ key, title, Icon }) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={cn(
                "flex shrink-0 items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-[12.5px] transition-colors md:w-full",
                view === key
                  ? "bg-muted font-semibold text-foreground"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
              )}
            >
              <Icon className="size-3.5 shrink-0 opacity-70" />
              <span className="whitespace-nowrap">{title}</span>
            </button>
          ))}
        </nav>

        {/* Panel kerja sebagai lembar yang terangkat dari mejanya, dengan
            satu garis warna fase di tepi atas — penanda diam yang mengingatkan
            di tahap mana orang sedang bekerja tanpa perlu dibaca. */}
        <main className="scrollbar-slim relative min-w-0 flex-1 overflow-y-auto rounded-tl-2xl border-l border-t border-border bg-paper px-6 pb-24 pt-8 shadow-[-8px_-8px_28px_-20px_rgba(30,25,20,0.25)] md:px-10">
          <span
            aria-hidden
            className={cn(
              "pointer-events-none absolute inset-x-0 top-0 h-[3px] rounded-tl-2xl opacity-80",
              tint.bg,
            )}
          />
          {needsProject && !project ? (
            <EmptyState />
          ) : (
            <div className="mx-auto max-w-[1080px]">
              <ViewComponent />
            </div>
          )}
        </main>
      </div>

      {verdict ? (
        <div className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-2xl rounded-lg border border-destructive/30 bg-card p-4 shadow-xl">
          <p className="text-[13px] font-semibold text-destructive">{verdict.message}</p>
          {verdict.alternative ? (
            <p className="mt-2 text-[12.5px] leading-relaxed text-muted-foreground">
              <span className="font-medium text-foreground">Yang bisa dikerjakan: </span>
              {verdict.alternative}
            </p>
          ) : null}
          <div className="mt-3 flex items-center gap-3">
            <Button variant="outline" size="sm" onClick={dismissVerdict}>
              Mengerti
            </Button>
            <span className="font-mono text-[10.5px] text-faint">{verdict.rule}</span>
          </div>
        </div>
      ) : null}

      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex flex-col items-center gap-2 px-4">
        {toasts.map((item) => (
          <button
            key={item.id}
            onClick={() => dismissToast(item.id)}
            className={cn(
              "pointer-events-auto max-w-xl rounded-md px-3.5 py-2 text-left text-[12.5px] shadow-lg",
              item.tone === "error"
                ? "bg-destructive text-white"
                : "bg-foreground text-background",
            )}
          >
            {item.message}
          </button>
        ))}
      </div>
    </div>
  );
}

function EmptyState() {
  const { setView } = useActions();
  return (
    <div className="mx-auto max-w-md pt-16 text-center">
      <BookStack className="mx-auto w-28 opacity-90" />
      <p className="mt-6 font-serif text-[19px]">Belum ada proyek terbuka.</p>
      <p className="mx-auto mt-2 max-w-[36ch] text-[12.5px] leading-relaxed text-muted-foreground">
        Pilih proyek di kanan atas, atau mulai dari langkah pertama — jenis karya
        yang Anda pilih menentukan struktur bab dan batasnya.
      </p>
      <Button className="mt-6" onClick={() => setView("buat_proyek")}>
        Buat proyek
      </Button>

      <div className="mt-16 border-t border-border pt-10">
        <QuoteRotator tema="waktu" />
      </div>
    </div>
  );
}

/* --- Menu akun -----------------------------------------------------------
   Ditaruh di header, bukan dikubur di sidebar: keluar dari akun harus selalu
   satu klik jauhnya, terutama di komputer bersama. */

function AccountMenu({
  onOpenAccount,
  onSignedOut,
}: {
  onOpenAccount: () => void;
  onSignedOut?: () => void;
}) {
  const { account, logout } = useAuth();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  if (!account) return null;
  const initial = (account.display_name || account.email || "?").trim().charAt(0).toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Menu akun"
        className="grid size-7 place-items-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground transition-opacity hover:opacity-85"
      >
        {initial}
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-9 z-50 w-60 rounded-lg border border-border bg-card p-1.5 shadow-xl"
        >
          <div className="border-b border-border px-2.5 pb-2.5 pt-1.5">
            <p className="truncate text-[12.5px] font-medium">{account.display_name}</p>
            <p className="truncate text-[11px] text-muted-foreground">{account.email}</p>
            <p className="tabular mt-1.5 text-[11px] text-faint">
              Paket {account.plan_detail.label} · {account.credits.toLocaleString("id-ID")} kredit
            </p>
          </div>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onOpenAccount();
            }}
            className="mt-1 flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-[12.5px] transition-colors hover:bg-muted"
          >
            <UserRound className="size-3.5 text-faint" /> Kelola akun
          </button>
          <button
            role="menuitem"
            onClick={async () => {
              setOpen(false);
              await logout();
              onSignedOut?.();
            }}
            className="flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-[12.5px] transition-colors hover:bg-muted"
          >
            <LogOut className="size-3.5 text-faint" /> Keluar
          </button>
        </div>
      ) : null}
    </div>
  );
}
