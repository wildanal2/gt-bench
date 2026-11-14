#!/usr/bin/env python3
"""Cek silang angka di GT terhadap lapisan teks PDF halaman sumber.

Pemakaian:
    python3 scripts/check_gt_numbers.py data/gt [--prefix ID07,ID08]

Untuk tiap data/gt/<P>.json, semua token angka (mis. 1.234,56 / 169,338 / 5,11) dicari di
lapisan teks data/pages/<P>.pdf (spasi dibuang). Halaman tanpa lapisan teks (scan/gambar)
dilewati dan dilaporkan sebagai "tanpa lapisan teks": angkanya harus dicek manusia dari gambar.
Angka yang tidak ditemukan BELUM TENTU salah (bisa dari grafik vektor/banner), tapi wajib dicek.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "data" / "pages"


def numbers(elements):
    content = [{k: v for k, v in el.items() if k != "gt_note"} for el in elements]
    s = re.sub(r"<[^>]+>", " ", json.dumps(content, ensure_ascii=False))
    return set(re.findall(r"\d[\d.,]*\d", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("gt_dir")
    ap.add_argument("--prefix", default="")
    a = ap.parse_args()
    pref = tuple(p.strip() for p in a.prefix.split(",") if p.strip())
    for f in sorted(Path(a.gt_dir).glob("*.json")):
        if pref and not f.stem.startswith(pref):
            continue
        layer = subprocess.run(["pdftotext", str(PAGES / f"{f.stem}.pdf"), "-"],
                               capture_output=True, text=True).stdout
        flat = re.sub(r"\s+", "", layer)
        nums = numbers(json.loads(f.read_text(encoding="utf-8")))
        if len(flat) < 50:
            print(f"{f.stem}: {len(nums)} angka; tanpa lapisan teks -> cek visual")
            continue
        miss = sorted(n for n in nums if n not in flat)
        tag = "ok" if not miss else f"{len(miss)} tidak ditemukan: {miss[:10]}"
        print(f"{f.stem}: {len(nums)} angka; {tag}")


if __name__ == "__main__":
    main()
