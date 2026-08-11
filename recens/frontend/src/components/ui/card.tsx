import * as React from "react";
import { cn } from "@/lib/utils";

/* Panel: pembungkus netral tanpa gaya judul yang memaksa.
   Judul ditulis sebagai heading sungguhan dengan kontras ukuran dan bobot,
   bukan label kapital ber-tracking — kebiasaan yang membuat setiap panel
   terlihat sama pentingnya padahal tidak. */

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-lg border border-border bg-card", className)}
      {...props}
    />
  ),
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col gap-1 px-5 pb-3 pt-4", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-[15px] font-semibold leading-snug", className)} {...props} />
  ),
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("max-w-2xl text-[12.5px] leading-relaxed text-muted-foreground", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-5 pb-5", className)} {...props} />
  ),
);
CardContent.displayName = "CardContent";

/** Bagian tanpa bingkai — dipakai ketika isinya sudah punya bentuk sendiri. */
export function Section({
  title,
  description,
  action,
  className,
  children,
}: {
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn("mb-9", className)}>
      {title || action ? (
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3 border-b border-border pb-2">
          <div className="min-w-0">
            {title ? <h3 className="text-[15px] font-semibold leading-snug">{title}</h3> : null}
            {description ? (
              <p className="mt-0.5 max-w-2xl text-[12.5px] leading-relaxed text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export { Card, CardHeader, CardTitle, CardDescription, CardContent };
