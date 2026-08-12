import * as React from "react";

import { api, GuardrailError, type GuardrailVerdict } from "@/lib/api";
import type { Catalog, Health, Manuscript, Project, ProjectSummary } from "@/lib/types";

interface Toast {
  id: number;
  message: string;
  tone: "default" | "error";
}

interface AppState {
  catalog: Catalog | null;
  health: Health | null;
  projects: ProjectSummary[];
  project: Project | null;
  manuscript: Manuscript | null;
  view: string;
  loading: boolean;
  bootError: string | null;
  toasts: Toast[];
  /** Penolakan batas produk yang sedang ditampilkan. */
  verdict: GuardrailVerdict | null;
}

interface AppActions {
  setView: (view: string) => void;
  openProject: (id: number) => Promise<void>;
  refreshProject: () => Promise<void>;
  reloadProjects: () => Promise<void>;
  closeProject: () => void;
  toast: (message: string, tone?: "default" | "error") => void;
  dismissToast: (id: number) => void;
  dismissVerdict: () => void;
  /** Bungkus pemanggilan API: kegagalan biasa jadi toast, penolakan batas jadi panel. */
  run: <T,>(work: () => Promise<T>) => Promise<T | undefined>;
}

const StateContext = React.createContext<AppState | null>(null);
const ActionsContext = React.createContext<AppActions | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<AppState>({
    catalog: null,
    health: null,
    projects: [],
    project: null,
    manuscript: null,
    view: "buat_proyek",
    loading: true,
    bootError: null,
    toasts: [],
    verdict: null,
  });

  const toastId = React.useRef(0);

  const toast = React.useCallback((message: string, tone: "default" | "error" = "default") => {
    const id = ++toastId.current;
    setState((prev) => ({ ...prev, toasts: [...prev.toasts, { id, message, tone }] }));
    setTimeout(
      () => setState((prev) => ({ ...prev, toasts: prev.toasts.filter((t) => t.id !== id) })),
      tone === "error" ? 7000 : 3500,
    );
  }, []);

  const dismissToast = React.useCallback((id: number) => {
    setState((prev) => ({ ...prev, toasts: prev.toasts.filter((t) => t.id !== id) }));
  }, []);

  const run = React.useCallback(
    async <T,>(work: () => Promise<T>): Promise<T | undefined> => {
      try {
        return await work();
      } catch (error) {
        if (error instanceof GuardrailError) {
          setState((prev) => ({ ...prev, verdict: error.verdict }));
        } else {
          toast(error instanceof Error ? error.message : "Permintaan gagal.", "error");
        }
        return undefined;
      }
    },
    [toast],
  );

  const loadProject = React.useCallback(async (id: number) => {
    const [project, manuscript] = await Promise.all([
      api.get<Project>(`/projects/${id}`),
      api.get<Manuscript>(`/projects/${id}/manuscript`),
    ]);
    setState((prev) => ({ ...prev, project, manuscript }));
  }, []);

  const openProject = React.useCallback(
    async (id: number) => {
      await run(() => loadProject(id));
    },
    [loadProject, run],
  );

  const refreshProject = React.useCallback(async () => {
    setState((current) => {
      if (current.project) void run(() => loadProject(current.project!.id));
      return current;
    });
  }, [loadProject, run]);

  const reloadProjects = React.useCallback(async () => {
    await run(async () => {
      const projects = await api.get<ProjectSummary[]>("/projects");
      setState((prev) => ({ ...prev, projects }));
    });
  }, [run]);

  const setView = React.useCallback((view: string) => {
    setState((prev) => ({ ...prev, view }));
  }, []);

  const closeProject = React.useCallback(() => {
    setState((prev) => ({ ...prev, project: null, manuscript: null }));
  }, []);

  const dismissVerdict = React.useCallback(() => {
    setState((prev) => ({ ...prev, verdict: null }));
  }, []);

  React.useEffect(() => {
    (async () => {
      try {
        const [catalog, projects, health] = await Promise.all([
          api.get<Catalog>("/catalog"),
          api.get<ProjectSummary[]>("/projects"),
          api.get<Health>("/health"),
        ]);
        setState((prev) => ({ ...prev, catalog, projects, health, loading: false }));
        if (projects.length) await loadProject(projects[0].id);
      } catch (error) {
        setState((prev) => ({
          ...prev,
          loading: false,
          bootError: error instanceof Error ? error.message : "Gagal memuat aplikasi.",
        }));
      }
    })();
  }, [loadProject]);

  const actions = React.useMemo<AppActions>(
    () => ({
      setView,
      openProject,
      refreshProject,
      reloadProjects,
      closeProject,
      toast,
      dismissToast,
      dismissVerdict,
      run,
    }),
    [
      setView,
      openProject,
      refreshProject,
      reloadProjects,
      closeProject,
      toast,
      dismissToast,
      dismissVerdict,
      run,
    ],
  );

  return (
    <StateContext.Provider value={state}>
      <ActionsContext.Provider value={actions}>{children}</ActionsContext.Provider>
    </StateContext.Provider>
  );
}

export function useApp(): AppState {
  const context = React.useContext(StateContext);
  if (!context) throw new Error("useApp harus dipakai di dalam AppProvider.");
  return context;
}

export function useActions(): AppActions {
  const context = React.useContext(ActionsContext);
  if (!context) throw new Error("useActions harus dipakai di dalam AppProvider.");
  return context;
}

/** Ratakan pohon bagian menjadi daftar berurutan. */
export function flattenSections<T extends { children: T[] }>(sections: T[], out: T[] = []): T[] {
  for (const section of sections) {
    out.push(section);
    flattenSections(section.children, out);
  }
  return out;
}
