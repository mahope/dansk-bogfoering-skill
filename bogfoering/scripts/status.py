"""Overblik til månedsluk: hvad mangler, før bogføringen er ajour?

  python status.py              # hele året
  python status.py --maaned 2026-09
"""
import argparse
import collections
import datetime as dt
import json
import os

import analyse
import dublet
import billy
import leverandoer as L

ap = argparse.ArgumentParser()
ap.add_argument("--fra", default=f"{dt.date.today().year}-01-01")
ap.add_argument("--maaned")
a = ap.parse_args()
mn, mx = billy.maaned_interval(a.maaned) if a.maaned else (a.fra, "2099-12-31")

alle = billy.bills(mn, mx)
kl = [b for b in alle if b["state"] == "draft"]
bogf = [b for b in alle if b["state"] == "approved"]
kat = collections.Counter()
for b in kl:
    ir = L.ikke_regning(b.get("lineDescription") or "")
    kat[ir[0] if ir else "udgift"] += 1

print(f"Periode {mn} – {mx}")
print(f"  Bogførte regninger: {len(bogf)}   Kladder: {len(kl)}  " + ", ".join(f"{k} {v}" for k, v in kat.most_common()))

udg = [b for b in kl if not L.ikke_regning(b.get("lineDescription") or "")]
uden = [b for b in udg if not billy.attachments(b["id"])]
print(f"  Udgiftskladder uden bilag: {len(uden)}")
for b in uden:
    print(f"     {b['entryDate']} {billy.kr(b['amount']):>10} {b['currencyId']} {b.get('lineDescription')}")

dub = dublet.find_dubletter(alle)
print(f"  Dubletkandidater: {len(dub)} (sikre: {sum(1 for d in dub if d['sikker'])}) — kør dubletter.py")

pr_maaned = collections.Counter(b["entryDate"][:7] for b in udg)
print("  Udgiftskladder pr. måned: " + ", ".join(f"{k} {v}" for k, v in sorted(pr_maaned.items())))

ub = [b for b in bogf if not b["isPaid"]]
if ub:
    print(f"  Bogførte men ikke markeret betalt: {len(ub)} (bank-afstemning mangler)")

rp = os.path.join(billy.HOME, "regler.json")
if os.path.exists(rp):
    r = json.load(open(rp, encoding="utf-8"))
    print(f"  Regler lært {r['genereret']} fra {r['regninger']} regninger ({len(r['regler'])} leverandører).")
sp = os.path.join(billy.HOME, "skygge.jsonl")
if os.path.exists(sp):
    print(f"  Skyggeforslag i log: {sum(1 for _ in open(sp, encoding='utf-8'))} — kør skygge.py for træfsikkerhed.")

# moms-frist
returns = billy.paged("/salesTaxReturns", "salesTaxReturns")
idag = dt.date.today().isoformat()
aabne = [r for r in returns if not r["isSettled"] and r["startDate"] <= idag]
for r in aabne[-2:]:
    print(f"  Moms {r['periodText']}: ikke afregnet, frist {r['reportDeadline']}")
for r in returns:
    if r["isSettled"] and not r["isPaid"] and r["reportDeadline"] < idag and r["startDate"] >= f"{dt.date.today().year - 1}-01-01":
        print(f"  ⚑ Moms {r['periodText']}: afregnet {r['settledAmount']} kr. men ikke markeret betalt i Billy.")
