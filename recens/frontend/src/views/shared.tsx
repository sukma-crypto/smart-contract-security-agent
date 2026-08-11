import * as React from "react";

/** Judul halaman beserta kalimat penjelasnya. */
export function PageHeader({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h2 className="font-serif text-[22px] font-semibold leading-tight">{title}</h2>
      {children ? (
        <p className="mt-1 max-w-3xl text-[13px] text-muted-foreground">{children}</p>
      ) : null}
    </div>
  );
}

/** Baris kontrol yang membungkus rapi pada layar sempit. */
export function Row({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <div className={`flex flex-wrap items-end gap-2.5 ${className}`}>{children}</div>;
}

/** Jalankan aksi async sambil menampilkan status memuat pada tombolnya. */
export function useBusy() {
  const [busy, setBusy] = React.useState<string | null>(null);
  const withBusy = React.useCallback(
    async (key: string, work: () => Promise<unknown>) => {
      setBusy(key);
      try {
        await work();
      } finally {
        setBusy(null);
      }
    },
    [],
  );
  return { busy, withBusy, isBusy: (key: string) => busy === key };
}

export function titleOf(entry: { title?: string | string[] } | undefined): string {
  if (!entry?.title) return "(tanpa judul)";
  return Array.isArray(entry.title) ? (entry.title[0] ?? "") : entry.title;
}

export function containerOf(
  entry: { "container-title"?: string | string[] } | undefined,
): string {
  const value = entry?.["container-title"];
  if (!value) return "";
  return Array.isArray(value) ? (value[0] ?? "") : value;
}

export function yearOf(entry: { issued?: { "date-parts": number[][] } } | undefined): string {
  const parts = entry?.issued?.["date-parts"];
  const year = parts?.[0]?.[0];
  return year ? String(year) : "t.t.";
}

export function authorsOf(
  entry: { author?: { family?: string; given?: string; literal?: string }[] } | undefined,
): string {
  const names = (entry?.author ?? [])
    .map((a) => a.family || a.literal || "")
    .filter(Boolean);
  return names.length ? names.join(", ") : "—";
}

/** Ubah nilai sel tabel apa pun menjadi teks yang aman ditampilkan. */
export function cellText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
