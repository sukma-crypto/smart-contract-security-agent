import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Ilustrasi meja kerja akademik.
 *
 * Semuanya SVG inline dengan satu gaya: garis setebal 1,6 memakai warna teks
 * saat ini, bidang datar berintensitas rendah dari palet. Karena memakai
 * `currentColor` untuk garisnya, ilustrasi ikut berubah saat mode gelap tanpa
 * perlu berkas terpisah — dan karena inline, tidak ada permintaan jaringan
 * tambahan saat halaman dibuka.
 */

type SvgProps = React.SVGProps<SVGSVGElement>;

const stroke = {
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  fill: "none",
};

/* --- Alas laptop ------------------------------------------------------------
   Dipakai di bawah kartu demo agar naskah terbaca sebagai layar laptop. */

export function LaptopBase({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 420 26" className={cn("w-full text-ink/85", className)} {...props}>
      {/* Bidang alas berbentuk trapesium, melebar ke bawah. */}
      <path d="M6 0 H414 L420 20 Q420 26 414 26 H6 Q0 26 0 20 Z" fill="currentColor" />
      {/* Takik pembuka di tengah. */}
      <path d="M186 4 H234 Q236 10 228 10 H192 Q184 10 186 4 Z" fill="hsl(0 0% 100% / 0.16)" />
      {/* Kaki bayangan. */}
      <rect x="70" y="26" width="280" height="3" rx="1.5" fill="currentColor" opacity="0.25" />
    </svg>
  );
}

/* --- Tumpukan buku ---------------------------------------------------------- */

export function BookStack({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 120 96" className={cn("text-ink", className)} aria-hidden {...props}>
      {/* Buku bawah — hijau lagoon */}
      <g>
        <rect x="8" y="70" width="104" height="18" rx="3" fill="var(--color-lagoon)" opacity="0.9" />
        <rect x="8" y="70" width="10" height="18" rx="3" fill="var(--color-ink)" opacity="0.35" />
        <path d="M22 74 H98" {...stroke} strokeWidth={1.2} opacity="0.35" stroke="white" />
        <rect x="8" y="70" width="104" height="18" rx="3" {...stroke} />
      </g>
      {/* Buku tengah — amber */}
      <g>
        <rect x="14" y="52" width="92" height="18" rx="3" fill="var(--color-amber)" opacity="0.92" />
        <rect x="14" y="52" width="9" height="18" rx="3" fill="var(--color-ink)" opacity="0.3" />
        <path d="M27 56 H94" {...stroke} strokeWidth={1.2} opacity="0.4" stroke="white" />
        <rect x="14" y="52" width="92" height="18" rx="3" {...stroke} />
      </g>
      {/* Buku atas — violet */}
      <g>
        <rect x="20" y="34" width="80" height="18" rx="3" fill="var(--color-violet)" opacity="0.85" />
        <rect x="20" y="34" width="8" height="18" rx="3" fill="var(--color-ink)" opacity="0.3" />
        <path d="M32 38 H88" {...stroke} strokeWidth={1.2} opacity="0.4" stroke="white" />
        <rect x="20" y="34" width="80" height="18" rx="3" {...stroke} />
      </g>
      {/* Buku terbuka di puncak */}
      <g>
        <path d="M60 12 Q46 6 30 10 V30 Q46 26 60 32 Q74 26 90 30 V10 Q74 6 60 12 Z" fill="hsl(var(--card))" />
        <path d="M60 12 Q46 6 30 10 V30 Q46 26 60 32 Q74 26 90 30 V10 Q74 6 60 12 Z" {...stroke} />
        <path d="M60 12 V32" {...stroke} />
        <path d="M37 16 H52 M37 21 H50" {...stroke} strokeWidth={1.1} opacity="0.5" />
        <path d="M68 16 H83 M68 21 H81" {...stroke} strokeWidth={1.1} opacity="0.5" />
      </g>
    </svg>
  );
}

/* --- Tumpukan kertas bersitasi ---------------------------------------------- */

export function PaperStack({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 96 104" className={cn("text-ink", className)} aria-hidden {...props}>
      {/* Dua lembar di belakang, sedikit miring. */}
      <rect x="14" y="14" width="64" height="82" rx="4" fill="hsl(var(--card))" transform="rotate(-7 46 55)" />
      <rect x="14" y="14" width="64" height="82" rx="4" {...stroke} transform="rotate(-7 46 55)" opacity="0.5" />
      <rect x="18" y="10" width="64" height="82" rx="4" fill="hsl(var(--card))" transform="rotate(4 50 51)" />
      <rect x="18" y="10" width="64" height="82" rx="4" {...stroke} transform="rotate(4 50 51)" opacity="0.7" />
      {/* Lembar depan */}
      <rect x="16" y="8" width="64" height="84" rx="4" fill="hsl(var(--card))" />
      <rect x="16" y="8" width="64" height="84" rx="4" {...stroke} />
      {/* Baris teks */}
      <path d="M26 24 H70 M26 32 H70 M26 40 H58" {...stroke} strokeWidth={1.2} opacity="0.45" />
      {/* Sitasi yang disorot */}
      <rect x="26" y="48" width="34" height="9" rx="2.5" fill="var(--color-lagoon)" opacity="0.22" />
      <path d="M29 52.5 H57" {...stroke} strokeWidth={1.2} stroke="var(--color-lagoon)" />
      <path d="M26 66 H70 M26 74 H64" {...stroke} strokeWidth={1.2} opacity="0.45" />
    </svg>
  );
}

/* --- Lampu meja -------------------------------------------------------------- */

export function DeskLamp({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 92 120" className={cn("text-ink", className)} aria-hidden {...props}>
      {/* Cahaya */}
      <path d="M30 44 L6 112 H78 L54 44 Z" fill="var(--color-amber)" opacity="0.14" />
      {/* Kap lampu */}
      <path d="M26 44 L44 16 L70 30 L52 52 Z" fill="var(--color-clay)" opacity="0.9" />
      <path d="M26 44 L44 16 L70 30 L52 52 Z" {...stroke} />
      {/* Lengan */}
      <path d="M48 48 L70 74 M70 74 L60 104" {...stroke} strokeWidth={2.2} />
      {/* Alas */}
      <ellipse cx="58" cy="108" rx="20" ry="6" fill="hsl(var(--card))" />
      <ellipse cx="58" cy="108" rx="20" ry="6" {...stroke} />
    </svg>
  );
}

/* --- Cangkir kopi ------------------------------------------------------------ */

export function CoffeeCup({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 72 72" className={cn("text-ink", className)} aria-hidden {...props}>
      {/* Uap */}
      <path d="M26 16 Q30 10 26 4 M36 16 Q40 8 36 2 M46 16 Q50 10 46 4" {...stroke} strokeWidth={1.3} opacity="0.4" />
      {/* Cangkir */}
      <path d="M14 26 H56 V46 Q56 60 42 60 H28 Q14 60 14 46 Z" fill="var(--color-clay)" opacity="0.16" />
      <path d="M14 26 H56 V46 Q56 60 42 60 H28 Q14 60 14 46 Z" {...stroke} />
      {/* Telinga */}
      <path d="M56 32 Q68 32 68 40 Q68 48 56 48" {...stroke} />
      {/* Piring */}
      <path d="M8 64 H62" {...stroke} strokeWidth={2} />
    </svg>
  );
}

/* --- Kaca pembesar di atas jurnal -------------------------------------------- */

export function JournalSearch({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 96 96" className={cn("text-ink", className)} aria-hidden {...props}>
      <rect x="10" y="12" width="60" height="74" rx="4" fill="hsl(var(--card))" />
      <rect x="10" y="12" width="60" height="74" rx="4" {...stroke} />
      <path d="M20 26 H60 M20 34 H60 M20 42 H48" {...stroke} strokeWidth={1.2} opacity="0.45" />
      <path d="M20 62 H52 M20 70 H44" {...stroke} strokeWidth={1.2} opacity="0.45" />
      {/* Lensa */}
      <circle cx="62" cy="54" r="20" fill="var(--color-lagoon)" opacity="0.14" />
      <circle cx="62" cy="54" r="20" {...stroke} strokeWidth={2} />
      <path d="M76 68 L90 82" {...stroke} strokeWidth={3} />
    </svg>
  );
}

/* --- Labu ukur dengan grafik -------------------------------------------------- */

export function DataFlask({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 96 96" className={cn("text-ink", className)} aria-hidden {...props}>
      {/* Labu */}
      <path d="M38 10 V38 L18 76 Q14 86 24 86 H72 Q82 86 78 76 L58 38 V10" {...stroke} />
      <path d="M34 10 H62" {...stroke} strokeWidth={2} />
      {/* Cairan */}
      <path d="M24 60 L72 60 L78 76 Q82 86 72 86 H24 Q14 86 18 76 Z" fill="var(--color-lagoon)" opacity="0.2" />
      {/* Batang grafik di dalam */}
      <rect x="32" y="66" width="8" height="14" rx="1.5" fill="var(--color-lagoon)" opacity="0.85" />
      <rect x="44" y="60" width="8" height="20" rx="1.5" fill="var(--color-amber)" opacity="0.9" />
      <rect x="56" y="70" width="8" height="10" rx="1.5" fill="var(--color-violet)" opacity="0.85" />
      {/* Gelembung */}
      <circle cx="40" cy="50" r="2.4" opacity="0.4" {...stroke} strokeWidth={1.2} />
      <circle cx="54" cy="44" r="1.8" opacity="0.35" {...stroke} strokeWidth={1.2} />
    </svg>
  );
}

/* --- Dokumen tercentang ------------------------------------------------------- */

export function CheckedDoc({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 96 96" className={cn("text-ink", className)} aria-hidden {...props}>
      <path d="M20 8 H58 L76 26 V88 H20 Z" fill="hsl(var(--card))" />
      <path d="M20 8 H58 L76 26 V88 H20 Z" {...stroke} />
      <path d="M58 8 V26 H76" {...stroke} />
      {/* Baris dengan centang */}
      {[40, 54, 68].map((y, index) => (
        <g key={y}>
          <circle
            cx="32"
            cy={y}
            r="5.5"
            fill="var(--color-lagoon)"
            opacity={index === 2 ? 0.18 : 0.85}
          />
          <path
            d={`M29.5 ${y} l2 2 l3.5 -4`}
            stroke={index === 2 ? "var(--color-lagoon)" : "white"}
            strokeWidth={1.7}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
          />
          <path d={`M44 ${y} H66`} {...stroke} strokeWidth={1.3} opacity="0.45" />
        </g>
      ))}
    </svg>
  );
}

/* --- Topi wisuda ------------------------------------------------------------- */

export function GradCap({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 96 72" className={cn("text-ink", className)} aria-hidden {...props}>
      <path d="M48 12 L88 28 L48 44 L8 28 Z" fill="var(--color-ink)" opacity="0.9" />
      <path d="M48 12 L88 28 L48 44 L8 28 Z" {...stroke} />
      <path d="M24 34 V52 Q48 64 72 52 V34" {...stroke} />
      <path d="M88 28 V50" {...stroke} strokeWidth={1.4} />
      <circle cx="88" cy="53" r="3.5" fill="var(--color-amber)" />
    </svg>
  );
}

/* --- Pena ---------------------------------------------------------------------- */

export function Pen({ className, ...props }: SvgProps) {
  return (
    <svg viewBox="0 0 72 72" className={cn("text-ink", className)} aria-hidden {...props}>
      <path d="M14 58 L18 44 L52 10 L62 20 L28 54 Z" fill="var(--color-amber)" opacity="0.28" />
      <path d="M14 58 L18 44 L52 10 L62 20 L28 54 Z" {...stroke} />
      <path d="M18 44 L28 54" {...stroke} />
      <path d="M46 16 L56 26" {...stroke} />
      <path d="M8 64 Q20 60 32 64" {...stroke} strokeWidth={1.3} opacity="0.5" />
    </svg>
  );
}

/* --- Pola latar ---------------------------------------------------------------- */

/** Kisi titik halus — memberi tekstur tanpa menarik perhatian. */
export function DotGrid({ className }: { className?: string }) {
  return (
    <svg className={cn("absolute inset-0 size-full", className)} aria-hidden>
      <defs>
        <pattern id="recens-dots" width="22" height="22" patternUnits="userSpaceOnUse">
          <circle cx="1.5" cy="1.5" r="1.5" fill="currentColor" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#recens-dots)" />
    </svg>
  );
}

/** Garis bergaris seperti kertas folio. */
export function RuledLines({ className }: { className?: string }) {
  return (
    <svg className={cn("absolute inset-0 size-full", className)} aria-hidden>
      <defs>
        <pattern id="recens-ruled" width="100%" height="30" patternUnits="userSpaceOnUse">
          <line x1="0" y1="29.5" x2="100%" y2="29.5" stroke="currentColor" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#recens-ruled)" />
    </svg>
  );
}
