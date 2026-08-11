import * as React from "react";

/** Muncul saat elemen masuk layar — dipakai untuk reveal saat digulir. */
export function useReveal<T extends HTMLElement = HTMLDivElement>() {
  const ref = React.useRef<T>(null);
  const [shown, setShown] = React.useState(false);

  React.useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.05 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return { ref, shown };
}

export interface Segment {
  /** Teks yang diketik huruf demi huruf. */
  text?: string;
  /** Potongan yang muncul sekaligus, mis. sitasi yang tersisip. */
  chip?: string;
  /** Jeda sebelum potongan berikutnya, dalam milidetik. */
  pause?: number;
}

export interface TypedPart {
  kind: "text" | "chip";
  value: string;
  done: boolean;
}

/**
 * Mengetik urutan potongan.
 *
 * Berbeda dari animasi mengetik biasa: sebagian potongan bukan huruf yang
 * mengalir melainkan sitasi yang muncul utuh, karena begitulah cara Recens
 * bekerja — sitasi tidak diketik pengguna, ia disisipkan dari pustaka.
 */
export function useTypewriter(segments: Segment[], speed = 26, startDelay = 500) {
  const [parts, setParts] = React.useState<TypedPart[]>([]);
  const [finished, setFinished] = React.useState(false);

  React.useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    if (reduced) {
      setParts(
        segments.map((segment) => ({
          kind: segment.chip ? "chip" : "text",
          value: segment.chip ?? segment.text ?? "",
          done: true,
        })),
      );
      setFinished(true);
      return;
    }

    let cancelled = false;
    const timers: number[] = [];
    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        timers.push(window.setTimeout(resolve, ms));
      });

    (async () => {
      await wait(startDelay);
      for (const segment of segments) {
        if (cancelled) return;

        if (segment.chip) {
          setParts((prev) => [...prev, { kind: "chip", value: segment.chip!, done: true }]);
          await wait(segment.pause ?? 420);
          continue;
        }

        const text = segment.text ?? "";
        setParts((prev) => [...prev, { kind: "text", value: "", done: false }]);
        for (let index = 1; index <= text.length; index += 1) {
          if (cancelled) return;
          setParts((prev) => {
            const next = [...prev];
            next[next.length - 1] = {
              kind: "text",
              value: text.slice(0, index),
              done: index === text.length,
            };
            return next;
          });
          // Jeda sedikit lebih panjang setelah tanda baca supaya terasa wajar.
          const char = text[index - 1];
          await wait(/[.,;:]/.test(char) ? speed * 6 : speed);
        }
        await wait(segment.pause ?? 120);
      }
      if (!cancelled) setFinished(true);
    })();

    return () => {
      cancelled = true;
      timers.forEach(window.clearTimeout);
    };
  }, [segments, speed, startDelay]);

  return { parts, finished };
}

/** Angka yang menghitung naik saat masuk layar. */
export function useCountUp(target: number, shown: boolean, duration = 1100) {
  const [value, setValue] = React.useState(0);

  React.useEffect(() => {
    if (!shown) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      // easeOutCubic
      setValue(Math.round(target * (1 - Math.pow(1 - progress, 3))));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, shown, duration]);

  return value;
}
