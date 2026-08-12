import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/* --- Badge -----------------------------------------------------------------
   Penanda kecil dengan warna yang menyampaikan status, bukan hiasan. */

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded px-1.5 py-px text-[11px] font-medium leading-[1.5]",
  {
    variants: {
      variant: {
        default: "bg-muted text-muted-foreground",
        outline: "border border-border text-muted-foreground",
        success: "bg-success/12 text-success",
        warning: "bg-warning/12 text-warning",
        danger: "bg-destructive/12 text-destructive",
        accent: "bg-accent text-accent-foreground",
        mono: "bg-accent font-mono text-[10.5px] text-accent-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

/* --- Callout ---------------------------------------------------------------
   Tanpa ikon dan tanpa latar penuh: hanya garis tepi berwarna. Kotak berlatar
   yang bertumpuk membuat semua pesan terasa sama mendesaknya. */

const calloutTone = {
  default: "border-border-strong",
  success: "border-success",
  warning: "border-warning",
  danger: "border-destructive",
} as const;

export function Callout({
  title,
  variant = "default",
  className,
  children,
}: {
  title?: React.ReactNode;
  variant?: keyof typeof calloutTone;
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={cn("rule-left py-1", calloutTone[variant], className)}>
      {title ? (
        <p
          className={cn(
            "text-[13px] font-semibold leading-snug",
            variant === "success" && "text-success",
            variant === "warning" && "text-warning",
            variant === "danger" && "text-destructive",
          )}
        >
          {title}
        </p>
      ) : null}
      {children ? (
        <div className="text-[12.5px] leading-relaxed text-muted-foreground [&_p+p]:mt-1">
          {children}
        </div>
      ) : null}
    </div>
  );
}

/* --- Statistik -------------------------------------------------------------
   Dua bentuk: baris angka sebaris untuk konteks, dan kartu hanya ketika
   perbandingan antarangka memang jadi maksudnya (dashboard). */

export function StatLine({
  items,
  className,
}: {
  items: { label: string; value: React.ReactNode; tone?: "default" | "warning" | "danger" }[];
  className?: string;
}) {
  return (
    <dl className={cn("flex flex-wrap items-baseline gap-x-6 gap-y-1.5", className)}>
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline gap-1.5">
          <dd
            className={cn(
              "tabular text-[15px] font-semibold leading-none",
              item.tone === "warning" && "text-warning",
              item.tone === "danger" && "text-destructive",
            )}
          >
            {item.value}
          </dd>
          <dt className="text-[11.5px] text-muted-foreground">{item.label}</dt>
        </div>
      ))}
    </dl>
  );
}

const METRIC_TONE = {
  default: "border-border-strong",
  lagoon: "border-lagoon",
  amber: "border-amber",
  violet: "border-violet",
  clay: "border-clay",
  success: "border-success",
} as const;

export function Metric({
  value,
  label,
  hint,
  tone = "default",
}: {
  value: React.ReactNode;
  label: string;
  hint?: React.ReactNode;
  tone?: keyof typeof METRIC_TONE;
}) {
  return (
    <div className={cn("border-l-2 pl-3", METRIC_TONE[tone])}>
      <div className="tabular text-[24px] font-semibold leading-none">{value}</div>
      <div className="mt-1.5 text-[11.5px] leading-snug text-muted-foreground">{label}</div>
      {hint ? <div className="mt-1">{hint}</div> : null}
    </div>
  );
}

/** Lencana status bab: warnanya menyatakan keadaan, bukan sekadar membingkai teks. */
const STATUS_TONE: Record<string, string> = {
  belum: "bg-muted text-muted-foreground",
  draf: "bg-amber/15 text-warning",
  selesai: "bg-success/15 text-success",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-medium capitalize",
        STATUS_TONE[status] ?? STATUS_TONE.belum,
      )}
    >
      {status}
    </span>
  );
}

export function MetricRow({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid min-w-0 flex-1 grid-cols-[repeat(auto-fit,minmax(7.5rem,1fr))] gap-x-6 gap-y-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

/* --- Progress --- */

/**
 * Bilah kemajuan yang warnanya ikut berubah seiring isinya.
 *
 * Versi sebelumnya setinggi 1px berwarna abu-abu, dan pada tabel kerangka bab
 * ia praktis tidak terlihat — padahal justru kolom itulah yang paling ingin
 * dilihat orang yang sedang menggarap naskahnya. Warnanya berpindah dari clay
 * (baru mulai) ke amber (separuh jalan) ke hijau (mendekati target), sehingga
 * satu sapuan mata sudah cukup untuk tahu bab mana yang tertinggal.
 */
export const Progress = React.forwardRef<
  React.ComponentRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { value?: number }
>(({ className, value = 0, ...props }, ref) => {
  const pct = Math.min(Math.max(value, 0), 100);
  const tone = pct >= 85 ? "bg-success" : pct >= 40 ? "bg-amber" : pct > 0 ? "bg-clay" : "bg-border";
  return (
    <ProgressPrimitive.Root
      ref={ref}
      className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-border/70", className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn("h-full rounded-full transition-all duration-700", tone)}
        style={{ width: `${pct}%` }}
      />
    </ProgressPrimitive.Root>
  );
});
Progress.displayName = "Progress";

/* --- Tabs --- */

export const Tabs = TabsPrimitive.Root;

export const TabsList = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("flex flex-wrap items-center gap-5 border-b border-border", className)}
    {...props}
  />
));
TabsList.displayName = "TabsList";

export const TabsTrigger = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "-mb-px border-b-2 border-transparent pb-2 text-[13px] text-muted-foreground transition-colors hover:text-foreground data-[state=active]:border-primary data-[state=active]:font-semibold data-[state=active]:text-foreground",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = TabsPrimitive.Content;

/* --- Tabel -----------------------------------------------------------------
   Bergaris horizontal saja, seperti tabel pada naskah ilmiah. */

export function DataTable({
  columns,
  rows,
  note,
  className,
  emptyLabel = "Belum ada data.",
}: {
  columns: React.ReactNode[];
  rows: React.ReactNode[][];
  note?: React.ReactNode;
  className?: string;
  emptyLabel?: string;
}) {
  return (
    <div className={className}>
      <div className="scrollbar-slim overflow-x-auto">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th
                  key={index}
                  className="whitespace-nowrap border-b border-border-strong px-3 pb-2 pt-0 text-left text-[10.5px] font-semibold uppercase tracking-[0.06em] text-muted-foreground first:pl-0"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length || 1}
                  className="px-2.5 py-6 text-center text-muted-foreground"
                >
                  {emptyLabel}
                </td>
              </tr>
            ) : (
              // Baris diberi nafas dan sorot saat disentuh. Tabel hasil
              // statistik dibaca menyilang — mata menyusuri satu baris dari
              // kolom pertama sampai terakhir — dan tanpa sorot, baris yang
              // sedang dibaca gampang lompat pada tabel dua belas kolom.
              rows.map((row, rowIndex) => (
                <tr
                  key={rowIndex}
                  className="border-b border-border transition-colors last:border-0 hover:bg-muted/60"
                >
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 align-top first:pl-0">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {note ? (
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{note}</p>
      ) : null}
    </div>
  );
}

/* --- Temuan ----------------------------------------------------------------
   Ditulis seperti catatan tepi pembimbing: aturan yang dilanggar, kutipan
   naskahnya, lalu usulan perbaikan. Tanpa latar, supaya daftar panjang tetap
   enak dibaca. */

export function Finding({
  severity = "sedang",
  title,
  children,
  excerpt,
  suggestion,
  where,
}: {
  severity?: string;
  title?: React.ReactNode;
  children?: React.ReactNode;
  excerpt?: string;
  suggestion?: string;
  where?: string;
}) {
  const tone =
    severity === "tinggi"
      ? "border-destructive"
      : severity === "rendah"
        ? "border-border-strong"
        : "border-warning";
  return (
    <div className={cn("rule-left py-2", tone)}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        {title ? <span className="text-[13px] leading-snug">{title}</span> : null}
        {children ? <span className="text-[13px] leading-snug">{children}</span> : null}
        {where ? <span className="text-[11px] text-faint">{where}</span> : null}
      </div>
      {excerpt ? (
        <p className="mt-1 font-mono text-[11px] leading-relaxed text-muted-foreground">
          {excerpt}
        </p>
      ) : null}
      {suggestion ? (
        <p className="mt-1 text-[12px] text-primary">
          <span className="text-faint">→ </span>
          {suggestion}
        </p>
      ) : null}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <p className="py-6 text-[12.5px] text-muted-foreground">{children}</p>;
}

export function Pre({ children }: { children: React.ReactNode }) {
  return (
    <pre className="scrollbar-slim measure max-h-80 overflow-auto whitespace-pre-wrap break-words border-l-2 border-border py-1 pl-3.5 font-mono text-[11.5px] leading-relaxed text-muted-foreground">
      {children}
    </pre>
  );
}
