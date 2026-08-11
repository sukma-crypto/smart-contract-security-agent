import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Ilustrasi khusus halaman masuk.
 *
 * Bahasanya sama dengan `landing/illustrations.tsx` — garis 1,6 memakai
 * `currentColor`, bidang datar dari palet — tetapi bendanya sengaja berbeda.
 * Halaman masuk yang mengulang persis pemandangan halaman depan terasa seperti
 * halaman yang gagal berpindah.
 */

type SvgProps = React.SVGProps<SVGSVGElement>;

const stroke = {
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  fill: "none",
};

/* --- Rak buku perpustakaan --------------------------------------------------
   Punggung buku dengan tinggi dan warna berbeda-beda; deretannya sengaja tidak
   rapi supaya terbaca sebagai rak yang dipakai, bukan pola berulang. */

const SPINES: { w: number; h: number; fill: string; tilt?: boolean }[] = [
  { w: 12, h: 62, fill: "var(--color-lagoon)" },
  { w: 9, h: 54, fill: "var(--color-amber)" },
  { w: 14, h: 66, fill: "var(--color-violet)" },
  { w: 8, h: 48, fill: "var(--color-clay)" },
  { w: 11, h: 60, fill: "var(--color-lagoon)" },
  { w: 13, h: 52, fill: "var(--color-amber)", tilt: true },
];

export function Bookshelf({ className, ...props }: SvgProps) {
  let x = 14;
  return (
    <svg viewBox="0 0 180 108" className={cn("text-ink", className)} aria-hidden {...props}>
      {SPINES.map((spine, index) => {
        const left = x;
        x += spine.w + 3;
        const top = 84 - spine.h;
        return (
          <g
            key={index}
            transform={spine.tilt ? `rotate(9 ${left + spine.w / 2} 84)` : undefined}
          >
            <rect
              x={left}
              y={top}
              width={spine.w}
              height={spine.h}
              rx="2"
              fill={spine.fill}
              opacity="0.88"
            />
            <rect x={left} y={top} width={spine.w} height={spine.h} rx="2" {...stroke} />
            {/* Dua pita label pada punggung buku. */}
            <path
              d={`M${left + 2} ${top + 10} H${left + spine.w - 2}`}
              {...stroke}
              strokeWidth={1.1}
              stroke="white"
              opacity="0.5"
            />
            <path
              d={`M${left + 2} ${top + spine.h - 12} H${left + spine.w - 2}`}
              {...stroke}
              strokeWidth={1.1}
              stroke="white"
              opacity="0.35"
            />
          </g>
        );
      })}

      {/* Beberapa buku direbahkan di ujung kanan, seperti rak sungguhan. */}
      <g>
        <rect x="120" y="70" width="46" height="7" rx="2" fill="var(--color-violet)" opacity="0.8" />
        <rect x="120" y="70" width="46" height="7" rx="2" {...stroke} />
        <rect x="124" y="77" width="42" height="7" rx="2" fill="var(--color-lagoon)" opacity="0.8" />
        <rect x="124" y="77" width="42" height="7" rx="2" {...stroke} />
      </g>

      {/* Papan rak */}
      <path d="M6 84 H174" {...stroke} strokeWidth={2.4} />
      <path d="M12 88 V96 M168 88 V96" {...stroke} strokeWidth={2} opacity="0.6" />
    </svg>
  );
}

/* --- Buku terbuka dengan pembatas -------------------------------------------
   Anchor utama panel kanan: sebuah halaman yang sedang dibaca. */

export function OpenBook({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 160 108" className={cn("text-ink", className)} aria-hidden {...props}>
      {/* Bayangan lembut di bawah buku */}
      <ellipse cx="80" cy="100" rx="58" ry="5" fill="currentColor" opacity="0.14" />

      {/* Dua halaman terbuka, bertemu di punggung */}
      <path d="M80 24 Q52 12 16 20 V88 Q52 80 80 92 Z" fill="hsl(var(--card))" />
      <path d="M80 24 Q108 12 144 20 V88 Q108 80 80 92 Z" fill="hsl(var(--card))" />
      <path d="M80 24 Q52 12 16 20 V88 Q52 80 80 92 Z" {...stroke} />
      <path d="M80 24 Q108 12 144 20 V88 Q108 80 80 92 Z" {...stroke} />
      <path d="M80 24 V92" {...stroke} />

      {/* Baris teks kiri */}
      <path d="M26 34 H68 M26 42 H68 M26 50 H60" {...stroke} strokeWidth={1.2} opacity="0.4" />
      {/* Sitasi tersorot di halaman kiri — perkara utama produknya */}
      <rect x="26" y="56" width="30" height="8" rx="2" fill="var(--color-lagoon)" opacity="0.22" />
      <path d="M29 60 H53" {...stroke} strokeWidth={1.2} stroke="var(--color-lagoon)" />
      <path d="M26 70 H68" {...stroke} strokeWidth={1.2} opacity="0.4" />

      {/* Baris teks kanan */}
      <path d="M92 34 H134 M92 42 H134 M92 50 H134 M92 58 H120" {...stroke} strokeWidth={1.2} opacity="0.4" />
      {/* Tabel kecil: hasil uji statistik */}
      <rect x="92" y="64" width="42" height="14" rx="2" {...stroke} strokeWidth={1.2} opacity="0.55" />
      <path d="M92 71 H134 M113 64 V78" {...stroke} strokeWidth={1} opacity="0.4" />

      {/* Pembatas kain */}
      <path d="M80 24 V64 L74 58 L68 64 V24" fill="var(--color-clay)" opacity="0.9" />
      <path d="M80 24 V64 L74 58 L68 64 V24" {...stroke} strokeWidth={1.2} />
    </svg>
  );
}

/* --- Gulungan ijazah ---------------------------------------------------------
   Diletakkan kecil di sudut; penanda tujuan akhirnya. */

export function Diploma({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 96 56" className={cn("text-ink", className)} aria-hidden {...props}>
      <rect x="14" y="10" width="68" height="36" rx="3" fill="hsl(var(--card))" />
      <rect x="14" y="10" width="68" height="36" rx="3" {...stroke} />
      <path d="M24 22 H62 M24 29 H58 M24 36 H48" {...stroke} strokeWidth={1.2} opacity="0.45" />
      {/* Gulungan di kedua ujung */}
      <rect x="8" y="6" width="8" height="44" rx="4" fill="var(--color-lagoon)" opacity="0.9" />
      <rect x="8" y="6" width="8" height="44" rx="4" {...stroke} />
      <rect x="80" y="6" width="8" height="44" rx="4" fill="var(--color-lagoon)" opacity="0.9" />
      <rect x="80" y="6" width="8" height="44" rx="4" {...stroke} />
      {/* Meterai */}
      <circle cx="68" cy="38" r="7" fill="var(--color-amber)" opacity="0.9" />
      <circle cx="68" cy="38" r="7" {...stroke} strokeWidth={1.2} />
      <path d="M68 34.5 L69.2 37 L71.8 37.3 L69.9 39.1 L70.4 41.7 L68 40.4 L65.6 41.7 L66.1 39.1 L64.2 37.3 L66.8 37 Z" fill="white" opacity="0.85" />
    </svg>
  );
}

/* --- Latar bergaris ----------------------------------------------------------
   Kertas bergaris di belakang formulir.

   Harus sangat samar. Percobaan pertama memakai garis setebal 1px pada warna
   border penuh, dan hasilnya terbaca sebagai tabel, bukan kertas — yang di
   layar besar justru membuat formulir tampak seperti baris spreadsheet. Yang
   dipakai sekarang: garis berjarak lebih lebar, hanya 40% intensitas border,
   diredam di keempat sisinya, plus satu garis tepi merah bata seperti buku
   tulis. Garis tepi itulah yang sebenarnya membuat permukaannya terbaca
   sebagai kertas; garis mendatarnya cukup terasa, tidak perlu terlihat. */

export function PaperRules({ className }: { className?: string }) {
  const fade = "linear-gradient(to bottom, transparent, black 22%, black 70%, transparent)";
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0", className)}>
      <div
        className="absolute inset-0"
        style={{
          backgroundImage:
            "repeating-linear-gradient(to bottom, transparent 0 35px, hsl(var(--border) / 0.4) 35px 36px)",
          maskImage: fade,
          WebkitMaskImage: fade,
        }}
      />
      <div
        className="absolute inset-y-0 left-6 w-px bg-clay/15 sm:left-10 lg:left-14"
        style={{ maskImage: fade, WebkitMaskImage: fade }}
      />
    </div>
  );
}

/* --- Lencana Recens ---------------------------------------------------------- */

export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("size-9", className)} aria-hidden>
      <rect width="40" height="40" rx="10" fill="var(--color-ink)" />
      <path d="M11 29 V13 Q11 11 13 11 H22 Q28 11 28 16.5 Q28 21 23 21.8 L29 29" {...stroke} stroke="white" strokeWidth={2.4} />
      <circle cx="30" cy="12" r="3.4" fill="var(--color-amber)" />
    </svg>
  );
}
