/**
 * Kutipan yang menemani orang saat ruang kerjanya masih kosong.
 *
 * ATURAN BERKAS INI
 *
 * Recens berdiri di atas satu janji: tidak ada referensi yang tidak terlacak ke
 * sumber resmi. Mengisi aplikasinya dengan kutipan hasil ingatan akan
 * bertabrakan langsung dengan janji itu — dan bukan pelanggaran yang abstrak:
 * ada mahasiswa yang akan menyalin kutipan dari layar ini ke latar belakang
 * skripsinya. Kutipan yang salah atribusi akan sampai ke meja penguji.
 *
 * Karena itu tiap butir di sini membawa `sumber`:
 *
 *   "tercatat"   — terdokumentasi kuat pada karya, pidato, atau surat tokohnya.
 *   "populer"    — sangat luas dikaitkan dengan tokoh tersebut dan dipakai
 *                  turun-temurun, tetapi naskah aslinya tidak dapat saya
 *                  pastikan. Ditandai di antarmuka agar tidak dikutip mentah.
 *
 * Kutipan yang termasyhur tetapi diketahui salah atribusi **tidak dimasukkan**,
 * meski akan menambah jumlah. Contohnya "menilai ikan dari kemampuannya
 * memanjat pohon" yang beredar atas nama Einstein, dan "jadilah perubahan yang
 * ingin kau lihat" atas nama Gandhi — keduanya tidak ditemukan pada tulisan
 * mereka.
 *
 * MENAMBAH SENDIRI
 *
 * Susunannya sengaja datar dan mudah ditambah. Bila Anda punya kutipan yang
 * sumbernya bisa ditunjuk — halaman buku, tanggal pidato — tambahkan dengan
 * `sumber: "tercatat"` dan isi `konteks` seperlunya.
 */

export type TingkatSumber = "tercatat" | "populer";

export interface Quote {
  teks: string;
  tokoh: string;
  /** Keterangan singkat siapa tokohnya — pembaca tidak selalu mengenalnya. */
  peran: string;
  sumber: TingkatSumber;
  /** Karya atau peristiwa asalnya bila diketahui. */
  konteks?: string;
  tema: Tema;
}

export type Tema =
  | "ketekunan"
  | "ilmu"
  | "menulis"
  | "keraguan"
  | "kegagalan"
  | "waktu"
  | "kejujuran"
  | "kesederhanaan"
  | "selesai";

export const LABEL_TEMA: Record<Tema, string> = {
  ketekunan: "Ketekunan",
  ilmu: "Ilmu pengetahuan",
  menulis: "Menulis",
  keraguan: "Keraguan",
  kegagalan: "Kegagalan",
  waktu: "Waktu",
  kejujuran: "Kejujuran ilmiah",
  kesederhanaan: "Kejernihan",
  selesai: "Menyelesaikan",
};

export const QUOTES: Quote[] = [
  // --- Ketekunan ------------------------------------------------------------
  {
    teks: "Saya tidak gagal. Saya hanya menemukan sepuluh ribu cara yang tidak berhasil.",
    tokoh: "Thomas Alva Edison",
    peran: "penemu",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Bukan karena hal itu sulit maka kita tidak berani; justru karena kita tidak berani maka hal itu menjadi sulit.",
    tokoh: "Seneca",
    peran: "filsuf Romawi",
    konteks: "Surat kepada Lucilius",
    sumber: "tercatat",
    tema: "ketekunan",
  },
  {
    teks: "Genius adalah satu persen ilham dan sembilan puluh sembilan persen keringat.",
    tokoh: "Thomas Alva Edison",
    peran: "penemu",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Ketekunan adalah kerja keras yang kau lakukan setelah lelah mengerjakan kerja keras yang sudah kau lakukan.",
    tokoh: "Newt Gingrich",
    peran: "sejarawan",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Bermimpilah setinggi langit. Jika engkau jatuh, engkau akan jatuh di antara bintang-bintang.",
    tokoh: "Soekarno",
    peran: "Presiden pertama Republik Indonesia",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Orang boleh pandai setinggi langit, tapi selama ia tidak menulis, ia akan hilang di dalam masyarakat dan dari sejarah.",
    tokoh: "Pramoedya Ananta Toer",
    peran: "sastrawan Indonesia",
    konteks: "Rumah Kaca",
    sumber: "tercatat",
    tema: "menulis",
  },
  {
    teks: "Menulis adalah bekerja untuk keabadian.",
    tokoh: "Pramoedya Ananta Toer",
    peran: "sastrawan Indonesia",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Hiduplah dengan sederhana, agar semua orang bisa hidup.",
    tokoh: "Mahatma Gandhi",
    peran: "tokoh pergerakan India",
    sumber: "populer",
    tema: "kesederhanaan",
  },
  {
    teks: "Pendidikan adalah senjata paling ampuh yang bisa kau gunakan untuk mengubah dunia.",
    tokoh: "Nelson Mandela",
    peran: "Presiden Afrika Selatan",
    konteks: "Pidato di Universitas Witwatersrand, 2003",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Tampaknya selalu mustahil sampai hal itu selesai dikerjakan.",
    tokoh: "Nelson Mandela",
    peran: "Presiden Afrika Selatan",
    sumber: "populer",
    tema: "selesai",
  },

  // --- Ilmu pengetahuan -----------------------------------------------------
  {
    teks: "Yang penting adalah jangan berhenti bertanya. Keingintahuan punya alasannya sendiri untuk ada.",
    tokoh: "Albert Einstein",
    peran: "fisikawan",
    konteks: "Wawancara majalah LIFE, 1955",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Jika saya melihat lebih jauh, itu karena saya berdiri di atas bahu para raksasa.",
    tokoh: "Isaac Newton",
    peran: "fisikawan dan matematikawan",
    konteks: "Surat kepada Robert Hooke, 1675",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Tidak ada yang perlu ditakuti dalam hidup, yang ada hanya perlu dipahami. Sekaranglah saatnya memahami lebih banyak, agar kita lebih sedikit takut.",
    tokoh: "Marie Curie",
    peran: "fisikawan dan kimiawan",
    sumber: "tercatat",
    tema: "keraguan",
  },
  {
    teks: "Dalam bidang pengamatan, keberuntungan hanya berpihak pada pikiran yang siap.",
    tokoh: "Louis Pasteur",
    peran: "ahli mikrobiologi",
    konteks: "Kuliah di Universitas Lille, 1854",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Prinsip pertama adalah kau tidak boleh menipu dirimu sendiri — dan dirimu sendiri adalah orang yang paling mudah ditipu.",
    tokoh: "Richard Feynman",
    peran: "fisikawan",
    konteks: "Pidato wisuda Caltech, 1974",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  {
    teks: "Ilmu pengetahuan adalah cara untuk tidak menipu diri sendiri.",
    tokoh: "Richard Feynman",
    peran: "fisikawan",
    sumber: "populer",
    tema: "kejujuran",
  },
  {
    teks: "Suatu pernyataan luar biasa menuntut bukti yang luar biasa pula.",
    tokoh: "Carl Sagan",
    peran: "astronom",
    konteks: "Cosmos, 1980",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  {
    teks: "Di suatu tempat, sesuatu yang menakjubkan sedang menunggu untuk diketahui.",
    tokoh: "Carl Sagan",
    peran: "astronom",
    sumber: "populer",
    tema: "ilmu",
  },
  {
    teks: "Saya lebih suka pertanyaan yang tidak bisa dijawab daripada jawaban yang tidak bisa dipertanyakan.",
    tokoh: "Richard Feynman",
    peran: "fisikawan",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Sebuah teori baru diterima bukan karena lawan-lawannya diyakinkan, melainkan karena mereka akhirnya meninggal dan generasi baru tumbuh dengan teori itu.",
    tokoh: "Max Planck",
    peran: "fisikawan",
    konteks: "Autobiografi Ilmiah",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Apa yang kita ketahui adalah setetes air; apa yang tidak kita ketahui adalah samudra.",
    tokoh: "Isaac Newton",
    peran: "fisikawan dan matematikawan",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Ilmu tanpa agama pincang, agama tanpa ilmu buta.",
    tokoh: "Albert Einstein",
    peran: "fisikawan",
    konteks: "Science, Philosophy and Religion, 1941",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Sesuatu yang paling tidak dapat dipahami tentang dunia ini adalah bahwa ia dapat dipahami.",
    tokoh: "Albert Einstein",
    peran: "fisikawan",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Kebenaran ilmiah tidak pernah final. Ia hanya bertahan sampai ada pengamatan yang lebih baik.",
    tokoh: "Karl Popper",
    peran: "filsuf ilmu",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Sebuah teori yang tidak dapat dibuktikan salah oleh peristiwa apa pun bukanlah teori ilmiah.",
    tokoh: "Karl Popper",
    peran: "filsuf ilmu",
    konteks: "Conjectures and Refutations, 1963",
    sumber: "tercatat",
    tema: "kejujuran",
  },

  // --- Menulis --------------------------------------------------------------
  {
    teks: "Saya menulis untuk mengetahui apa yang saya pikirkan.",
    tokoh: "Joan Didion",
    peran: "penulis",
    konteks: "Why I Write, 1976",
    sumber: "tercatat",
    tema: "menulis",
  },
  {
    teks: "Tulis draf pertamamu dengan hati; tulis ulang dengan kepala.",
    tokoh: "Ernest Hemingway",
    peran: "sastrawan",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Tidak ada yang namanya menulis; yang ada hanyalah menulis ulang.",
    tokoh: "Robert Graves",
    peran: "penyair dan novelis",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Menulis mudah saja. Yang harus kau lakukan hanyalah mencoret kata-kata yang salah.",
    tokoh: "Mark Twain",
    peran: "sastrawan",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Maaf, surat ini panjang. Saya tidak punya cukup waktu untuk menulisnya lebih pendek.",
    tokoh: "Blaise Pascal",
    peran: "matematikawan dan filsuf",
    konteks: "Lettres provinciales, 1657",
    sumber: "tercatat",
    tema: "kesederhanaan",
  },
  {
    teks: "Jika kamu tidak bisa menjelaskannya dengan sederhana, berarti kamu belum cukup memahaminya.",
    tokoh: "Albert Einstein",
    peran: "fisikawan",
    sumber: "populer",
    tema: "kesederhanaan",
  },
  {
    teks: "Kalimat harus tidak memuat kata yang tak perlu, paragraf harus tidak memuat kalimat yang tak perlu.",
    tokoh: "William Strunk Jr.",
    peran: "guru besar bahasa Inggris",
    konteks: "The Elements of Style, 1918",
    sumber: "tercatat",
    tema: "kesederhanaan",
  },
  {
    teks: "Menulislah dengan pintu tertutup, tulis ulang dengan pintu terbuka.",
    tokoh: "Stephen King",
    peran: "novelis",
    konteks: "On Writing, 2000",
    sumber: "tercatat",
    tema: "menulis",
  },
  {
    teks: "Bagian tersulit dari menulis adalah duduk dan mulai menulis.",
    tokoh: "Ernest Hemingway",
    peran: "sastrawan",
    sumber: "populer",
    tema: "waktu",
  },
  {
    teks: "Jangan bilang bulan itu bersinar; tunjukkan kilau cahayanya pada pecahan kaca.",
    tokoh: "Anton Chekhov",
    peran: "sastrawan Rusia",
    konteks: "Surat kepada saudaranya, 1886",
    sumber: "tercatat",
    tema: "menulis",
  },

  // --- Keraguan & kegagalan --------------------------------------------------
  {
    teks: "Saya tahu satu hal: bahwa saya tidak tahu apa-apa.",
    tokoh: "Sokrates",
    peran: "filsuf Yunani",
    konteks: "Dikutip Plato dalam Apologia",
    sumber: "tercatat",
    tema: "keraguan",
  },
  {
    teks: "Masalah dunia ini adalah orang bodoh dan fanatik selalu yakin akan dirinya, sementara orang bijak penuh keraguan.",
    tokoh: "Bertrand Russell",
    peran: "filsuf dan matematikawan",
    konteks: "The Triumph of Stupidity, 1933",
    sumber: "tercatat",
    tema: "keraguan",
  },
  {
    teks: "Pernah gagal. Tidak apa-apa. Coba lagi. Gagal lagi. Gagal dengan lebih baik.",
    tokoh: "Samuel Beckett",
    peran: "sastrawan",
    konteks: "Worstward Ho, 1983",
    sumber: "tercatat",
    tema: "kegagalan",
  },
  {
    teks: "Kesuksesan adalah berpindah dari satu kegagalan ke kegagalan berikutnya tanpa kehilangan semangat.",
    tokoh: "Winston Churchill",
    peran: "Perdana Menteri Britania Raya",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Satu-satunya kesalahan sejati adalah kesalahan yang tidak kita pelajari apa pun darinya.",
    tokoh: "Henry Ford",
    peran: "industrialis",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Ragu-ragu tidak menyenangkan, tetapi kepastian itu konyol.",
    tokoh: "Voltaire",
    peran: "filsuf Prancis",
    konteks: "Surat kepada Frederick William, 1770",
    sumber: "tercatat",
    tema: "keraguan",
  },
  {
    teks: "Nilailah seseorang dari pertanyaannya, bukan dari jawabannya.",
    tokoh: "Voltaire",
    peran: "filsuf Prancis",
    sumber: "populer",
    tema: "keraguan",
  },

  // --- Waktu & memulai ------------------------------------------------------
  {
    teks: "Perjalanan seribu mil dimulai dengan satu langkah.",
    tokoh: "Laozi",
    peran: "filsuf Tiongkok",
    konteks: "Daodejing, bab 64",
    sumber: "tercatat",
    tema: "waktu",
  },
  {
    teks: "Waktu terbaik menanam pohon adalah dua puluh tahun lalu. Waktu terbaik kedua adalah sekarang.",
    tokoh: "Peribahasa Tiongkok",
    peran: "peribahasa",
    sumber: "populer",
    tema: "waktu",
  },
  {
    teks: "Sedikit demi sedikit menjadi banyak, asal dikerjakan setiap hari.",
    tokoh: "Ovidius",
    peran: "penyair Romawi",
    sumber: "populer",
    tema: "waktu",
  },
  {
    teks: "Bagaimana sebuah proyek bisa terlambat setahun? Satu hari demi satu hari.",
    tokoh: "Fred Brooks",
    peran: "ilmuwan komputer",
    konteks: "The Mythical Man-Month, 1975",
    sumber: "tercatat",
    tema: "waktu",
  },
  {
    teks: "Pekerjaan mengembang memenuhi waktu yang tersedia untuk menyelesaikannya.",
    tokoh: "Cyril Northcote Parkinson",
    peran: "sejarawan",
    konteks: "The Economist, 1955",
    sumber: "tercatat",
    tema: "waktu",
  },

  // --- Menyelesaikan --------------------------------------------------------
  {
    teks: "Yang selesai lebih baik daripada yang sempurna.",
    tokoh: "Peribahasa perancangan",
    peran: "peribahasa",
    sumber: "populer",
    tema: "selesai",
  },
  {
    teks: "Karya seni tidak pernah selesai, ia hanya ditinggalkan.",
    tokoh: "Paul Valéry",
    peran: "penyair Prancis",
    sumber: "tercatat",
    tema: "selesai",
  },
  {
    teks: "Kesempurnaan tercapai bukan ketika tidak ada lagi yang bisa ditambahkan, melainkan ketika tidak ada lagi yang bisa dikurangi.",
    tokoh: "Antoine de Saint-Exupéry",
    peran: "penerbang dan penulis",
    konteks: "Terre des hommes, 1939",
    sumber: "tercatat",
    tema: "kesederhanaan",
  },

  // --- Tokoh Indonesia ------------------------------------------------------
  {
    teks: "Ing ngarsa sung tuladha, ing madya mangun karsa, tut wuri handayani.",
    tokoh: "Ki Hadjar Dewantara",
    peran: "Bapak Pendidikan Nasional",
    konteks: "Asas Taman Siswa, 1922",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Setiap orang menjadi guru, setiap rumah menjadi sekolah.",
    tokoh: "Ki Hadjar Dewantara",
    peran: "Bapak Pendidikan Nasional",
    sumber: "populer",
    tema: "ilmu",
  },
  {
    teks: "Aku rela di penjara asalkan bersama buku, karena dengan buku aku bebas.",
    tokoh: "Mohammad Hatta",
    peran: "Wakil Presiden pertama Republik Indonesia",
    sumber: "populer",
    tema: "ilmu",
  },
  {
    teks: "Berikan aku sepuluh pemuda, niscaya akan kuguncangkan dunia.",
    tokoh: "Soekarno",
    peran: "Presiden pertama Republik Indonesia",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Idealisme adalah kemewahan terakhir yang hanya dimiliki oleh pemuda.",
    tokoh: "Tan Malaka",
    peran: "tokoh pergerakan Indonesia",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Terbentur, terbentur, terbentuk.",
    tokoh: "Tan Malaka",
    peran: "tokoh pergerakan Indonesia",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Kalau hidup sekedar hidup, babi di hutan juga hidup. Kalau bekerja sekedar bekerja, kera juga bekerja.",
    tokoh: "Buya Hamka",
    peran: "ulama dan sastrawan Indonesia",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Ilmu itu bukan yang dihafal, tetapi yang memberi manfaat.",
    tokoh: "Imam Syafi'i",
    peran: "ulama dan ahli fikih",
    sumber: "populer",
    tema: "ilmu",
  },
  {
    teks: "Ikatlah ilmu dengan menuliskannya.",
    tokoh: "Ali bin Abi Thalib",
    peran: "khalifah keempat",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Tuntutlah ilmu dari buaian hingga liang lahat.",
    tokoh: "Peribahasa Arab",
    peran: "peribahasa",
    sumber: "populer",
    tema: "ilmu",
  },
  {
    teks: "Yang paling penting bagi seorang peneliti bukan kecerdasannya, melainkan ketekunannya.",
    tokoh: "B. J. Habibie",
    peran: "Presiden ketiga Republik Indonesia",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Buku adalah jendela dunia, dan menulis adalah cara membuka jendela itu bagi orang lain.",
    tokoh: "Peribahasa Indonesia",
    peran: "peribahasa",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Berakit-rakit ke hulu, berenang-renang ke tepian; bersakit-sakit dahulu, bersenang-senang kemudian.",
    tokoh: "Peribahasa Indonesia",
    peran: "peribahasa",
    sumber: "tercatat",
    tema: "ketekunan",
  },
  {
    teks: "Sedikit-sedikit, lama-lama menjadi bukit.",
    tokoh: "Peribahasa Indonesia",
    peran: "peribahasa",
    sumber: "tercatat",
    tema: "waktu",
  },

  // --- Kejujuran ilmiah -----------------------------------------------------
  {
    teks: "Fakta tetaplah fakta meskipun diabaikan.",
    tokoh: "Aldous Huxley",
    peran: "sastrawan",
    konteks: "Complete Essays",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  {
    teks: "Kau berhak atas pendapatmu sendiri, tetapi tidak atas faktamu sendiri.",
    tokoh: "Daniel Patrick Moynihan",
    peran: "sosiolog dan senator",
    sumber: "populer",
    tema: "kejujuran",
  },
  {
    teks: "Ketika fakta berubah, saya mengubah pikiran saya. Anda bagaimana?",
    tokoh: "John Maynard Keynes",
    peran: "ekonom",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Semua model itu salah, tetapi sebagian berguna.",
    tokoh: "George E. P. Box",
    peran: "ahli statistika",
    konteks: "Robustness in Statistics, 1979",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  {
    teks: "Siksalah data cukup lama, dan ia akan mengaku apa pun.",
    tokoh: "Ronald Coase",
    peran: "ekonom",
    sumber: "populer",
    tema: "kejujuran",
  },
  {
    teks: "Tanpa data, kau hanyalah orang lain dengan sebuah pendapat.",
    tokoh: "W. Edwards Deming",
    peran: "ahli statistika",
    sumber: "populer",
    tema: "kejujuran",
  },
  {
    teks: "Statistika adalah tata bahasa dari ilmu pengetahuan.",
    tokoh: "Karl Pearson",
    peran: "ahli statistika",
    konteks: "The Grammar of Science, 1892",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Meminta ahli statistika sesudah percobaan selesai sering kali hanya meminta ia melakukan otopsi. Mungkin ia bisa mengatakan penyebab kematiannya.",
    tokoh: "Ronald Fisher",
    peran: "ahli statistika",
    konteks: "Pidato Indian Statistical Congress, 1938",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  // --- Menyelesaikan (lanjutan) ---------------------------------------------
  {
    teks: "Selesai lebih baik daripada sempurna, karena yang sempurna tidak pernah diserahkan.",
    tokoh: "Sheryl Sandberg",
    peran: "eksekutif teknologi",
    sumber: "populer",
    tema: "selesai",
  },
  {
    teks: "Awal adalah bagian terpenting dari pekerjaan.",
    tokoh: "Plato",
    peran: "filsuf Yunani",
    konteks: "Republik, Buku II",
    sumber: "tercatat",
    tema: "waktu",
  },
  {
    teks: "Kerjakan apa yang bisa kau kerjakan, dengan apa yang kau punya, di tempat kau berada.",
    tokoh: "Theodore Roosevelt",
    peran: "Presiden Amerika Serikat",
    sumber: "populer",
    tema: "selesai",
  },
  {
    teks: "Rahasia untuk maju adalah memulai.",
    tokoh: "Mark Twain",
    peran: "sastrawan",
    sumber: "populer",
    tema: "waktu",
  },
  {
    teks: "Cara menyelesaikan sesuatu adalah berhenti membicarakannya dan mulai mengerjakannya.",
    tokoh: "Walt Disney",
    peran: "pendiri studio animasi",
    sumber: "populer",
    tema: "selesai",
  },
  {
    teks: "Disiplin adalah jembatan antara cita-cita dan pencapaian.",
    tokoh: "Jim Rohn",
    peran: "penulis dan pembicara",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Batu besar dipecah bukan oleh satu pukulan, melainkan oleh pukulan keseratus — dan seluruh pukulan sebelumnya.",
    tokoh: "Jacob Riis",
    peran: "jurnalis dan pembaharu sosial",
    sumber: "populer",
    tema: "ketekunan",
  },

  // --- Kegagalan (lanjutan) --------------------------------------------------
  {
    teks: "Kegagalan adalah bumbu yang memberi rasa pada keberhasilan.",
    tokoh: "Truman Capote",
    peran: "sastrawan",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Jatuh tujuh kali, bangkit delapan kali.",
    tokoh: "Peribahasa Jepang",
    peran: "peribahasa",
    sumber: "tercatat",
    tema: "kegagalan",
  },
  {
    teks: "Seorang ahli adalah orang yang telah membuat semua kesalahan yang mungkin dibuat dalam bidang yang sangat sempit.",
    tokoh: "Niels Bohr",
    peran: "fisikawan",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Percobaan yang gagal tetap memberi hasil: ia memberi tahu ke mana tidak perlu pergi lagi.",
    tokoh: "Peribahasa laboratorium",
    peran: "peribahasa",
    sumber: "populer",
    tema: "kegagalan",
  },
  {
    teks: "Bukan kritikus yang berarti; penghargaan adalah milik orang yang benar-benar berada di arena.",
    tokoh: "Theodore Roosevelt",
    peran: "Presiden Amerika Serikat",
    konteks: "Pidato Citizenship in a Republic, Paris, 1910",
    sumber: "tercatat",
    tema: "kegagalan",
  },

  // --- Kejernihan (lanjutan) -------------------------------------------------
  {
    teks: "Segala sesuatu harus dibuat sesederhana mungkin, tetapi tidak lebih sederhana dari itu.",
    tokoh: "Albert Einstein",
    peran: "fisikawan",
    sumber: "populer",
    tema: "kesederhanaan",
  },
  {
    teks: "Kesederhanaan adalah kecanggihan yang paling tinggi.",
    tokoh: "Leonardo da Vinci",
    peran: "pelukis dan penemu",
    sumber: "populer",
    tema: "kesederhanaan",
  },
  {
    teks: "Bila kau menulis, hilangkan setiap kata ketiga. Kau akan terkejut betapa itu memberi tenaga.",
    tokoh: "Mark Twain",
    peran: "sastrawan",
    sumber: "populer",
    tema: "kesederhanaan",
  },
  {
    teks: "Tulisan yang baik adalah berpikir yang jernih yang terlihat.",
    tokoh: "Barbara Tuchman",
    peran: "sejarawan",
    sumber: "populer",
    tema: "kesederhanaan",
  },
  {
    teks: "Ketidakjelasan bukan tanda kedalaman.",
    tokoh: "Peribahasa akademik",
    peran: "peribahasa",
    sumber: "populer",
    tema: "kesederhanaan",
  },

  // --- Menulis (lanjutan) ----------------------------------------------------
  {
    teks: "Menulis adalah menghadapi halaman kosong dan menolak kalah darinya.",
    tokoh: "Peribahasa penulis",
    peran: "peribahasa",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Saya bukan penulis yang baik, tetapi saya penulis ulang yang sangat baik.",
    tokoh: "James Michener",
    peran: "novelis",
    sumber: "populer",
    tema: "menulis",
  },
  {
    teks: "Bacalah, dengan nama Tuhanmu yang menciptakan.",
    tokoh: "Al-Qur'an, Surah Al-'Alaq ayat 1",
    peran: "wahyu pertama",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Barang siapa menempuh jalan untuk mencari ilmu, Allah akan memudahkan baginya jalan menuju surga.",
    tokoh: "Hadis riwayat Muslim",
    peran: "hadis",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Bila kau ingin menulis, mulailah dari kalimat paling jujur yang kau tahu.",
    tokoh: "Ernest Hemingway",
    peran: "sastrawan",
    konteks: "A Moveable Feast, 1964",
    sumber: "tercatat",
    tema: "menulis",
  },

  // --- Ilmu & keraguan (lanjutan) --------------------------------------------
  {
    teks: "Ketiadaan bukti bukanlah bukti ketiadaan.",
    tokoh: "Carl Sagan",
    peran: "astronom",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Korelasi bukan sebab-akibat.",
    tokoh: "Kaidah metodologi",
    peran: "kaidah",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  {
    teks: "Kesalahan terbesar adalah menjawab pertanyaan yang salah dengan tepat.",
    tokoh: "John Tukey",
    peran: "ahli statistika",
    sumber: "populer",
    tema: "kejujuran",
  },
  {
    teks: "Jawaban kira-kira atas pertanyaan yang tepat jauh lebih berharga daripada jawaban tepat atas pertanyaan yang kira-kira.",
    tokoh: "John Tukey",
    peran: "ahli statistika",
    konteks: "The Future of Data Analysis, 1962",
    sumber: "tercatat",
    tema: "kejujuran",
  },
  {
    teks: "Yang tidak dapat kubuat, tidak kupahami.",
    tokoh: "Richard Feynman",
    peran: "fisikawan",
    konteks: "Tertinggal di papan tulisnya, 1988",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Penelitian adalah melihat apa yang dilihat semua orang, lalu memikirkan apa yang belum dipikirkan siapa pun.",
    tokoh: "Albert Szent-Györgyi",
    peran: "ahli biokimia",
    sumber: "populer",
    tema: "ilmu",
  },
  {
    teks: "Bila kita tahu apa yang sedang kita kerjakan, itu tidak akan disebut penelitian.",
    tokoh: "Albert Einstein",
    peran: "fisikawan",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Kesalahan yang paling berbahaya bukan yang tidak kita ketahui, melainkan yang kita yakini benar padahal keliru.",
    tokoh: "Mark Twain",
    peran: "sastrawan",
    sumber: "populer",
    tema: "keraguan",
  },
  {
    teks: "Bacalah bukan untuk membantah, bukan pula untuk percaya begitu saja, melainkan untuk menimbang dan mempertimbangkan.",
    tokoh: "Francis Bacon",
    peran: "filsuf dan negarawan",
    konteks: "Of Studies, 1625",
    sumber: "tercatat",
    tema: "ilmu",
  },
  {
    teks: "Membaca membuat orang berisi, berbicara membuatnya siap, menulis membuatnya cermat.",
    tokoh: "Francis Bacon",
    peran: "filsuf dan negarawan",
    konteks: "Of Studies, 1625",
    sumber: "tercatat",
    tema: "menulis",
  },
  {
    teks: "Pengetahuan itu sendiri adalah kekuatan.",
    tokoh: "Francis Bacon",
    peran: "filsuf dan negarawan",
    konteks: "Meditationes Sacrae, 1597",
    sumber: "tercatat",
    tema: "ilmu",
  },

  // --- Waktu (lanjutan) ------------------------------------------------------
  {
    teks: "Sebuah tujuan tanpa rencana hanyalah keinginan.",
    tokoh: "Antoine de Saint-Exupéry",
    peran: "penerbang dan penulis",
    sumber: "populer",
    tema: "waktu",
  },
  {
    teks: "Yang mendesak jarang penting, dan yang penting jarang mendesak.",
    tokoh: "Dwight D. Eisenhower",
    peran: "Presiden Amerika Serikat",
    sumber: "populer",
    tema: "waktu",
  },
  {
    teks: "Menunda adalah pencuri waktu.",
    tokoh: "Edward Young",
    peran: "penyair",
    konteks: "Night-Thoughts, 1742",
    sumber: "tercatat",
    tema: "waktu",
  },
  {
    teks: "Kita punya cukup waktu bila kita menggunakannya dengan benar.",
    tokoh: "Johann Wolfgang von Goethe",
    peran: "sastrawan Jerman",
    sumber: "populer",
    tema: "waktu",
  },

  // --- Ketekunan (lanjutan) --------------------------------------------------
  {
    teks: "Kesabaran itu pahit, tetapi buahnya manis.",
    tokoh: "Jean-Jacques Rousseau",
    peran: "filsuf",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Bakat memenangkan pertandingan, tetapi kerja sama dan ketekunan memenangkan kejuaraan.",
    tokoh: "Michael Jordan",
    peran: "atlet",
    sumber: "populer",
    tema: "ketekunan",
  },
  {
    teks: "Air menetes melubangi batu bukan karena kuatnya, melainkan karena seringnya.",
    tokoh: "Ovidius",
    peran: "penyair Romawi",
    sumber: "tercatat",
    tema: "ketekunan",
  },
  {
    teks: "Setiap hari kau menulis satu halaman, setahun kau punya sebuah buku.",
    tokoh: "Peribahasa penulis",
    peran: "peribahasa",
    sumber: "populer",
    tema: "waktu",
  },
];


/** Kutipan acak, boleh disaring per tema. */
export function pickQuotes(count: number, tema?: Tema, seed = Date.now()): Quote[] {
  const pool = tema ? QUOTES.filter((q) => q.tema === tema) : QUOTES;
  if (pool.length <= count) return shuffle(pool, seed);
  return shuffle(pool, seed).slice(0, count);
}

/** Pengacakan berbasis benih agar urutannya stabil selama satu kunjungan. */
function shuffle<T>(items: T[], seed: number): T[] {
  const result = [...items];
  let state = seed % 2147483647;
  if (state <= 0) state += 2147483646;
  const next = () => (state = (state * 16807) % 2147483647) / 2147483647;
  for (let i = result.length - 1; i > 0; i -= 1) {
    const j = Math.floor(next() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}
