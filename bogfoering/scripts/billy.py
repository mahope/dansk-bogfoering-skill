"""Fælles Billy-klient til bogføringsskillet.

Token: miljøvariablen BILLY_API_TOKEN, ellers filen i config.billy_token_fil (se config.py). Printes aldrig.
Al tilstand (regler, skyggelog, cache, backups) ligger i config.tilstand_mappe (standard ~/.bogfoering/).
"""
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

import config

API = "https://api.billysbilling.com/v2"
CFG = config.load()
HOME = CFG["tilstand_mappe"]
CACHE = os.path.join(HOME, "cache")
BACKUP = os.path.join(HOME, "backup")

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8")

_T = None


def ensure_dirs():
    """Opretter tilstandsmapperne første gang, noget skal skrives (ikke ved import)."""
    for d in (HOME, CACHE, BACKUP):
        os.makedirs(d, exist_ok=True)


def _token():
    global _T
    if _T is None:
        _T = config.token(CFG)
    return _T


def aar_start():
    return f"{dt.date.today().year}-01-01"


def req(method, path, data=None, headers=None, retries=3):
    ensure_dirs()
    h = {"X-Access-Token": _token()}
    h.update(headers or {})
    if isinstance(data, (dict, list)):
        data = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    for i in range(retries):
        try:
            r = urllib.request.Request(API + path, data=data, headers=h, method=method)
            body = urllib.request.urlopen(r, timeout=60).read()
            return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503) and i < retries - 1:
                time.sleep(2 * (i + 1))
                continue
            msg = e.read().decode("utf-8", "replace")[:300]
            raise SystemExit(f"Billy {method} {path} -> HTTP {e.code}: {msg}")


def paged(path, key):
    out, page = [], 1
    sep = "&" if "?" in path else "?"
    while True:
        d = req("GET", f"{path}{sep}pageSize=1000&page={page}")
        out += d[key]
        if page >= d["meta"]["paging"]["pageCount"]:
            return out
        page += 1


def bills(mn=None, mx="2099-12-31", states=("draft", "approved")):
    mn = mn or aar_start()
    return [b for b in paged(f"/bills?minEntryDate={mn}&maxEntryDate={mx}", "bills") if b["state"] in states]


def lines(bill_id):
    return req("GET", f"/billLines?billId={bill_id}")["billLines"]


def attachments(bill_id):
    # OBS: ?ownerId= ignoreres af Billy og returnerer ALT. Brug ownerReference.
    return req("GET", f"/attachments?ownerReference=bill:{bill_id}")["attachments"]


def file_meta(file_id):
    return req("GET", f"/files/{file_id}")["file"]


def file_bytes(file_id):
    """Henter filindhold med disk-cache (filer i Billy er uforanderlige)."""
    p = os.path.join(CACHE, "files", file_id)
    if os.path.exists(p):
        with open(p, "rb") as fh:
            return fh.read()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = urllib.request.urlopen(file_meta(file_id)["downloadUrl"], timeout=60).read()
    with open(p, "wb") as fh:
        fh.write(data)
    return data


def file_text(file_id):
    """PDF-tekst (cachet). Billeder giver tom tekst, der er ingen OCR her.

    Kræver den valgfrie pakke PyMuPDF (pip install pymupdf). Uden den returneres tom tekst, og intet caches,
    så teksten kommer med, når pakken er installeret."""
    p = os.path.join(CACHE, "text", file_id + ".txt")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            cached = fh.read()
        # ældre versioner cachede importfejlen som tekst; læs PDF'en igen i stedet
        if not cached.startswith("[pdf-fejl: No module named"):
            return cached
    data = file_bytes(file_id)
    txt = ""
    if data[:4] == b"%PDF":
        try:
            import fitz  # PyMuPDF
        except ImportError:
            print("PyMuPDF mangler (pip install pymupdf): PDF-tekst springes over", file=sys.stderr)
            return ""
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            txt = re.sub(r"\s+", " ", " ".join(pg.get_text() for pg in doc))
        except Exception as e:  # beskadiget PDF
            txt = f"[pdf-fejl: {e}]"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(txt)
    return txt


def upload_file(path_or_bytes, filename, content_type="application/pdf"):
    if isinstance(path_or_bytes, str):
        with open(path_or_bytes, "rb") as fh:
            data = fh.read()
    else:
        data = path_or_bytes
    r = req("POST", "/files", data, {"Content-Type": content_type, "X-Filename": filename})
    return r["files"][0]["id"]


def attach(bill_id, file_id):
    return req("POST", "/attachments", {"attachment": {"ownerReference": f"bill:{bill_id}", "fileId": file_id}})


def accounts():
    return {a["id"]: a for a in req("GET", "/accounts?pageSize=1000")["accounts"]}


def tax_rates():
    return {t["id"]: t for t in req("GET", "/taxRates?pageSize=1000")["taxRates"]}


def backup(name, obj):
    ensure_dirs()
    p = os.path.join(BACKUP, time.strftime("%Y-%m-%d_%H%M%S_") + name + ".json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    return p


def kr(v):
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def maaned_interval(m):
    """'2026-09' -> ('2026-09-01', '2026-09-30'). Billy ruller ugyldige datoer som 2026-09-31 videre til næste måned."""
    import calendar
    y, mo = map(int, m.split("-"))
    return f"{y:04d}-{mo:02d}-01", f"{y:04d}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"


SKYGGE_MARKOR = CFG["skyggedrift_markoer"]


def kraev_ikke_skyggedrift(tving=False):
    """Skrivende kontering/godkendelse er spærret, så længe skyggedrift-markøren findes."""
    if os.path.exists(SKYGGE_MARKOR) and not tving:
        raise SystemExit(f"Skyggedrift er aktiv ({SKYGGE_MARKOR} findes): kontering og godkendelse "
                         "skrives ikke til Billy. Slet markøren, når kriteriet i SKILL.md er nået, og ejeren har sagt go.")
