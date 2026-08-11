# Yang belum jadi

Catatan serah-terima untuk melanjutkan Recens. Disusun setelah audit kode, bukan
dari ingatan.

**Ringkasnya:** mesin produknya sudah jadi dan terverifikasi — 275 pengujian
lulus, alur delapan langkah berjalan dari buat proyek sampai ekspor DOCX, dan
tiap proyek kini terkunci ke pemiliknya. Yang belum ada adalah sisa **lapisan
layanan**: hal-hal yang mengubah mesin menjadi produk yang bisa dipakai orang
lain lewat internet.

Urutan di bawah adalah urutan kerja yang saya sarankan.

---

## P0 — Blocker keamanan

Dua yang pertama sudah beres. Dua sisanya belum, dan selama itu **jangan taruh
di internet publik**.

### 1. ~~Tidak ada autentikasi sama sekali~~ — **selesai**

Sudah ada di `recens/core/auth.py` dan `recens/api/auth.py`:

- Kata sandi lewat PBKDF2-HMAC-SHA256, 600.000 iterasi, garam acak per akun.
  Jumlah iterasi tersimpan di dalam string hash, jadi bisa dinaikkan tanpa
  membatalkan kata sandi yang sudah ada.
- Token sesi disimpan sebagai SHA-256; yang asli hanya pernah ada di kuki
  peramban (`httponly`, `samesite=lax`, `secure` mengikuti `RECENS_HTTPS`).
- CRUD lengkap: daftar, masuk, keluar, baca/ubah profil, ganti kata sandi,
  hapus akun, daftar sesi aktif, cabut sesi.
- Dependency `current_account` di FastAPI.

**Yang masih kurang di sini:** pemulihan kata sandi lewat surel (lihat P4) dan
pembatas laju pada `/api/auth/login` (lihat P0 #4). Tanpa yang kedua, kata sandi
bisa ditebak berkali-kali tanpa hambatan.

### 2. ~~Proyek tidak memeriksa kepemilikan~~ — **selesai**

`get_project` kini menyaring `account_id` dan dipakai sebagai *dependency*
FastAPI, bukan dipanggil di dalam badan fungsi — sehingga pemeriksaannya
berjalan sebelum kode rutenya dan tidak bisa terlewat di satu titik. Sumber daya
yang diakses lewat ID sendiri (`sections`, `blocks`, `refs`, `datasets`,
`analyses`, `revisions`, `rulesets`) ditelusuri balik ke pemiliknya lewat
pembantu `owned_*` di `recens/api/deps.py`.

Dua celah yang baru terlihat saat dikerjakan, dan keduanya sudah ditutup:

- uji statistik bisa memakai `dataset_id` milik proyek lain;
- hasil analisis bisa disisipkan ke naskah proyek lain lewat `section_id`.

Keduanya sekarang menuntut kedua ID berada di proyek yang sama.

**Jaganya:** `recens/tests/test_auth.py` — 60 uji yang memeriksa tiap sumber
daya satu per satu, dan membuktikan datanya memang masih ada, bukan sekadar
tidak terlihat. Jangan hapus berkas itu; kebocoran semacam ini gampang kembali
diam-diam.

### 3. Unggahan tanpa batas ukuran

`await file.read()` membaca seluruh berkas ke memori tanpa batas.

- **Berkas:** `recens/api/library.py`, `recens/api/analysis.py`,
  `recens/api/review.py`
- **Risiko:** satu berkas 2 GB membuat proses kehabisan memori
- **Kerjakan:** batasi lewat `Content-Length`, baca bertahap ke disk, dan tolak
  di atas ambang (mis. 25 MB untuk PDF, 50 MB untuk data)
- **Perkiraan:** 2 jam

### 4. Tanpa CORS dan rate limit

Belum ada `CORSMiddleware` maupun pembatas laju.

- **Yang paling mendesak:** `POST /api/auth/login`. Sekarang kata sandi bisa
  ditebak berkali-kali tanpa hambatan. PBKDF2 600.000 iterasi memang membuat
  tiap percobaan mahal — itu juga berarti pengiriman beruntun bisa menghabiskan
  CPU server. Batasi per alamat IP **dan** per surel.
- Endpoint yang memanggil model bahasa dan pencarian literatur juga perlu
  dibatasi. Keduanya kini sudah menuntut sesi, jadi tidak lagi terbuka untuk
  siapa pun, tetapi satu akun masih bisa mengurasnya.
- **Kerjakan:** `CORSMiddleware` dengan daftar asal yang eksplisit, plus
  `slowapi` atau pembatas di tingkat reverse proxy
- **Perkiraan:** 3 jam

---

## P1 — Supaya bisa dideploy

### 5. Vercel tidak cocok untuk backend ini apa adanya

Ini keputusan arsitektur yang perlu diambil lebih dahulu, sebelum menulis kode
deploy.

Recens memakai SQLite di disk lokal dan menulis berkas unggahan serta hasil
ekspor ke disk. Vercel serverless **tidak punya disk permanen** — setiap
pemanggilan mendapat sistem berkas sementara. Selain itu perakitan DOCX/PDF dan
uji statistik memakan CPU dan waktu, sementara fungsi serverless punya batas
durasi.

Dua jalan yang masuk akal:

| Jalan | Frontend | Backend | Basis data | Berkas |
|---|---|---|---|---|
| **A. Terpisah** | Vercel | Railway / Fly / Render | Postgres terkelola | S3 / R2 |
| **B. Satu VPS** | Nginx | Uvicorn + systemd | Postgres lokal | Disk lokal |

Jalan A lebih rapi untuk berkembang; jalan B lebih murah dan sederhana untuk
menguji ke pengguna pertama. Untuk jalan A, `vite.config.ts` sudah memakai
`base: "/static/"` sehingga perlu disesuaikan bila frontend pindah domain.

### 6. SQLite → Postgres

- **Berkas:** `recens/db.py` — memakai `sqlite3` langsung dengan SQL mentah
- **Catatan:** kueri sebagian besar SQL standar, tetapi ada beberapa yang khas
  SQLite (`INTEGER PRIMARY KEY AUTOINCREMENT`, penyimpanan JSON sebagai TEXT)
- **Kerjakan:** pindah ke SQLAlchemy Core atau asyncpg; sekalian ganti kolom
  `*_json` bertipe TEXT menjadi `JSONB`
- **Perkiraan:** 2–3 hari

### 7. Tidak ada sistem migrasi

Skema dibuat lewat `CREATE TABLE IF NOT EXISTS` di `recens/db.py`. Begitu ada
data pengguna sungguhan, mengubah skema tidak akan aman.

Ada penambal seadanya di `db._patch_columns()` — dipasang saat menambahkan
`accounts.password_hash`. Ia hanya sanggup menambah kolom yang boleh kosong,
dan **bukan** pengganti sistem migrasi. Begitu ada perubahan yang menuntut
penulisan ulang data, penambal itu tidak akan menolong.

- **Kerjakan:** pasang Alembic sebelum pengguna pertama masuk, lalu jadikan
  `_patch_columns()` migrasi pertama dan hapus fungsinya
- **Perkiraan:** setengah hari

### 8. Berkas pengguna ke penyimpanan objek

`recens/config.py` menulis ke `uploads_dir` dan `exports_dir` di disk lokal.

- **Kerjakan:** ganti dengan S3 atau Cloudflare R2; hasil ekspor sebaiknya
  disajikan lewat presigned URL, bukan `FileResponse`
- **Berkas:** `recens/api/review.py` (`download_export`)
- **Perkiraan:** 1 hari

### 9. Tidak ada Dockerfile atau konfigurasi deploy

Belum ada `Dockerfile`, `docker-compose.yml`, maupun `vercel.json`.

- **Catatan:** `pyreadstat` dan `pdfplumber` butuh pustaka sistem, jadi image
  ramping seperti `python:3.11-slim` perlu paket tambahan
- **Perkiraan:** setengah hari

---

## P2 — Sudah ditulis tetapi belum terbukti

### 10. Jalur Claude API belum pernah dijalankan

Kode di `recens/core/llm/providers.py` tidak pernah dieksekusi karena tidak ada
kunci API selama pengembangan. Pengujian sengaja menghapus `ANTHROPIC_API_KEY`
agar hermetis, jadi yang terverifikasi adalah **jalur deterministiknya**.

- **Kerjakan:** setel `ANTHROPIC_API_KEY`, lalu jalankan satu per satu:
  lanjutan kalimat, parafrase, bahasa akademik, narasi hasil, mode sidang,
  cover letter, respon reviewer, abstrak terstruktur, terjemahan
- **Yang paling perlu diperhatikan:** penjaga penelusuran angka di
  `recens/core/stats/narrative.py`. Ia sudah diuji dengan angka buatan, tetapi
  belum pernah diuji terhadap narasi yang benar-benar disusun model. Perhatikan
  angka yang ditulis model dengan ketelitian berbeda dari hasil hitung.
- **Sudah ditemukan satu penolakan palsu tanpa perlu kunci API:** narasi
  deterministiknya sendiri tidak lolos penjaganya, karena "R² 0,887 berarti
  menjelaskan 88,7% variasi" dibaca sebagai angka baru. Bentuk persen kini
  diterima, dan ada uji yang memastikan draf bawaan selalu lolos penjaganya —
  pakai uji itu sebagai tolok ukur saat menguji narasi model. Penolakan palsu
  yang sering terjadi akan membuat penjaganya dimatikan orang, dan justru
  penjaga inilah jaminan "angka dihitung mesin".
- **Perkiraan:** 1 hari termasuk perbaikan

### 11. Parser pedoman baru diuji dengan teks buatan sendiri

`recens/core/guidelines.py` membaca pola yang bisa saya antisipasi. Pedoman
fakultas asli formatnya sangat beragam: ada yang memakai tabel, ada yang
menulis "4 cm" sebagai "4cm", ada yang memakai gambar hasil pindaian.

- **Kerjakan:** kumpulkan 5–10 PDF pedoman asli dari beberapa kampus, jalankan
  `parse_guidelines()`, lalu bandingkan hasilnya dengan pembacaan manusia
- **Ini komponen mesin yang paling mungkin meleset di lapangan.** Kabar baiknya,
  bidang `evidence` dan `assumed` sudah dirancang untuk membuat kesalahan
  terlihat, bukan tersembunyi.
- **Perkiraan:** 1 hari

---

## P3 — Fitur yang belum tersambung

Semuanya sudah dinyatakan terbuka di README, bukan disembunyikan.

| Fitur | Keadaan | Berkas |
|---|---|---|
| **OCR** | Ditolak terus terang saat berkas berupa foto | `recens/core/annotations.py` |
| **Gerbang pembayaran** | Hanya pembukuan kredit internal; QRIS, dompet digital, VA, kartu belum ada | `recens/core/credits.py` |
| **Garuda/SINTA** | Adaptor menunggu `RECENS_GARUDA_BASE_URL`; tidak ada API publik yang stabil | `recens/core/citations/sources.py` |
| **Embedding multibahasa** | Memakai BM25 leksikal lokal, bukan pencarian semantik | `recens/core/retrieval.py` |
| **Layanan cek kemiripan eksternal** | Hanya membandingkan ke pustaka proyek | `recens/core/checks/similarity.py` |

Prioritaskan gerbang pembayaran **paling akhir** — ia baru berguna setelah ada
pengguna yang mau membayar.

---

## P4 — Operasional

- **Logging** — tidak ada `logging` sama sekali; saat ini kegagalan hanya
  terlihat di respons HTTP
- **Pemantauan galat** — Sentry atau sejenisnya
- **Surel** — verifikasi alamat dan pemulihan kata sandi belum ada. Ini terasa
  langsung: orang yang lupa kata sandinya sekarang kehilangan naskahnya, karena
  tidak ada jalan masuk lain. Kerjakan lebih awal daripada terlihat.
- **Cadangan** — belum ada, dan ini naskah skripsi orang; kehilangan data di
  sini artinya kehilangan pekerjaan berbulan-bulan
- **Uji beban** — perakitan DOCX dan uji statistik memakan CPU; belum diketahui
  berapa pengguna serentak yang sanggup ditangani

---

## Yang sudah beres, jangan dikerjakan ulang

Supaya waktu tidak habis di tempat yang salah:

- Mesin statistik — 20 prosedur, diverifikasi terhadap tabel tercetak
  (`r_table(60) = 0,2542`), terhadap koefisien regresi yang ditanam lalu
  dipulihkan, dan terhadap statsmodels/SciPy pada alur Bab 4 utuh
- Alur Bab 4: validitas, reliabilitas, asumsi klasik, regresi, uji beda, N-Gain
  — angka, tabel, narasi, sampai tersisip sebagai Tabel 4.1 dst. di naskah
- Pemisah desimal koma di seluruh tabel dan kalimat hasil, sementara nilai di
  `values` tetap bilangan agar penjaga penelusuran angka tetap bekerja
- Lima pemeriksaan naskah — PUEBI, silang sitasi, konsistensi, kemiripan, batas
- Perenderan sitasi APA/IEEE/Harvard/Vancouver/gaya kampus
- Ekspor DOCX dengan penomoran romawi ke arab, field daftar isi, caption
  berbasis bab; plus PDF dan LaTeX
- Tiga jaminan arsitektural: verifikasi sitasi, penelusuran angka, batas produk
- Autentikasi dan isolasi antar-akun, beserta halaman masuk/daftar dan
  pengelolaan akun di ruang kerja
- Impor coretan pembimbing dari anotasi PDF dan komentar DOCX
- Konversi naskah ke IMRAD, profil jurnal tujuan, glosarium dwibahasa
- Antarmuka React lengkap dengan halaman depan dan mode gelap

---

## Urutan kerja yang disarankan

1. ~~Autentikasi + kepemilikan proyek~~ (P0 #1, #2) — **selesai**
2. **Batas unggahan + CORS + rate limit** (P0 #3, #4) — cepat, dan pembatas laju
   pada halaman masuk adalah lubang terbesar yang tersisa
3. **Putuskan arsitektur deploy** (P1 #5) — menentukan bentuk pekerjaan berikutnya
4. **Postgres + Alembic** (P1 #6, #7)
5. **Uji jalur Claude API** (P2 #10) — bisa dikerjakan paralel, hanya perlu kunci
6. **Uji parser dengan pedoman asli** (P2 #11) — paling cepat menemukan celah
   nyata; kalau punya PDF pedoman, kerjakan ini lebih awal
7. Sisanya menyusul sesuai kebutuhan
