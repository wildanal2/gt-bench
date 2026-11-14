# Standar GT per Halaman

Satu standar untuk semua halaman uji di `data/`, baik dokumen Indonesia (`ID..`) maupun DP-Bench (`DPB..`).

## Berkas

- Halaman: `data/pages/<page_id>.pdf` (satu halaman), `page_id` = `<doc_id>_p<NNN>` (nomor halaman di dokumen asli).
- GT: `data/gt/<page_id>.json`, berisi array elemen **dalam urutan baca**.
- Varian scan sintetis: `data/scans/<profil>/<page_id>.pdf`, memakai GT halaman sumbernya.
- Validasi: `.venv/bin/python scripts/validate_gt.py data/gt`.

## Elemen

Semua elemen punya `page_idx: 0`, `bbox`, dan `gt_note` (string, diawali status verifikasi, lihat bawah).

- `bbox` **opsional**: `[x0, y0, x1, y1]` ternormalisasi 0–1 dengan origin kiri-atas, hanya kalau berasal dari
  anotasi manusia (saat ini DP-Bench). Tanpa anotasi manusia, `bbox: null` (semua halaman `ID..`).
  Pada varian `fax_skew` halaman diputar, sehingga bbox sumber tidak berlaku.

| type | key wajib | catatan |
|---|---|---|
| `text` | `text`, `in_figure` | `text_level` (int ≥1) **hanya** untuk judul/heading; skala per jenis dokumen, lihat bagian keputusan di bawah. |
| `table` | `table_body`, `table_caption`, `table_footnote` | `table_body` = HTML `<table>…</table>`; baris header pakai `<th>`; sel gabung pakai `rowspan`/`colspan`; sel kosong `<td></td>`. |
| `image` | `img_path` (null), `image_caption`, `image_footnote` | foto, logo, grafik, diagram, stempel, tanda tangan. |

### GT DP-Bench (`DPB..`)

Hasil konversi GT manusia Upstage DP-Bench. Status `verif:dpbench:upstage`, kategori asli ada di `gt_note`
(`src=Paragraph`, `src=Header`, …). Bedanya dengan GT `ID..`: header tabel tidak ditandai `<th>`, caption
berdiri sebagai elemen `text` (belum ditautkan ke tabel/gambar), heading hanya satu level, dan persamaan
ditulis LaTeX (`src=Equation`). Lisensi: `data/NOTICE_DPBENCH.md`.

Aturan isi dan keputusan di bawah ini berlaku untuk anotasi halaman `ID..`.

## Aturan isi

1. **Verbatim.** Salin teks persis seperti tercetak: ejaan, kapitalisasi, tanda baca, format angka
   Indonesia (`1.234,56`, `(6.222.853)`, `5,11%`). Jangan membetulkan typo.
2. **Baris dalam satu paragraf digabung dengan satu spasi.** Pemenggalan kata di akhir baris
   (`perusa-` / `haan`) dibiarkan apa adanya, dengan tanda hubung, lalu dicatat `hyphen` di `gt_note`.
3. **Satu elemen = satu blok logis**: paragraf, butir daftar, judul, sel isian formulir yang berdiri sendiri.
   Butir daftar bernomor = satu elemen per butir, nomor/huruf butir ikut di `text`.
4. **Anti-duplikasi.** Caption tabel/gambar masuk `table_caption`/`image_caption`, bukan elemen `text`
   terpisah. Catatan kaki tabel masuk `table_footnote`. Teks yang sudah ada di dalam tabel tidak diulang.
5. **Teks di dalam gambar/grafik/infografis** (label sumbu, angka di chart, teks di slide yang berupa gambar
   tetapi tetap terbaca) dicatat sebagai `text` dengan `in_figure: true`, tepat setelah elemen `image`-nya.
6. **Furniture** (header berjalan, footer, nomor halaman, URL footer, watermark): tetap dicatat sebagai `text`,
   `gt_note` berisi `furniture`.
7. **Bilingual berdampingan** (kiri ID, kanan EN): baca kolom kiri penuh per blok, lalu kanan,
   kecuali sumber jelas berpasangan per baris. Catat `bilingual` di `gt_note`.
8. **Formulir**: label + kotak isian kosong → `text` label saja. Struktur kisi jelas → `table`.
   Teks vertikal ditulis dalam urutan baca normal, `gt_note: vertikal`.
9. **Tidak yakin** → tulis bacaan terbaik, beri `[?]` di `gt_note` beserta alasannya. Tidak terbaca → `[ilegibel]` di `text`.
10. **Stempel, paraf, tanda tangan** → `image` dengan `gt_note` `stempel`/`paraf`/`tanda_tangan`.
    Teks stempel yang terbaca → `text`, `in_figure: true`.

11. **Tipe caption/footnote**: `table_caption`, `table_footnote`, `image_caption`, `image_footnote` berisi
    string atau `null`. Jangan pakai list atau `""`. Beberapa baris digabung dengan `\n`.

## Keputusan dari pilot (12 Nov 2026)

Kasus berikut muncul di pilot dan sudah diputuskan. Draf berikutnya mengikuti keputusan ini:

- **Judul bertumpuk beberapa baris** (judul peraturan: PERATURAN … / NOMOR … / TENTANG … / …) dicatat sebagai
  **satu** elemen `text_level: 1`.
- **Label + daftar** (`Menimbang :`, `Mengingat :`) → label dicatat sebagai elemen sendiri, lalu satu elemen per butir (`a. bahwa …`).
- **Butir tanpa nomor** (penanda kotak/bulat) → satu elemen per butir, penanda tidak ditulis.
- **Paragraf yang terpotong antar kolom** digabung menjadi satu elemen, `gt_note: lintas_kolom`.
  Paragraf lanjutan dari halaman sebelumnya tetap dijadikan elemen sendiri, `gt_note: lanjutan`.
- **Judul laporan di atas tabel** ("LAPORAN POSISI KEUANGAN", periode) → `text` (judul = `text_level 1`).
  Hanya catatan satuan seperti "(Jutaan)" yang masuk `table_caption`.
- **Baris seksi di tabel** (ASET, LIABILITAS) → `<td>` biasa dengan sel nilai kosong, tanpa colspan.
- **Judul dan sumber yang tercetak di dalam infografis** → `text` `in_figure: true`, bukan `image_caption`.
  Label grafik batang ditulis satu elemen per batang (label + nilai, sesuai urutan baca).
- **Hiasan tanpa teks** (pita, bentuk dekoratif, garis potong) tidak dicatat. Gambar ilustrasi/foto tetap dicatat sebagai `image`.
- **Teks yang hanya ada di lapisan teks tetapi tidak terlihat di halaman** tidak dicatat. Yang menjadi acuan adalah tampilan visual halaman.
- **Kata ulang yang terpotong di akhir baris** (`benar-` / `benar`) ditulis utuh `benar-benar`. Aturan 2 hanya berlaku untuk pemenggalan suku kata.
- **Footer beberapa baris** → satu elemen per baris, nomor halaman sebagai elemen sendiri.

## Keputusan dari laporan keuangan (13 Nov 2026)

- **Bilingual berpasangan** (paragraf ID dan EN sejajar): urutannya blok ID lalu blok EN-nya, bergantian per pasangan.
  Ini menggantikan bacaan harfiah aturan 7 untuk halaman yang jelas berpasangan.
- **Tabel bilingual dengan label ID dan EN di kolom terpisah** → tabel 5 kolom: label ID | Catatan | tahun | tahun | label EN.
  Sel header di atas kolom label diisi `<th></th>`. Kedua catatan satuan (ID, EN) masuk `table_caption`, dipisah `\n`.
- **Label ID/EN bertumpuk dalam satu sel** → digabung dengan satu spasi.
- **`text_level` tetap** di semua halaman laporan keuangan (bukan per halaman):
  - 1 = judul sampul, judul surat/laporan (Surat Pernyataan Direksi, Laporan Auditor Independen, Laporan Posisi
    Keuangan, dst.), judul bagian besar (`UMUM`, `PERMODALAN`, `TABLE OF CONTENTS`), Pengurus/Pemegang Saham.
  - 2 = nama perusahaan di bawah judul, seksi laporan auditor (Opini, Basis Opini, Hal Audit Utama, Informasi Lain,
    Tanggung Jawab …), laporan bernomor di publikasi risiko (`1. Laporan Ukuran Utama …`), subjudul ikhtisar.
  - 3 = butir Hal Audit Utama (`1. Kerugian Kredit Ekspektasian …`).
  - 4 = `Bagaimana audit kami merespons Hal Audit Utama` di bawah tiap butir.
  - Pasangan ID/EN memakai level yang sama.
- **Tabel lanjutan dari halaman sebelumnya**: tanpa judul baru, header ditulis hanya kalau dicetak ulang, `gt_note: lanjutan`.
- **Baris seksi yang melebar sampai kolom No.**: label ditaruh di sel pertama, sel lain `<td></td>`, tanpa colspan.
- **Kalimat footer yang berulang** ("Catatan atas laporan keuangan … merupakan bagian …") → `text` furniture, bukan `table_footnote`.
- **Blok identitas penandatangan** (Nama / Alamat / Jabatan : …) → satu elemen `text` per butir bernomor dengan pola
  `1. Nama : … Alamat Kantor : … Jabatan : …`. Tidak dibuat tabel.
- **Blok tanpa garis dengan pola label : nilai di dalam laporan publikasi** (Pengurus, Pemegang Saham) → tabel 3 kolom: label | `:` | nilai.
- **Spasi ganda** di sumber diringkas menjadi satu spasi.
- **Kata majemuk berhubung yang terpotong di akhir baris** (`held-to-` / `maturity`, `POST-` / `EMPLOYMENT`) ditulis utuh.
- **Sel yang diblok hitam/abu tanpa nilai** → `<td></td>`.
- **Meterai, QR code, strip ikon navigasi** → `image`. Teks yang terbaca di meterai/QR → `text` `in_figure: true`.

## Keputusan untuk peraturan (13 Nov 2026)

Di dokumen peraturan (ID13–ID17), `text_level` **tetap** di semua halaman supaya hierarki bisa dinilai lintas
halaman.

| Unsur | `text_level` | Contoh `text` |
|---|---|---|
| Judul peraturan (PERATURAN … NOMOR … TENTANG …) | 1 | satu elemen, baris digabung |
| BAB + judul BAB | 2 | `BAB I KETENTUAN UMUM` (dua baris digabung) |
| Bagian + judulnya | 3 | `Bagian Kesatu Umum` |
| Paragraf + judulnya | 4 | `Paragraf 1 Persyaratan` |
| Pasal | 5 | `Pasal 1` |

- Ayat `(1)`, huruf `a.`, dan angka `1.` → `text` biasa, satu elemen per ayat/butir. Nomornya ikut ditulis.
- `Menimbang :`, `Mengingat :`, `MEMUTUSKAN:`, `Menetapkan :` → `text` biasa, bukan heading.
- Kop "MENTERI KEUANGAN REPUBLIK INDONESIA" dan penanda "SALINAN" → `text` biasa, `gt_note: kop` / `penanda salinan`.
- Header/footer berjalan (nomor halaman `- 2 -`, URL jdih/peraturan.go.id, "www.djpp.kemenkumham.go.id") → furniture.
- Lanjutan kalimat/ayat dari halaman sebelumnya → elemen sendiri, `gt_note: lanjutan`.
- Penjelasan/lampiran yang memuat tabel → `table`.

## Keputusan untuk jurnal dan formulir (13 Nov 2026)

**Jurnal (ID21–ID24)**: `text_level` **tetap** di semua halaman: judul paper 1, seksi (`1. Pendahuluan`,
`Abstract`, `Daftar Pustaka`/`References`) 2, subseksi (`2.1 …`) 3, sub-subseksi 4.
- Penulis, afiliasi, email, info artikel → `text` biasa (satu elemen per blok).
- `Abstract`/`Abstrak` dan `Keywords`/`Kata kunci`: kalau label dicetak sebaris dengan isinya, label ikut di
  `text` (bukan heading). Kalau label berdiri sendiri, label jadi heading level 2.
- Header jurnal (nama jurnal, vol/no, DOI, lisensi) di setiap halaman → furniture.
- Persamaan → `text` berisi LaTeX, `gt_note: src=Equation; isi berupa LaTeX`. Nomor persamaan `(1)` ikut di akhir.
- Daftar pustaka → satu elemen per entri, nomor `[1]` ikut ditulis.
- Caption `Table 1. …` / `Gambar 1. …` masuk `table_caption`/`image_caption`. Label dan isi di dalam gambar/diagram
  → `text` `in_figure: true`.

**Formulir (ID18–ID20)**: ikuti `ID19_p001.json`. Kisi berbingkai → `table` (kotak isian kosong `<td></td>`).
Label lepas → `text`. Kode isian (I.01, A.10) ikut di label. Teks vertikal ditulis normal, `gt_note: vertikal`.
- Bilingual (ID20): label ID dan EN yang bertumpuk di satu sel/blok digabung dengan ` / ` kalau dicetak dengan
  garis miring. Kalau tidak, digabung dengan satu spasi.
- Petunjuk pengisian (halaman instruksi berisi teks panjang) → paragraf/butir seperti biasa.

**Formulir SPT 1770 S, struktur seragam** (mengikuti `ID20_p007.json`): satu tabel untuk seksi A–G, dengan kolom
pertama berisi label seksi (teks vertikal, `rowspan`). `<AUTO>` di luar bingkai dijadikan kolom sendiri, ditulis
`&lt;AUTO&gt;`. Opsi bercabang dua kolom dibaca kolom kiri dulu (a, b, lalu c, d). Blok IDENTITAS ditulis sebagai `text`.

## Keputusan untuk dek, panduan, dan infografis (13 Nov 2026)

Acuan: `ID01_p003.json` (slide berupa gambar), `ID04_p002.json` (newsletter/infografis), `ID06_p002.json` (BRS).

- **Slide yang seluruhnya gambar** (tanpa lapisan teks): diperlakukan sebagai tata letak biasa. Judul slide → `text_level 1`,
  teks slide → `text` (`in_figure: false`), ilustrasi/ikon bergambar → `image`. Hanya teks di dalam ilustrasi, foto,
  atau logo yang `in_figure: true`.
- **Tabel di slide** → `table` kalau berkisi jelas.
- **Screenshot aplikasi** (panduan e-Form): `image`. Label UI yang terbaca pada ukuran cetak → `text` `in_figure: true`,
  dibaca baris demi baris dari kiri ke kanan. Teks yang terlalu kecil untuk dibaca dilewati, dan hal ini dicatat di `gt_note` image-nya.
- **Langkah bernomor di panduan** → satu elemen per langkah.
- **Grafik** (batang, garis, pai): `image` + `text` `in_figure: true` untuk judul, label, dan nilai yang tercetak.
  Grafik batang ditulis satu elemen per batang, sedangkan grafik garis/pai satu elemen per label data yang tercetak.
  Label sumbu dan legenda masing-masing satu elemen.
- **Tabel statistik BRS** → `table` biasa. Judul `Tabel N. …` masuk `table_caption`. `Sumber: …` dan catatan masuk `table_footnote`.
- **`text_level` tetap** (bukan per halaman), supaya hierarki bisa dinilai lintas halaman:
  - Slide (ID01, ID02): judul sampul dan judul slide = 1, subjudul di dalam slide = 2.
  - Siaran pers (ID03): judul dokumen = 1, seksi `A.`/`B.` = 2.
  - BRS (ID06): judul rilis = 1, seksi `A.`/`B.`/`C.` = 2, subseksi `1.`/`2.`/`3.` = 3.
  - Newsletter (ID04, ID05), ditentukan dari ukuran huruf di lapisan teks: judul sampul dan judul artikel
    (±25–28 pt) = 1; subjudul artikel, tagline sampul, dan judul boks/infografis (±16–19 pt) = 2; subjudul
    di dalam kolom (±14 pt) = 3. Kicker kecil di atas judul artikel digabung dengan judulnya.
- **Kotak sorotan/angka besar** (mis. "5,11%" + keterangan) → `text`. Kotak yang merupakan bagian dari grafik → `in_figure: true`.

## Keputusan untuk dokumen uji awal `UA..` (14 Nov 2026)

Paper berbahasa Inggris (UA01–UA07), file uji tabel (UA08–UA11), dan scan (UA12–UA16).

- **Skala heading paper** sama dengan jurnal: judul 1, seksi utama (Abstract, `1 Introduction`, References) 2,
  subseksi 3, sub-subseksi 4. Heading tebal yang sebaris dengan paragraf (mis. `Acknowledgements`) tetap bagian paragraf.
- **Surat dan paket instruksi (UA16)**: judul dokumen atau halaman 1, judul bagian 2.
- **Stempel arXiv vertikal** di tepi kiri → `text` furniture, selalu elemen pertama.
- **Catatan kaki** → `text`, `gt_note: footnote`. Angka superskrip penanda ditulis sebagai angka biasa.
- **Kode/listing** → satu `text` per blok, baris dipisah `\n`, `gt_note: kode`, tanpa nomor baris di margin.
- **Matematika inline** (di teks dan sel tabel) ditulis rata mengikuti lapisan teks: subskrip/superskrip jadi
  karakter biasa tanpa markup dan tanpa superskrip Unicode (`10−9`, `O(n2 · d)`, `β1`). Persamaan display ditulis
  LaTeX. Parser yang mengeluarkan LaTeX inline (`$10^{-9}$`) perlu dinormalisasi dulu sebelum dibandingkan.
- **Small caps** ditulis kapital penuh sesuai lapisan teks.
- **Gambar berisi cuplikan halaman/screenshot** → satu `image`; teks di dalamnya yang terlalu kecil tidak ditranskripsi
  (dicatat di `gt_note`).
- **UA13 (linn) dan UA14 (skew)** memakai GT yang sama dengan UA12 (ccitt), karena isinya sama.

## `gt_note`

Daftar penanda dipisah `; `. Penanda pertama adalah status: `draf_model` atau `verif:<siapa>:<tanggal>`. Contoh:
`draf_model; src=Heading; furniture` atau `draf_model; [?] angka buram`.

## Status verifikasi

Draf belum boleh dipakai sebagai GT final. Setelah diverifikasi manusia, ganti `draf_model` menjadi
`verif:<inisial>:<tanggal>` di **setiap** elemen.
