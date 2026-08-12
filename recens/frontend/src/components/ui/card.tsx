import * as React from "react";
import { cn } from "@/lib/utils";

/* Panel: pembungkus netral tanpa gaya judul yang memaksa.
   Judul ditulis sebagai heading sungguhan dengan kontras ukuran dan bobot,
   bukan label kapital ber-tracking — kebiasaan yang membuat setiap panel
   terlihat sama pentingnya padahal tidak.

   Kartunya memakai `sheet`: bayangan lembut alih-alih garis tepi tegas,
   sehingga panel terbaca sebagai kertas yang terangkat dari mejanya. Garis
   tepi tunggal di atas latar seputih isinya membuat seluruh halaman rata dan
   tidak punya titik pandang. */

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      /* Naik sedikit saat disentuh. Bukan hiasan: pada halaman berisi enam
         kartu, gerak sekecil ini yang memberi tahu mana yang sedang ditunjuk
         tanpa perlu garis sorot yang meramaikan bidang. */
      className={cn(
        "sheet transition-shadow duration-200",
        "hover:shadow-[0_1px_2px_hsl(30_20%_20%/0.05),0_14px_34px_-16px_hsl(30_24%_18%/0.26)]",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col gap-1 px-6 pb-3.5 pt-5", className)} {...props} />
  ),
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn(
        "font-serif text-[17px] font-semibold leading-snug tracking-[-0.005em]",
        className,
      )}
      {...props}
    />
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
    <div ref={ref} className={cn("px-6 pb-6", className)} {...props} />
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
            {title ? (
              <h3 className="flex items-baseline gap-2 font-serif text-[17px] font-semibold leading-snug tracking-[-0.005em]">
                <span aria-hidden className="h-3 w-[3px] shrink-0 translate-y-px rounded-full bg-lagoon/70" />
                {title}
              </h3>
            ) : null}
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
