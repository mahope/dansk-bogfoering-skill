"""Momstjek pr. periode: Billys egen momsangivelse + kontrol af det, der kan gøre den forkert.

  python moms.py                 # indeværende og forrige periode
  python moms.py --periode half:2026-2

Ved halvårlig momsafregning er fristerne: H1 (jan-jun) 1/9, H2 (jul-dec) 1/3 (tjek altid din egen frist på skat.dk).
Billy beregner rubrikkerne ud fra de BOGFØRTE poster. Kladder tæller ikke med — derfor er det
afgørende, at alle kladder i perioden er konteret og godkendt (eller slettet som dublet) før indberetning.
Indberetning sker i TastSelv Erhverv (eller via Billys SKAT-integration) — aldrig fra dette script.
"""
import argparse
import collections
import datetime as dt

import billy
import leverandoer as L

ap = argparse.ArgumentParser()
ap.add_argument("--periode")
a = ap.parse_args()

returns = billy.paged("/salesTaxReturns", "salesTaxReturns")
idag = dt.date.today().isoformat()
if a.periode:
    valgte = [r for r in returns if r["period"] == a.periode]
else:
    valgte = [r for r in returns if r["startDate"] <= idag] [-3:]
# vis kun seneste korrektion pr. periode + evt. afregnet original
pr_periode = collections.defaultdict(list)
for r in valgte:
    pr_periode[r["period"]].append(r)

for periode, rs in pr_periode.items():
    r0 = rs[0]
    print(f"\n=== {r0['periodText']} ({r0['startDate']} – {r0['endDate']}), frist {r0['reportDeadline']}")
    for r in rs:
        full = billy.req("GET", f"/salesTaxReturns/{r['id']}")["salesTaxReturn"]
        status = ("AFREGNET" if r["isSettled"] else "ikke afregnet") + (", BETALT" if r["isPaid"] else ", ikke markeret betalt")
        print(f"  Angivelse (korrektion {r['correctionNo']}): {status}. Afregnet beløb: {r['settledAmount']}")
        for grp in full.get("report") or []:
            for f in grp.get("fields") or []:
                v = f.get("vatAmount", f.get("turnoverAmount"))
                if v:
                    print(f"     {f['name']:52} {billy.kr(v):>12}")
        if r["isSettled"] and not r["isPaid"] and r["reportDeadline"] < idag:
            print("  ⚑ Afregnet men ikke markeret betalt, og fristen er passeret. Tjek skattekontoen; marker betalt i Billy, hvis den er betalt.")

    # Kontroller for perioden
    alle = billy.bills(r0["startDate"], r0["endDate"])
    kl = [b for b in alle if b["state"] == "draft"]
    regn = [b for b in kl if not L.ikke_regning(b.get("lineDescription") or "")]
    andre = [b for b in kl if L.ikke_regning(b.get("lineDescription") or "")]
    print(f"\n  Kladder i perioden: {len(kl)}  (heraf {len(regn)} udgifter, {len(andre)} momsoverførsler/skat/overførsler)")
    if regn:
        import analyse
        R = analyse.regler()
        s = sum(b["amount"] * (b["exchangeRate"] or 1) for b in regn)
        sats = {"K": 0.20, "KR": 0.05}  # andel af beløb inkl. moms: 25 % moms = 20 % af bruttobeløbet; KR = 25 % heraf
        est, ukendt = 0.0, 0
        for b in regn:
            f = analyse.foreslaa(b, R)
            if f["moms"] in sats:
                est += b["amount"] * (b["exchangeRate"] or 1) * sats[f["moms"]]
            elif not f["moms"]:
                ukendt += 1
        print(f"  ⚑ {len(regn)} udgiftskladder for {billy.kr(s)} kr. er IKKE med i momsen.")
        print(f"     Ud fra konteringsforslagene giver de ca. {billy.kr(est)} kr. ekstra købsmoms (danske K/KR-poster; udenlandske er netto 0)."
              + (f" {ukendt} kladder uden forslag er ikke regnet med." if ukendt else ""))
        if any(r["isSettled"] for r in rs):
            print("     Perioden er allerede afregnet → beløbet skal med i en korrektion af momsangivelsen, når kladderne er bogført.")
    momskonto = {i for i, x in billy.accounts().items() if str(x["accountNo"]) == str(billy.CFG["billy_konti"]["momskonto"])}
    uden = [b for b in alle if b["state"] == "approved" and not billy.attachments(b["id"])
            and not all(l["accountId"] in momskonto for l in billy.lines(b["id"]))]
    if uden:
        print(f"  ⚑ {len(uden)} bogførte regninger uden bilag (momsfradrag kræver bilag):")
        for b in uden[:15]:
            print(f"      {b['entryDate']} {billy.kr(b['amount']):>10} {b['currencyId']} {b.get('lineDescription')}")
    print("  Næste skridt: kør dubletter.py og konter.py for perioden, få kladderne bogført, og sammenlign så tallene ovenfor igen.")
