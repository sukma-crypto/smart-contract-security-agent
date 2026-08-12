/**
 * Kalimat yang berganti-ganti di halaman depan.
 *
 * Satu aturan mengikat seluruh berkas ini: **tidak ada kalimat yang menjanjikan
 * sesuatu yang tidak dilakukan produknya.**
 *
 * Godaan terbesar pada halaman seperti ini adalah menulis "skripsi selesai
 * dalam semalam" atau "generate BAB II sekali klik". Dua-duanya bertabrakan
 * dengan Bagian 8.1 rancangan produk, yang justru menolak menulis bab utuh.
 * Bagi pembaca akademik janji semacam itu bukan menambah keyakinan melainkan
 * menguranginya: mahasiswa tahu persis apa yang terjadi pada karya yang ditulis
 * mesin sekali jalan, dan dosen pembimbing lebih tahu lagi.
 *
 * Karena itu tiap kalimat di bawah menunjuk pekerjaan yang benar-benar
 * dikerjakan Recens dan sudah terverifikasi berjalan — bukan perasaan tentang
 * hasil akhirnya. Yang meyakinkan orang yang sedang menggarap skripsi bukan
 * "cepat selesai", melainkan "bagian yang selama ini membuat saya mandek
 * ternyata ada yang mengurus".
 */

export interface Claim {
  /** Bagian tetap di depan, dibaca sebagai satu kalimat dengan pointnya. */
  lead: string;
  /** Bagian yang berganti — inilah yang diberi warna dan gerak. */
  point: string;
}

/** Baris berputar di hero. Pendek, satu tarikan napas. */
export const HERO_CLAIMS: Claim[] = [
  { lead: "Dengan Recens,", point: "olah data BAB IV jalan sendiri." },
  { lead: "Dengan Recens,", point: "sitasi tidak pernah lagi menggantung." },
  { lead: "Dengan Recens,", point: "format DOCX sudah benar sejak unduhan pertama." },
  { lead: "Dengan Recens,", point: "pedoman kampus jadi aturan, bukan tebakan." },
  { lead: "Dengan Recens,", point: "tidak ada coretan dosen yang terlewat." },
  { lead: "Dengan Recens,", point: "tiap angka di hasil bisa dipertanggungjawabkan." },
];

/**
 * Kalimat panjang untuk pita di tengah halaman.
 *
 * Tiap butir menyebut satu titik mandek yang nyata, lalu menjawabnya dengan
 * kemampuan yang memang ada. Bentuk "dulu begini, sekarang begitu" dipilih
 * karena pembacanya sedang mengalami sisi kirinya.
 */
export interface Assurance {
  /** Keluhan yang dikenali pembaca. */
  pain: string;
  /** Jawaban Recens atasnya — harus benar-benar berjalan. */
  answer: string;
  /** Bukti pendek yang bisa diperiksa, bukan slogan. */
  proof: string;
}

export const ASSURANCES: Assurance[] = [
  {
    pain: "Berhenti di BAB IV karena tidak tahu uji apa yang dipakai.",
    answer: "Pemandu metode memilihkan ujinya dari pertanyaan penelitian dan skala datamu, lalu menjalankannya.",
    proof: "20 prosedur: validitas, reliabilitas, asumsi klasik, regresi, uji beda, sampai SEM-PLS.",
  },
  {
    pain: "Menabung untuk membayar jasa olah data.",
    answer: "Uji instrumen sampai regresi berganda dijalankan sendiri, lengkap dengan butir mana yang perlu digugurkan.",
    proof: "Angka diverifikasi terhadap tabel r product moment dan statsmodels.",
  },
  {
    pain: "Ditanya penguji dari mana angka itu datang, lalu diam.",
    answer: "Tiap analisis menyimpan data, langkah, parameter, dan hasilnya — bisa ditelusuri ulang kapan pun.",
    proof: "Narasi yang memuat angka di luar hasil hitung ditolak sistem, bukan diloloskan.",
  },
  {
    pain: "Berhari-hari mengatur margin, penomoran, dan daftar isi di Word.",
    answer: "Pedoman fakultas dibaca menjadi aturan yang mengikat, lalu dokumen dirakit mengikutinya.",
    proof: "Romawi ke arab, daftar isi, caption berbasis bab — sudah benar sebelum kamu membukanya.",
  },
  {
    pain: "Revisi yang sama diulang di bimbingan berikutnya.",
    answer: "Coretan pembimbing dari PDF dan komentar Word menjadi daftar tugas berstatus, terhubung ke lokasinya di naskah.",
    proof: "Komentar yang tidak bisa ditautkan dengan yakin dicatat tanpa lokasi, bukan ditebak.",
  },
  {
    pain: "Daftar pustaka tidak sinkron dengan sitasi dalam teks.",
    answer: "Sitasi ditarik dari metadata resmi dan daftar pustaka selalu mengikuti apa yang benar-benar dikutip.",
    proof: "APA, IEEE, Harvard, Vancouver, dan gaya kampus — dari satu pustaka yang sama.",
  },
];

/** Pengingat singkat yang berputar di bawah pita — nada tenang, bukan iklan. */
export const REASSURANCES: string[] = [
  "Naskahmu tetap milikmu. Recens menemani menulis, bukan menggantikan.",
  "Hasil yang tidak signifikan tetap dilaporkan apa adanya, beserta cara membahasnya.",
  "Referensi hanya masuk bila terlacak ke basis data resmi.",
  "Seluruh fitur terbuka di semua paket — yang membedakan hanya kuota dan durasi.",
  "Berjalan penuh tanpa kunci API: statistik, pemeriksaan, dan format semuanya lokal.",
];
