#!/usr/bin/env python3
"""Bangun data/manifest.csv: satu baris per halaman uji (halaman asli + varian scan sintetis).

Pemakaian (dari root repo):
    python3 scripts/build_manifest.py

Sumber informasi:
    data/sources.csv       metadata per dokumen (sumber, kategori, lisensi)
    data/pages/<page_id>.pdf
    data/scans/<profil>/<page_id>.pdf
    data/gt/<page_id>.json
Modality halaman asli dideteksi dari lapisan teks (pdftotext): < 50 karakter = scan.
"""
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# profil yang memutar halaman membuat bbox sumber tidak berlaku lagi
ROTATED_PROFILES = {"fax_skew"}

FIELDS = ["page_id", "doc_id", "sumber", "kategori", "bahasa", "varian", "modality", "pdf", "gt",
          "gt_status", "n_elemen", "n_teks", "n_heading", "n_tabel", "n_gambar", "bbox", "lisensi"]


def has_text_layer(pdf):
    out = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout
    return len(re.sub(r"\s", "", out)) >= 50


def gt_info(path):
    els = json.loads(path.read_text(encoding="utf-8"))
    types = Counter(e["type"] for e in els)
    notes = [e.get("gt_note", "") for e in els]
    if all(n.startswith("verif:") for n in notes):
        status = "verif:" + notes[0].split(";")[0].split(":", 1)[1]
    elif any(n.startswith("verif:") for n in notes):
        status = "sebagian_verif"
    else:
        status = "draf_model"
    text = " ".join(e.get("text", "") for e in els)
    return dict(
        gt_status=status, n_elemen=len(els), n_teks=types["text"], n_tabel=types["table"],
        n_gambar=types["image"], n_heading=sum(1 for e in els if "text_level" in e),
        bbox="ada" if all(e.get("bbox") for e in els) else "null",
    ), text


def main():
    docs = {r["doc_id"]: r for r in csv.DictReader(open(DATA / "sources.csv", encoding="utf-8"))}
    rows, missing = [], []
    for pdf in sorted((DATA / "pages").glob("*.pdf")):
        page_id = pdf.stem
        doc_id = page_id.rsplit("_p", 1)[0]
        meta = docs.get(doc_id, {})
        gt = DATA / "gt" / f"{page_id}.json"
        if not gt.exists():
            missing.append(page_id)
            continue
        info, text = gt_info(gt)
        if meta.get("sumber") == "dpbench":
            lang = "ko" if re.search("[가-힣]", text) else "en"
        else:
            lang = "id"
        base = dict(page_id=page_id, doc_id=doc_id, sumber=meta.get("sumber", "?"),
                    kategori=meta.get("kategori", "?"), bahasa=lang, gt=str(gt.relative_to(ROOT)),
                    lisensi=meta.get("lisensi_catatan", ""), **info)
        rows.append(dict(base, varian="asli", modality="digital" if has_text_layer(pdf) else "scan",
                         pdf=str(pdf.relative_to(ROOT))))
        for scan in sorted((DATA / "scans").glob(f"*/{page_id}.pdf")):
            prof = scan.parent.name
            bbox = info["bbox"]
            if bbox == "ada" and prof in ROTATED_PROFILES:
                bbox = "tidak berlaku (halaman diputar)"
            rows.append(dict(base, varian=prof, modality="scan_sintetis", pdf=str(scan.relative_to(ROOT)),
                             bbox=bbox))

    with open(DATA / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} baris ditulis ke data/manifest.csv")
    asli = [r for r in rows if r["varian"] == "asli"]
    for key in ("sumber", "kategori", "modality", "gt_status"):
        print(f"  halaman asli per {key}: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(r[key] for r in asli).items())))
    print("  varian scan: " + ", ".join(f"{k}={v}" for k, v in sorted(Counter(r["varian"] for r in rows if r["varian"] != "asli").items())))
    if missing:
        print(f"  PERINGATAN: {len(missing)} halaman tanpa GT: {missing[:10]}")


if __name__ == "__main__":
    main()
