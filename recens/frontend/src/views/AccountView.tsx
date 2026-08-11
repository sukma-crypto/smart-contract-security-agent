import * as React from "react";
import {
  Check,
  Coins,
  LogOut,
  Monitor,
  Smartphone,
  TriangleAlert,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Section } from "@/components/ui/card";
import { Callout } from "@/components/ui/display";
import { Field, Input } from "@/components/ui/form";
import { api } from "@/lib/api";
import { passwordStrength, useAuth, type SessionInfo } from "@/lib/auth";
import { useActions, useApp } from "@/lib/store";
import { cn } from "@/lib/utils";
import { PageHeader, Row, useBusy } from "@/views/shared";

export function AccountView() {
  const { account, refresh, logout } = useAuth();
  const { toast, run } = useActions();
  const [sessions, setSessions] = React.useState<SessionInfo[] | null>(null);

  const loadSessions = React.useCallback(async () => {
    await run(async () => setSessions(await api.get<SessionInfo[]>("/auth/sessions")));
  }, [run]);

  React.useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  if (!account) return null;

  return (
    <>
      <PageHeader title="Akun">
        Profil, kata sandi, perangkat yang sedang masuk, dan paket berjalan. Naskah Anda hanya
        bisa dibuka lewat akun ini.
      </PageHeader>

      <div className="space-y-9">
        <PlanPanel />
        <ProfilePanel onSaved={refresh} onToast={toast} />
        <PasswordPanel onToast={toast} onChanged={loadSessions} />
        <SessionsPanel sessions={sessions} onChanged={loadSessions} onToast={toast} />
        <DangerPanel onDeleted={logout} onToast={toast} />
      </div>
    </>
  );
}

/* --- Paket berjalan ---------------------------------------------------------- */

function PlanPanel() {
  const { account } = useAuth();
  if (!account) return null;
  const plan = account.plan_detail;

  return (
    <Section title="Paket berjalan">
      <div className="flex flex-wrap items-end gap-x-10 gap-y-5">
        <div>
          <p className="font-serif text-[24px] font-semibold leading-none">{plan.label}</p>
          <p className="mt-1.5 text-[12px] text-muted-foreground">{plan.suitable_for}</p>
        </div>
        <div className="flex items-baseline gap-2">
          <Coins className="size-4 translate-y-0.5 text-amber" />
          <span className="tabular font-serif text-[24px] font-semibold leading-none">
            {account.credits.toLocaleString("id-ID")}
          </span>
          <span className="text-[12px] text-muted-foreground">kredit tersisa</span>
        </div>
        {account.valid_until ? (
          <div>
            <p
              className={cn(
                "tabular text-[15px] font-medium leading-none",
                account.expired && "text-destructive",
              )}
            >
              {new Date(account.valid_until).toLocaleDateString("id-ID", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </p>
            <p className="mt-1.5 text-[12px] text-muted-foreground">
              {account.expired ? "masa berlaku berakhir" : "berlaku sampai"}
            </p>
          </div>
        ) : null}
        <div>
          <p className="tabular text-[15px] font-medium leading-none">
            {account.project_count}
            {plan.project_limit ? ` / ${plan.project_limit}` : ""}
          </p>
          <p className="mt-1.5 text-[12px] text-muted-foreground">proyek</p>
        </div>
      </div>

      <p className="mt-5 rule-left border-lagoon/40 text-[12px] leading-relaxed text-muted-foreground">
        {plan.feature_access} Yang membedakan paket adalah kuota dan durasinya, bukan fiturnya —
        analisis data, pemeriksaan naskah, auto-format, dan ekspor berjalan lokal dan tidak
        menagih kredit sama sekali.
      </p>

      {account.expired ? (
        <Callout variant="warning" title="Masa berlaku berakhir" className="mt-5">
          Naskah dan data Anda tetap tersimpan dan bisa diekspor. Yang berhenti hanyalah fitur
          yang memakai kredit.
        </Callout>
      ) : null}
    </Section>
  );
}

/* --- Profil ------------------------------------------------------------------ */

function ProfilePanel({
  onSaved,
  onToast,
}: {
  onSaved: () => Promise<void>;
  onToast: (message: string, tone?: "default" | "error") => void;
}) {
  const { account } = useAuth();
  const { busy, withBusy } = useBusy();
  const [name, setName] = React.useState(account?.display_name ?? "");
  const [email, setEmail] = React.useState(account?.email ?? "");

  const changed = name !== account?.display_name || email !== account?.email;

  async function save() {
    await withBusy("simpan", async () => {
      try {
        await api.patch("/auth/me", { display_name: name, email });
        await onSaved();
        onToast("Profil tersimpan.");
      } catch (error) {
        onToast(error instanceof Error ? error.message : "Gagal menyimpan.", "error");
      }
    });
  }

  return (
    <Section title="Profil">
      <Row>
        <Field label="Nama tampilan" htmlFor="akun-nama" className="w-64">
          <Input id="akun-nama" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Surel" htmlFor="akun-surel" className="w-72">
          <Input
            id="akun-surel"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        <Button onClick={save} disabled={!changed} loading={busy === "simpan"}>
          Simpan
        </Button>
      </Row>
      <p className="mt-2.5 text-[11.5px] text-muted-foreground">
        Surel inilah yang dipakai untuk masuk. Menggantinya berlaku mulai sesi berikutnya.
      </p>
    </Section>
  );
}

/* --- Kata sandi -------------------------------------------------------------- */

function PasswordPanel({
  onToast,
  onChanged,
}: {
  onToast: (message: string, tone?: "default" | "error") => void;
  onChanged: () => Promise<void>;
}) {
  const { account } = useAuth();
  const { busy, withBusy } = useBusy();
  const [current, setCurrent] = React.useState("");
  const [next, setNext] = React.useState("");

  const strength = React.useMemo(
    () => passwordStrength(next, account?.email ?? "", account?.display_name ?? ""),
    [next, account],
  );
  const ready = current.length > 0 && next.length > 0 && !strength.problem;

  async function change() {
    await withBusy("ganti", async () => {
      try {
        const result = await api.post<{ note: string }>("/auth/me/password", {
          current_password: current,
          new_password: next,
          logout_other_sessions: true,
        });
        setCurrent("");
        setNext("");
        await onChanged();
        onToast(result.note);
      } catch (error) {
        onToast(error instanceof Error ? error.message : "Gagal mengganti.", "error");
      }
    });
  }

  return (
    <Section
      title="Kata sandi"
      description="Perangkat lain yang sedang masuk otomatis dikeluarkan setelah kata sandi diganti."
    >
      <Row>
        <Field label="Kata sandi saat ini" htmlFor="sandi-lama" className="w-60">
          <Input
            id="sandi-lama"
            type="password"
            autoComplete="current-password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        </Field>
        <Field label="Kata sandi baru" htmlFor="sandi-baru" className="w-60">
          <Input
            id="sandi-baru"
            type="password"
            autoComplete="new-password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
          />
        </Field>
        <Button onClick={change} disabled={!ready} loading={busy === "ganti"}>
          Ganti kata sandi
        </Button>
      </Row>
      {next && strength.problem ? (
        <p className="mt-3 max-w-[62ch] text-[11.5px] leading-relaxed text-muted-foreground">
          {strength.problem}
        </p>
      ) : null}
      {next && !strength.problem ? (
        <p className="mt-3 flex items-center gap-1.5 text-[11.5px] text-success">
          <Check className="size-3.5" /> {strength.label}
        </p>
      ) : null}
    </Section>
  );
}

/* --- Sesi aktif --------------------------------------------------------------
   Halaman ini punya satu tugas praktis: memberi jalan keluar bagi orang yang
   lupa keluar dari komputer perpustakaan. Karena itu tiap baris menyebut
   perangkat dan kapan terakhir dipakai, bukan sekadar nomor sesi. */

function SessionsPanel({
  sessions,
  onChanged,
  onToast,
}: {
  sessions: SessionInfo[] | null;
  onChanged: () => Promise<void>;
  onToast: (message: string, tone?: "default" | "error") => void;
}) {
  const { busy, withBusy } = useBusy();

  async function revoke(session: SessionInfo) {
    await withBusy(`cabut-${session.id}`, async () => {
      try {
        await api.del(`/auth/sessions/${session.id}`);
        await onChanged();
        onToast("Perangkat dikeluarkan.");
      } catch (error) {
        onToast(error instanceof Error ? error.message : "Gagal mencabut.", "error");
      }
    });
  }

  return (
    <Section title="Perangkat yang sedang masuk">
      {sessions === null ? (
        <p className="text-[12.5px] text-muted-foreground">Memuat…</p>
      ) : (
        <ul className="divide-y divide-border">
          {sessions.map((session) => {
            const mobile = /mobile|android|iphone|ipad/i.test(session.user_agent);
            const Icon = mobile ? Smartphone : Monitor;
            return (
              <li key={session.id} className="flex items-center gap-4 py-3">
                <Icon className="size-4 shrink-0 text-faint" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12.5px]">
                    {describeAgent(session.user_agent)}
                    {session.current ? (
                      <span className="ml-2 rounded bg-success/12 px-1.5 py-0.5 text-[10.5px] font-medium text-success">
                        perangkat ini
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 text-[11px] text-faint">
                    Terakhir dipakai {relativeTime(session.last_seen_at)}
                    {session.ip ? ` · ${session.ip}` : ""}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => revoke(session)}
                  loading={busy === `cabut-${session.id}`}
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                >
                  <LogOut className="size-3.5" />
                  {session.current ? "Keluar" : "Cabut"}
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function describeAgent(agent: string): string {
  if (!agent) return "Perangkat tidak dikenal";
  const browser =
    /edg\//i.test(agent) ? "Edge"
    : /chrome|crios/i.test(agent) ? "Chrome"
    : /firefox|fxios/i.test(agent) ? "Firefox"
    : /safari/i.test(agent) ? "Safari"
    : "Peramban lain";
  const system =
    /windows/i.test(agent) ? "Windows"
    : /android/i.test(agent) ? "Android"
    : /iphone|ipad|ios/i.test(agent) ? "iOS"
    : /mac os/i.test(agent) ? "macOS"
    : /linux/i.test(agent) ? "Linux"
    : "";
  return system ? `${browser} di ${system}` : browser;
}

function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 90) return "baru saja";
  if (seconds < 3600) return `${Math.round(seconds / 60)} menit lalu`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} jam lalu`;
  return `${Math.round(seconds / 86400)} hari lalu`;
}

/* --- Zona bahaya --------------------------------------------------------------
   Yang hilang di sini adalah naskah berbulan-bulan, dan belum ada cadangan yang
   bisa memulihkannya. Karena itu penghapusan menuntut kata sandi dan ketikan
   ulang surel — dan panelnya tertutup sampai sengaja dibuka. */

function DangerPanel({
  onDeleted,
  onToast,
}: {
  onDeleted: () => Promise<void>;
  onToast: (message: string, tone?: "default" | "error") => void;
}) {
  const { account } = useAuth();
  const { projects } = useApp();
  const { busy, withBusy } = useBusy();
  const [open, setOpen] = React.useState(false);
  const [password, setPassword] = React.useState("");
  const [confirm, setConfirm] = React.useState("");

  const ready =
    password.length > 0 && confirm.trim().toLowerCase() === (account?.email ?? "").toLowerCase();

  async function remove() {
    await withBusy("hapus", async () => {
      try {
        await api.del("/auth/me", { password, confirm });
        await onDeleted();
      } catch (error) {
        onToast(error instanceof Error ? error.message : "Gagal menghapus.", "error");
      }
    });
  }

  return (
    <Section title="Hapus akun">
      {!open ? (
        <div className="flex flex-wrap items-center gap-4">
          <p className="max-w-[52ch] text-[12.5px] leading-relaxed text-muted-foreground">
            Menghapus akun ikut menghapus{" "}
            <strong className="font-medium text-foreground">
              {projects.length} proyek
            </strong>{" "}
            beserta seluruh naskah, referensi, data penelitian, dan riwayat versinya. Tidak ada
            cadangan yang bisa memulihkannya.
          </p>
          <Button variant="outline" onClick={() => setOpen(true)}>
            Saya ingin menghapus akun
          </Button>
        </div>
      ) : (
        <div className="rounded-lg border border-destructive/30 bg-destructive/[0.04] p-5">
          <p className="flex items-start gap-2 text-[12.5px] font-medium text-destructive">
            <TriangleAlert className="mt-px size-4 shrink-0" />
            Ekspor naskah Anda lebih dahulu bila masih dibutuhkan. Langkah ini tidak bisa
            dibatalkan.
          </p>
          <Row className="mt-4">
            <Field label="Kata sandi" htmlFor="hapus-sandi" className="w-56">
              <Input
                id="hapus-sandi"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Field>
            <Field
              label="Ketik ulang surel akun ini"
              htmlFor="hapus-surel"
              className="w-72"
              hint={account?.email}
            >
              <Input
                id="hapus-surel"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder={account?.email}
              />
            </Field>
            <Button
              variant="destructive"
              onClick={remove}
              disabled={!ready}
              loading={busy === "hapus"}
            >
              Hapus akun selamanya
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Batal
            </Button>
          </Row>
        </div>
      )}
    </Section>
  );
}
