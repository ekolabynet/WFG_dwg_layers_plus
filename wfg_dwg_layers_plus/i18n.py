# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Language of the plugin: Polish when QGIS runs in Polish, English otherwise.

Source texts in the code are Polish; ``tr("…")`` returns the English text from
``i18n_en.EN``. A missing translation falls back to the Polish text
(test/test_i18n.py checks that none is missing). ``WFG_LANG=pl|en`` forces
the language (tests, preview). No QGIS import at module level, so the core
modules stay testable with plain Python.
"""
import os


def _detect():
    forced = os.environ.get("WFG_LANG", "")
    if forced:
        return forced[:2].lower()
    loc = ""
    try:
        from qgis.core import QgsApplication
        loc = QgsApplication.locale() or ""
    except Exception:
        loc = ""
    if not loc:
        try:
            from qgis.PyQt.QtCore import QLocale
            loc = QLocale.system().name()
        except Exception:
            loc = os.environ.get("LANG", "")
    return "pl" if str(loc).lower().startswith("pl") else "en"


LANG = _detect()
_EN = None


def tr(text):
    """Polish source text -> text in the language of the plugin."""
    global _EN
    if LANG == "pl":
        return text
    if _EN is None:
        from .i18n_en import EN
        _EN = EN
    return _EN.get(text, text)
