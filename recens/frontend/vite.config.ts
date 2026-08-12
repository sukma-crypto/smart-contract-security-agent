import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Hasil build masuk ke recens/web/ dan ikut di-commit, sehingga `python -m recens`
// tetap berjalan tanpa Node. FastAPI menyajikan index.html di "/" dan aset di
// "/static", karena itu base disetel ke /static/.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/",
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  build: {
    outDir: "../web",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    // Saat `npm run dev`, API tetap diambil dari server FastAPI.
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
