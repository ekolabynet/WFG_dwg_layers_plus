# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""The whole plugin loaded into a real QGIS (offscreen) with a stand-in iface; skipped without QGIS."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from qgis.core import QgsApplication
    from qgis.PyQt.QtCore import QObject, pyqtSignal
    from qgis.PyQt.QtWidgets import QMainWindow, QMenu
    HAVE_QGIS = True
except ImportError:
    HAVE_QGIS = False

if HAVE_QGIS:
    class FakeIface(QObject):
        initializationCompleted = pyqtSignal()

        def __init__(self):
            super().__init__()
            self.win = QMainWindow()
            bar = self.win.menuBar()
            self.layer_menu = bar.addMenu("&Layer")
            helpm = QMenu("&Help", self.win)
            helpm.setObjectName("mHelpMenu")
            bar.addMenu(helpm)
            self.toolbar_icons = []

        def mainWindow(self):  # noqa: N802
            return self.win

        def addToolBarIcon(self, action):  # noqa: N802
            self.toolbar_icons.append(action)

        def removeToolBarIcon(self, action):  # noqa: N802
            if action in self.toolbar_icons:      # QGIS ignores actions that are not on the toolbar
                self.toolbar_icons.remove(action)

        def insertAddLayerAction(self, action):  # noqa: N802
            self.layer_menu.addAction(action)

        def removeAddLayerAction(self, action):  # noqa: N802
            self.layer_menu.removeAction(action)


@unittest.skipUnless(HAVE_QGIS, "needs QGIS")
class TestPluginLoad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qgs = QgsApplication([], False)
        cls.qgs.initQgis()

    def test_menu_toolbox_and_unload(self):
        from wfg_dwg_layers_plus import classFactory
        iface = FakeIface()
        plugin = classFactory(iface)
        plugin.initGui()
        bar = iface.win.menuBar()
        titles = [a.text().replace("&", "") for a in bar.actions()]
        self.assertEqual(titles, ["Layer", "WorkFieldGIS", "Help"])
        shared = [a.menu() for a in bar.actions() if a.text().replace("&", "") == "WorkFieldGIS"][0]
        sub = shared.actions()[0].menu()
        self.assertEqual(sub.title(), "WFG DWG Layers+")
        self.assertEqual(len([a for a in sub.actions() if not a.isSeparator()]), 7)
        self.assertEqual(len(iface.toolbar_icons), 1)
        ids = [p.id() for p in QgsApplication.processingRegistry().providers()]
        self.assertIn(plugin.provider.id(), ids)
        plugin.unload()
        titles = [a.text().replace("&", "") for a in bar.actions()]
        self.assertEqual(titles, ["Layer", "Help"])
        self.assertEqual(iface.toolbar_icons, [])
        self.assertEqual(iface.layer_menu.actions(), [])


if __name__ == "__main__":
    unittest.main()
