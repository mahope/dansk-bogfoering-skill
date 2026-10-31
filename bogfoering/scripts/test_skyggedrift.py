"""Skyggedrift-markøren skal spærre kontering, godkendelse og momsrettelser (konter.py, ret_moms.py)."""
import os
import tempfile
import unittest

import billy


class Skyggedrift(unittest.TestCase):
    def setUp(self):
        self.gammel = billy.SKYGGE_MARKOR
        self.mappe = tempfile.TemporaryDirectory()
        billy.SKYGGE_MARKOR = os.path.join(self.mappe.name, "SKYGGEDRIFT")

    def tearDown(self):
        billy.SKYGGE_MARKOR = self.gammel
        self.mappe.cleanup()

    def test_markoer_spaerrer_og_tving_aabner(self):
        open(billy.SKYGGE_MARKOR, "w").close()
        with self.assertRaises(SystemExit):
            billy.kraev_ikke_skyggedrift()
        billy.kraev_ikke_skyggedrift(tving=True)

    def test_uden_markoer_er_der_aabent(self):
        billy.kraev_ikke_skyggedrift()


if __name__ == "__main__":
    unittest.main()
