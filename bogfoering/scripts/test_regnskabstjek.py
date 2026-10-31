"""Tests for regnskabstjek (ingen netværk). Kør: python -m unittest test_regnskabstjek -v

Kontokoblingen (Billy-kontonr -> bankkontoens slutcifre) injiceres i hvert kald, så testene ikke afhænger af en config-fil.
"""
import datetime as dt
import json
import os
import tempfile
import unittest

import regnskabstjek as rt

D = dt.date.fromisoformat
# Billy-cashAccountId -> Billy-kontonummer
KONTO = {"bank": "5710", "udbyder": "5804", "moms": "5715"}
# Billy-kontonummer -> slutcifre på bankkontoen
KONTI = {"5710": "0001", "5715": "0002"}


def bet(id_, dato, beloeb, side="debit", konto="bank", voided=False):
    return {"id": id_, "entryDate": dato, "cashAmount": beloeb, "cashSide": side, "cashAccountId": konto, "isVoided": voided}


BANK = {"0001": [(D("2026-07-14"), "ind", 15000.0), (D("2026-07-02"), "ud", 1250.0), (D("2026-07-16"), "ind", 500.0)],
        "0002": [(D("2026-07-14"), "ind", 3000.0)]}


def tjek(betalinger, **kw):
    return rt.tjek_betalinger(betalinger, BANK, KONTO, kw.pop("konti", KONTI), **kw)


class Betalinger(unittest.TestCase):
    def test_match_paa_beloeb_retning_og_dato(self):
        self.assertEqual(tjek([bet("a", "2026-07-14", 15000), bet("b", "2026-07-03", 1250.0, "credit")]), [])

    def test_kortbetaling_paa_bank_uden_bankpostering_fanges(self):
        # Mønstret: 49,95 kr bogført på bankkontoen, men pengene kom via en betalingsudbyder
        fund = tjek([bet("kort", "2026-07-06", 49.95)])
        self.assertEqual([f["id"] for f in fund], ["kort"])

    def test_forkert_retning_fanges(self):
        self.assertEqual(len(tjek([bet("x", "2026-07-14", 15000, side="credit")])), 1)

    def test_uden_for_vindue_fanges_inden_for_godkendes(self):
        self.assertEqual(len(tjek([bet("x", "2026-07-18", 15000)])), 1)
        self.assertEqual(tjek([bet("x", "2026-07-17", 15000)]), [])

    def test_en_bankpostering_kan_kun_bruges_en_gang(self):
        fund = tjek([bet("a", "2026-07-14", 15000), bet("b", "2026-07-15", 15000)])
        self.assertEqual([f["id"] for f in fund], ["b"])

    def test_udbyderkonto_tjekkes_ikke_mod_banken(self):
        self.assertEqual(tjek([bet("s", "2026-07-06", 49.95, konto="udbyder")]), [])

    def test_momskonto_matches_mod_egen_bankkonto(self):
        self.assertEqual(tjek([bet("m", "2026-07-14", 3000, konto="moms")]), [])
        self.assertEqual(len(tjek([bet("m", "2026-07-14", 15000, konto="moms")])), 1)

    def test_annullerede_kun_med_flag(self):
        p = [bet("v", "2026-07-06", 49.95, voided=True)]
        self.assertEqual(tjek(p), [])
        self.assertEqual(len(tjek(p, med_annullerede=True)), 1)

    def test_annulleret_stjaeler_ikke_bankpostering_fra_gyldig(self):
        # annulleret og gyldig betaling på samme beløb og dag: den gyldige skal have bankposteringen
        p = [bet("annulleret", "2026-07-14", 15000, voided=True), bet("gyldig", "2026-07-14", 15000)]
        fund = tjek(p, med_annullerede=True)
        self.assertEqual([f["id"] for f in fund], ["annulleret"])

    def test_foer_bankdata_kan_ikke_afgoeres(self):
        self.assertEqual(tjek([bet("gl", "2025-01-01", 999)]), [])

    def test_kontomapping_kommer_fra_kaldet(self):
        # Samme betaling: uden for mappingen tjekkes den ikke, og en anden mapping peger på en anden bankkonto
        p = [bet("x", "2026-07-14", 15000)]
        self.assertEqual(tjek(p, konti={}), [])
        self.assertEqual(len(tjek(p, konti={"5710": "0002"})), 1)  # 15.000 findes ikke på konto 0002
        self.assertEqual(tjek(p, konti={"5710": "0001"}), [])


def fak(id_, nr, dato, beloeb, typ="invoice", krediterer=None, valuta="DKK", state="approved"):
    return {"id": id_, "invoiceNo": nr, "entryDate": dato, "grossAmount": beloeb, "type": typ,
            "creditedInvoiceId": krediterer, "currencyId": valuta, "state": state}


class Kreditnotaer(unittest.TestCase):
    F = [fak("f10", "10", "2026-05-05", 700), fak("f11", "11", "2026-02-02", 1234.5)]

    def test_korrekte_kreditnotaer_giver_intet(self):
        k = [fak("k20", "20", "2026-10-28", 700, "creditNote", "f10"), fak("k21", "21", "2026-10-28", 0.1, "creditNote", "f11")]
        self.assertEqual(rt.tjek_kreditnotaer(self.F + k), [])

    def test_hver_fejltype_fanges(self):
        cases = {
            "kreditnota uden henvisning til faktura": fak("a", "1", "2026-10-01", 10, "creditNote", None),
            "kreditnota peger på ukendt faktura": fak("b", "2", "2026-10-01", 10, "creditNote", "findes-ikke"),
            "kreditnota større end fakturaen": fak("c", "3", "2026-10-01", 701, "creditNote", "f10"),
            "kreditnota dateret før fakturaen": fak("d", "4", "2026-05-01", 10, "creditNote", "f10"),
            "kreditnota i anden valuta end fakturaen": fak("e", "5", "2026-10-01", 10, "creditNote", "f10", valuta="EUR"),
        }
        for forventet, k in cases.items():
            with self.subTest(forventet):
                self.assertEqual([f["tjek"] for f in rt.tjek_kreditnotaer(self.F + [k])], [forventet])

    def test_usendt_kreditnota_til_sendt_faktura_fanges(self):
        f = [fak("f", "10", "2026-05-05", 700) | {"sentState": "sent"}]
        usendt = fak("k", "20", "2026-10-28", 700, "creditNote", "f") | {"sentState": "unsent"}
        sendt = fak("k", "20", "2026-10-28", 700, "creditNote", "f") | {"sentState": "sent"}
        self.assertEqual([x["tjek"] for x in rt.tjek_kreditnotaer(f + [usendt])], ["kreditnota ikke sendt til kunden"])
        self.assertEqual(rt.tjek_kreditnotaer(f + [sendt]), [])

    def test_usendt_paa_begge_sider_er_ok(self):
        # Et fakturasystem sender selv PDF'en; i Billy står både faktura og kreditnota som unsent
        f = [fak("f", "30", "2026-07-30", 49.95) | {"sentState": "unsent"}]
        k = fak("k", "31", "2026-09-01", 49.95, "creditNote", "f") | {"sentState": "unsent"}
        self.assertEqual(rt.tjek_kreditnotaer(f + [k]), [])

    def test_kladder_ignoreres(self):
        self.assertEqual(rt.tjek_kreditnotaer(self.F + [fak("x", None, "2026-10-01", 10, "creditNote", None, state="draft")]), [])


class UdenBilag(unittest.TestCase):
    def test_kun_bogfoerte_regninger_uden_bilag_og_ikke_ikke_regninger(self):
        regn = [{"id": "1", "state": "approved", "lineDescription": "OpenAI"},
                {"id": "2", "state": "approved", "lineDescription": "Income sorter"},
                {"id": "3", "state": "draft", "lineDescription": "Hetzner"},
                {"id": "4", "state": "approved", "lineDescription": "GitHub"}]
        fund = rt.tjek_uden_bilag(regn, lambda i: i == "4", lambda t: t.startswith("Income sorter"))
        self.assertEqual([f["id"] for f in fund], ["1"])


class BankLoader(unittest.TestCase):
    def test_laeser_tx_noeglen_og_springer_pending_over(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.json"), "w", encoding="utf-8") as fh:
                json.dump({"konto": "Eksempel Drift …0001", "tx": [
                    {"booking_date": "2026-07-14", "credit_debit_indicator": "CRDT", "transaction_amount": {"amount": "15000.00"}},
                    {"booking_date": "2026-07-15", "credit_debit_indicator": "DBIT", "transaction_amount": {"amount": "10"}, "status": "PDNG"},
                ]}, fh)
            with open(os.path.join(d, "b.json"), "w", encoding="utf-8") as fh:
                json.dump({"konto": "Anden konto …9999", "tx": [
                    {"booking_date": "2026-07-14", "credit_debit_indicator": "CRDT", "transaction_amount": {"amount": "1.00"}}]}, fh)
            self.assertEqual(rt.bank_tx(d, KONTI), {"0001": [(D("2026-07-14"), "ind", 15000.0)]})
            self.assertEqual(rt.bank_tx(d, {}), {})


if __name__ == "__main__":
    unittest.main()
