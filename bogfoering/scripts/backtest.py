"""Backtest: hvor godt rammer reglerne bogholderens faktiske kontering?

  python laer.py --godkendt-foer 2026-08-15 --ud regler_backtest.json
  python backtest.py --regler regler_backtest.json --godkendt-fra 2026-08-15

Reglerne læres KUN af regninger før skæringsdatoen og afprøves på de bogførte regninger efter den,
som om de var kladder. Det giver et ærligt tal for træfsikkerheden uden at vente på skyggedriften.
"""
import argparse
import collections
import datetime as dt
import json
import os

import analyse
import billy

ap = argparse.ArgumentParser()
ap.add_argument("--regler", default="regler_backtest.json")
ap.add_argument("--fra", default=f"{dt.date.today().year - 1}-01-01", help="bilagsdato fra")
ap.add_argument("--godkendt-fra", required=True, help="test på regninger godkendt fra denne dato")
ap.add_argument("--til", default="2099-12-31")
a = ap.parse_args()

R = json.load(open(os.path.join(billy.HOME, a.regler), encoding="utf-8"))
test = [b for b in billy.bills(a.fra, a.til, states=("approved",)) if (b.get("approvedTime") or "")[:10] >= a.godkendt_fra]
ACC, TAX = billy.accounts(), billy.tax_rates()
stat = collections.Counter()
pr_sik = collections.defaultdict(collections.Counter)
afv = []
for b in test:
    f = analyse.foreslaa(b, R)
    lns = billy.lines(b["id"])
    if not f["kontoId"]:
        stat["intet forslag"] += 1
        pr_sik[f["sikkerhed"]]["intet forslag"] += 1
        afv.append((b["entryDate"], b.get("lineDescription"), f["lev"], "-", lns))
        continue
    res = analyse.sammenlign(f["kontoId"], f["momsId"], lns, ACC, TAX)
    stat[res] += 1
    pr_sik[f["sikkerhed"]][res] += 1
    if res != "rigtig":
        afv.append((b["entryDate"], b.get("lineDescription"), f["lev"], f"{f['konto']} / {f['moms']}", lns))

acc, tax = billy.accounts(), billy.tax_rates()
nk = lambda i: f"{acc[i]['accountNo']} {acc[i]['name']}" if i in acc else "-"
nm = lambda i: (tax[i].get("abbreviation") or tax[i]["name"]) if i in tax else "-"
n = sum(stat.values())
print(f"Backtest på {n} regninger godkendt fra {a.godkendt_fra} (regler lært af godkendelser før):")
for k, v in stat.most_common():
    print(f"  {k:18} {v:4}  {100*v/n:5.1f} %")
print("\nPr. sikkerhed:")
for s, c in pr_sik.items():
    t = sum(c.values())
    ok = c['rigtig'] + c['skattemæssigt ens']
    print(f"  {s:12} {c['rigtig']:3} helt rigtige, {ok:3} skattemæssigt korrekte af {t:3} = {100*c['rigtig']/t:5.1f} % / {100*ok/t:5.1f} %")
ok_i_alt = stat["rigtig"] + stat["skattemæssigt ens"]
print(f"\nSkattemæssigt korrekte (samme momsbeløb og fradragstype): {ok_i_alt} af {n} = {100*ok_i_alt/n:.1f} %")
print("\nAfvigelser (forslag → bogholderen):")
for d, t, lev, fo, lns in sorted(afv, key=lambda x: x[0])[:60]:
    pr = " + ".join(f"{nk(l['accountId'])} / {nm(l['taxRateId'])}" for l in lns)
    print(f"  {d} {str(t)[:24]:24} {str(lev)[:14]:14} {fo[:42]:42} → {pr}")
