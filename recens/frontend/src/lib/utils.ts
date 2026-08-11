import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Angka dengan pemisah ribuan gaya Indonesia. */
export function num(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return value.toLocaleString("id-ID", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return `${Math.round(value * 100)}%`;
}
