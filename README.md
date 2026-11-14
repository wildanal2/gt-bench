# gt-bench: Bahan Uji Document Parsing

Kumpulan halaman uji beserta ground truth (GT) terverifikasi untuk menguji parser dokumen
(MinerU, Docling, LlamaParse, LiteParse, dan lainnya). Repo ini hanya berisi bahan uji. Menjalankan parser
dan menghitung metrik dilakukan di luar folder `data/`.

## Isi

| Sumber | Halaman | GT | bbox |
|---|---|---|---|
| Dokumen Indonesia `ID01–ID25`: laporan keuangan, peraturan, formulir, jurnal, dek, infografis | 174 (158 digital, 16 scan nyata), 104 tabel | diverifikasi manusia (`verif:…`) | `null` |
| DP-Bench `DPB…` (Upstage, Inggris/Korea) | 200, 55 tabel | GT manusia DP-Bench | ada |
| Dokumen uji awal `UA01–UA16`: paper arXiv/IEEE, file uji tabel, scan faks dan surat (Inggris, 1 Spanyol) | 73 (61 digital, 12 scan) | diverifikasi manusia (`verif:…`) | `null` |
| Varian scan sintetis `clean300`, `office150`, `lowres96`, `fax_skew` | 60 halaman DP-Bench × 4 | ikut halaman sumber | ikut sumber, kecuali `fax_skew` |

## Struktur

```
data/
  manifest.csv       DAFTAR UJI: satu baris per halaman (asli + varian scan) → pdf yang diuji + gt pembandingnya
  sources.csv        satu baris per dokumen: sumber, kategori, judul, url, lisensi
  pages/             halaman uji, satu PDF per halaman: <doc_id>_p<NNN>.pdf
  gt/                GT per halaman: <doc_id>_p<NNN>.json
  scans/<profil>/    varian scan sintetis: <page_id>.pdf (GT-nya data/gt/<page_id>.json)
  documents/         PDF utuh (ID01–ID25, UA01–UA16), untuk uji dokumen panjang, latency, throughput
  download_log.csv   asal unduhan dokumen Indonesia (sha256)
  NOTICE_DPBENCH.md  lisensi DP-Bench
docs/ANOTASI.md      standar GT: skema, aturan isi, keputusan anotasi
scripts/             alat pemeliharaan dataset (tidak dibutuhkan untuk menguji parser)
```

## Cara menguji parser

1. **Ambil daftar uji dari `data/manifest.csv`.** Kolom `pdf` berisi file yang dimasukkan ke parser, dan kolom
   `gt` berisi pembandingnya. Filter dengan kolom `sumber`, `kategori`, `modality` (`digital` / `scan` /
   `scan_sintetis`), dan `varian`.
2. **Jalankan parser per halaman** dan simpan output di luar `data/`, dengan nama mengikuti `page_id`:
   ```
   predictions/<tool>/<varian>/<page_id>.md      (atau .json / .html sesuai keluaran tool)
   predictions/<tool>/run_log.csv                page_id, varian, detik, status (ok/gagal), pesan_error
   ```
   Catat versi tool dan pengaturannya (OCR on/off, model, bahasa) di `predictions/<tool>/README.md`.
3. **Jangan mengubah apa pun di `data/`.** Kalau menemukan GT yang salah, catat `page_id`, nomor elemen, dan
   koreksinya, lalu laporkan ke pengelola dataset.
4. **Laporkan skor terpisah** per sumber (`id` / `dpbench` / `uji_awal`) dan per modality. Pakai hanya halaman
   dengan `gt_status` diawali `verif:`. Lihat juga kolom `risiko`: beberapa dokumen `UA` ditulis tim Docling atau
   berasal dari test suite publik, sehingga skornya bisa bias. Skor scan sintetis jangan
   dicampur dengan scan nyata.

## Format GT (ringkas)

Setiap file GT berisi array elemen **dalam urutan baca**. Rincian lengkapnya ada di `docs/ANOTASI.md`.

```json
{"type": "text",  "text": "...", "text_level": 2, "in_figure": false, "page_idx": 0, "bbox": null, "gt_note": "verif:..."}
{"type": "table", "table_body": "<table>...</table>", "table_caption": "...", "table_footnote": null, ...}
{"type": "image", "img_path": null, "image_caption": null, "image_footnote": null, ...}
```

## Konvensi GT yang memengaruhi skor

Konvensi berikut perlu diputuskan sama untuk semua tool **sebelum** menghitung skor:

- **Furniture.** Header berjalan, footer, dan nomor halaman tetap ada di GT dengan `furniture` di `gt_note`
  (520 elemen di halaman ID). Banyak parser sengaja membuangnya. Pilih apakah elemen ini dikecualikan atau
  dinilai terpisah.
- **Teks di dalam gambar** (`in_figure: true`, 1.025 elemen di halaman ID) mencakup label grafik, teks slide
  berupa gambar, dan teks stempel. Parser yang tidak meng-OCR gambar akan kehilangan elemen ini, jadi nilai
  terpisah atau kecualikan.
- **Teks verbatim.** Typo dan format angka Indonesia (`1.234,56`, `(6.222.853)`) ditulis persis seperti
  tercetak. Pemenggalan kata di akhir baris tetap memakai tanda hubung.
- **Halaman bilingual** (ID07, ID11, ID25): urutan baca berpasangan per blok, paragraf ID lalu paragraf EN-nya.
- **Level heading** tetap per jenis dokumen (lihat `docs/ANOTASI.md`), tidak dihitung ulang per halaman.
- **Tabel** berupa HTML dengan `<th>`, `rowspan`, dan `colspan`. Caption dan catatan tabel ada di
  `table_caption`/`table_footnote`, bukan sebagai elemen teks. Persamaan ditulis LaTeX.
- **GT DP-Bench berbeda dalam beberapa hal:** header tabel tidak ditandai `<th>`, caption berdiri sebagai elemen
  teks, heading hanya satu level, dan kategori asli ada di `gt_note` (`src=…`).
- **bbox** hanya ada di halaman DP-Bench (ternormalisasi 0–1, origin kiri-atas). Metrik berbasis posisi
  (mAP/IoU) hanya bisa dihitung di DP-Bench dan varian scan-nya selain `fax_skew`.

## Lisensi dan kerahasiaan

- Dataset ini disediakan untuk riset dan benchmark parser dokumen. Hak cipta setiap dokumen tetap milik penerbitnya.
- Laporan keuangan bank (ID07–ID12, ID25) adalah dokumen berhak cipta milik perusahaan. Dokumen ini diambil dari
  publikasi resmi mereka dan disertakan apa adanya untuk keperluan pengujian. Pemilik hak yang keberatan dapat membuka issue.
- DP-Bench: MIT (Upstage), lihat `data/NOTICE_DPBENCH.md`.
- Dokumen lain: lihat kolom `lisensi_catatan` di `data/sources.csv`.
- Mengirim halaman ke parser berbasis cloud (misalnya LlamaParse) berarti mengunggah dokumen ke pihak ketiga.
  Pastikan itu diizinkan untuk dokumen terkait.

## Pemeliharaan dataset (untuk pengelola)

```bash
uv venv .venv && uv pip install --python .venv/bin/python pypdf cryptography numpy pillow   # + poppler
.venv/bin/python scripts/validate_gt.py data/gt        # cek skema GT dan HTML tabel
.venv/bin/python scripts/review_gt.py                  # alat review/koreksi GT di browser (http://127.0.0.1:8765)
.venv/bin/python scripts/check_gt_numbers.py data/gt   # cek angka GT terhadap lapisan teks PDF
.venv/bin/python scripts/make_scan_variants.py data/pages data/scans --only ID16 --profiles office150
.venv/bin/python scripts/build_manifest.py             # bangun ulang data/manifest.csv
.venv/bin/python scripts/download_id_docs.py           # unduh ulang dokumen ID (ID09, ID12: lewat browser)
```

Kalau GT dikoreksi, `gt_note` setiap elemen diawali `verif:<inisial>:<tanggal>`, dan versi lama disimpan di
`.cache/review/history/`.
