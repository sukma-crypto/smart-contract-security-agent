import * as React from "react";

import App from "@/App";
import { AuthView, type AuthMode } from "@/auth/AuthView";
import { Landing } from "@/landing/Landing";
import { AuthProvider, useAuth } from "@/lib/auth";
import { AppProvider } from "@/lib/store";

/**
 * Tiga wajah, tiga pekerjaan berbeda.
 *
 * Halaman depan menjelaskan dan meyakinkan — di situlah warna dan gerak
 * berguna. Halaman masuk memakai bahasa visual yang sama supaya perpindahannya
 * tidak terasa seperti keluar dari produk. Ruang kerja menemani orang menulis
 * berjam-jam, jadi ia sengaja tenang; menyamakan ketiganya akan merusak salah
 * satunya.
 *
 * Penyedia state aplikasi hanya dipasang di ruang kerja, sehingga halaman depan
 * dan halaman masuk tidak memanggil API proyek sama sekali.
 */
export default function Root() {
  return (
    <AuthProvider>
      <Routes />
    </AuthProvider>
  );
}

function Routes() {
  const [path, setPath] = React.useState(() => window.location.pathname);
  const { account, checking } = useAuth();

  React.useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go = React.useCallback((next: string) => {
    window.history.pushState({}, "", next);
    setPath(next);
    window.scrollTo({ top: 0 });
  }, []);

  const inWorkspace = path.startsWith("/app");
  const onAuthPage = path === "/masuk" || path === "/daftar";

  // Dua pengalihan yang tidak boleh dikerjakan saat render: ruang kerja tanpa
  // akun, dan halaman masuk bagi orang yang sudah masuk. `pushState` adalah
  // efek samping, jadi ia dijalankan di dalam efek — bukan di badan komponen,
  // yang di React mode ketat akan terpanggil dua kali.
  const redirect =
    checking ? null
    : inWorkspace && !account ? "/masuk"
    : onAuthPage && account ? "/app"
    : null;

  React.useEffect(() => {
    if (redirect) go(redirect);
  }, [redirect, go]);

  // Pemeriksaan sesi berlangsung sekejap, tetapi cukup untuk membuat halaman
  // masuk berkedip muncul bagi orang yang sebenarnya sudah masuk. Karena itu
  // hanya halaman yang bergantung pada identitas yang ditahan.
  if (redirect || (checking && (inWorkspace || onAuthPage))) {
    return (
      <div className="grid h-full place-items-center bg-paper text-[13px] text-muted-foreground">
        Memeriksa sesi…
      </div>
    );
  }

  if (onAuthPage) {
    return (
      <AuthView
        mode={path === "/daftar" ? "daftar" : "masuk"}
        onModeChange={(mode: AuthMode) => go(mode === "daftar" ? "/daftar" : "/masuk")}
        onDone={() => go("/app")}
        onHome={() => go("/")}
      />
    );
  }

  if (inWorkspace) {
    // Ruang kerja tidak punya isi tanpa akun: seluruh datanya milik seseorang.
    return (
      <AppProvider>
        <App onExit={() => go("/")} onSignedOut={() => go("/")} />
      </AppProvider>
    );
  }

  return (
    <Landing
      onEnter={() => go(account ? "/app" : "/daftar")}
      onSignIn={() => go("/masuk")}
      signedIn={Boolean(account)}
    />
  );
}
