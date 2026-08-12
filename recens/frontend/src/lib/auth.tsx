import * as React from "react";

import { api, setUnauthorizedHandler } from "@/lib/api";

export interface Account {
  id: number;
  email: string;
  display_name: string;
  plan: string;
  credits: number;
  valid_until: string | null;
  expired: boolean;
  project_count: number;
  created_at: string;
  plan_detail: {
    key: string;
    label: string;
    suitable_for: string;
    credits: number;
    duration_days: number | null;
    project_limit: number | null;
    watermark: boolean;
    feature_access: string;
  };
}

export interface SessionInfo {
  id: number;
  user_agent: string;
  ip: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  current: boolean;
}

interface AuthValue {
  account: Account | null;
  /** Benar selama pemeriksaan sesi pertama; dipakai menahan layar agar tidak berkedip. */
  checking: boolean;
  login: (email: string, password: string) => Promise<Account>;
  register: (input: { email: string; password: string; display_name?: string }) => Promise<Account>;
  logout: () => Promise<void>;
  setAccount: (account: Account | null) => void;
  refresh: () => Promise<void>;
}

const AuthContext = React.createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = React.useState<Account | null>(null);
  const [checking, setChecking] = React.useState(true);

  React.useEffect(() => {
    // Sesi berumur 30 hari, jadi orang yang kembali besok tidak perlu masuk
    // lagi. Kukinya tidak terbaca JavaScript, sehingga satu-satunya cara
    // mengetahui masih masuk atau tidak adalah menanyakannya ke server.
    (async () => {
      try {
        setAccount(await api.get<Account>("/auth/me"));
      } catch {
        setAccount(null);
      } finally {
        setChecking(false);
      }
    })();
  }, []);

  React.useEffect(() => {
    // Sesi bisa berakhir di tengah pekerjaan. Saat itu terjadi, keadaan lokal
    // dikosongkan supaya antarmuka langsung menawarkan halaman masuk alih-alih
    // memunculkan galat berulang di tiap permintaan berikutnya.
    setUnauthorizedHandler(() => setAccount(null));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = React.useCallback(async (email: string, password: string) => {
    const result = await api.post<{ account: Account }>("/auth/login", { email, password });
    setAccount(result.account);
    return result.account;
  }, []);

  const register = React.useCallback(
    async (input: { email: string; password: string; display_name?: string }) => {
      const result = await api.post<{ account: Account }>("/auth/register", input);
      setAccount(result.account);
      return result.account;
    },
    [],
  );

  const logout = React.useCallback(async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAccount(null);
    }
  }, []);

  const refresh = React.useCallback(async () => {
    try {
      setAccount(await api.get<Account>("/auth/me"));
    } catch {
      setAccount(null);
    }
  }, []);

  const value = React.useMemo<AuthValue>(
    () => ({ account, checking, login, register, logout, setAccount, refresh }),
    [account, checking, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error("useAuth harus dipakai di dalam AuthProvider.");
  return context;
}

/* --- Kekuatan kata sandi ----------------------------------------------------
   Aturannya sengaja dibuat sama persis dengan yang ditegakkan server di
   `core/auth.py`. Ukuran yang berbeda antara keduanya akan menghasilkan hal
   paling menjengkelkan di halaman pendaftaran: penunjuk hijau, lalu ditolak. */

export const MIN_PASSWORD = 10;

const COMMON = new Set([
  "password", "password123", "qwerty123", "12345678", "123456789", "1234567890",
  "indonesia", "indonesia1", "adminadmin", "administrator", "iloveyou",
  "sayangkamu", "namasaya", "rahasia123", "katasandi",
  "skripsi123", "mahasiswa", "mahasiswa123", "universitas", "recens123",
]);

export interface Strength {
  /** 0 tidak layak, 1 lemah, 2 cukup, 3 kuat. */
  score: 0 | 1 | 2 | 3;
  label: string;
  /** Alasan penolakan bila ada — kalimat yang sama dengan yang dipakai server. */
  problem: string | null;
}

export function passwordStrength(password: string, email = "", name = ""): Strength {
  if (!password) return { score: 0, label: "", problem: null };

  const folded = password.toLowerCase();
  const local = email.split("@")[0]?.toLowerCase() ?? "";

  let problem: string | null = null;
  if (password.length < MIN_PASSWORD) {
    problem = `Kata sandi minimal ${MIN_PASSWORD} karakter. Kalimat pendek yang mudah Anda ingat — misalnya tiga kata yang tidak berhubungan — lebih aman daripada satu kata dengan angka di ujungnya.`;
  } else if (COMMON.has(folded)) {
    problem = "Kata sandi ini termasuk yang paling sering dipakai. Pilih yang lain.";
  } else if (new Set(folded).size <= 3) {
    problem = "Kata sandi terlalu berulang. Tambahkan kata lain.";
  } else if (
    [local, name.toLowerCase()].some((piece) => piece.length >= 4 && folded.includes(piece))
  ) {
    problem = "Kata sandi sebaiknya tidak memuat nama atau surel Anda sendiri.";
  }

  if (problem) return { score: 0, label: "Belum memenuhi", problem };

  // Yang dihargai panjang dan keragaman kata, bukan campuran simbol: "tiga
  // kata acak" lebih sulit ditebak daripada "Skripsi2024!" meski terlihat
  // lebih sederhana.
  const words = password.trim().split(/\s+/).filter(Boolean).length;
  const variety = new Set(folded).size;
  const points = password.length / 8 + words / 2 + variety / 10;

  if (points >= 3.4) return { score: 3, label: "Kuat", problem: null };
  if (points >= 2.4) return { score: 2, label: "Cukup", problem: null };
  return { score: 1, label: "Lemah", problem: null };
}
