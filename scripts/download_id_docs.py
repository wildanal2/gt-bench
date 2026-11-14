#!/usr/bin/env python3
"""Unduh dokumen Indonesia (baris sumber=id di data/sources.csv) lalu potong halaman terpilih.

Jalankan di komputer Anda (butuh akses ke situs .go.id / bank):
    python3 scripts/download_id_docs.py                 # unduh + potong halaman
    python3 scripts/download_id_docs.py --only ID07,ID13
    python3 scripts/download_id_docs.py --no-split      # unduh saja

Opsional: `pip install pypdf` untuk memotong halaman. Tanpa pypdf, hanya unduh.
Keluaran:
    data/documents/<ID>.pdf           dokumen utuh
    data/pages/<ID>_p<NNN>.pdf        satu file per halaman terpilih (nomor 1-based)
    data/download_log.csv             status, sha256, jumlah halaman
Kolom `halaman_dipilih`: "all", "1-12", atau "1-3;12-13". "MANUAL" = unduh lewat browser.
"""
import argparse
import csv
import hashlib
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources.csv"
RAW = ROOT / "data" / "documents"
PAGES = ROOT / "data" / "pages"
LOG = ROOT / "data" / "download_log.csv"
UA = "Mozilla/5.0 (benchmark-dataset-builder; riset internal)"


def parse_pages(spec, n):
    if spec.strip().lower() == "all":
        return list(range(1, n + 1))
    out = []
    for part in spec.split(";"):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return [p for p in out if 1 <= p <= n]


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if not data.startswith(b"%PDF"):
        raise ValueError("respons bukan PDF (mungkin halaman HTML/login/captcha)")
    dest.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def split(pdf_path, doc_id, spec):
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return None, "pypdf tidak terpasang; halaman tidak dipotong"
    reader = PdfReader(str(pdf_path))
    n = len(reader.pages)
    for p in parse_pages(spec, n):
        w = PdfWriter()
        w.add_page(reader.pages[p - 1])
        with open(PAGES / f"{doc_id}_p{p:03d}.pdf", "wb") as f:
            w.write(f)
    return n, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="daftar ID dipisah koma")
    ap.add_argument("--no-split", action="store_true")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    RAW.mkdir(parents=True, exist_ok=True)
    PAGES.mkdir(parents=True, exist_ok=True)

    rows = [r for r in csv.DictReader(open(SRC, encoding="utf-8")) if r["sumber"] == "id"]
    log = []
    for row in rows:
        doc_id = row["doc_id"]
        if only and doc_id not in only:
            continue
        entry = {"id": doc_id, "status": "", "sha256": "", "pages_total": "", "note": ""}
        if row["halaman_dipilih"].strip().upper() == "MANUAL":
            entry.update(status="manual", note="unduh lewat browser lalu simpan sebagai " + f"data/documents/{doc_id}.pdf")
            log.append(entry)
            print(f"[{doc_id}] MANUAL: {row['url']}")
            continue
        dest = RAW / f"{doc_id}.pdf"
        try:
            if not dest.exists():
                entry["sha256"] = download(row["url"], dest)
                time.sleep(1.0)  # sopan ke server
            else:
                entry["sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
            entry["status"] = "ok"
            if not args.no_split:
                n, note = split(dest, doc_id, row["halaman_dipilih"])
                entry["pages_total"] = n or ""
                entry["note"] = note
            print(f"[{doc_id}] ok")
        except Exception as e:  # noqa: BLE001 - catat semua kegagalan agar bisa diulang
            entry.update(status="gagal", note=str(e)[:200])
            print(f"[{doc_id}] GAGAL: {e}", file=sys.stderr)
        log.append(entry)

    # gabungkan dengan log lama supaya --only tidak menghapus baris dokumen lain
    old = {r["id"]: r for r in csv.DictReader(open(LOG, encoding="utf-8"))} if LOG.exists() else {}
    old.update({e["id"]: e for e in log})
    merged = [old[k] for k in sorted(old)]
    with open(LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "status", "sha256", "pages_total", "note"])
        w.writeheader()
        w.writerows(merged)
    ok = sum(1 for e in log if e["status"] == "ok")
    print(f"selesai: {ok}/{len(log)} berhasil; log di {LOG}")


if __name__ == "__main__":
    main()
