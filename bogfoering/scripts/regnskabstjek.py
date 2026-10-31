"""Regnskabstjek: finder poster i Billy, som en bogholder ville gøre indsigelse imod. Kun læsning.

    python regnskabstjek.py                    # fra 1/1 i år
    python regnskabstjek.py --fra 2026-07-01
    python regnskabstjek.py --med-annullerede  # tag annullerede betalinger med (bevis på at tjekket fanger noget)
    python regnskabstjek.py --uden-bilagstjek  # spring det langsomme bilagstjek over
    python regnskabstjek.py --bilagsindhold    # læs PDF'erne: købers CVR og beløb (kræver PyMuPDF)
    python regnskabstjek.py --straks           # straksafskrivning på regningslinjerne

Tjek (reglerne og kilderne står i reference/dansk-bogfoering.md og reference/laerte-regler.md):
  1. Betalinger på en bankkonto i Billy (kontiene i config bank.konti) uden en postering med samme beløb og
     retning på den tilsvarende bankkonto inden for ±3 dage. Fanger fx kortbetalinger, som går via en
     betalingsudbyder, men blev bogført på bankkontoen.
  2. Kreditnotaer, der ikke peger på en faktura, peger på en ukendt faktura, overstiger fakturaen
     eller er dateret før den.
  3. Bogførte regninger uden bilag (bankkladder der ikke er regninger, fx Income sorter, springes over).
  4. Huller og dubletter i fakturanumrene (mbek § 58: fortløbende nummer).
  5. --bilagsindhold: bilag uden købers CVR, eller hvor regningens beløb ikke står på bilaget.
  6. --straks: småanskaffelser over straksafskrivningsgrænsen og udstyr under den.

Bankdata (valgfri) ligger som JSON-filer i config bank.data_mappe, i Enable Banking/PSD2-format: et objekt med
"konto" (visningsnavn, der indeholder kontoens slutcifre) og "tx" (liste af PSD2-transaktioner med booking_date,
credit_debit_indicator, transaction_amount.amount og status). Koblingen fra Billy-kontonummer til slutcifre står
i config bank.konti, fx {"5710": "0001"}. Uden bank.konti springes betalingstjekket over.

Fund er "tjek", ikke fejl: de skal ses af et menneske. Kun id'er, datoer og beløb vises, ingen navne.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re

VINDUE_DAGE = 3


# ---------- rene funktioner (testes i test_regnskabstjek.py) ----------

def _dato(s):
    return dt.date.fromisoformat(s[:10])


def bank_tx(sti, konti):
    """{'0001': [(dato, retning 'ind'/'ud', beløb), ...], ...} fra bankfilerne i mappen sti (nøglen hedder 'tx').
    konti: {Billy-kontonr: slutcifre}. Filer, hvis 'konto' ikke indeholder nogle af slutcifrene, springes over."""
    ud = {}
    for f in glob.glob(os.path.join(sti, "*.json")):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        slut = next((v for v in konti.values() if v in d.get("konto", "")), None)
        if not slut:
            continue
        rows = []
        for t in d.get("tx", []):
            if t.get("status") == "PDNG":
                continue
            dag = t.get("booking_date") or t.get("value_date")
            amt = float((t.get("transaction_amount") or {}).get("amount") or 0)
            if dag and amt:
                rows.append((_dato(dag), "ind" if t.get("credit_debit_indicator") == "CRDT" else "ud", round(abs(amt), 2)))
        ud.setdefault(slut, []).extend(rows)
    return ud


def tjek_betalinger(betalinger, bank, konto_nr, konti, vindue=VINDUE_DAGE, med_annullerede=False):
    """betalinger: Billy bankPayments (dicts). bank: output fra bank_tx. konto_nr: {cashAccountId: '5710', ...}.
    konti: {Billy-kontonr: bankkontoens slutcifre}, fra config bank.konti.
    Hver bankpostering kan kun matche én betaling. Billy 'debit' på en bankkonto = penge ind."""
    fund = []
    brugt = set()
    # betalinger før første bankdato kan ikke afgøres (banken giver kun ~540 dage)
    start = {k: min((r[0] for r in rows), default=None) for k, rows in bank.items()}
    slut_dato = {k: max((r[0] for r in rows), default=None) for k, rows in bank.items()}
    kandidater = []
    for p in betalinger:
        nr = konto_nr.get(p.get("cashAccountId"))
        if nr not in konti or (p.get("isVoided") and not med_annullerede):
            continue
        slut = konti[nr]
        dag = _dato(p["entryDate"])
        # uden for bankdataenes periode (for gammel, eller nyere end seneste hentning) kan ikke afgøres
        if (slut not in bank or start[slut] is None or dag < start[slut]
                or dag + dt.timedelta(days=vindue) > slut_dato[slut]):
            continue
        kandidater.append((dag, p, slut, nr))
    # gyldige betalinger får bankposteringerne først; annullerede må ikke "stjæle" dem
    for dag, p, slut, nr in sorted(kandidater, key=lambda x: (bool(x[1].get("isVoided")), x[0])):
        retning = "ind" if p.get("cashSide") == "debit" else "ud"
        beloeb = round(abs(float(p.get("cashAmount") or 0)), 2)
        bedst = None
        for i, (bd, br, bb) in enumerate(bank[slut]):
            if (slut, i) in brugt or br != retning or abs(bb - beloeb) > 0.005:
                continue
            afst = abs((bd - dag).days)
            if afst <= vindue and (bedst is None or afst < bedst[0]):
                bedst = (afst, i)
        if bedst is None:
            fund.append({"tjek": "betaling uden bankpostering", "id": p["id"], "dato": str(dag), "konto": nr,
                         "retning": retning, "beloeb": beloeb, "annulleret": bool(p.get("isVoided"))})
        else:
            brugt.add((slut, bedst[1]))
    return fund


def tjek_kreditnotaer(fakturaer):
    """fakturaer: ALLE Billy-invoices (også før perioden, kreditnotaer kan pege langt tilbage)."""
    pr_id = {f["id"]: f for f in fakturaer}
    fund = []
    for k in fakturaer:
        if k.get("type") != "creditNote" or k.get("state") == "draft":
            continue
        base = {"id": k["id"], "nr": k.get("invoiceNo"), "dato": k.get("entryDate"), "beloeb": k.get("grossAmount")}
        org_id = k.get("creditedInvoiceId")
        if not org_id:
            fund.append({**base, "tjek": "kreditnota uden henvisning til faktura"})
            continue
        org = pr_id.get(org_id)
        if org is None:
            fund.append({**base, "tjek": "kreditnota peger på ukendt faktura", "faktura_id": org_id})
            continue
        if float(k.get("grossAmount") or 0) - float(org.get("grossAmount") or 0) > 0.005:
            fund.append({**base, "tjek": "kreditnota større end fakturaen", "faktura_nr": org.get("invoiceNo"),
                         "faktura_beloeb": org.get("grossAmount")})
        if (k.get("entryDate") or "") < (org.get("entryDate") or ""):
            fund.append({**base, "tjek": "kreditnota dateret før fakturaen", "faktura_nr": org.get("invoiceNo"),
                         "faktura_dato": org.get("entryDate")})
        if k.get("currencyId") != org.get("currencyId"):
            fund.append({**base, "tjek": "kreditnota i anden valuta end fakturaen", "faktura_nr": org.get("invoiceNo")})
        # kreditnotaen skal sendes til køber (JV D.A.8.1.1.4). Kun når fakturaen selv er sendt fra Billy:
        # nogle fakturasystemer sender selv PDF'erne, så deres fakturaer og kreditnotaer står altid 'unsent' i Billy
        if (k.get("sentState") or "unsent") == "unsent" and (org.get("sentState") or "unsent") != "unsent":
            fund.append({**base, "tjek": "kreditnota ikke sendt til kunden", "faktura_nr": org.get("invoiceNo")})
    return fund


def tjek_uden_bilag(regninger, har_bilag, er_ikke_regning):
    return [{"tjek": "bogført regning uden bilag", "id": b["id"], "dato": b.get("entryDate"), "beloeb": b.get("grossAmount")}
            for b in regninger
            if b.get("state") == "approved" and not er_ikke_regning(b.get("lineDescription") or "") and not har_bilag(b["id"])]


def beloeb_varianter(x):
    """De måder et beløb typisk står på en faktura: 2468.42, 2,468.42, 2.468,42, 2468,42, 2 468,42 (og uden decimaler ved hele tal)."""
    x = round(abs(float(x)), 2)
    heltal, dec = f"{x:.2f}".split(".")
    tusind = f"{int(heltal):,}"
    v = {f"{heltal}.{dec}", f"{heltal},{dec}", f"{tusind}.{dec}", f"{tusind.replace(',', '.')},{dec}",
         f"{tusind.replace(',', ' ')},{dec}"}
    if dec == "00":
        v |= {heltal, tusind, tusind.replace(",", ".")}
    return v


_VALUTA = {k: re.compile(rx) for k, rx in {
    "DKK": r"\bDKK\b|\bkr\b\.?", "EUR": r"\bEUR\b|€", "USD": r"\bUSD\b|\$", "GBP": r"\bGBP\b|£",
    "SEK": r"\bSEK\b", "NOK": r"\bNOK\b"}.items()}


def _cvr_moenster(cvr):
    cifre = [c for c in str(cvr or "") if c.isdigit()]
    # tillad mellemrum, punktum og bindestreg mellem cifrene, men ikke andre cifre omkring
    return re.compile(r"(?<!\d)" + r"[\s.\-]?".join(cifre) + r"(?!\d)") if cifre else None


def tjek_bilag_indhold(regninger, bilag_tekster, cvr, er_ikke_regning, navn=""):
    """Bilaget skal være selve fakturaen til netop denne regning (mbek § 58, § 59 og § 66).
    bilag_tekster(bill_id) -> liste af PDF-tekster. Fund er advarsler, ikke stop:
      - udenlandsk faktura uden købers momsnummer (mbek § 59, omvendt betalingspligt)
      - dansk faktura over 3.000 kr. uden købers navn (mbek § 58, stk. 1, nr. 4). Købers CVR kræves ikke på en
        dansk faktura; en dansk forenklet faktura på højst 3.000 kr. behøver slet ikke nævne køber (mbek § 66)
      - regningens beløb står ikke på noget bilag (springes over, når bilaget er i en anden valuta end regningen,
        fx en EUR-faktura på en DKK-bankkladde, for så kan beløbet ikke sammenlignes direkte)"""
    cvr_rx = _cvr_moenster(cvr)
    navn = (navn or "").strip().lower()
    fund = []
    for b in regninger:
        if er_ikke_regning(b.get("lineDescription") or ""):
            continue
        tekster = [t for t in bilag_tekster(b["id"]) if t and not t.startswith("[pdf-fejl")]
        if not tekster:
            continue  # ingen læsbar PDF; tjek_uden_bilag tager regninger helt uden bilag
        base = {"id": b["id"], "dato": b.get("entryDate"), "beloeb": b.get("grossAmount"), "valuta": b.get("currencyId")}
        alt = " ".join(tekster)
        valuta = b.get("currencyId") or "DKK"
        andre = [k for k, rx in _VALUTA.items() if k != valuta and rx.search(alt)]
        egen = bool(_VALUTA[valuta].search(alt)) if valuta in _VALUTA else valuta in alt
        udland = valuta != "DKK" or bool(andre)
        if udland:
            if cvr_rx and not cvr_rx.search(alt):
                fund.append({**base, "tjek": "udenlandsk bilag uden købers momsnummer (mbek § 59)"})
        elif float(b.get("grossAmount") or 0) > 3000 and navn and navn not in alt.lower():
            fund.append({**base, "tjek": "dansk bilag over 3.000 kr. uden købers navn (mbek § 58)"})
        if andre and not egen:
            continue
        # beløbet skal stå som et helt tal, ikke som del af et længere tal (fx 500 i 1500,00)
        if not any(re.search(r"(?<![\d.,])" + re.escape(v) + r"(?![\d]|[.,]\d)", alt) for v in beloeb_varianter(b.get("grossAmount") or 0)):
            fund.append({**base, "tjek": "regningens beløb står ikke på bilaget"})
    return fund


def tjek_fakturanumre(fakturaer, fra="0000-00-00"):
    """Fakturanumre skal være fortløbende (mbek § 58, stk. 1, nr. 2). Finder dubletter og huller i godkendte
    og annullerede fakturaer og kreditnotaer (i Billy deler de nummerserie). Kun numeriske numre; et hul meldes, når fakturaen
    efter hullet er dateret fra og med 'fra'."""
    nr = [(int(f["invoiceNo"]), f) for f in fakturaer
          if f.get("state") in ("approved", "voided") and str(f.get("invoiceNo") or "").isdigit()]
    fund, set_ = [], {}
    for n, f in nr:
        if n in set_ and (f.get("entryDate") or "") >= fra:
            fund.append({"tjek": "fakturanummer brugt to gange", "nr": n, "id": f["id"], "dato": f.get("entryDate"),
                         "andet_id": set_[n]["id"]})
        set_.setdefault(n, f)
    numre = sorted(set_)
    for a, b in zip(numre, numre[1:]):
        if b - a > 1 and (set_[b].get("entryDate") or "") >= fra:
            mangler = list(range(a + 1, b))
            fund.append({"tjek": "hul i fakturanumre", "mangler": mangler[:10] + (["…"] if len(mangler) > 10 else []),
                         "dato": set_[b].get("entryDate"), "efter_nr": a, "foer_nr": b})
    return fund


# Straksafskrivningsgrænse ekskl. fradragsberettiget moms, JV C.C.2.4.2.4.2.5 (læst 31/10-2026).
# Tilføj nye år, når Den juridiske vejledning er opdateret. Ukendte år tjekkes ikke.
STRAKS_GRAENSE = {2025: 34400, 2026: 36000}


def linje_netto(linje, tax_mode):
    """Linjens beløb ekskl. moms. Billy-regninger har ofte taxMode 'incl', hvor amount er inkl. moms."""
    return float(linje.get("amount") or 0) - (float(linje.get("tax") or 0) if tax_mode == "incl" else 0)


def tjek_straksafskrivning(linjer, smaa_konto, udstyr_konto, graenser=STRAKS_GRAENSE):
    """linjer: dicts med konto (kontonr), beloeb_dkk (ekskl. moms), dato, bill_id.
    Småanskaffelser over grænsen skal formentlig afskrives som udstyr; udstyr under grænsen kan straksafskrives.
    Samlesæt tæller som ét driftsmiddel, og software kan ikke straksafskrives fra 2025: derfor kun 'tjek'."""
    fund = []
    for l in linjer:
        g = graenser.get(int(str(l.get("dato") or "0")[:4] or 0))
        if g is None:
            continue
        b = round(float(l.get("beloeb_dkk") or 0), 2)
        if l.get("konto") == smaa_konto and b > g:
            fund.append({"tjek": "småanskaffelse over straksafskrivningsgrænsen", "id": l.get("bill_id"),
                         "dato": l.get("dato"), "beloeb_ekskl_moms": b, "graense": g})
        elif l.get("konto") == udstyr_konto and 0 < b <= g:
            fund.append({"tjek": "udstyr under straksafskrivningsgrænsen", "id": l.get("bill_id"),
                         "dato": l.get("dato"), "beloeb_ekskl_moms": b, "graense": g})
    return fund


# ---------- kørsel mod Billy ----------

def main():
    import billy
    import config
    import leverandoer

    cfg = config.load()
    konti = cfg["bank"]["konti"]

    ap = argparse.ArgumentParser()
    ap.add_argument("--fra", default=f"{dt.date.today().year}-01-01")
    ap.add_argument("--med-annullerede", action="store_true")
    ap.add_argument("--uden-bilagstjek", action="store_true")
    ap.add_argument("--bilagsindhold", action="store_true", help="læs PDF'erne: købers CVR og beløb (langsomt, kræver PyMuPDF)")
    ap.add_argument("--straks", action="store_true", help="tjek straksafskrivning på linjerne (henter linjer pr. regning)")
    a = ap.parse_args()

    konto_nr = {acc["id"]: str(acc.get("accountNo")) for acc in billy.paged("/accounts", "accounts")}
    # OBS: /bankPayments ignorerer minEntryDate, så der filtreres lokalt
    betalinger = [p for p in billy.paged("/bankPayments", "bankPayments") if (p.get("entryDate") or "") >= a.fra]
    if konti:
        bank = bank_tx(cfg["bank"]["data_mappe"], konti)
        if not bank:
            print(f"Ingen bankfiler fundet i {cfg['bank']['data_mappe']}: betalingstjekket kan ikke afgøre noget.")
        fund = tjek_betalinger(betalinger, bank, konto_nr, konti, med_annullerede=a.med_annullerede)
    else:
        fund = []
        print("Ingen bank.konti i config: betalingstjekket mod bankdata springes over.")

    alle_fakturaer = billy.paged("/invoices", "invoices")
    fund += [f for f in tjek_kreditnotaer(alle_fakturaer) if (f.get("dato") or "") >= a.fra]
    fund += tjek_fakturanumre(alle_fakturaer, a.fra)

    ikke_regning = lambda t: bool(leverandoer.ikke_regning(t))  # noqa: E731
    regninger = billy.bills(a.fra) if (not a.uden_bilagstjek or a.bilagsindhold or a.straks) else []
    if not a.uden_bilagstjek:
        fund += tjek_uden_bilag(regninger, lambda i: bool(billy.attachments(i)), ikke_regning)
    if a.bilagsindhold:
        try:
            import fitz  # noqa: F401  (PyMuPDF; uden den kan PDF'erne ikke læses, og tjekket ville intet finde)
        except ImportError:
            raise SystemExit("--bilagsindhold kræver PyMuPDF: pip install pymupdf")
        v = cfg["virksomhed"]
        if not v.get("cvr") or not v.get("navn"):
            print("virksomhed.cvr og/eller virksomhed.navn mangler i config: de tilsvarende bilagstjek springes over.")
        fund += tjek_bilag_indhold(regninger, lambda i: [billy.file_text(x["fileId"]) for x in billy.attachments(i)],
                                   v.get("cvr"), ikke_regning, v.get("navn"))
    if a.straks:
        kt = cfg["billy_konti"]
        linjer = []
        for b in regninger:
            kurs = float(b.get("exchangeRate") or 1)
            if b.get("state") != "approved" or float(b.get("grossAmount") or 0) * kurs < 1000:
                continue  # kun regninger over 1.000 kr. kan rumme en linje tæt på grænsen
            for l in billy.lines(b["id"]):
                netto = linje_netto(l, b.get("taxMode"))
                linjer.append({"konto": konto_nr.get(l.get("accountId")), "beloeb_dkk": netto * kurs,
                               "dato": b.get("entryDate"), "bill_id": b["id"]})
        fund += tjek_straksafskrivning(linjer, kt.get("smaaanskaffelser", "1840"), kt.get("udstyr", "1880"))

    print(f"Regnskabstjek fra {a.fra}: {len(fund)} ting at se på")
    for slags in sorted({f["tjek"] for f in fund}):
        rk = [f for f in fund if f["tjek"] == slags]
        print(f"\n⚑ {slags} ({len(rk)})")
        for f in sorted(rk, key=lambda x: x.get("dato") or ""):
            print("   " + " | ".join(f"{k} {v}" for k, v in f.items() if k != "tjek"))


if __name__ == "__main__":
    main()
