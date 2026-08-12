/** Lapisan pemanggilan API Recens. */

export interface GuardrailVerdict {
  error: string;
  rule: string;
  message: string;
  alternative: string;
}

/** Penolakan batas produk dibawa utuh agar antarmuka bisa menawarkan jalan yang sah. */
export class GuardrailError extends Error {
  verdict: GuardrailVerdict;
  constructor(verdict: GuardrailVerdict) {
    super(verdict.message);
    this.name = "GuardrailError";
    this.verdict = verdict;
  }
}

/** Sesi habis atau belum ada. Dibedakan agar antarmuka bisa mengantar ke halaman masuk. */
export class UnauthorizedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "UnauthorizedError";
  }
}

/**
 * Dipanggil sekali saat permintaan mana pun dijawab 401.
 *
 * Sesi bisa berakhir di tengah pekerjaan — kedaluwarsa, atau dicabut dari
 * perangkat lain. Tanpa kait ini, layar hanya menampilkan pesan galat dan
 * orang tidak tahu bahwa yang perlu dilakukan hanyalah masuk kembali.
 */
let onUnauthorized: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const config: RequestInit = { ...options, headers: { ...(options.headers ?? {}) } };
  if (config.body && !(config.body instanceof FormData)) {
    (config.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const response = await fetch(`/api${path}`, config);
  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload?.detail ?? payload;
    if (detail && typeof detail === "object" && detail.error === "batas_produk") {
      throw new GuardrailError(detail as GuardrailVerdict);
    }
    const message =
      typeof detail === "string" ? detail : (detail?.message ?? "Permintaan gagal.");
    if (response.status === 401) {
      onUnauthorized?.();
      throw new UnauthorizedError(message);
    }
    throw new Error(message);
  }
  return payload as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "DELETE", body: body ? JSON.stringify(body) : undefined }),
  upload: <T,>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),
};
