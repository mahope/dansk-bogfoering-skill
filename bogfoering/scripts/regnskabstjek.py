"""Regnskabstjek: finder poster i Billy, som en bogholder ville gøre indsigelse imod. Kun læsning.

    python regnskabstjek.py                    # fra 1/1 i år
    python regnskabstjek.py --fra 2026-07-01
    python regnskabstjek.py --med-annullerede  # tag annullerede betalinger med (bevis på at tjekket fanger noget)
    python regnskabstjek.py --uden-bilagstjek  # spring det langsomme bilagstjek over

Tjek (reglerne og kilderne står i reference/dansk-bogfoering.md og reference/laerte-regler.md):
  1. Betalinger på en bankkonto i Billy (kontiene i config bank.konti) uden en postering med samme beløb og
     retning på den tilsvarende bankkonto inden for ±3 dage. Fanger fx kortbetalinger, som går via en
     betalingsudbyder, men blev bogført på bankkontoen.
  2. Kreditnotaer, der ikke peger på en faktura, peger på en ukendt faktura, overstiger fakturaen
     eller er dateret før den.
  3. Bogførte regninger uden bilag (bankkladder der ikke er regninger, fx Income sorter, springes over).

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
        ud[slut] = rows
    return ud


def tjek_betalinger(betalinger, bank, konto_nr, konti, vindue=VINDUE_DAGE, med_annullerede=False):
    """betalinger: Billy bankPayments (dicts). bank: output fra bank_tx. konto_nr: {cashAccountId: '5710', ...}.
    konti: {Billy-kontonr: bankkontoens slutcifre}, fra config bank.konti.
    Hver bankpostering kan kun matche én betaling. Billy 'debit' på en bankkonto = penge ind."""
    fund = []
    brugt = set()
    # betalinger før første bankdato kan ikke afgøres (banken giver kun ~540 dage)
    start = {k: min((r[0] for r in rows), default=None) for k, rows in bank.items()}
    kandidater = []
    for p in betalinger:
        nr = konto_nr.get(p.get("cashAccountId"))
        if nr not in konti or (p.get("isVoided") and not med_annullerede):
            continue
        slut = konti[nr]
        dag = _dato(p["entryDate"])
        if slut not in bank or start[slut] is None or dag < start[slut]:
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

    if not a.uden_bilagstjek:
        regninger = billy.bills(a.fra)
        fund += tjek_uden_bilag(regninger, lambda i: bool(billy.attachments(i)),
                                lambda t: bool(leverandoer.ikke_regning(t)))

    print(f"Regnskabstjek fra {a.fra}: {len(fund)} ting at se på")
    for slags in sorted({f["tjek"] for f in fund}):
        rk = [f for f in fund if f["tjek"] == slags]
        print(f"\n⚑ {slags} ({len(rk)})")
        for f in sorted(rk, key=lambda x: x.get("dato") or ""):
            print("   " + " | ".join(f"{k} {v}" for k, v in f.items() if k != "tjek"))


if __name__ == "__main__":
    main()
