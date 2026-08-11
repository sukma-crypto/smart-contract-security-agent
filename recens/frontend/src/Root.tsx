import * as React from "react";

import App from "@/App";
import { Landing } from "@/landing/Landing";
import { AppProvider } from "@/lib/store";

/**
 * Dua wajah, dua pekerjaan berbeda.
 *
 * Halaman depan menjelaskan dan meyakinkan — di situlah warna dan gerak
 * berguna. Ruang kerja menemani orang menulis berjam-jam, jadi ia sengaja
 * tenang. Menyamakan keduanya akan merusak salah satunya.
 *
 * Penyedia state aplikasi hanya dipasang di ruang kerja, sehingga halaman
 * depan tidak memanggil API sama sekali dan terbuka seketika.
 */
export default function Root() {
  const [path, setPath] = React.useState(() => window.location.pathname);

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

  if (path.startsWith("/app")) {
    return (
      <AppProvider>
        <App onExit={() => go("/")} />
      </AppProvider>
    );
  }
  return <Landing onEnter={() => go("/app")} />;
}
