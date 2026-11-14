# CLAUDE.md

Repo ini adalah **bahan uji** untuk menguji parser dokumen (MinerU, Docling, LlamaParse, LiteParse, dan lainnya):
halaman PDF beserta ground truth (GT) terverifikasi. Pengguna biasanya ingin menjalankan sebuah parser pada
halaman-halaman ini, lalu membandingkan keluarannya dengan GT. Bahasa kerja: Indonesia.

## Aturan wajib

- **Jangan mengubah apa pun di `data/`, `docs/`, atau `scripts/`** saat membantu pengujian. GT sudah diverifikasi
  manusia. Kalau GT tampak salah, catat `page_id`, indeks elemen, dan usulan koreksinya di
  `predictions/<tool>/gt_issues.md`, lalu beri tahu pengguna. Jangan membetulkannya sendiri.
- **Semua keluaran pengujian masuk ke `predictions/`** (diabaikan git). Kode evaluasi buatan pengguna juga diletakkan
  di sana atau di `eval/`, bukan di `scripts/`.
- **Sebagian data berhak cipta** (laporan keuangan bank ID07–ID12, ID25). Pakai hanya untuk pengujian parser.
  **Sebelum memakai parser cloud** (LlamaParse, API berbayar lain), tanyakan dulu ke pengguna, karena
  halamannya akan terkirim ke pihak ketiga.
- Jangan menebak flag CLI atau API parser. Cek dokumentasi versi yang terpasang (`--help`, docs resmi).

## Struktur

```
data/manifest.csv      daftar uji, satu baris per halaman uji (mulai dari sini)
data/pages/            <page_id>.pdf, satu halaman per file (input parser)
data/scans/<profil>/   <page_id>.pdf, varian scan sintetis (input parser, GT sama dengan halaman sumber)
data/gt/               <page_id>.json, GT per halaman
data/documents/        PDF utuh ID01–ID25 dan UA01–UA16 (uji latency, throughput, dokumen panjang; tanpa GT per dokumen)
data/sources.csv       metadata per dokumen (kategori, judul, url, lisensi)
docs/ANOTASI.md        standar GT lengkap (rujukan kalau ragu soal cara GT ditulis)
```

`page_id` = `<doc_id>_p<NNN>`, mis. `ID07_p010` (nomor halaman di dokumen asli) atau `DPB01030000000001_p001`.

## data/manifest.csv

| kolom | isi |
|---|---|
| `page_id`, `doc_id` | identitas halaman dan dokumen |
| `sumber` | `id` (dokumen Indonesia), `dpbench` (Upstage DP-Bench, en/ko), atau `uji_awal` (paper, file uji tabel, scan; en/es) |
| `kategori` | `laporan_keuangan`, `peraturan_scan`, `peraturan_digital`, `formulir`, `jurnal_id`, `dek_pemerintah`, `infografis_pemerintah`, `dpbench`, `paper_layout`, `tabel`, `scan_ocr` |
| `bahasa` | `id`, `en`, `ko`, `es` |
| `varian` | `asli`, atau profil scan sintetis `clean300` / `office150` / `lowres96` / `fax_skew` |
| `modality` | `digital` (ada lapisan teks), `scan` (scan nyata), `scan_sintetis` |
| `pdf` | path file yang dimasukkan ke parser |
| `gt` | path GT pembanding (varian scan menunjuk ke GT halaman sumbernya) |
| `gt_status` | `verif:<siapa>:<tanggal>` (terverifikasi) atau `draf_model` (**belum boleh dipakai menilai**, kecualikan) |
| `n_elemen`, `n_teks`, `n_heading`, `n_tabel`, `n_gambar` | jumlah elemen GT |
| `bbox` | `ada` (DP-Bench), `null` (halaman ID), `tidak berlaku (halaman diputar)` (`fax_skew`) |
| `lisensi` | catatan lisensi |
| `risiko` | alasan skor bisa bias (mis. paper tim Docling, file uji publik, duplikat) |

## Format GT

Setiap `data/gt/<page_id>.json` adalah array elemen **dalam urutan baca**:

```json
[
 {"type": "text", "text": "BAB I", "text_level": 2, "in_figure": false, "page_idx": 0, "bbox": null, "gt_note": "verif:AB:2026-11-14"},
 {"type": "table", "table_body": "<table><tr><th>Pos</th><th>2024</th></tr><tr><td>Kas</td><td>1.234</td></tr></table>",
  "table_caption": "dalam jutaan Rupiah", "table_footnote": null, "page_idx": 0, "bbox": null, "gt_note": "verif:..."},
 {"type": "image", "img_path": null, "image_caption": null, "image_footnote": null, "page_idx": 0, "bbox": null, "gt_note": "verif:...; logo"}
]
```

- `text_level` hanya ada di heading (1 = tertinggi). Skalanya tetap per jenis dokumen (lihat `docs/ANOTASI.md`).
- `in_figure: true` berarti teks di dalam gambar, grafik, slide bergambar, atau stempel.
- `table_body` berupa HTML dengan `<th>`, `rowspan`, dan `colspan`. Teks `<`/`>` di dalam sel di-escape (`&lt;`).
- `bbox`: `[x0, y0, x1, y1]` ternormalisasi 0–1, origin kiri-atas. Hanya ada di halaman DP-Bench.
- `gt_note`: penanda dipisah `; `. Yang penting untuk evaluasi:
  - `furniture`: header, footer, atau nomor halaman.
  - `src=<Kategori>`: kategori asli DP-Bench.
  - `src=Equation`: isi elemen berupa LaTeX.
  - `bilingual`: halaman berpasangan ID/EN.

## Konvensi yang memengaruhi skor

Tanyakan ke pengguna bagaimana konvensi berikut diperlakukan **sebelum** menghitung skor, lalu catat pilihannya di
`predictions/<tool>/README.md`. Perlakuan harus sama untuk semua tool.

1. **Furniture** (520 elemen di halaman ID). Banyak parser sengaja membuang header/footer. Biasanya elemen ini
   dikecualikan atau dinilai terpisah.
2. **`in_figure`** (1.025 elemen di halaman ID). Parser tanpa OCR gambar tidak akan mengeluarkannya.
3. **Teks verbatim.** Typo dan format angka Indonesia (`1.234,56`, `(6.222.853)`, `5,11%`) ditulis persis seperti
   tercetak. Pemenggalan kata di akhir baris tetap memakai tanda hubung (`perusa- haan`). Normalisasi
   (spasi, tanda kutip, tanda hubung) harus diterapkan sama ke GT dan prediksi.
4. **Halaman bilingual** (ID07, ID11, ID25): urutan baca berpasangan per blok, paragraf ID lalu paragraf EN-nya.
5. **Caption dan catatan tabel** ada di `table_caption`/`table_footnote` (halaman ID), bukan sebagai elemen teks.
6. **GT DP-Bench berbeda:** header tabel tidak ditandai `<th>` (gunakan TEDS-S atau abaikan tag th/td), caption
   berdiri sebagai elemen teks, dan heading hanya satu level.
7. **Metrik berbasis posisi** (mAP/IoU) hanya bisa dihitung untuk `sumber=dpbench` dengan `bbox=ada`.
8. **Laporkan skor terpisah** per `sumber` dan per `modality`. Kecualikan halaman `gt_status=draf_model`, dan
   sebutkan kolom `risiko` saat melaporkan hasil subset `uji_awal`. Jangan mencampur `scan_sintetis` dengan `scan` nyata.

## Alur pengujian yang disarankan

1. Baca `data/manifest.csv` dan pilih subset dengan pengguna, misalnya semua `varian=asli`, atau hanya `kategori=laporan_keuangan`.
2. Jalankan parser **per halaman** pada kolom `pdf`. Simpan keluaran mentah apa adanya:
   ```
   predictions/<tool>/<varian>/<page_id>.<ext>     # .md / .json / .html sesuai keluaran tool
   predictions/<tool>/run_log.csv                  # page_id,varian,detik,status,pesan_error
   predictions/<tool>/README.md                    # versi tool, perangkat (CPU/GPU), pengaturan (OCR, bahasa, model)
   ```
   - Halaman yang gagal atau timeout tetap dicatat di `run_log.csv` dengan `status=gagal`. Itulah bahan Failure Rate.
   - Ukur waktu per halaman, termasuk waktu muat model terpisah kalau bisa.
3. Konversi keluaran tool ke bentuk yang bisa dibandingkan dengan GT (urutan elemen teks, HTML tabel, heading +
   level). Konverternya disimpan di `eval/` atau `predictions/<tool>/`.
4. Hitung metrik. Setiap kali ada angka yang janggal, lihat contoh halamannya dulu sebelum menyimpulkan tool-nya
   jelek. Sering kali penyebabnya konvensi di atas, bukan kesalahan tool.
5. Uji latency dan throughput untuk dokumen panjang memakai `data/documents/*.pdf`.

## Membaca data dengan Python

```python
import csv, json
rows = [r for r in csv.DictReader(open("data/manifest.csv", encoding="utf-8")) if r["varian"] == "asli"]
for r in rows:
    gt = json.load(open(r["gt"], encoding="utf-8"))
    body = [e for e in gt if "furniture" not in e["gt_note"]]   # contoh: kecualikan furniture
    tables = [e["table_body"] for e in body if e["type"] == "table"]
    # jalankan parser pada r["pdf"], simpan ke predictions/<tool>/asli/{r['page_id']}.md
```

## Alat yang sudah ada (pemeliharaan dataset)

- `scripts/validate_gt.py data/gt`: cek skema GT. Jalankan setelah ada koreksi GT yang disetujui pengelola.
- `scripts/review_gt.py`: alat review GT di browser (http://127.0.0.1:8765), khusus untuk pengelola dataset.
- `scripts/build_manifest.py`: bangun ulang `data/manifest.csv`.
- Lingkungan: `uv venv .venv && uv pip install --python .venv/bin/python pypdf cryptography numpy pillow`,
  ditambah poppler. Parser yang diuji sebaiknya dipasang di venv terpisah supaya dependensinya tidak bentrok.
