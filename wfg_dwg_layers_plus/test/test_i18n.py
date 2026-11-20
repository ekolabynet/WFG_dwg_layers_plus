# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Every tr("…") literal has an English text with the same placeholders (no QGIS needed).

    python -m unittest wfg_dwg_layers_plus.test.test_i18n -v
"""
import ast
import os
import re
import unittest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDERS = re.compile(r"\{[^}]*\}|%[-\d.]*[sd]")


def _tr_literals():
    for base, _dirs, files in os.walk(PKG):
        if os.path.basename(base) in ("test", "__pycache__"):
            continue
        for fn in files:
            if not fn.endswith(".py") or fn.startswith("i18n"):
                continue
            path = os.path.join(base, fn)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for n in ast.walk(tree):
                if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "tr" and n.args
                        and isinstance(n.args[0], ast.Constant)):
                    yield os.path.relpath(path, PKG), n.lineno, n.args[0].value


class TestI18n(unittest.TestCase):
    def setUp(self):
        from wfg_dwg_layers_plus.i18n_en import EN
        self.en = EN
        self.used = list(_tr_literals())

    def test_every_text_translated(self):
        missing = ["%s:%d %r" % (f, ln, s[:60]) for f, ln, s in self.used if s not in self.en]
        self.assertEqual(missing, [])

    def test_placeholders_match(self):
        bad = ["%s:%d %r" % (f, ln, s[:60]) for f, ln, s in self.used if s in self.en
               and sorted(PLACEHOLDERS.findall(s)) != sorted(PLACEHOLDERS.findall(self.en[s]))]
        self.assertEqual(bad, [])

    def test_no_unused_translations(self):
        used = {s for _f, _ln, s in self.used}
        self.assertEqual(sorted(k[:60] for k in self.en if k not in used), [])

    def test_colour_split_label_keeps_separator(self):
        # gui/color_split_dialog.py splits the combo text on two spaces + "("
        self.assertIn("  (", self.en["{0}  ({1} kolorów, {2} obiektów)"])

    def test_language_switch(self):
        from wfg_dwg_layers_plus import i18n
        old = i18n.LANG
        try:
            i18n.LANG = "en"
            self.assertEqual(i18n.tr("Zamknij"), "Close")
            self.assertEqual(i18n.tr("tekst bez tłumaczenia"), "tekst bez tłumaczenia")
            i18n.LANG = "pl"
            self.assertEqual(i18n.tr("Zamknij"), "Zamknij")
        finally:
            i18n.LANG = old


if __name__ == "__main__":
    unittest.main()
