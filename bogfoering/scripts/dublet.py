"""Dubletter: find kladder, der er samme køb som en bogført regning, og slå dem sikkert sammen."""
import hashlib
import json
import os
import shutil

import billy
import leverandoer as L
from analyse import D, bilagstekst, fakturanumre

# Leverandører, hvor to ens køb samme uge er normalt (billetter, dagligvarer, MobilePay) — aldrig 'sikker'.
GENERISKE = {"MobilePay-betaling", "Dagligvarer", "Restaurant", "DSB", "Rejsekort", "Rema 1000"}


def find_dubletter(alle, maks_dage_samme=5, maks_dage_fx=4, fx_tol=0.025, sikker_tol=0.015):
    """Returnerer liste af dict(kladde, maal, type, grund, lev_kladde, lev_maal, sikker, flere_kandidater).

    'sikker' (må slås sammen automatisk af dubletter.py --apply) kræver ALT dette:
      - kladden er i DKK og den bogførte regning i fremmed valuta (bank-vs-bilagsindbakke-mønstret),
        ELLER begge sider har samme fakturanummer i bilaget,
      - samme (eller alias-) leverandør genkendt på begge sider, og ikke en generisk leverandør,
      - kursafvigelse ≤ sikker_tol.
    Par i samme valuta med samme beløb er derfor 'tjek' — det kan være to ens køb (fx to DSB-billetter).
    Par tildeles globalt efter kvalitet, så et dårligt match ikke 'bruger' en regning, en bedre kladde skulle have.
    Momsoverførsler, skat og hævninger (leverandoer.IKKE_REGNING) indgår aldrig.
    """
    dr = [b for b in alle if b["state"] == "draft" and not L.ikke_regning(b.get("lineDescription") or "")]
    ap = [b for b in alle if b["state"] == "approved"]
    lev_c, fnr_c = {}, {}

    def lev(b):
        if b["id"] not in lev_c:
            lev_c[b["id"]] = L.fra_banktekst(b.get("lineDescription") or "") or L.fra_fakturatekst(bilagstekst(b["id"]))
        return lev_c[b["id"]]

    def fnr(b):
        if b["id"] not in fnr_c:
            fnr_c[b["id"]] = fakturanumre(bilagstekst(b["id"]))
        return fnr_c[b["id"]]

    # Bogførte regninger, der allerede har optaget en bankkladde ved tidligere oprydning, kan ikke bruges igen.
    p = os.path.join(billy.HOME, "traening_par.json")
    brugt = {x["approved"] for x in json.load(open(p, encoding="utf-8"))} if os.path.exists(p) else set()

    kand = []
    for d in dr:
        ld = lev(d)
        for a in ap:
            if a["id"] in brugt:
                continue
            dage = abs((D(a["entryDate"]) - D(d["entryDate"])).days)
            fx = False
            if a["currencyId"] == d["currencyId"] and abs(a["amount"] - d["amount"]) < 0.01 and dage <= maks_dage_samme:
                afv, grund = 0.0, "samme beløb"
            elif a["currencyId"] != "DKK" and d["currencyId"] == "DKK" and dage <= maks_dage_fx and a.get("exchangeRate"):
                k = a["amount"] * a["exchangeRate"]
                afv = abs(d["amount"] - k) / k
                if afv >= fx_tol:
                    continue
                fx, grund = True, f"{a['amount']} {a['currencyId']} × kurs {a['exchangeRate']} ({100*(d['amount']-k)/k:+.1f} %)"
            else:
                continue
            la = lev(a)
            if ld and la and not L.samme_leverandoer(ld, la):
                continue  # to kendte, forskellige leverandører = ikke samme køb
            fd, fa = fnr(d), fnr(a)
            if fd and fa and not (fd & fa):
                continue  # forskellige fakturanumre = forskellige køb
            kendt = bool(ld and la)
            generisk = ld in GENERISKE or la in GENERISKE
            sikker = kendt and not generisk and afv <= sikker_tol and (fx or bool(fd and fa and fd & fa))
            kand.append(((0 if kendt else 1, dage, afv), d, a, grund, ld, la, sikker))

    kand.sort(key=lambda x: x[0])
    antal = {}
    for _, d, *_ in kand:
        antal[d["id"]] = antal.get(d["id"], 0) + 1
    td, ta, ud = set(), set(), []
    for _, d, a, grund, ld, la, sikker in kand:
        if d["id"] in td or a["id"] in ta:
            continue
        td.add(d["id"])
        ta.add(a["id"])
        ud.append(dict(kladde=d, maal=a, type="kladde→bogført", grund=grund, lev_kladde=ld, lev_maal=la,
                       sikker=sikker, flere_kandidater=antal[d["id"]] > 1))
    # kladde mod kladde (vises kun — slås aldrig sammen automatisk)
    for i, a in enumerate(dr):
        for b in dr[i + 1:]:
            if (a["currencyId"] == b["currencyId"] and abs(a["amount"] - b["amount"]) < 0.01
                    and abs((D(a["entryDate"]) - D(b["entryDate"])).days) <= 3
                    and lev(a) and lev(a) == lev(b) and lev(a) not in GENERISKE):
                ud.append(dict(kladde=b, maal=a, type="kladde→kladde", grund="samme leverandør og beløb",
                               lev_kladde=lev(b), lev_maal=lev(a), sikker=False, flere_kandidater=False))
    return sorted(ud, key=lambda x: x["kladde"]["entryDate"])


def _sha(file_id):
    return hashlib.sha256(billy.file_bytes(file_id)).hexdigest()


def flyt_bilag_og_slet(kladde_id, maal_id):
    """Kopiér kladdens bilag til målet (sammenlignet på INDHOLD, ikke filnavn), verificér,
    tag backup inkl. selve filerne, og slet kladden. Rører aldrig en bogført regning ud over at tilføje bilag."""
    k = billy.req("GET", f"/bills/{kladde_id}")["bill"]
    if k["state"] != "draft":
        raise SystemExit(f"{kladde_id} er {k['state']}, ikke en kladde — afbryder")
    m = billy.req("GET", f"/bills/{maal_id}")["bill"]
    if m["state"] not in ("approved", "draft") or maal_id == kladde_id:
        raise SystemExit(f"Målet {maal_id} er ugyldigt ({m['state']}) — afbryder")
    katts = billy.attachments(kladde_id)
    har = {_sha(a["fileId"]) for a in billy.attachments(maal_id)}
    for a in katts:
        if _sha(a["fileId"]) in har:
            continue
        f = billy.file_meta(a["fileId"])
        nf = billy.upload_file(billy.file_bytes(a["fileId"]), f["fileName"], f.get("fileType") or "application/pdf")
        billy.attach(maal_id, nf)
    nu = {_sha(a["fileId"]) for a in billy.attachments(maal_id)}
    mangler = [a["fileId"] for a in katts if _sha(a["fileId"]) not in nu]
    if mangler:
        raise SystemExit(f"Bilag {mangler} blev ikke flyttet til {maal_id} — kladden er IKKE slettet")
    # Backup: regningen, linjerne og selve bilagsfilerne, så intet kan gå tabt.
    bdir = os.path.join(billy.BACKUP, f"bilag_{kladde_id}")
    os.makedirs(bdir, exist_ok=True)
    bilag = []
    for a in katts:
        f = billy.file_meta(a["fileId"])
        shutil.copy(os.path.join(billy.CACHE, "files", a["fileId"]), os.path.join(bdir, f"{a['fileId']}_{f['fileName']}"))
        bilag.append(dict(fileId=a["fileId"], navn=f["fileName"], sha256=_sha(a["fileId"])))
    billy.backup(f"slettet_kladde_{kladde_id}", dict(bill=k, lines=billy.lines(kladde_id), maal=maal_id, bilag=bilag))
    billy.req("DELETE", f"/bills/{kladde_id}")
    if m["state"] == "approved" and k.get("lineDescription"):
        p = os.path.join(billy.HOME, "traening_par.json")
        par = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
        par.append(dict(banktekst=k["lineDescription"], approved=maal_id))
        json.dump(par, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return k
