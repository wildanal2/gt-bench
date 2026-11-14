#!/usr/bin/env python3
"""Alat verifikasi GT berbasis browser (lokal, tanpa internet).

Pemakaian (dari root repo):
    .venv/bin/python scripts/review_gt.py            # buka http://127.0.0.1:8765
    .venv/bin/python scripts/review_gt.py --port 9000 --no-browser

Kiri: daftar halaman + progres. Tengah: gambar halaman. Kanan: elemen GT yang bisa diedit
(teks, level heading, sel tabel, caption). Tombol "Verifikasi" menyimpan dan mengganti status
`draf_model` menjadi `verif:<inisial>:<tanggal>` di semua elemen halaman itu.
Setiap simpan divalidasi dengan validate_gt.py; versi lama disimpan di .cache/review/history/.
"""
import argparse
import datetime
import html
import json
import re
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from check_gt_numbers import numbers  # noqa: E402
from validate_gt import validate  # noqa: E402

DATA = ROOT / "data"
PAGES, GT = DATA / "pages", DATA / "gt"
CACHE = ROOT / ".cache" / "review"
IMG, HIST = CACHE / "img", CACHE / "history"
PAGE_RE = re.compile(r"^[A-Za-z0-9_-]+$")
LOCK = threading.Lock()


def status_of(els):
    notes = [e.get("gt_note", "") for e in els]
    if notes and all(n.startswith("verif:") for n in notes):
        return "verif"
    if any(n.startswith("verif:") for n in notes):
        return "sebagian"
    return "draf"


def text_layer(page_id):
    out = subprocess.run(["pdftotext", str(PAGES / f"{page_id}.pdf"), "-"], capture_output=True, text=True).stdout
    return re.sub(r"\s+", "", out)


def list_pages():
    out = []
    for g in sorted(GT.glob("*.json")):
        els = json.loads(g.read_text(encoding="utf-8"))
        flagged = sum(1 for e in els if "[?]" in e.get("gt_note", "") or "[ilegibel]" in json.dumps(e, ensure_ascii=False))
        out.append(dict(id=g.stem, status=status_of(els), n=len(els), flagged=flagged,
                        tables=sum(1 for e in els if e["type"] == "table")))
    return out


def page_detail(page_id):
    els = json.loads((GT / f"{page_id}.json").read_text(encoding="utf-8"))
    flat = text_layer(page_id)
    scan = len(flat) < 50
    missing = None if scan else sorted(n for n in numbers(els) if n not in flat)
    return dict(id=page_id, elements=els, scan=scan, missing_numbers=missing, status=status_of(els))


def set_status(els, token):
    for e in els:
        note = e.get("gt_note", "")
        first, _, rest = note.partition(";")
        if first.startswith(("draf_model", "verif:")):
            note = token + (";" + rest if rest else "")
        else:
            note = token + ("; " + note if note else "")
        e["gt_note"] = note
    return els


def save_page(page_id, els, action, initials):
    if action == "verify":
        if not re.fullmatch(r"[A-Za-z]{1,6}", initials or ""):
            return ["isi inisial (1-6 huruf) dulu"]
        els = set_status(els, f"verif:{initials.upper()}:{datetime.date.today().isoformat()}")
    elif action == "unverify":
        els = set_status(els, "draf_model")
    target = GT / f"{page_id}.json"
    tmp = CACHE / f"{page_id}.tmp.json"
    tmp.write_text(json.dumps(els, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    errs = validate(tmp)
    if errs:
        tmp.unlink()
        return errs
    with LOCK:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        (HIST / f"{page_id}.{stamp}.json").write_bytes(target.read_bytes())
        tmp.replace(target)
    return []


def page_words(page_id):
    """Kata + kotak ternormalisasi dari lapisan teks PDF (hanya untuk sorotan di alat review)."""
    out = subprocess.run(["pdftotext", "-bbox", str(PAGES / f"{page_id}.pdf"), "-"], capture_output=True, text=True).stdout
    m = re.search(r'<page width="([\d.]+)" height="([\d.]+)"', out)
    if not m:
        return []
    W, H = float(m.group(1)), float(m.group(2))
    words = []
    for x0, y0, x1, y1, t in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', out):
        words.append([html.unescape(t), round(float(x0) / W, 5), round(float(y0) / H, 5),
                      round(float(x1) / W, 5), round(float(y1) / H, 5)])
    return words


def render_png(page_id):
    png = IMG / f"{page_id}.png"
    if not png.exists():
        subprocess.run(["pdftoppm", "-r", "130", "-png", "-singlefile", str(PAGES / f"{page_id}.pdf"),
                        str(png.with_suffix(""))], check=True)
    return png.read_bytes()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - senyapkan log per request
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def page_id(self, raw):
        pid = raw.split("?")[0]
        if not PAGE_RE.match(pid) or not (GT / f"{pid}.json").exists():
            self.send(404, {"error": "halaman tidak ada"})
            return None
        return pid

    def do_GET(self):
        p = self.path
        if p in ("/", "/index.html"):
            return self.send(200, HTML.encode(), "text/html; charset=utf-8")
        if p.startswith("/api/pages"):
            return self.send(200, list_pages())
        if p.startswith("/api/page/"):
            pid = self.page_id(p[len("/api/page/"):])
            return pid and self.send(200, page_detail(pid))
        if p.startswith("/api/words/"):
            pid = self.page_id(p[len("/api/words/"):])
            return pid and self.send(200, page_words(pid))
        if p.startswith("/img/"):
            pid = self.page_id(p[len("/img/"):].removesuffix(".png"))
            return pid and self.send(200, render_png(pid), "image/png")
        self.send(404, {"error": "tidak ada"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/manifest":
            r = subprocess.run([sys.executable, str(ROOT / "scripts/build_manifest.py")], capture_output=True, text=True)
            return self.send(200, {"output": r.stdout + r.stderr})
        if self.path.startswith("/api/page/"):
            pid = self.page_id(self.path[len("/api/page/"):])
            if not pid:
                return None
            errs = save_page(pid, body.get("elements", []), body.get("action", "save"), body.get("initials", ""))
            if errs:
                return self.send(400, {"errors": errs})
            return self.send(200, page_detail(pid))
        self.send(404, {"error": "tidak ada"})


HTML = r"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verifikasi GT</title>
<style>
:root{--bg:#f6f7f9;--panel:#fff;--line:#dfe3e8;--ink:#1d2329;--mute:#6b7682;--acc:#2f6fdd;--ok:#1f9d55;--warn:#c27c0e;--bad:#d64545}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,-apple-system,sans-serif;color:var(--ink);background:var(--bg);height:100vh;display:grid;grid-template-columns:230px 1fr 1fr;grid-template-rows:auto 1fr}
header{grid-column:1/-1;display:flex;gap:12px;align-items:center;padding:8px 14px;background:var(--panel);border-bottom:1px solid var(--line)}
header h1{font-size:15px;margin:0 8px 0 0}.prog{flex:1;height:8px;background:#e8ebef;border-radius:4px;overflow:hidden;max-width:320px}.prog i{display:block;height:100%;background:var(--ok)}
button{font:inherit;border:1px solid var(--line);background:#fff;border-radius:6px;padding:5px 10px;cursor:pointer}button:hover{border-color:var(--acc)}
button.pri{background:var(--acc);color:#fff;border-color:var(--acc)}button.ok{background:var(--ok);color:#fff;border-color:var(--ok)}
input,select,textarea{font:inherit;border:1px solid var(--line);border-radius:5px;padding:4px 6px;background:#fff;color:var(--ink)}
#side{overflow:auto;border-right:1px solid var(--line);background:var(--panel)}
#side .flt{padding:8px;display:flex;flex-direction:column;gap:6px;position:sticky;top:0;background:var(--panel);border-bottom:1px solid var(--line)}
.pg{display:flex;gap:6px;align-items:center;padding:5px 10px;cursor:pointer;border-left:3px solid transparent}.pg:hover{background:#f0f3f7}.pg.cur{background:#e7effc;border-left-color:var(--acc)}
.dot{width:9px;height:9px;border-radius:50%;background:#c3c9d0;flex:none}.dot.verif{background:var(--ok)}.dot.sebagian{background:var(--warn)}
.tag{font-size:11px;padding:0 5px;border-radius:4px;background:#eef1f4;color:var(--mute)}.tag.f{background:#fff3df;color:var(--warn)}
#view{overflow:auto;background:#e9ecef;padding:10px;text-align:center}#view img{background:#fff;box-shadow:0 1px 4px #0002;max-width:none;display:block}#stage{position:relative;display:inline-block}#ov{position:absolute;inset:0;pointer-events:none}#ov i{position:absolute;background:#ffd84d66;outline:1px solid #e0a800}#ov b{position:absolute;outline:3px solid #2f6fdd;outline-offset:3px;border-radius:2px}#loc{font-size:12px;color:var(--mute);margin-left:8px}
#viewbar{position:sticky;top:0;display:flex;gap:6px;justify-content:center;margin-bottom:8px}
#ed{overflow:auto;padding:10px 12px;border-left:1px solid var(--line)}
.bar{position:sticky;top:-10px;z-index:2;background:var(--bg);padding:8px 0;display:flex;gap:6px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--line);margin-bottom:8px}
.msg{padding:8px 10px;border-radius:6px;margin-bottom:8px;font-size:13px}.msg.w{background:#fff6e5;border:1px solid #f0d49a}.msg.e{background:#fdecec;border:1px solid #f1b5b5}.msg.i{background:#eaf6ee;border:1px solid #b6dfc3}
.num{display:inline-block;margin:2px;padding:0 5px;border-radius:4px;background:#fff;border:1px solid #f0d49a;cursor:pointer}
.card{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px;margin-bottom:8px}.card.flag{border-color:var(--warn);box-shadow:0 0 0 2px #f6dfb5}.card.hl{box-shadow:0 0 0 3px var(--acc)}
.card .h{display:flex;gap:6px;align-items:center;margin-bottom:6px}.card .h .sp{flex:1}.card .h button{padding:1px 7px;font-size:12px}
.badge{font-size:11px;font-weight:600;padding:1px 6px;border-radius:4px;color:#fff}.b-text{background:#5b6b7c}.b-table{background:#7a4fd0}.b-image{background:#1a8f8f}.b-head{background:var(--acc)}
.card textarea{width:100%;resize:vertical;min-height:34px}.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:5px;font-size:13px;color:var(--mute)}
.row input[type=text]{flex:1;min-width:120px}.note{width:100%;font-size:12px;color:var(--mute)}
.tw{overflow:auto;max-height:420px;margin:6px 0;border:1px solid var(--line);border-radius:5px}
.tw table{border-collapse:collapse;font-size:12.5px}.tw td,.tw th{border:1px solid #cfd5dc;padding:2px 5px;min-width:24px;vertical-align:top}.tw th{background:#f1f3f6}
.tw td:focus,.tw th:focus{outline:2px solid var(--acc);background:#fffbe6}
.lbl{font-size:12px;color:var(--mute)}kbd{font-size:11px;border:1px solid var(--line);border-radius:3px;padding:0 3px;background:#fff}
</style></head><body>
<header><h1>Verifikasi GT</h1><span id="ptxt" class="lbl"></span><div class="prog"><i id="pbar"></i></div>
<label class="lbl">Inisial <input id="ini" size="5" maxlength="6" placeholder="AB"></label>
<button id="mf">Perbarui manifest</button><span class="lbl"><kbd>Ctrl/⌘ S</kbd> simpan · <kbd>Ctrl/⌘ Enter</kbd> verifikasi + lanjut</span></header>
<aside id="side"><div class="flt">
<input id="q" placeholder="Cari halaman, mis. ID07">
<select id="fs"><option value="flag">Bertanda ? (cek ulang)</option><option value="draf">Belum diverifikasi</option><option value="verif">Sudah diverifikasi</option><option value="">Semua status</option></select>
<select id="fsrc"><option value="UA">Uji awal (UA)</option><option value="ID">Dokumen Indonesia</option><option value="DPB">DP-Bench</option><option value="">Semua sumber</option></select>
</div><div id="list"></div></aside>
<main id="view"><div id="viewbar"><button data-z="-1">−</button><button data-z="0">Pas lebar</button><button data-z="1">+</button><span id="loc"></span></div><div id="stage"><img id="img" alt=""><div id="ov"></div></div></main>
<section id="ed"><p class="lbl">Pilih halaman di kiri.</p></section>
<script>
let pages=[],cur=null,els=[],dirty=false,zoom=0,words=[];
const norm=t=>t.toLowerCase().replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu,'');
function elText(el){if(el.type==='text')return el.text;const d=document.createElement('div');
  if(el.type==='table'){d.innerHTML=el.table_body.replace(/<\/(td|th)>/g,' </$1>');return [el.table_caption,d.textContent,el.table_footnote].filter(Boolean).join(' ')}
  return [el.image_caption,el.image_footnote].filter(Boolean).join(' ')}
function locate(i){
  const ov=$('#ov');ov.textContent='';if(!words.length)return;
  const E=elText(els[i]).split(/\s+/).map(norm).filter(Boolean).slice(0,400);
  if(!E.length){$('#loc').textContent='Elemen gambar: posisi tidak terdeteksi dari lapisan teks';return}
  const est=Math.round(i/Math.max(1,els.length)*words.length);let best=null;
  for(let s=0;s<words.length;s++){if(words[s].n!==E[0]&&words[s].n!==E[1])continue;
    let k=s,hit=[];for(const t of E){for(let g=0;g<4&&k+g<words.length;g++){if(words[k+g].n===t){hit.push(k+g);k=k+g+1;break}}if(k>=words.length)break}
    const sc=hit.length;if(!best||sc>best.sc||(sc===best.sc&&Math.abs(s-est)<Math.abs(best.s-est)))best={sc,s,hit}}
  if(!best||best.sc<Math.min(2,E.length)){$('#loc').textContent='Posisi tidak ditemukan di lapisan teks';return}
  let X0=1,Y0=1,X1=0,Y1=0;
  best.hit.forEach(h=>{const[,x0,y0,x1,y1]=words[h];X0=Math.min(X0,x0);Y0=Math.min(Y0,y0);X1=Math.max(X1,x1);Y1=Math.max(Y1,y1);
    const b=document.createElement('i');Object.assign(b.style,{left:x0*100+'%',top:y0*100+'%',width:(x1-x0)*100+'%',height:(y1-y0)*100+'%'});ov.append(b)});
  const u=document.createElement('b');Object.assign(u.style,{left:X0*100+'%',top:Y0*100+'%',width:(X1-X0)*100+'%',height:(Y1-Y0)*100+'%'});ov.append(u);
  $('#loc').textContent=`Elemen ${i+1}: ${best.sc}/${E.length} kata cocok`;
  const v=$('#view'),img=$('#img');v.scrollTop=img.offsetTop+Y0*img.clientHeight-90;v.scrollLeft=Math.max(0,img.offsetLeft+X0*img.clientWidth-40);
}
const $=s=>document.querySelector(s);
const ini=$('#ini');try{ini.value=localStorage.getItem('ini')||''}catch(e){}
ini.oninput=()=>{try{localStorage.setItem('ini',ini.value)}catch(e){}};
async function api(u,b){const r=await fetch(u,b?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{});return [r.ok,await r.json()]}
async function loadList(){[,pages]=await api('/api/pages');renderList()}
function renderList(){
  const q=$('#q').value.trim().toUpperCase(),fs=$('#fs').value,src=$('#fsrc').value;
  const scope=pages.filter(p=>!src||p.id.startsWith(src));const done=scope.filter(p=>p.status==='verif').length;
  $('#ptxt').textContent=`${done}/${scope.length} terverifikasi`;$('#pbar').style.width=(scope.length?100*done/scope.length:0)+'%';
  const L=$('#list');L.textContent='';
  scope.filter(p=>(!q||p.id.toUpperCase().includes(q))&&(!fs||(fs==='flag'?p.flagged>0:fs==='draf'?p.status!=='verif':p.status==='verif'))).forEach(p=>{
    const d=document.createElement('div');d.className='pg'+(p.id===cur?' cur':'');d.dataset.id=p.id;
    d.innerHTML=`<span class="dot ${p.status}"></span><span style="flex:1"></span>`;d.children[1].textContent=p.id;
    if(p.tables){const t=document.createElement('span');t.className='tag';t.textContent=p.tables+' tbl';d.append(t)}
    if(p.flagged){const t=document.createElement('span');t.className='tag f';t.textContent=p.flagged+' ?';t.title='elemen bertanda [?] / [ilegibel]';d.append(t)}
    d.onclick=()=>openPage(p.id);L.append(d)});
}
['q','fs','fsrc'].forEach(i=>$('#'+i).addEventListener('input',renderList));
async function openPage(id){
  if(dirty&&!confirm('Ada perubahan belum disimpan. Tinggalkan?'))return;
  const [ok,d]=await api('/api/page/'+id);if(!ok)return;cur=id;dirty=false;[,words]=await api('/api/words/'+id);words.forEach(w=>w.n=norm(w[0]));$('#ov').textContent='';$('#loc').textContent=words.length?'Klik elemen di kanan untuk melihat posisinya':'Halaman scan: posisi tidak bisa ditampilkan';
  $('#img').src='/img/'+id+'.png';applyZoom();renderEditor(d);renderList();
  document.querySelector('.pg.cur')?.scrollIntoView({block:'nearest'});
}
function applyZoom(){const img=$('#img'),W=$('#view').clientWidth-24;img.style.width=zoom===0?W+'px':(W*(1+zoom*0.25))+'px'}
$('#viewbar').onclick=e=>{const z=e.target.dataset.z;if(z===undefined)return;zoom=z==='0'?0:zoom+ +z;applyZoom()};
window.onresize=applyZoom;
function mark(){dirty=true;$('#savebtn')&&($('#savebtn').textContent='Simpan *')}
function renderEditor(d,errors){
  els=d.elements;const E=$('#ed');E.textContent='';
  const bar=document.createElement('div');bar.className='bar';
  bar.innerHTML=`<b></b><span class="tag"></span><span style="flex:1"></span><button id="savebtn">Simpan</button><button class="ok" id="verbtn">✓ Verifikasi + lanjut</button>`;
  bar.children[0].textContent=d.id;bar.children[1].textContent=d.status==='verif'?'terverifikasi':d.status;
  if(d.status!=='draf'){const u=document.createElement('button');u.textContent='Batalkan verif';u.onclick=()=>save('unverify');bar.insertBefore(u,bar.children[3])}
  E.append(bar);$('#savebtn').onclick=()=>save('save');$('#verbtn').onclick=()=>save('verify',true);
  if(errors){const m=document.createElement('div');m.className='msg e';m.textContent='Belum tersimpan: '+errors.join(' · ');E.append(m)}
  if(d.scan){const m=document.createElement('div');m.className='msg w';m.textContent='Halaman scan (tanpa lapisan teks): semua angka harus dicek dari gambar.';E.append(m)}
  else if(d.missing_numbers&&d.missing_numbers.length){const m=document.createElement('div');m.className='msg w';
    m.innerHTML='Angka ini tidak ada di lapisan teks PDF (cek, bisa dari grafik/gambar): ';
    d.missing_numbers.forEach(n=>{const s=document.createElement('span');s.className='num';s.textContent=n;s.onclick=()=>jump(n);m.append(s)});E.append(m)}
  else{const m=document.createElement('div');m.className='msg i';m.textContent='Semua angka cocok dengan lapisan teks PDF.';E.append(m)}
  els.forEach((el,i)=>E.append(card(el,i)));
  const add=document.createElement('div');add.className='row';add.append('Tambah di akhir: ');
  ['text','table','image'].forEach(t=>{const b=document.createElement('button');b.textContent='+ '+t;b.onclick=()=>insert(els.length,t);add.append(b)});E.append(add);
}
function jump(n){const i=els.findIndex(e=>JSON.stringify(e).includes(n));if(i<0)return;const c=document.querySelectorAll('.card')[i];c.scrollIntoView({block:'center'});c.classList.add('hl');setTimeout(()=>c.classList.remove('hl'),1500)}
function field(label,val,set){const r=document.createElement('label');r.className='row';r.append(label);const inp=document.createElement('input');inp.type='text';inp.value=val??'';inp.placeholder='(kosong = null)';inp.oninput=()=>{set(inp.value.trim()?inp.value:null);mark()};r.append(inp);return r}
function card(el,i){
  const c=document.createElement('div');c.className='card'+(/\[\?\]/.test(el.gt_note)||JSON.stringify(el).includes('[ilegibel]')?' flag':'');c.addEventListener('focusin',()=>locate(i));c.addEventListener('click',()=>locate(i));
  const h=document.createElement('div');h.className='h';
  const b=document.createElement('span');b.className='badge '+(el.text_level?'b-head':'b-'+el.type);b.textContent=(i+1)+' · '+(el.text_level?'heading '+el.text_level:el.type)+(el.in_figure?' · dlm gambar':'');h.append(b);
  const sp=document.createElement('span');sp.className='sp';h.append(sp);
  [['↑','naik',()=>move(i,-1)],['↓','turun',()=>move(i,1)],['+','sisip teks di bawah',()=>insert(i+1,'text')],['⧉','duplikat',()=>{els.splice(i+1,0,JSON.parse(JSON.stringify(els[i])));rerender()}],['✕','hapus',()=>{if(confirm('Hapus elemen '+(i+1)+'?')){els.splice(i,1);rerender()}}]]
    .forEach(([t,ti,f])=>{const x=document.createElement('button');x.textContent=t;x.title=ti;x.onclick=f;h.append(x)});
  c.append(h);
  if(el.type==='text'){
    const ta=document.createElement('textarea');ta.value=el.text;ta.rows=Math.min(12,Math.max(1,Math.ceil(el.text.length/70)));ta.oninput=()=>{el.text=ta.value;mark()};c.append(ta);
    const r=document.createElement('div');r.className='row';
    const s=document.createElement('select');['bukan heading',1,2,3,4,5,6].forEach(v=>{const o=document.createElement('option');o.value=typeof v==='number'?v:'';o.textContent=typeof v==='number'?'heading '+v:v;s.append(o)});
    s.value=el.text_level||'';s.onchange=()=>{if(s.value)el.text_level=+s.value;else delete el.text_level;mark();rerender()};
    const cb=document.createElement('input');cb.type='checkbox';cb.checked=el.in_figure;cb.onchange=()=>{el.in_figure=cb.checked;mark();rerender()};
    const cl=document.createElement('label');cl.append(cb,' teks di dalam gambar');r.append(s,cl);c.append(r);
  }else if(el.type==='table'){
    c.append(field('Caption',el.table_caption,v=>el.table_caption=v));
    const tw=document.createElement('div');tw.className='tw';tw.innerHTML=el.table_body;
    tw.querySelectorAll('td,th').forEach(td=>{td.contentEditable='true';td.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();td.blur()}};
      td.oninput=()=>{const t=tw.querySelector('table').cloneNode(true);t.querySelectorAll('[contenteditable]').forEach(n=>n.removeAttribute('contenteditable'));
        t.querySelectorAll('td,th').forEach(n=>{if(!n.querySelector('br'))n.textContent=n.textContent});el.table_body=t.outerHTML;html.value=el.table_body;mark()}});
    c.append(tw);
    const det=document.createElement('details');const sm=document.createElement('summary');sm.className='lbl';sm.textContent='Edit HTML (baris/kolom/rowspan/colspan)';
    const html=document.createElement('textarea');html.value=el.table_body;html.rows=8;html.style.fontFamily='ui-monospace,monospace';html.style.fontSize='12px';
    html.onchange=()=>{el.table_body=html.value;mark();rerender()};det.append(sm,html);c.append(det);
    c.append(field('Footnote',el.table_footnote,v=>el.table_footnote=v));
  }else{
    c.append(field('Caption',el.image_caption,v=>el.image_caption=v));
    c.append(field('Footnote',el.image_footnote,v=>el.image_footnote=v));
  }
  if(/\[\?\]/.test(el.gt_note)){const fx=document.createElement('button');fx.textContent='✓ Keraguan beres';fx.title='ganti [?] di catatan menjadi dicek:, alasan tetap tersimpan';
    fx.onclick=()=>{el.gt_note=el.gt_note.replace(/\[\?\]\s*/g,'dicek: ');rerender()};const fr=document.createElement('div');fr.className='row';fr.append(fx,' kalau bacaan di atas sudah benar');c.append(fr)}
  if(JSON.stringify(el).includes('[ilegibel]')){const w=document.createElement('div');w.className='row';w.style.color='var(--warn)';w.textContent='Ada [ilegibel]: ganti dengan teks yang terbaca, atau biarkan kalau memang tidak terbaca.';c.append(w)}
  const n=document.createElement('input');n.className='note';n.value=el.gt_note;n.title='gt_note';n.oninput=()=>{el.gt_note=n.value;mark()};
  const nl=document.createElement('div');nl.className='row';nl.append('catatan ',n);c.append(nl);
  return c;
}
function rerender(){const st=document.getElementById('ed').scrollTop;mark();renderEditor({id:cur,elements:els,scan:false,missing_numbers:null,status:(pages.find(p=>p.id===cur)||{}).status||'draf'});document.getElementById('ed').scrollTop=st;
  const m=document.querySelector('.msg.i');m&&(m.textContent='Belum disimpan: cek angka dijalankan ulang setelah simpan.')}
function move(i,d){const j=i+d;if(j<0||j>=els.length)return;[els[i],els[j]]=[els[j],els[i]];rerender()}
function insert(i,t){const base={page_idx:0,bbox:null,gt_note:'draf_model; tambah_manual'};
  const e=t==='text'?{type:'text',text:'(isi teks)',in_figure:false,...base}:t==='table'?{type:'table',table_body:'<table><tr><td></td></tr></table>',table_caption:null,table_footnote:null,...base}:{type:'image',img_path:null,image_caption:null,image_footnote:null,...base};
  els.splice(i,0,e);rerender()}
async function save(action,next){
  if(action==='verify'&&!ini.value.trim()){alert('Isi inisial dulu (pojok kanan atas).');ini.focus();return}
  const [ok,d]=await api('/api/page/'+cur,{elements:els,action,initials:ini.value.trim()});
  if(!ok){renderEditor({id:cur,elements:els,scan:false,missing_numbers:[],status:'draf'},d.errors||[d.error]);return}
  dirty=false;await loadList();
  if(next){const vis=[...document.querySelectorAll('.pg')].map(x=>x.dataset.id);const nx=vis.find(x=>x!==cur);if(nx)return openPage(nx)}
  renderEditor(d);
}
document.addEventListener('keydown',e=>{if(!(e.ctrlKey||e.metaKey)||!cur)return;
  if(e.key==='s'){e.preventDefault();save('save')}else if(e.key==='Enter'){e.preventDefault();save('verify',true)}});
window.onbeforeunload=e=>{if(dirty){e.preventDefault();return ''}};
$('#mf').onclick=async()=>{$('#mf').textContent='Memproses…';const [,d]=await api('/api/manifest',{});$('#mf').textContent='Perbarui manifest';alert(d.output)};
loadList().then(()=>{const f=document.querySelector('.pg');f&&openPage(f.dataset.id)});
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    for d in (IMG, HIST):
        d.mkdir(parents=True, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"Alat verifikasi berjalan di {url}  (Ctrl+C untuk berhenti)")
    if not a.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nberhenti")


if __name__ == "__main__":
    main()
