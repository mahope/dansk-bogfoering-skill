"""Tests for config.py (ingen netværk, ingen rigtige filer). Kør: python -m unittest test_config -v"""
import json
import os
import tempfile
import unittest
from unittest import mock

import config


class Standardvaerdier(unittest.TestCase):
    def test_manglende_config_giver_standardvaerdier(self):
        with tempfile.TemporaryDirectory() as d:
            ingen = os.path.join(d, "findes-ikke.json")
            with mock.patch.dict(os.environ, {"BOGFOERING_CONFIG": ingen}):
                cfg = config.load()
        self.assertEqual(cfg["virksomhed"], {"navn": "", "cvr": ""})
        self.assertEqual(cfg["bank"]["konti"], {})
        self.assertEqual(cfg["tilstand_mappe"], os.path.abspath(os.path.expanduser("~/.bogfoering")))
        self.assertEqual(cfg["skyggedrift_markoer"], os.path.join(cfg["tilstand_mappe"], "SKYGGEDRIFT"))
        self.assertEqual(cfg["bank"]["data_mappe"], os.path.join(cfg["tilstand_mappe"], "bank"))
        self.assertEqual(cfg["billy_konti"]["momskonto"], "5715")

    def test_env_overstyrer_config_stien(self):
        with tempfile.TemporaryDirectory() as d:
            sti = os.path.join(d, "min.json")
            with open(sti, "w", encoding="utf-8") as fh:
                json.dump({"virksomhed": {"cvr": "12345678"}, "tilstand_mappe": os.path.join(d, "tilstand"),
                           "bank": {"konti": {"5710": "0001"}}}, fh)
            with mock.patch.dict(os.environ, {"BOGFOERING_CONFIG": sti}):
                self.assertEqual(config.config_sti(), sti)
                cfg = config.load()
            self.assertEqual(cfg["virksomhed"]["cvr"], "12345678")
            self.assertEqual(cfg["virksomhed"]["navn"], "")  # ikke angivet -> standard
            self.assertEqual(cfg["bank"]["konti"], {"5710": "0001"})
            self.assertEqual(cfg["skyggedrift_markoer"], os.path.join(d, "tilstand", "SKYGGEDRIFT"))

    def test_ugyldig_config_fejler_hoejt(self):
        with tempfile.TemporaryDirectory() as d:
            sti = os.path.join(d, "daarlig.json")
            with open(sti, "w", encoding="utf-8") as fh:
                fh.write("{ikke json")
            with self.assertRaises(SystemExit):
                config.load(sti)


class Token(unittest.TestCase):
    def test_miljoevariabel_vinder_over_fil(self):
        with tempfile.TemporaryDirectory() as d:
            fil = os.path.join(d, "t.env")
            with open(fil, "w", encoding="utf-8") as fh:
                fh.write("BILLY_API_TOKEN=fra-fil\n")
            cfg = {"billy_token_fil": fil}
            with mock.patch.dict(os.environ, {"BILLY_API_TOKEN": "fra-miljoe"}):
                self.assertEqual(config.token(cfg), "fra-miljoe")
            with mock.patch.dict(os.environ, {"BILLY_API_TOKEN": ""}):
                self.assertEqual(config.token(cfg), "fra-fil")

    def test_manglende_token_er_en_tydelig_fejl_uden_at_laekke(self):
        with tempfile.TemporaryDirectory() as d:
            fil = os.path.join(d, "t.env")
            with open(fil, "w", encoding="utf-8") as fh:
                fh.write("ANDET=hemmelig-vaerdi\n")
            with mock.patch.dict(os.environ, {"BILLY_API_TOKEN": "", "BOGFOERING_CONFIG": os.path.join(d, "ingen.json")}):
                with self.assertRaises(SystemExit) as c:
                    config.token({"billy_token_fil": None})
                self.assertIn("BILLY_API_TOKEN", str(c.exception))
                with self.assertRaises(SystemExit) as c:
                    config.token({"billy_token_fil": fil})
                self.assertNotIn("hemmelig-vaerdi", str(c.exception))


if __name__ == "__main__":
    unittest.main()
