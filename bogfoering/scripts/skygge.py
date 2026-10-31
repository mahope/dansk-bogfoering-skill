"""Sammenlign skillets skyggeforslag med det, bogholderen faktisk bogførte.

  python skygge.py            # træfsikkerhed + liste over afvigelser
Kladder, der stadig er kladder, tælles som 'afventer'. Slettede kladder (dubletter) tælles som 'slettet'.
Målet, før bogholderen kan undværes: ≥95 % rigtig konto OG momskode over mindst to måneder.
"""
import collections
import json
import os

import billy

p = os.path.join(billy.HOME, "skygge.jsonl")
if not os.path.exists(p):
    raise SystemExit("Ingen skyggelog endnu. Kør konter.py først.")
forslag = {}
for l in open(p, encoding="utf-8"):
    f = json.loads(l)
    forslag.setdefault(f["id"], f)  # første forslag tæller

acc, tax = billy.accounts(), billy.tax_rates()
navn_k = lambda i: (f"{acc[i]['accountNo']} {acc[i]['name']}" if i in acc else "-")
navn_m = lambda i: ((tax[i].get("abbreviation") or tax[i]["name"]) if i in tax else "-")

stat = collections.Counter()
pr_sik = collections.defaultdict(collections.Counter)
afv = []
for bid, f in forslag.items():
    try:
        b = billy.req("GET", f"/bills/{bid}")["bill"]
    except SystemExit:
        stat["slettet"] += 1
        continue
    if b["state"] != "approved":
        stat["afventer"] += 1
        continue
    lns = billy.lines(bid)
    ok_k = all(l["accountId"] == f["kontoId"] for l in lns)
    ok_m = all(l["taxRateId"] == f["momsId"] for l in lns)
    res = "rigtig" if ok_k and ok_m else "konto rigtig, moms forkert" if ok_k else "moms rigtig, konto forkert" if ok_m else "forkert"
    stat[res] += 1
    pr_sik[f["sikkerhed"]][res == "rigtig"] += 1
    if res != "rigtig":
        afv.append((f["dato"], f["tekst"], f["lev"], f"{f['konto']} / {f['moms']}",
                    " + ".join(f"{navn_k(l['accountId'])} / {navn_m(l['taxRateId'])}" for l in lns)))

vurderet = sum(v for k, v in stat.items() if k not in ("afventer", "slettet"))
print(f"Forslag i log: {len(forslag)}. Bogført af bogholderen siden: {vurderet}. Afventer: {stat['afventer']}. Slettet: {stat['slettet']}.")
if vurderet:
    print(f"Helt rigtige: {stat['rigtig']} af {vurderet} = {100*stat['rigtig']/vurderet:.0f} %")
    for k in ("konto rigtig, moms forkert", "moms rigtig, konto forkert", "forkert"):
        if stat[k]:
            print(f"  {k}: {stat[k]}")
    for s, c in pr_sik.items():
        print(f"  sikkerhed {s}: {c[True]} rigtige af {c[True]+c[False]}")
if afv:
    print("\nAfvigelser (skillets forslag → bogholderen):")
    for d, t, lev, fo, pr in sorted(afv):
        print(f"  {d} {t[:28]:28} {str(lev)[:14]:14} {fo}  →  {pr}")
    print("\nRet afvigelser ved at køre laer.py igen (lærer af de nye bogføringer) eller ved at tilføje en særregel i analyse.py.")
