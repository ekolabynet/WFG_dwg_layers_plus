# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Warnings about side steps that may fail without stopping the main work.

A failed legend refresh or colour swatch must not abort an import, but it should
not vanish either: the reason goes to View > Panels > Log Messages, tab
"WFG DWG Layers+".
"""

import sys

TAG = "WFG DWG Layers+"


def _label(obj):
    """Layer name for a message; a layer whose C++ object is gone has none."""
    name = getattr(obj, "name", None)
    if callable(name):
        try:
            return str(name())
        except Exception:  # nosec B110
            # the failing step is often a deleted layer: name() fails too
            return "?"
    return str(obj)


def warn_exception(what, *args):
    """Writes the exception being handled to the QGIS message log. Never raises.

    ``what`` says which step failed, already translated (``tr(...)``), with
    ``{0}``… for ``args``. Layers in ``args`` are named here, not by the caller,
    because asking a broken layer for its name would raise inside ``except``.
    """
    exc = sys.exc_info()[1]
    try:
        what = what.format(*[_label(a) for a in args]) if args else str(what)
    except Exception:  # nosec B110
        # a wrong placeholder must not hide the warning itself
        pass
    text = "{0}: {1}".format(what, exc) if exc is not None else str(what)
    try:
        from qgis.core import Qgis, QgsMessageLog

        QgsMessageLog.logMessage(text, TAG, Qgis.Warning)
    except Exception:  # nosec B110
        # outside QGIS (tests, qgis_process without a GUI log) there is nowhere
        # to write; a warning must never become an error
        pass
