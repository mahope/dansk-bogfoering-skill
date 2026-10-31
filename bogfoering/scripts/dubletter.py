"""Find (og eventuelt ryd op i) kladder, der er dubletter af bogførte regninger.

  python dubletter.py                    # vis kandidater (læser kun)
  python dubletter.py --apply            # slå de SIKRE par sammen (samme leverandør på begge sider)
  python dubletter.py --apply --id X Y   # slå kun de nævnte kladde-id'er sammen (også usikre, efter manuelt tjek)

Sammenlægning = bilag kopieres fra kladden til den bogførte regning, verificeres, kladden gemmes som backup
i <tilstand_mappe>/backup/ og slettes. Parret gemmes som træningsdata til laer.py.
Kladde→kladde-par slås aldrig sammen automatisk.
"""
import argparse

import analyse
import dublet
import billy

ap = argparse.ArgumentParser()
ap.add_argument("--fra", default=billy.aar_start())
ap.add_argument("--apply", action="store_true")
ap.add_argument("--id", nargs="+", help="kun disse kladde-id'er (mindst ét)")
a = ap.parse_args()

alle = billy.bills(a.fra)
par = dublet.find_dubletter(alle)
sikre = [p for p in par if p["sikker"] and p["type"] == "kladde→bogført"]
print(f"{len(par)} dubletkandidater, heraf {len(sikre)} sikre (samme leverandør genkendt på begge sider).\n")
for p in par:
    k, m = p["kladde"], p["maal"]
    mark = "SIKKER " if p["sikker"] else "tjek   "
    print(f"{mark} {k['entryDate']} {billy.kr(k['amount']):>10} {k['currencyId']} {(k.get('lineDescription') or '')[:28]:28} "
          f"→ {m['state']:8} {m['entryDate']} {m['amount']} {m['currencyId']} ({p['grund']}; lev {p['lev_kladde']}/{p['lev_maal']})"
          f"{' FLERE KANDIDATER' if p['flere_kandidater'] else ''}  [{k['id']}]")

if a.apply:
    valgte = [p for p in par if p["kladde"]["id"] in a.id] if a.id is not None else sikre
    valgte = [p for p in valgte if p["type"] == "kladde→bogført"]
    print(f"\nSlår {len(valgte)} par sammen …")
    for p in valgte:
        k = dublet.flyt_bilag_og_slet(p["kladde"]["id"], p["maal"]["id"])
        print(f"  slettet kladde {k['entryDate']} {k['amount']} {k.get('lineDescription')} (bilag flyttet til {p['maal']['id']})")
    print("Backup af hver slettet kladde ligger i", billy.BACKUP)
