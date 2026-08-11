import * as React from "react";
import { Check, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/display";
import { SimpleSelect } from "@/components/ui/form";
import { cn } from "@/lib/utils";
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

export default function App({ onExit }: { onExit?: () => void }) {
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

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="flex shrink-0 items-center gap-3 px-5 py-3">
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
      </header>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <nav className="scrollbar-slim flex shrink-0 gap-4 overflow-x-auto px-5 pb-3 md:w-[13.5rem] md:flex-col md:gap-0 md:overflow-y-auto md:px-5 md:pb-8">
          {steps.map((step) => {
            const current = view === step.key;
            const complete = done[step.key];
            return (
              <button
                key={step.key}
                onClick={() => setView(step.key)}
                className={cn(
                  "group flex shrink-0 items-baseline gap-2.5 py-1.5 text-left transition-colors md:w-full",
                  current ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                  step.active === false && "opacity-45",
                )}
              >
                <span
                  className={cn(
                    "tabular grid size-4 shrink-0 place-items-center rounded-full text-[9.5px] font-semibold transition-colors",
                    current
                      ? "bg-primary text-primary-foreground"
                      : complete
                        ? "bg-success/15 text-success"
                        : "border border-border-strong text-faint",
                  )}
                >
                  {complete && !current ? <Check className="size-2.5" strokeWidth={3} /> : step.number}
                </span>
                <span className="min-w-0">
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
            );
          })}

          <div className="hidden h-px bg-border md:my-3 md:block" />

          {[
            { key: "dashboard", title: "Progres" },
            { key: "limits", title: "Batas produk" },
          ].map(({ key, title }) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={cn(
                "flex shrink-0 items-baseline gap-2.5 py-1.5 text-left text-[12.5px] transition-colors md:w-full md:pl-[26px]",
                view === key
                  ? "font-semibold text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <span className="whitespace-nowrap">{title}</span>
            </button>
          ))}
        </nav>

        <main className="scrollbar-slim min-w-0 flex-1 overflow-y-auto rounded-tl-xl border-l border-t border-border bg-paper px-6 pb-24 pt-7 md:px-10">
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
    <div className="mx-auto max-w-sm pt-20 text-center">
      <p className="font-serif text-[17px]">Belum ada proyek terbuka.</p>
      <p className="mt-1.5 text-[12.5px] text-muted-foreground">
        Pilih proyek di kanan atas, atau mulai dari langkah pertama.
      </p>
      <Button className="mt-5" onClick={() => setView("buat_proyek")}>
        Buat proyek
      </Button>
    </div>
  );
}
