import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cva, type VariantProps } from "class-variance-authority";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";

import { cn } from "@/lib/utils";

/* --- Badge --- */

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-tight",
  {
    variants: {
      variant: {
        default: "border-border bg-muted text-muted-foreground",
        success: "border-success/30 bg-success/10 text-success",
        warning: "border-warning/30 bg-warning/10 text-warning",
        danger: "border-destructive/30 bg-destructive/10 text-destructive",
        accent: "border-primary/25 bg-accent text-accent-foreground",
        mono: "border-primary/25 bg-accent font-mono text-accent-foreground",
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

/* --- Callout: catatan, peringatan, dan penolakan --- */

const calloutVariants = cva("rounded-md border px-3.5 py-3 text-[13px]", {
  variants: {
    variant: {
      default: "border-border bg-muted text-foreground",
      success: "border-success/25 bg-success/10 text-foreground",
      warning: "border-warning/30 bg-warning/10 text-foreground",
      danger: "border-destructive/30 bg-destructive/10 text-foreground",
    },
  },
  defaultVariants: { variant: "default" },
});

const calloutIcons = {
  default: Info,
  success: CheckCircle2,
  warning: AlertTriangle,
  danger: XCircle,
} as const;

export function Callout({
  title,
  variant = "default",
  className,
  children,
}: {
  title?: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger";
  className?: string;
  children?: React.ReactNode;
}) {
  const Icon = calloutIcons[variant];
  return (
    <div className={cn(calloutVariants({ variant }), className)}>
      <div className="flex gap-2.5">
        <Icon
          className={cn(
            "mt-0.5 size-4 shrink-0",
            variant === "success" && "text-success",
            variant === "warning" && "text-warning",
            variant === "danger" && "text-destructive",
            variant === "default" && "text-muted-foreground",
          )}
        />
        <div className="min-w-0 flex-1">
          {title ? <div className="mb-0.5 font-semibold">{title}</div> : null}
          {children}
        </div>
      </div>
    </div>
  );
}

/* --- Metric --- */

export function Metric({
  value,
  label,
  hint,
}: {
  value: React.ReactNode;
  label: string;
  hint?: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/60 px-3.5 py-3">
      <div className="tabular text-xl font-semibold leading-tight">{value}</div>
      <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{label}</div>
      {hint ? <div className="mt-1">{hint}</div> : null}
    </div>
  );
}

export function MetricRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(8rem,1fr))] gap-2.5">{children}</div>
  );
}

/* --- Progress --- */

export const Progress = React.forwardRef<
  React.ComponentRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { value?: number }
>(({ className, value = 0, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn("relative h-1.5 w-full overflow-hidden rounded-full bg-border", className)}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full rounded-full bg-primary transition-all"
      style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }}
    />
  </ProgressPrimitive.Root>
));
Progress.displayName = "Progress";

/* --- Tabs --- */

export const Tabs = TabsPrimitive.Root;

export const TabsList = React.forwardRef<
  React.ComponentRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("flex flex-wrap items-center gap-1", className)}
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
      "rounded-md border border-transparent px-3 py-1.5 text-[13px] text-muted-foreground transition-colors hover:bg-muted data-[state=active]:border-border data-[state=active]:bg-card data-[state=active]:font-semibold data-[state=active]:text-foreground",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = TabsPrimitive.Content;

/* --- Table --- */

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
      <div className="scrollbar-slim overflow-x-auto rounded-md border border-border">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-muted/70">
              {columns.map((column, index) => (
                <th
                  key={index}
                  className="border-b border-border px-3 py-2 text-left text-[11px] font-semibold text-muted-foreground"
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
                  className="px-3 py-6 text-center text-muted-foreground"
                >
                  {emptyLabel}
                </td>
              </tr>
            ) : (
              rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-b border-border/60 last:border-0">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 align-top">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {note ? <p className="mt-1.5 text-[11px] text-muted-foreground">{note}</p> : null}
    </div>
  );
}

/* --- Finding: satu temuan pemeriksaan --- */

export function Finding({
  severity = "sedang",
  title,
  children,
  excerpt,
  suggestion,
}: {
  severity?: string;
  title?: React.ReactNode;
  children?: React.ReactNode;
  excerpt?: string;
  suggestion?: string;
}) {
  const border =
    severity === "tinggi"
      ? "border-l-destructive"
      : severity === "rendah"
        ? "border-l-border"
        : "border-l-warning";
  return (
    <div className={cn("mb-1.5 rounded-r-md border-l-[3px] bg-muted/60 px-3 py-2", border)}>
      {title ? <div className="text-[13px] font-medium">{title}</div> : null}
      {children ? <div className="text-[13px]">{children}</div> : null}
      {excerpt ? (
        <p className="mt-1 font-mono text-[11.5px] leading-relaxed text-muted-foreground">
          {excerpt}
        </p>
      ) : null}
      {suggestion ? <p className="mt-1 text-[11.5px] text-primary">→ {suggestion}</p> : null}
    </div>
  );
}

/* --- Empty --- */

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-border px-4 py-8 text-center text-[13px] text-muted-foreground">
      {children}
    </div>
  );
}

export function Pre({ children }: { children: React.ReactNode }) {
  return (
    <pre className="scrollbar-slim max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted/60 p-3 font-mono text-[11.5px] leading-relaxed">
      {children}
    </pre>
  );
}
