"""Fælles analyse: klassificér kladder, foreslå kontering, find dubletter."""
import datetime as dt
import functools
import re
import json
import os

import billy
import leverandoer as L

D = lambda s: dt.date.fromisoformat(s[:10])


def regler():
    p = os.path.join(billy.HOME, "regler.json")
    if not os.path.exists(p):
        raise SystemExit("Ingen regler endnu. Kør først:  python laer.py")
    return json.load(open(p, encoding="utf-8"))


def bilagstekst(bill_id):
    t = ""
    for a in billy.attachments(bill_id):
        try:
            t += " " + billy.file_text(a["fileId"])
        except SystemExit:
            pass
    return t


@functools.lru_cache(maxsize=1)
def _repraesentation():
    """(kontoId, kontonavn, momsId) for restaurant/repræsentation: konto billy_konti.restaurant og momskode KR.
    Elementer er None, hvis kontoen eller koden ikke findes i Billy."""
    nr = billy.CFG["billy_konti"]["restaurant"]
    accs = billy.accounts()
    konto = next((i for i, a in accs.items() if str(a.get("accountNo")) == str(nr)), None)
    navn = f"{nr} {accs[konto]['name']}" if konto else None
    moms = next((i for i, t in billy.tax_rates().items() if t.get("abbreviation") == "KR"), None)
    return konto, navn, moms


def foreslaa(bill, R, med_pdf=True):
    """Returnér dict med leverandør, forslag (kontoId/momsId), sikkerhed, begrundelse og flag."""
    tekst = bill.get("lineDescription") or ""
    res = dict(id=bill["id"], dato=bill["entryDate"], beloeb=bill["amount"], valuta=bill["currencyId"],
               tekst=tekst, lev=None, kontoId=None, konto=None, momsId=None, moms=None,
               sikkerhed="ingen", begrundelse="", flag=[])
    ir = L.ikke_regning(tekst)
    if ir:
        res.update(sikkerhed="ikke-regning", begrundelse=f"{ir[0]}: {ir[1]}")
        return res
    atts = billy.attachments(bill["id"])
    if not atts:
        res["flag"].append("MANGLER BILAG")
    lev = L.fra_banktekst(tekst)
    pdf = bilagstekst(bill["id"]) if (med_pdf and atts) else ""
    if not lev and pdf:
        lev = L.fra_fakturatekst(pdf)
    res["lev"] = lev
    land = L.momsland(pdf) if pdf else None

    # Særregler, som bogholderens historik ikke dækker godt
    if lev == "Restaurant":
        # Restaurantkontoen har normalt KR (6,25 % = 25 % af momsen) som standardmomskode. Kontoen og koden slås op i Billy.
        konto_id, konto_navn, moms_id = _repraesentation()
        res.update(kontoId=konto_id, konto=konto_navn, momsId=moms_id, moms="KR" if moms_id else None,
                   begrundelse="Restaurant = repræsentation: kun 25 % af momsen (KR) og 25 % skattefradrag. Kræver formål og deltagere på bilaget/egenbilag. Er det ren egen forplejning på rejse, er det i stedet en rejseudgift.",
                   sikkerhed="vurdér")
        res["flag"].append("REPRÆSENTATION")
        return res
    if lev in ("Dagligvarer", "Rema 1000", "MobilePay-betaling"):
        res["flag"].append("TJEK ERHVERV/PRIVAT")
        res.update(sikkerhed="vurdér", begrundelse=(
            "Dagligvarer/MobilePay til en person: kan være privat, forplejning på rejse (rejseudgift) eller repræsentation (restaurant/KR). "
            "Ejeren skal afgøre formålet. Der gættes ikke."))
        return res

    r = R["regler"].get(lev) if lev else None
    if r:
        res.update(kontoId=r["kontoId"], konto=r["konto"], momsId=r["momsId"], moms=r["moms"],
                   sikkerhed=r["sikkerhed"] if res["sikkerhed"] == "ingen" else res["sikkerhed"],
                   begrundelse=res["begrundelse"] or f"Bogholderen har bogført {lev} sådan {round(r['andel']*r['n'])} af {r['n']} gange.")
        # Momskoden følger leverandørens land. Advar hvis fakturaen peger et andet sted hen end historikken.
        if land and r.get("momslande") and land not in r["momslande"]:
            res["flag"].append(f"MOMSLAND {land} AFVIGER FRA HISTORIK {list(r['momslande'])}")
            res["sikkerhed"] = "lav"
    elif not land and bill["currencyId"] in ("USD", "EUR") and R.get("fallback_pr_momsland"):
        # Kun for regninger i fremmed valuta. Bankkladder er altid i DKK og siger intet om leverandørens land,
        # så de får aldrig et valuta-gæt (det ville give falsk dansk købsmoms på udenlandske køb).
        land = {"USD": "UDLAND", "EUR": "EU"}[bill["currencyId"]]
        f = R["fallback_pr_momsland"].get(land)
        if f:
            res.update(kontoId=f["kontoId"], konto=f["konto"], momsId=f["momsId"], moms=f["moms"], sikkerhed="lav",
                       begrundelse=res["begrundelse"] or f"Ukendt leverandør uden læsbart bilag; gættet ud fra valuta ({bill['currencyId']} → {land}).")
            res["flag"].append("GÆT UD FRA VALUTA")
    if not res["kontoId"] and land and land in R.get("fallback_pr_momsland", {}):
        f = R["fallback_pr_momsland"][land]
        res.update(kontoId=f["kontoId"], konto=f["konto"], momsId=f["momsId"], moms=f["moms"], sikkerhed="lav",
                   begrundelse=res["begrundelse"] or f"Ukendt leverandør. Fakturaen ser {land}-baseret ud; mest brugte kontering for {land} er valgt.")
    elif not res["kontoId"]:
        res["sikkerhed"] = "ingen"
        res["begrundelse"] = res["begrundelse"] or "Ukendt leverandør og intet læsbart bilag. Kræver manuel vurdering."
    if bill["currencyId"] == "DKK" and lev and r and r.get("valutaer") and "DKK" not in r["valutaer"]:
        res["flag"].append("BANKKLADDE I DKK FOR VALUTALEVERANDØR — TJEK FOR DUBLET")
    return res


def fakturanumre(tekst):
    """Fakturanumre i en bilagstekst (engelske og danske formuleringer)."""
    rx = r"(?:Invoice number|Invoice No\.?|Invoice #|Fakturanummer|Faktura nr\.?|Fakturanr\.?)\s*:?\s*#?([A-Z0-9][A-Z0-9-]{3,})"
    return set(re.findall(rx, tekst or "", re.I))


def sammenlign(kontoId, momsId, lns, acc, tax):
    """Sammenlign et forslag med faktiske linjer. Returnerer en af:
    'rigtig'              — samme konto og momskode
    'skattemæssigt ens'   — samme momsbeløb (momsgruppe) og samme fradragstype; kun rubrik/udgiftskonto afviger
    'forkert moms'        — anden momsgruppe (fx K mod KYU eller KF) → momsbeløbet bliver forkert
    'forkert kontotype'   — fx udstyr (afskrives) mod straks fradrag
    """
    kode = lambda i: (tax[i].get("abbreviation") if i in tax else None)
    nr = lambda i: (str(acc[i]["accountNo"]) if i in acc else None)
    if all(l["accountId"] == kontoId and l["taxRateId"] == momsId for l in lns):
        return "rigtig"
    g = L.MOMS_GRUPPE
    if any(g.get(kode(l["taxRateId"])) != g.get(kode(momsId)) for l in lns):
        return "forkert moms"
    s = L.SAERLIGE_KONTI
    if any((nr(l["accountId"]) in s or nr(kontoId) in s) and nr(l["accountId"]) != nr(kontoId) for l in lns):
        return "forkert kontotype"
    return "skattemæssigt ens"
