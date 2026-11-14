#!/usr/bin/env python3
"""Validasi file GT per halaman terhadap skema standar (lihat docs/ANOTASI.md).

Pemakaian:
    python3 scripts/validate_gt.py data/gt [file.json ...]
Keluar dengan kode 1 kalau ada kesalahan.
"""
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

COMMON = {"type", "page_idx", "bbox", "gt_note"}
KEYS = {
    "text": COMMON | {"text", "in_figure"},
    "table": COMMON | {"table_body", "table_caption", "table_footnote"},
    "image": COMMON | {"img_path", "image_caption", "image_footnote"},
}
OPTIONAL = {"text": {"text_level"}, "table": set(), "image": set()}


class TableCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.errors, self.cells = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag not in ("table", "thead", "tbody", "tr", "td", "th", "br"):
            self.errors.append(f"tag asing <{tag}> di tabel (teks seperti <AUTO> harus ditulis &lt;AUTO&gt;)")
        if tag in ("table", "thead", "tbody", "tr", "td", "th"):
            self.stack.append(tag)
            if tag in ("td", "th"):
                self.cells += 1
                for k, v in attrs:
                    if k in ("rowspan", "colspan") and not (v or "").isdigit():
                        self.errors.append(f"{k}={v!r} bukan angka")

    def handle_endtag(self, tag):
        if tag in ("table", "thead", "tbody", "tr", "td", "th"):
            if not self.stack or self.stack[-1] != tag:
                self.errors.append(f"tag </{tag}> tidak cocok")
            else:
                self.stack.pop()


def check_table(html):
    errs = []
    if not html.strip().startswith("<table") or not html.strip().endswith("</table>"):
        errs.append("table_body harus diawali <table dan diakhiri </table>")
    p = TableCheck()
    p.feed(html)
    errs += p.errors
    if p.stack:
        errs.append(f"tag tidak ditutup: {p.stack}")
    if p.cells == 0:
        errs.append("tabel tanpa sel")
    return errs


def validate(path):
    errs = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return [f"JSON tidak valid: {e}"]
    if not isinstance(data, list) or not data:
        return ["isi harus array elemen yang tidak kosong"]
    for i, el in enumerate(data):
        t = el.get("type")
        if t not in KEYS:
            errs.append(f"[{i}] type tidak dikenal: {t!r}")
            continue
        keys = set(el)
        missing = KEYS[t] - keys
        extra = keys - KEYS[t] - OPTIONAL[t]
        if missing:
            errs.append(f"[{i}] key hilang: {sorted(missing)}")
        if extra:
            errs.append(f"[{i}] key asing: {sorted(extra)}")
        if el.get("page_idx") != 0:
            errs.append(f"[{i}] page_idx harus 0")
        b = el.get("bbox")
        if b is not None and not (isinstance(b, list) and len(b) == 4
                                  and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in b)
                                  and b[0] <= b[2] and b[1] <= b[3]):
            errs.append(f"[{i}] bbox harus null atau [x0, y0, x1, y1] ternormalisasi 0-1")
        note = el.get("gt_note")
        if not isinstance(note, str):
            errs.append(f"[{i}] gt_note harus string")
        elif not note.startswith(("draf_model", "verif:")):
            errs.append(f"[{i}] gt_note harus diawali draf_model atau verif:")
        if t == "text":
            if not isinstance(el.get("text"), str) or not el["text"].strip():
                errs.append(f"[{i}] text kosong")
            if not isinstance(el.get("in_figure"), bool):
                errs.append(f"[{i}] in_figure harus bool")
            if "text_level" in el and not (isinstance(el["text_level"], int) and el["text_level"] >= 1):
                errs.append(f"[{i}] text_level harus int >= 1")
        if t == "table":
            errs += [f"[{i}] {e}" for e in check_table(el.get("table_body") or "")]
        if t == "image" and el.get("img_path") is not None:
            errs.append(f"[{i}] img_path harus null")
        for k in ("table_caption", "table_footnote", "image_caption", "image_footnote"):
            if k in el and not (el[k] is None or (isinstance(el[k], str) and el[k].strip())):
                errs.append(f"[{i}] {k} harus string tidak kosong atau null")
    return errs


def main(args):
    if not args:
        sys.exit(__doc__)
    files = []
    for a in args:
        p = Path(a)
        files += sorted(p.glob("*.json")) if p.is_dir() else [p]
    bad = 0
    for f in files:
        errs = validate(f)
        n = len(json.loads(f.read_text(encoding="utf-8"))) if not errs or "JSON" not in errs[0] else 0
        if errs:
            bad += 1
            print(f"GAGAL {f.name}")
            for e in errs:
                print(f"   {e}")
        else:
            print(f"ok    {f.name} ({n} elemen)")
    print(f"{len(files) - bad}/{len(files)} valid")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
