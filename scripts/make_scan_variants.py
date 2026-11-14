#!/usr/bin/env python3
"""Buat varian "scan" sintetis (PDF berisi gambar saja, tanpa text layer) dari PDF digital.

Pemakaian:
    python3 scripts/make_scan_variants.py data/pages data/scans [--profiles a,b,c] [--only ID07,DPB0103] [--limit N]

Keluaran: data/scans/<profil>/<page_id>.pdf (nama sama dengan halaman sumber, GT di data/gt/<page_id>.json).

GT halaman sumber dipakai ulang tanpa perubahan untuk teks, tabel, dan urutan baca.
- Profil tanpa rotasi: bbox ternormalisasi tetap valid.
- Profil dengan rotasi (`fax_skew`): bbox TIDAK valid; pakai hanya untuk CER/WER/TEDS/reading order.
Hasil deterministik (seed dari nama file + profil). Membutuhkan `pdftoppm` (poppler-utils).
"""
import argparse
import hashlib
import io
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

PROFILES = {
    # nama: (dpi render, dpi akhir, sigma noise, blur radius, jpeg quality, sudut skew, binarisasi)
    "clean300": (300, 300, 2, 0.0, 70, 0.0, False),
    "office150": (300, 150, 10, 0.6, 45, 0.0, False),
    "lowres96": (300, 96, 6, 0.4, 60, 0.0, False),
    "fax_skew": (300, 200, 0, 0.3, None, 1.5, True),
}


def seed_for(name, profile):
    return int(hashlib.sha1(f"{name}:{profile}".encode()).hexdigest()[:8], 16)


def render_pages(pdf, dpi):
    with tempfile.TemporaryDirectory() as td:
        subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-png", str(pdf), f"{td}/p"], check=True)
        for f in sorted(Path(td).glob("p-*.png")):
            # pdftoppm bisa mengeluarkan RGB walau diberi -gray; paksa ke L agar fillcolor=255 putih.
            yield Image.open(f).convert("L")


def degrade(img, profile, rng):
    render_dpi, out_dpi, sigma, blur, jpeg_q, skew, binarize = PROFILES[profile]
    if out_dpi != render_dpi:
        s = out_dpi / render_dpi
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.LANCZOS)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if skew:
        angle = skew if rng.random() > 0.5 else -skew
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
    arr = np.asarray(img, dtype=np.float32)
    if sigma:
        arr = arr + rng.normal(0, sigma, arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    if binarize:
        arr = np.where(arr > 160, 255, 0).astype(np.uint8)
        return Image.fromarray(arr).convert("1"), out_dpi
    img = Image.fromarray(arr)
    if jpeg_q:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=jpeg_q)
        img = Image.open(io.BytesIO(buf.getvalue()))
    return img, out_dpi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--profiles", default=",".join(PROFILES))
    ap.add_argument("--only", default="", help="awalan nama halaman dipisah koma, mis. ID07,ID13")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah PDF sumber (0 = semua)")
    args = ap.parse_args()

    profiles = [p for p in args.profiles.split(",") if p]
    unknown = set(profiles) - set(PROFILES)
    if unknown:
        raise SystemExit(f"profil tidak dikenal: {unknown}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(Path(args.src).glob("*.pdf"))
    only = tuple(s.strip() for s in args.only.split(",") if s.strip())
    if only:
        pdfs = [p for p in pdfs if p.name.startswith(only)]
    if args.limit:
        pdfs = pdfs[: args.limit]

    n = 0
    for pdf in pdfs:
        for profile in profiles:
            rng = np.random.default_rng(seed_for(pdf.name, profile))
            pages = [degrade(p, profile, rng) for p in render_pages(pdf, PROFILES[profile][0])]
            dest = out / profile / pdf.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            imgs = [im for im, _ in pages]
            imgs[0].save(dest, "PDF", resolution=pages[0][1], save_all=True, append_images=imgs[1:])
            n += 1
    print(f"{n} varian dibuat di {out}; jalankan scripts/build_manifest.py untuk memperbarui manifest")


if __name__ == "__main__":
    main()
