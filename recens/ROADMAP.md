# Yang belum jadi

Catatan serah-terima untuk melanjutkan Recens. Disusun setelah audit kode pada
commit `3776ec0`, bukan dari ingatan.

**Ringkasnya:** mesin produknya sudah jadi dan terverifikasi — 177 pengujian
lulus, alur delapan langkah berjalan dari buat proyek sampai ekspor DOCX. Yang
belum ada adalah **lapisan layanan**: hal-hal yang mengubah mesin menjadi
produk yang bisa dipakai orang lain lewat internet.

Urutan di bawah adalah urutan kerja yang saya sarankan.

---

## P0 — Blocker keamanan

Selama tiga hal ini belum ada, **jangan taruh di internet publik**. Aman dipakai
sendiri di `localhost`, tidak aman dibagikan.

### 1. Tidak ada autentikasi sama sekali

Tidak ada login, sesi, token, maupun kata sandi. Seluruh endpoint terbuka.

- **Berkas:** `recens/api/deps.py`, seluruh `recens/api/*.py`
- **Yang ada sekarang:** tabel `accounts` dengan kolom `email` dan `plan`, tetapi
  tanpa kolom kata sandi dan tanpa jalur masuk
- **Kerjakan:** tambah `password_hash` ke tabel `accounts`, endpoint
  daftar/masuk, sesi berbasis cookie httpOnly atau JWT, lalu dependency
  `current_account` di FastAPI
- **Perkiraan:** 1–2 hari

### 2. Proyek tidak memeriksa kepemilikan

Ini yang paling berbahaya, dan tidak terlihat sampai dibaca kodenya:

```python
# recens/api/deps.py
def get_project(project_id: int, conn = Depends(get_conn)) -> dict:
    row = db.fetch_one(conn, "SELECT * FROM projects WHERE id = ?", (project_id,))
    if row is None:
        raise HTTPException(404, ...)
    return dict(row)          # ← tidak ada pemeriksaan pemilik
```

Artinya `GET /api/projects/7` mengembalikan proyek nomor 7 milik siapa pun.
Begitu juga `DELETE`. Kolom `account_id` sudah ada di tabel `projects` tetapi
tidak pernah dipakai untuk menyaring.

- **Kerjakan:** setelah autentikasi ada, ubah menjadi
  `WHERE id = ? AND account_id = ?`, dan lakukan hal yang sama pada seluruh
  sumber daya turunan — `sections`, `blocks`, `refs`, `datasets`, `analyses`,
  `revisions`. Perhatikan bahwa endpoint seperti `PATCH /api/blocks/{id}` dan
  `POST /api/analyses/{id}/insert` menerima ID langsung tanpa lewat proyek,
  jadi keduanya perlu penelusuran ke pemiliknya.
- **Perkiraan:** setengah hari setelah autentikasi selesai
- **Saran:** tulis satu pengujian yang membuat dua akun lalu memastikan akun A
  mendapat 404 saat menyentuh proyek akun B. Tanpa pengujian itu, kebocoran
  seperti ini gampang kembali.

### 3. Unggahan tanpa batas ukuran

`await file.read()` membaca seluruh berkas ke memori tanpa batas.

- **Berkas:** `recens/api/library.py`, `recens/api/analysis.py`,
  `recens/api/review.py`
- **Risiko:** satu berkas 2 GB membuat proses kehabisan memori
- **Kerjakan:** batasi lewat `Content-Length`, baca bertahap ke disk, dan tolak
  di atas ambang (mis. 25 MB untuk PDF, 50 MB untuk data)
- **Perkiraan:** 2 jam

### 4. Tanpa CORS dan rate limit

Belum ada `CORSMiddleware` maupun pembatas laju. Endpoint yang memanggil model
bahasa dan pencarian literatur bisa dikuras siapa pun.

- **Kerjakan:** `CORSMiddleware` dengan daftar asal yang eksplisit, plus
  `slowapi` atau pembatas di tingkat reverse proxy
- **Perkiraan:** 2 jam

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

- **Kerjakan:** pasang Alembic sebelum pengguna pertama masuk
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
- **Surel** — verifikasi akun dan pemulihan kata sandi belum ada
- **Cadangan** — belum ada, dan ini naskah skripsi orang; kehilangan data di
  sini artinya kehilangan pekerjaan berbulan-bulan
- **Uji beban** — perakitan DOCX dan uji statistik memakan CPU; belum diketahui
  berapa pengguna serentak yang sanggup ditangani

---

## Yang sudah beres, jangan dikerjakan ulang

Supaya waktu tidak habis di tempat yang salah:

- Mesin statistik — 20 prosedur, diverifikasi terhadap tabel tercetak
  (`r_table(60) = 0,2542`) dan terhadap koefisien regresi yang ditanam lalu
  dipulihkan
- Lima pemeriksaan naskah — PUEBI, silang sitasi, konsistensi, kemiripan, batas
- Perenderan sitasi APA/IEEE/Harvard/Vancouver/gaya kampus
- Ekspor DOCX dengan penomoran romawi ke arab, field daftar isi, caption
  berbasis bab; plus PDF dan LaTeX
- Tiga jaminan arsitektural: verifikasi sitasi, penelusuran angka, batas produk
- Impor coretan pembimbing dari anotasi PDF dan komentar DOCX
- Konversi naskah ke IMRAD, profil jurnal tujuan, glosarium dwibahasa
- Antarmuka React lengkap dengan halaman depan dan mode gelap

---

## Urutan kerja yang disarankan

1. **Autentikasi + kepemilikan proyek** (P0 #1, #2) — tanpa ini yang lain tidak
   ada gunanya
2. **Batas unggahan + CORS + rate limit** (P0 #3, #4) — cepat, tutup sekalian
3. **Putuskan arsitektur deploy** (P1 #5) — menentukan bentuk pekerjaan berikutnya
4. **Postgres + Alembic** (P1 #6, #7)
5. **Uji jalur Claude API** (P2 #10) — bisa dikerjakan paralel, hanya perlu kunci
6. **Uji parser dengan pedoman asli** (P2 #11) — paling cepat menemukan celah
   nyata; kalau punya PDF pedoman, kerjakan ini lebih awal
7. Sisanya menyusul sesuai kebutuhan
