# Recens

**AI writing tool untuk seluruh karya tulis ilmiah.**

Satu ruang kerja untuk makalah, laporan, karya tulis ilmiah, proposal, skripsi,
tesis, disertasi, sampai artikel jurnal — mulai dari mengumpulkan referensi,
menulis, mengolah data, memeriksa naskah, hingga mengekspor dokumen yang
formatnya sudah benar.

Implementasi ini mengikuti dokumen *Recens — Rancangan Produk*.

---

## Mengapa dibangun seperti ini

Mayoritas penulis karya ilmiah tidak tersendat karena tidak bisa menulis. Mereka
tersendat karena tidak tahu struktur apa yang benar, format apa yang diminta,
metode apa yang tepat, dan referensi mana yang layak dikutip. Menulis hanyalah
gejala terakhir dari empat masalah itu.

Dua kalimat pada rancangan produk menentukan hampir seluruh keputusan teknis di
sini:

> Metadata sitasi hanya berasal dari basis data ilmiah resmi, dan angka hasil
> analisis seluruhnya dihitung mesin statistik — bukan diperkirakan model. Model
> hanya menyusun kalimat penjelasnya.

Keduanya tidak bisa dijamin lewat prompt, karena prompt bisa meleset dan bisa
diakali. Karena itu keduanya ditegakkan sebagai kode:

| Janji pada rancangan produk | Cara ditegakkan |
|---|---|
| Referensi tidak pernah karangan | `add_reference()` menurunkan status `verified` dari asal metadatanya, bukan dari argumen pemanggil. Tidak ada jalur kode yang bisa menandai metadata tak tertelusur sebagai sah — [`core/citations/library.py`](core/citations/library.py) |
| Sitasi tidak pernah menunjuk sumber yang tidak ada | Penanda sitasi yang citekey-nya di luar pustaka proyek dibuang dari keluaran model, dan yang tersisa di naskah dirender sebagai penanda mencolok, bukan dihapus diam-diam — [`core/llm/guardrails.py`](core/llm/guardrails.py), [`core/render.py`](core/render.py) |
| Angka hasil dihitung mesin, bukan model | Setiap angka pada narasi ditelusuri balik ke hasil perhitungan. Angka yang tidak tertelusur membatalkan narasi, dan draf deterministik dipakai sebagai gantinya — [`core/stats/narrative.py`](core/stats/narrative.py) |
| Hasil tidak signifikan dilaporkan apa adanya | Tidak ada parameter yang bisa membuat sebuah uji "diterima". Ketidaksignifikanan justru masuk ke `findings` dan `warnings` — [`core/stats/engine.py`](core/stats/engine.py) |
| Kutipan informan benar-benar diucapkan | Tiap segmen kualitatif diverifikasi ada di transkrip; yang tidak ditemukan tidak disimpan — [`core/stats/qualitative.py`](core/stats/qualitative.py) |

### Batas produk yang melekat

Batasan pada Bagian 8.1 rancangan produk berlaku pada setiap permintaan
(`guard_request`) dan setiap keluaran (`guard_output`), tanpa saklar untuk
mematikannya.

| Yang dilakukan Recens | Yang tidak dilakukan Recens |
|---|---|
| Menyusun kerangka dan struktur bab | Menghasilkan bab utuh sekali jalan tanpa keterlibatan pengguna |
| Melanjutkan kalimat yang sedang diketik pengguna | Mengarang data penelitian, hasil uji, atau temuan |
| Menyarankan sitasi dari sumber yang terverifikasi | Menghasilkan referensi yang tidak terlacak ke sumber resmi |
| Mengolah data yang diunggah dan menampilkan langkahnya | Memanipulasi hasil analisis agar hipotesis diterima |
| Memparafrase disertai penjelasan alasan perubahan | Memparafrase khusus untuk mengelabui sistem deteksi |

Setiap penolakan disertai jalan keluar yang sah, karena di balik permintaan yang
melanggar biasanya ada kebutuhan yang wajar — mahasiswa yang datanya belum
terkumpul, atau yang panik melihat angka kemiripan.

---

## Menjalankan

```bash
pip install -r recens/requirements.txt
cp recens/.env.example .env      # opsional
python -m recens                 # buka http://127.0.0.1:8000
```

**Kunci API tidak wajib.** Tanpa `ANTHROPIC_API_KEY`, yang memakai jalur
deterministik hanyalah fitur penyusunan kalimat. Seluruh perhitungan statistik,
pemeriksaan naskah, perenderan sitasi, perakitan format, dan ekspor berjalan
penuh secara lokal. `GET /api/health` menyatakan dengan jujur fitur mana yang
sedang aktif.

Menjalankan pengujian:

```bash
python -m pytest recens/tests -q      # 144 pengujian
```

---

## Alur kerja

Delapan langkah, satu alur untuk semua jenis karya — yang menyesuaikan hanyalah
panjang, struktur, dan sumber aturannya.

| # | Langkah | Karya pendek | Tugas akhir | Artikel publikasi |
|---|---|---|---|---|
| 1 | Buat proyek | ya | ya | ya |
| 2 | Muat aturan penulisan | ya | ya | ya |
| 3 | Kumpulkan referensi | ya | ya | ya |
| 4 | Susun outline | ya | ya | ya |
| 5 | Menulis di editor | ya | ya | ya |
| 6 | Olah data penelitian | opsional | bila kuantitatif/kualitatif | bila artikel hasil penelitian |
| 7 | Periksa naskah | ya | ya | + cek batas kata |
| 8 | Ekspor & kelola revisi | ekspor saja | + pelacak bimbingan, mode sidang | + template jurnal, berkas submisi |

Sembilan jenis karya didukung: makalah kuliah, laporan praktikum/kerja
praktik/magang, karya tulis ilmiah lomba, esai ilmiah, proposal penelitian,
skripsi/tesis/disertasi, artikel jurnal, artikel prosiding, dan artikel tinjauan
pustaka.

---

## Yang benar-benar berjalan

### Mesin statistik

Seluruh uji dihitung dengan NumPy/SciPy/statsmodels, bukan ditaksir model.
Nilai tabel pun dihitung dari distribusinya, bukan disalin dari lampiran:
`r_table(60) = 0,2542`, persis nilai pada tabel product moment tercetak.

- **Deskriptif** — statistik deskriptif, distribusi frekuensi, tabulasi silang
  dengan chi-square dan Cramér's V, kategorisasi jawaban responden
- **Uji instrumen** — validitas (r hitung vs r tabel) dan reliabilitas
  (Cronbach's Alpha, alpha bila butir dihapus). Korelasi butir–total *dan*
  versi terkoreksinya selalu dihitung; ketika keduanya memberi keputusan
  berbeda, butir itu ditandai — inilah yang biasanya ditanyakan penguji
- **Asumsi klasik** — normalitas (Shapiro-Wilk, Kolmogorov-Smirnov/Lilliefors),
  multikolinearitas (VIF, tolerance), heteroskedastisitas (Glejser,
  Breusch-Pagan), autokorelasi (Durbin-Watson)
- **Asosiatif** — korelasi Pearson/Spearman, regresi sederhana dan berganda
  lengkap dengan uji t, uji F, beta terstandar, dan koefisien determinasi
- **Komparatif** — uji t sampel bebas (dengan Levene menentukan Student atau
  Welch), uji t berpasangan, ANOVA satu jalur dengan uji lanjut Tukey, serta
  padanan non-parametriknya (Mann-Whitney, Wilcoxon, Kruskal-Wallis)
- **Eksperimen & R&D** — N-Gain ternormalisasi, validasi ahli dengan Aiken's V
- **SEM-PLS** — AVE dan Composite Reliability dihitung dari nilai loading yang
  dikeluarkan perangkat, plus uji Fornell-Larcker dan pembacaan uji jalur

**Pemandu metodologi** berupa pohon keputusan yang eksplisit dan bisa diperiksa:
tujuan penelitian, skala data, jumlah kelompok, dan sebaran data menentukan uji
mana yang disarankan beserta prasyaratnya. Termasuk penentuan ukuran sampel
(Slovin, aturan Green untuk regresi).

**Berkas yang diterima**: SPSS `.sav` (lewat pyreadstat, lengkap dengan label
variabel), Excel `.xlsx`, CSV (deteksi pemisah dan desimal koma otomatis), dan
transkrip wawancara. Untuk `.spv` dan tangkapan layar, tabel outputnya ditempel
lalu distrukturkan — angkanya dibaca apa adanya, tidak dihitung ulang.

### Pemeriksaan naskah

- **Bahasa akademik Indonesia** — ±70 bentuk tidak baku KBBI, ragam percakapan,
  kata depan `di`/`ke` yang tertukar dengan awalan, `dimana`/`yang mana` sebagai
  penghubung, pasangan mubazir, kalimat terlalu panjang, konjungsi di awal
  kalimat, kata ganti orang pertama. Setiap temuan membawa kutipan, posisi, dan
  usulan perbaikan
- **Cek silang sitasi** — sitasi menggantung, referensi tak dikutip, referensi
  yang dikutip tetapi belum terverifikasi, bagian tanpa sitasi, dan kemutakhiran
  rujukan
- **Cek konsistensi** — rumusan masalah, tujuan, hipotesis, dan simpulan
  dijajarkan lalu dipasangkan lewat irisan kata kunci; butir tanpa pasangan
  ditandai. Termasuk deteksi istilah yang dipakai bergantian
- **Cek kemiripan mandiri** — pencocokan 8-gram terhadap sumber di pustaka
  proyek, disertai rentang yang cocok dan cara memparafrasenya. Cakupannya
  dinyatakan terus terang: ini bukan pengganti pemeriksaan resmi kampus
- **Cek batas panjang** — perkiraan jumlah halaman dihitung dari luas area teks,
  ukuran huruf, dan jarak baris, sehingga ikut berubah begitu pedoman diganti

### Pedoman sebagai basis

PDF pedoman dibaca menjadi `RuleSet` yang mengikat outline, penomoran, format
dokumen, gaya sitasi, dan batas panjang. Setiap aturan menyertakan kutipan
kalimat asalnya, dan aturan yang tidak ditemukan dicatat pada `assumed` alih-alih
ditebak diam-diam.

### Sitasi

Perenderan APA 7, IEEE, Harvard, Vancouver, dan gaya kampus yang parameternya
diambil dari pedoman (mis. `dkk.` menggantikan `et al.`). Sitasi disimpan sebagai
penanda `[[cite:citekey]]`, bukan teks jadi — sehingga satu naskah bisa
dikeluarkan dalam gaya apa pun tanpa menyunting isinya, dan daftar pustaka tidak
pernah lepas sinkron. Gaya numerik otomatis urut kemunculan, gaya penulis-tahun
urut abjad.

### Ekspor

- **DOCX** — margin, huruf, spasi, penomoran romawi untuk bagian awal dan arab
  untuk bagian isi (lewat `w:pgNumType`), daftar isi dan daftar tabel/gambar
  sebagai field Word, penomoran caption berbasis bab, daftar pustaka dengan
  indentasi gantung
- **PDF** — melalui ReportLab dengan aturan yang sama
- **LaTeX** — `.tex` lengkap dengan `geometry`, `setspace`, dan berkas `.bib`
  yang dibangun dari pustaka proyek

---

## Peta kode

```
recens/
├── main.py                     perakitan API + ruang kerja web
├── config.py, db.py            pengaturan dan skema SQLite
├── core/
│   ├── worktypes.py            9 jenis karya, matriks langkah & perlakuan
│   ├── manuscript.py           naskah terstruktur: bab, blok, caption, penanda
│   ├── guidelines.py           pembacaan pedoman menjadi RuleSet
│   ├── render.py               penanda → sitasi dan acuan silang
│   ├── retrieval.py            BM25 lokal untuk Tanya Jurnal
│   ├── credits.py              kuota dan durasi — bukan penguncian fitur
│   ├── citations/              gaya, sumber resmi, pustaka proyek
│   ├── stats/                  mesin statistik, metodologi, kualitatif, narasi
│   ├── checks/                 lima pemeriksaan naskah
│   ├── exporters/              DOCX, PDF, LaTeX
│   └── llm/                    penyedia, prompt, layanan, dan penjaga batas
├── api/                        router per langkah alur kerja
├── web/                        ruang kerja (HTML/CSS/JS tanpa build)
└── tests/                      144 pengujian
```

Antarmuka web adalah satu halaman tanpa tahap build: buka `/`, dan seluruh
delapan langkah ada di sidebar kiri. Dokumentasi API otomatis tersedia di
`/docs`.

---

## Paket akses

Yang membedakan paket adalah **kuota dan durasi, bukan fitur**. Tidak ada
`is_feature_allowed(plan, feature)` di basis kode ini, dan memang tidak boleh
ada: skripsi S1 sama menuntutnya dengan tesis S2, sementara banyak tesis S2 justru
sepenuhnya kualitatif. Mengunci analisis data berdasarkan jenjang akan membuat
produk gagal di segmen terbesarnya.

Fitur yang berjalan lokal — analisis data, uji instrumen, pemeriksaan naskah,
cek kemiripan, auto-format, dan ekspor — tidak menagih kredit sama sekali.

---

## Catatan keterbatasan

Hal-hal berikut sengaja dinyatakan terbuka, bukan disamarkan:

- **Garuda/SINTA** tidak menyediakan API publik yang stabil. Adaptornya menunjuk
  ke endpoint yang dikonfigurasi lembaga; bila belum disetel, Recens mengatakan
  sumber itu belum tersedia alih-alih mengarang hasil pencarian.
- **Cek kemiripan** membandingkan naskah terhadap sumber di pustaka proyek, bukan
  terhadap seluruh internet. Angkanya adalah batas bawah dan bukan pengganti
  hasil sistem resmi kampus.
- **OCR** untuk PDF hasil pindaian dan foto tulisan tangan belum tersambung;
  halaman tanpa lapisan teks akan terbaca kosong.
- **Estimasi PLS-SEM** tetap dijalankan di SmartPLS atau Lisrel. Recens membaca
  keluarannya lalu menghitung AVE dan CR dari nilai loading tersebut.
- **Cronbach's Alpha pada tabel PLS** tidak dapat diturunkan dari nilai loading,
  sehingga kolomnya sengaja tidak diisi alih-alih ditaksir.
