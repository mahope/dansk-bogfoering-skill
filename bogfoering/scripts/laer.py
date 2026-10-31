"""Lær konteringsregler fra bogholderens bogførte regninger i Billy.

Kør:  python laer.py [--fra 2025-01-01]
Skriver <tilstand_mappe>/regler.json og viser en oversigt.

Kilder til leverandør pr. bogført regning (i prioriteret rækkefølge):
  1. Træningspar (banktekst -> bogført regning) fra dubletoprydning (traening_par.json)
  2. Bogført regnings egen beskrivelse matchet mod bank-regex
  3. Tekst i vedhæftede PDF'er matchet mod fakturatekst-regex
Regninger uden genkendt leverandør tælles med under '?' så man kan se dækningen.
"""
import argparse
import collections
import datetime as dt
import json
import os

import billy
import leverandoer as L

ap = argparse.ArgumentParser()
ap.add_argument("--fra", default=f"{dt.date.today().year - 1}-01-01")
ap.add_argument("--til", default="2099-12-31", help="lær kun af regninger til og med denne dato (backtest)")
ap.add_argument("--ud", default="regler.json", help="filnavn i tilstandsmappen (config tilstand_mappe)")
ap.add_argument("--godkendt-foer", help="lær kun af regninger GODKENDT før denne dato (backtest)")
ap.add_argument("--ingen-pdf", action="store_true", help="spring PDF-læsning over (hurtigt, lavere dækning)")
ap.add_argument("--bogholder-fra", default="0000-00-00",
                help="regninger GODKENDT fra denne dato er bogført af bogholderen og vægter over ældre bogføringer "
                     "(standard: alle godkendte regninger tæller som bogholderens)")
args = ap.parse_args()

acc = billy.accounts()
tax = billy.tax_rates()
par_path = os.path.join(billy.HOME, "traening_par.json")
par = {p["approved"]: p["banktekst"] for p in json.load(open(par_path, encoding="utf-8"))} if os.path.exists(par_path) else {}

godkendte = billy.bills(args.fra, args.til, states=("approved",))
if args.godkendt_foer:
    godkendte = [b for b in godkendte if (b.get("approvedTime") or "")[:10] < args.godkendt_foer]
print(f"{len(godkendte)} bogførte regninger siden {args.fra}. Læser linjer og bilag …", flush=True)

obs = []  # (leverandør, kilde, kontoId, momsId, beløb, valuta, momsland, regnings-id, dato)
for i, b in enumerate(godkendte, 1):
    if i % 50 == 0:
        print(f"  {i}/{len(godkendte)}", flush=True)
    vend, kilde, land = None, None, None
    if b["id"] in par:
        vend, kilde = L.fra_banktekst(par[b["id"]]), "træningspar"
    if not vend:
        vend = L.fra_banktekst(b.get("lineDescription") or "")
        kilde = "beskrivelse" if vend else None
    tekst = ""
    if not args.ingen_pdf:
        for a in billy.attachments(b["id"]):
            try:
                tekst += " " + billy.file_text(a["fileId"])
            except SystemExit:
                pass
        land = L.momsland(tekst)
        if not vend:
            vend = L.fra_fakturatekst(tekst)
            kilde = "faktura-pdf" if vend else None
    for ln in billy.lines(b["id"]):
        obs.append(dict(lev=vend or "?", kilde=kilde, konto=ln["accountId"], moms=ln["taxRateId"],
                        beloeb=ln["amount"], valuta=b["currencyId"], land=land, id=b["id"], dato=b["entryDate"],
                        bogholder=(b.get("approvedTime") or "")[:10] >= args.bogholder_fra,
                        godkendt=b.get("approvedTime") or "",
                        beskr=(ln.get("description") or b.get("lineDescription") or "")[:60]))

pr_lev = collections.defaultdict(list)
for o in obs:
    pr_lev[o["lev"]].append(o)


def navn_konto(i):
    a = acc.get(i)
    return f"{a['accountNo']} {a['name']}" if a else "?"


def navn_moms(i):
    t = tax.get(i)
    return (t.get("abbreviation") or t["name"]) if t else "ingen"


regler = {}
for lev, alle_obs in pr_lev.items():
    if lev == "?":
        continue
    # Bogholderens egne bogføringer er facit. Ældre bogføringer (før bogholderen) bruges kun, hvis der ikke er andre.
    prob = [o for o in alle_obs if o["bogholder"]]
    os_ = sorted(prob or alle_obs, key=lambda o: (o["godkendt"], o["dato"]))
    c = collections.Counter((o["konto"], o["moms"]) for o in os_)
    # Bogholderens praksis ændrer sig over tid: den nyeste beslutning vinder, hvis den er gentaget blandt de 3 seneste.
    seneste = [(o["konto"], o["moms"]) for o in os_[-3:]]
    if seneste.count(seneste[-1]) >= 2 or len(os_) == 1:
        (k, m) = seneste[-1]
    else:
        (k, m) = c.most_common(1)[0][0]
    n = c[(k, m)]
    andel = n / len(os_)
    if len(os_) >= 3 and len(set(seneste)) == 1 and andel >= 0.6:
        sikkerhed = "høj"
    elif len(os_) >= 2 and seneste[-2:].count((k, m)) == 2:
        sikkerhed = "middel"
    else:
        sikkerhed = "lav"
    if not prob:
        sikkerhed = "lav"
    regler[lev] = dict(
        kontoId=k, konto=navn_konto(k), momsId=m, moms=navn_moms(m),
        n=len(os_), andel=round(andel, 2), sikkerhed=sikkerhed,
        kilde="bogholder" if prob else "før bogholder", n_foer_bogholder=len(alle_obs) - len(prob),
        alternativer=[dict(konto=navn_konto(kk), moms=navn_moms(mm), n=nn) for (kk, mm), nn in c.most_common()[1:4]],
        valutaer=dict(collections.Counter(o["valuta"] for o in os_)),
        momslande=dict(collections.Counter(o["land"] for o in os_ if o["land"])),
        senest=max(o["dato"] for o in os_),
    )

# Fallback pr. momsland (til ukendte leverandører): mest brugte konto+moms for hvert land
fallback = {}
for land in ("DK", "EU", "UDLAND"):
    c = collections.Counter((o["konto"], o["moms"]) for o in obs if o["land"] == land and o["bogholder"])
    if c:
        (k, m), n = c.most_common(1)[0]
        fallback[land] = dict(kontoId=k, konto=navn_konto(k), momsId=m, moms=navn_moms(m), n=n, af=sum(c.values()))

ukendte = pr_lev.get("?", [])
out = dict(
    genereret=__import__("time").strftime("%Y-%m-%d %H:%M"), fra=args.fra,
    regninger=len(godkendte), linjer=len(obs), genkendt=len(obs) - len(ukendte),
    regler=dict(sorted(regler.items(), key=lambda x: -x[1]["n"])),
    fallback_pr_momsland=fallback,
    ukendte_eksempler=[dict(dato=o["dato"], beskr=o["beskr"], konto=navn_konto(o["konto"]), moms=navn_moms(o["moms"]), land=o["land"]) for o in ukendte[:40]],
    momskoder={t["id"]: dict(kode=t.get("abbreviation"), navn=t["name"], sats=t["rate"], kob=t.get("appliesToPurchases")) for t in tax.values()},
)
dst = os.path.join(billy.HOME, args.ud)
billy.ensure_dirs()
json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"\nGenkendt leverandør på {out['genkendt']} af {out['linjer']} linjer. {len(regler)} leverandørregler.")
for s in ("høj", "middel", "lav"):
    print(f"  sikkerhed {s}: {sum(1 for r in regler.values() if r['sikkerhed'] == s)}")
print("\nStørste regler:")
for lev, r in list(out["regler"].items())[:25]:
    alt = f"  (+{sum(a['n'] for a in r['alternativer'])} andet)" if r["alternativer"] else ""
    print(f"  {lev:22} {r['konto']:40} {r['moms']:4} n={r['n']:<3} {r['sikkerhed']}{alt}")
print("\nFallback pr. momsland:", {k: f"{v['konto']} / {v['moms']} ({v['n']}/{v['af']})" for k, v in fallback.items()})
print(f"\nGemte {dst}")
