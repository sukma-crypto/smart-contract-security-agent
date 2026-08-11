import * as React from "react";
import { Gauge, Moon, ScrollText, Sun, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Callout } from "@/components/ui/display";
import { SimpleSelect } from "@/components/ui/form";
import { cn } from "@/lib/utils";
import { flattenSections, useActions, useApp } from "@/lib/store";

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

export default function App() {
  const { catalog, project, projects, view, loading, bootError, toasts, verdict, health } =
    useApp();
  const { setView, openProject, closeProject, dismissToast, dismissVerdict } = useActions();
  const { dark, toggle } = useTheme();

  if (loading) {
    return (
      <div className="grid h-full place-items-center text-sm text-muted-foreground">
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
    <div className="flex h-full flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b border-border bg-card px-4 py-2.5">
        <div className="flex items-baseline gap-2">
          <h1 className="font-serif text-[21px] font-semibold leading-none tracking-tight">
            Recens
          </h1>
          <span className="hidden text-[11px] text-muted-foreground sm:inline">
            AI writing tool untuk seluruh karya tulis ilmiah
          </span>
        </div>
        <div className="flex-1" />
        <SimpleSelect
          className="w-[min(20rem,45vw)]"
          value={project ? String(project.id) : ""}
          placeholder="— pilih proyek —"
          onValueChange={(value) => (value ? openProject(Number(value)) : closeProject())}
          options={projects.map((p) => ({ value: String(p.id), label: p.name }))}
        />
        <span
          title={llm?.note}
          className={cn(
            "hidden rounded-full border px-2.5 py-1 text-[11px] md:inline",
            llm?.available
              ? "border-success/30 bg-success/10 text-success"
              : "border-warning/30 bg-warning/10 text-warning",
          )}
        >
          {llm?.available ? `model: ${llm.fast_model}` : "jalur deterministik"}
        </span>
        <Button variant="ghost" size="icon" onClick={toggle} aria-label="Ganti tema">
          {dark ? <Sun /> : <Moon />}
        </Button>
      </header>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <nav className="scrollbar-slim flex shrink-0 gap-1 overflow-x-auto border-b border-border bg-card p-2 md:w-60 md:flex-col md:overflow-y-auto md:border-b-0 md:border-r md:p-3">
          <p className="hidden px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground md:block">
            Alur kerja
          </p>
          {steps.map((step) => (
            <button
              key={step.key}
              onClick={() => setView(step.key)}
              className={cn(
                "flex shrink-0 items-start gap-2.5 rounded-md px-2.5 py-2 text-left transition-colors md:w-full",
                view === step.key
                  ? "bg-accent font-semibold text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted",
                step.active === false && "opacity-50",
              )}
            >
              <span
                className={cn(
                  "mt-px grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-semibold",
                  view === step.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-border text-muted-foreground",
                )}
              >
                {step.number}
              </span>
              <span className="min-w-0">
                <span className="block whitespace-nowrap text-[13px] md:whitespace-normal">
                  {step.title}
                </span>
                {step.note ? (
                  <span className="hidden text-[10.5px] font-normal leading-snug text-muted-foreground md:block">
                    {step.note}
                  </span>
                ) : null}
                {step.active === false ? (
                  <span className="hidden text-[10.5px] font-normal text-muted-foreground md:block">
                    opsional untuk karya ini
                  </span>
                ) : null}
              </span>
            </button>
          ))}

          <p className="hidden px-2 pb-1.5 pt-3 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground md:block">
            Ringkasan
          </p>
          {[
            { key: "dashboard", title: "Dashboard progres", Icon: Gauge },
            { key: "limits", title: "Batas produk", Icon: ScrollText },
          ].map(({ key, title, Icon }) => (
            <button
              key={key}
              onClick={() => setView(key)}
              className={cn(
                "flex shrink-0 items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13px] transition-colors md:w-full",
                view === key
                  ? "bg-accent font-semibold text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              <Icon className="size-4 shrink-0" />
              <span className="whitespace-nowrap">{title}</span>
            </button>
          ))}
        </nav>

        <main className="scrollbar-slim min-w-0 flex-1 overflow-y-auto px-5 pb-16 pt-5 md:px-7">
          {needsProject && !project ? (
            <Empty />
          ) : (
            <div className="mx-auto max-w-[1120px]">
              <ViewComponent />
            </div>
          )}
        </main>
      </div>

      {verdict ? (
        <div className="fixed inset-x-4 bottom-4 z-50 mx-auto max-w-2xl">
          <Callout variant="danger" title={`Batas produk: ${verdict.rule}`}>
            <p>{verdict.message}</p>
            {verdict.alternative ? (
              <p className="mt-2">
                <span className="font-semibold">Yang bisa dikerjakan: </span>
                {verdict.alternative}
              </p>
            ) : null}
            <Button variant="outline" size="sm" className="mt-3" onClick={dismissVerdict}>
              Tutup
            </Button>
          </Callout>
        </div>
      ) : null}

      <div className="pointer-events-none fixed inset-x-0 bottom-5 z-50 flex flex-col items-center gap-2 px-4">
        {toasts.map((item) => (
          <button
            key={item.id}
            onClick={() => dismissToast(item.id)}
            className={cn(
              "pointer-events-auto flex max-w-xl items-start gap-2 rounded-md px-3.5 py-2.5 text-left text-[13px] shadow-lg",
              item.tone === "error"
                ? "bg-destructive text-destructive-foreground"
                : "bg-foreground text-background",
            )}
          >
            <span className="flex-1">{item.message}</span>
            <X className="mt-0.5 size-3.5 shrink-0 opacity-70" />
          </button>
        ))}
      </div>
    </div>
  );
}

function Empty() {
  const { setView } = useActions();
  return (
    <div className="mx-auto max-w-md pt-16 text-center">
      <p className="text-[13px] text-muted-foreground">
        Pilih atau buat proyek lebih dahulu di langkah 1.
      </p>
      <Button className="mt-4" onClick={() => setView("buat_proyek")}>
        Ke langkah 1
      </Button>
    </div>
  );
}

export { flattenSections };
