"""Ret momskode på BOGFØRTE regninger i en åben momsperiode. Dokumenteret og med backup.

  python ret_moms.py --id <bill-id-prefix> [...] --til KYU --begrundelse "tekst"          # prøvekørsel
  python ret_moms.py --id <bill-id-prefix> [...] --til KYU --begrundelse "tekst" --udfoer  # skriver

Kun momskoden på linjen ændres (beløb, konto, bilag og betaling bevares). Før ændringen gemmes regning + linjer
i backup. Linjens beskrivelse får en kommentar sat bagpå, og ændringen logges i <tilstand_mappe>/aendringer/.
Skriver kun efter ejerens udtrykkelige go og kun med --tving, så længe skyggedrift er aktiv, og aldrig i en
afregnet momsperiode.
"""
import argparse
import datetime as dt
import json
import os

import billy

ap = argparse.ArgumentParser()
ap.add_argument("--id", nargs="+", required=True, help="regningens id eller de første tegn af det")
ap.add_argument("--til", required=True, help="momskode, fx KYU, KYE, KVU, K, KF")
ap.add_argument("--begrundelse", required=True)
ap.add_argument("--udfoer", action="store_true")
ap.add_argument("--tving", action="store_true", help="tillad skrivning selv om skyggedrift er aktiv (kun efter ejerens udtrykkelige go)")
ap.add_argument("--aar", type=int, default=dt.date.today().year, help="regnskabsår, som regningerne hentes fra")
a = ap.parse_args()

if a.udfoer:
    billy.kraev_ikke_skyggedrift(a.tving)

tr = billy.tax_rates()
mal = [i for i, t in tr.items() if (t.get("abbreviation") or "") == a.til]
if len(mal) != 1:
    raise SystemExit(f"Momskode {a.til} er ikke entydig i Billy: {len(mal)} træffere")
mal = mal[0]

# En periode der allerede er afregnet må ikke røres her (så skal der en korrektion af momsangivelsen til).
afregnet = [(r["startDate"], r["endDate"]) for r in billy.paged("/salesTaxReturns", "salesTaxReturns") if r["isSettled"]]

LOGDIR = os.path.join(billy.HOME, "aendringer")
os.makedirs(LOGDIR, exist_ok=True)
idag = dt.date.today().isoformat()

alle = {b["id"]: b for b in billy.bills(f"{a.aar}-01-01", f"{a.aar}-12-31", states=("approved",))}
for pre in a.id:
    kandidater = [b for i, b in alle.items() if i.startswith(pre)]
    if len(kandidater) != 1:
        print(f"{pre}: {len(kandidater)} træffere – springer over")
        continue
    b = kandidater[0]
    if any(s <= b["entryDate"] <= e for s, e in afregnet):
        print(f"{pre}: {b['entryDate']} ligger i en afregnet momsperiode – springer over (kræver korrektion)")
        continue
    ls = billy.lines(b["id"])
    if len(ls) != 1:
        print(f"{pre}: {len(ls)} linjer – springer over (kun enkeltlinje-regninger)")
        continue
    l = ls[0]
    gammel = tr.get(l["taxRateId"], {}).get("abbreviation")
    print(f"{b['id'][:8]} {b['entryDate']} {l['amount']} {b['currencyId']}: {gammel} -> {a.til}"
          + ("" if a.udfoer else "  (prøvekørsel)"))
    if not a.udfoer:
        continue
    bak = billy.backup(f"foer_ret_moms_{b['id'][:8]}", dict(bill=b, lines=ls))
    kommentar = f" [Rettet {idag}: momskode {gammel}->{a.til}. {a.begrundelse} Se aendringslog.]"
    ny = dict(id=l["id"], accountId=l["accountId"], taxRateId=mal, amount=l["amount"],
              description=(l.get("description") or "") + kommentar, quantity=l.get("quantity") or 1)
    billy.req("PUT", f"/bills/{b['id']}", {"bill": {"lines": [ny]}})
    efter = billy.req("GET", f"/bills/{b['id']}")["bill"]
    el = billy.lines(b["id"])[0]
    ok = (efter["state"] == "approved" and efter["isPaid"] and el["taxRateId"] == mal
          and abs(el["amount"] - l["amount"]) < 0.005)
    print(f"   efter: state={efter['state']} betalt={efter['isPaid']} saldo={efter['balance']} "
          f"brutto={efter.get('grossAmount')} netto={efter['amount']} moms={tr.get(el['taxRateId'], {}).get('abbreviation')} -> {'OK' if ok else 'AFVIGELSE – tjek backup'}")
    with open(os.path.join(LOGDIR, f"{idag}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(tid=dt.datetime.now().isoformat(timespec="seconds"), handling="ret_momskode",
                                regning=b["id"], dato=b["entryDate"], beloeb=l["amount"], valuta=b["currencyId"],
                                fra=gammel, til=a.til, begrundelse=a.begrundelse, backup=bak, verificeret=ok),
                           ensure_ascii=False) + "\n")
    if not ok:
        raise SystemExit("Efter-tjek fejlede – stopper. Backup: " + bak)
