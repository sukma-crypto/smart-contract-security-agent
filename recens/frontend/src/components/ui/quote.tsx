import * as React from "react";
import { Quote as QuoteMark } from "lucide-react";

import { cn } from "@/lib/utils";
import { pickQuotes, type Tema } from "@/lib/quotes";

/**
 * Kutipan yang bergilir di ruang yang memang sedang kosong.
 *
 * Dua hal yang menentukan bentuknya:
 *
 * Pertama, ia hanya boleh muncul di tempat yang tidak sedang dipakai bekerja.
 * Kutipan yang berkedip di sebelah naskah yang sedang diketik bukan motivasi,
 * melainkan gangguan — dan orang yang menulis skripsi sudah cukup terganggu.
 *
 * Kedua, atribusinya ditampilkan apa adanya. Butir bertanda `populer` diberi
 * catatan bahwa sumber aslinya belum dipastikan, karena ini alat tulis ilmiah:
 * ada mahasiswa yang akan menyalin kutipan dari layar ini ke latar belakang
 * skripsinya, dan ia berhak tahu mana yang aman dikutip.
 */
export function QuoteRotator({
  tema,
  interval = 11000,
  className,
  align = "center",
}: {
  /** Batasi ke satu tema agar kutipannya nyambung dengan halamannya. */
  tema?: Tema;
  interval?: number;
  className?: string;
  align?: "center" | "left";
}) {
  // Dipilih sekali per pemasangan: urutannya tetap selama kunjungan, tetapi
  // berbeda tiap kali orang membuka aplikasinya.
  const pool = React.useMemo(() => pickQuotes(12, tema), [tema]);
  const [index, setIndex] = React.useState(0);
  const [leaving, setLeaving] = React.useState(false);

  React.useEffect(() => {
    if (pool.length <= 1) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;

    let swap = 0;
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      setLeaving(true);
      swap = window.setTimeout(() => {
        setIndex((value) => (value + 1) % pool.length);
        setLeaving(false);
      }, 500);
    }, interval);

    return () => {
      window.clearInterval(timer);
      window.clearTimeout(swap);
    };
  }, [pool.length, interval]);

  if (!pool.length) return null;
  const quote = pool[index];

  return (
    <figure
      className={cn(
        "mx-auto max-w-[46ch]",
        align === "center" ? "text-center" : "text-left",
        className,
      )}
    >
      <QuoteMark
        aria-hidden
        className={cn(
          "size-4 text-lagoon/45",
          align === "center" ? "mx-auto" : "",
        )}
      />
      <div
        aria-live="polite"
        className={cn(
          "transition-all duration-500 ease-out",
          leaving ? "translate-y-1.5 opacity-0" : "translate-y-0 opacity-100",
        )}
      >
        <blockquote className="mt-3 font-serif text-[16px] leading-relaxed text-foreground/85">
          {quote.teks}
        </blockquote>
        <figcaption className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground/70">{quote.tokoh}</span>
          <span className="text-faint"> · {quote.peran}</span>
          {quote.konteks ? <span className="text-faint"> · {quote.konteks}</span> : null}
          {quote.sumber === "populer" ? (
            <span
              className="ml-1.5 text-faint"
              title="Sangat luas dikaitkan dengan tokoh ini, tetapi naskah aslinya belum dipastikan. Telusuri sumber primernya sebelum dikutip ke naskah."
            >
              (sumber belum dipastikan)
            </span>
          ) : null}
        </figcaption>
      </div>
    </figure>
  );
}
