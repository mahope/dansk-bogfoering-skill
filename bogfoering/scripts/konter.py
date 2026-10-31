"""Foreslå kontering af kladder i Billy ud fra de lærte regler.

  python konter.py                      # forslag for alle kladder i år (logges i skyggeloggen)
  python konter.py --maaned 2026-09     # kun én måned
  python konter.py --apply --id X Y     # skriv konto+momskode på de nævnte kladders linjer (godkender IKKE)
  python konter.py --apply --sikkerhed høj   # skriv på alle kladder med høj sikkerhed (godkender IKKE)
  python konter.py --godkend --id X     # godkend (bogfør) de nævnte kladder — kræver konto, momskode og bilag

Skyggedrift: hvert forslag skrives til <tilstand_mappe>/skygge.jsonl. Når bogholderen senere bogfører kladden,
sammenligner skygge.py forslaget med det, bogholderen faktisk gjorde. Brug --ingen-log til prøvekørsler.
Momsoverførsler, skattebetalinger, hævninger og Stripe-udbetalinger konteres aldrig som regninger.
"""
import argparse
import collections
import json
import os
import time

import analyse
import billy

ap = argparse.ArgumentParser()
ap.add_argument("--fra", default=billy.aar_start())
ap.add_argument("--maaned")
ap.add_argument("--apply", action="store_true")
ap.add_argument("--godkend", action="store_true")
ap.add_argument("--id", nargs="+", help="kun disse kladde-id'er (mindst ét)")
ap.add_argument("--tving", action="store_true", help="tillad --apply/--godkend selv om skyggedrift er aktiv (kun efter ejerens udtrykkelige go)")
ap.add_argument("--sikkerhed", choices=["høj", "middel"], help="med --apply: skriv kun forslag med mindst denne sikkerhed")
ap.add_argument("--ingen-log", action="store_true")
ap.add_argument("--json", action="store_true")
a = ap.parse_args()

R = analyse.regler()
mn, mx = billy.maaned_interval(a.maaned) if a.maaned else (a.fra, "2099-12-31")
kladder = [b for b in billy.bills(mn, mx, states=("draft",))]
if a.id is not None:
    kladder = [b for b in kladder if b["id"] in a.id]
if (a.apply or a.godkend):
    billy.kraev_ikke_skyggedrift(a.tving)
fs = [analyse.foreslaa(b, R) for b in sorted(kladder, key=lambda b: b["entryDate"])]

if a.json:
    print(json.dumps(fs, ensure_ascii=False, indent=1))
else:
    grp = collections.defaultdict(list)
    for f in fs:
        grp[f["sikkerhed"]].append(f)
    for s in ("høj", "middel", "lav", "vurdér", "ingen", "ikke-regning"):
        if not grp[s]:
            continue
        print(f"\n== {s.upper()} ({len(grp[s])})")
        for f in grp[s]:
            if s == "ikke-regning":
                print(f"  {f['dato']} {billy.kr(f['beloeb']):>10} {f['tekst'][:30]:30} {f['begrundelse'][:70]}")
                continue
            fl = ("  ⚑ " + ", ".join(f["flag"])) if f["flag"] else ""
            print(f"  {f['dato']} {billy.kr(f['beloeb']):>10} {f['valuta']} {f['tekst'][:28]:28} {str(f['lev'] or '?')[:16]:16} "
                  f"→ {str(f['konto'] or '-')[:34]:34} {str(f['moms'] or '-'):4}{fl}")
    print(f"\n{len(fs)} kladder. Sikkerhed: " + ", ".join(f"{k} {len(v)}" for k, v in grp.items()))

if not a.ingen_log and not a.apply and not a.godkend:
    p = os.path.join(billy.HOME, "skygge.jsonl")
    allerede = set()
    if os.path.exists(p):
        allerede = {json.loads(l)["id"] for l in open(p, encoding="utf-8")}
    nye = [f for f in fs if f["id"] not in allerede and f["sikkerhed"] != "ikke-regning"]
    with open(p, "a", encoding="utf-8") as fh:
        for f in nye:
            fh.write(json.dumps(dict(id=f["id"], tid=time.strftime("%Y-%m-%d %H:%M"), dato=f["dato"], tekst=f["tekst"],
                                     lev=f["lev"], kontoId=f["kontoId"], momsId=f["momsId"], konto=f["konto"], moms=f["moms"],
                                     sikkerhed=f["sikkerhed"]), ensure_ascii=False) + "\n")
    print(f"Skyggelog: {len(nye)} nye forslag gemt ({p}).")

RANG = {"høj": 3, "middel": 2, "lav": 1}
if a.apply:
    if a.id is None and not a.sikkerhed:
        raise SystemExit("--apply kræver --id eller --sikkerhed")
    min_r = RANG.get(a.sikkerhed or "lav", 1)
    BLOKERENDE = ("TJEK FOR DUBLET", "MANGLER BILAG", "GÆT UD FRA VALUTA", "AFVIGER", "TJEK ERHVERV/PRIVAT", "REPRÆSENTATION")
    n = 0
    for f in fs:
        if not f["kontoId"] or f["sikkerhed"] == "ikke-regning":
            continue
        if a.id is None:
            # Bulk (--sikkerhed): kun rene forslag. Alt med advarselsflag kræver eksplicit --id.
            if RANG.get(f["sikkerhed"], 0) < min_r or any(b in fl for fl in f["flag"] for b in BLOKERENDE):
                continue
        elif f["flag"]:
            print(f"  OBS {f['id']}: konteres trods flag {f['flag']} (valgt eksplicit med --id)")
        lns = billy.lines(f["id"])
        billy.backup(f"linjer_{f['id']}", lns)
        # PUT /billLines/<id> giver HTTP 500 i Billy — linjer opdateres gennem regningen (id bevares).
        billy.req("PUT", f"/bills/{f['id']}", {"bill": {"lines": [
            {"id": ln["id"], "accountId": f["kontoId"], "taxRateId": f["momsId"], "amount": ln["amount"],
             "description": ln["description"], "quantity": ln.get("quantity") or 1} for ln in lns]}})
        efter = billy.lines(f["id"])
        if any(l["accountId"] != f["kontoId"] or l["taxRateId"] != f["momsId"] for l in efter):
            raise SystemExit(f"Kontering af {f['id']} blev ikke gemt korrekt — stopper")
        n += 1
        print(f"  konteret {f['dato']} {f['tekst'][:30]} → {f['konto']} / {f['moms']}")
    print(f"{n} kladder konteret (ikke godkendt).")

if a.godkend:
    if a.id is None:
        raise SystemExit("--godkend kræver --id (godkendelse sker aldrig i bulk)")
    import leverandoer as L
    for bid in a.id:
        b = billy.req("GET", f"/bills/{bid}")["bill"]
        if b["state"] != "draft":
            print(f"  SPRINGER OVER {bid}: er {b['state']}, ikke kladde")
            continue
        if L.ikke_regning(b.get("lineDescription") or ""):
            print(f"  SPRINGER OVER {bid}: '{b.get('lineDescription')}' er ikke en regning (momsoverførsel/skat/hævning)")
            continue
        lns = billy.lines(bid)
        if not lns:
            print(f"  SPRINGER OVER {bid}: ingen linjer")
            continue
        if not billy.attachments(bid):
            print(f"  SPRINGER OVER {bid}: intet bilag")
            continue
        if any(not l["accountId"] or not l["taxRateId"] for l in lns):
            print(f"  SPRINGER OVER {bid}: linje mangler konto eller momskode")
            continue
        billy.req("PUT", f"/bills/{bid}", {"bill": {"state": "approved"}})
        print(f"  godkendt {bid}")
