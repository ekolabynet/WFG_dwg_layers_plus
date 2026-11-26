# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""The shared "WorkFieldGIS" menu with real Qt widgets (needs QGIS; skipped without it)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from qgis.PyQt.QtCore import QObject, pyqtSignal
    from qgis.PyQt.QtWidgets import QAction, QApplication, QMainWindow, QMenu
    HAVE_QT = True
except ImportError:
    HAVE_QT = False


if HAVE_QT:
    class FakeIface(QObject):
        initializationCompleted = pyqtSignal()

        def __init__(self, window):
            super().__init__()
            self._window = window

        def mainWindow(self):  # noqa: N802
            return self._window


@unittest.skipUnless(HAVE_QT, "needs QGIS / PyQt")
class TestSharedMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from wfg_dwg_layers_plus import wfg_menu
        self.M = wfg_menu
        self.win = QMainWindow()
        bar = self.win.menuBar()
        bar.addMenu(QMenu("&Plugins", self.win))
        helpm = QMenu("&Help", self.win)
        helpm.setObjectName("mHelpMenu")
        bar.addMenu(helpm)
        self.iface = FakeIface(self.win)

    def titles(self):
        return [a.text().replace("&", "") for a in self.win.menuBar().actions()]

    def sub_titles(self, menu):
        return [a.text() for a in menu.actions()]

    def test_first_plugin_makes_the_menu_before_help(self):
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.add_action(QAction("run", self.win))
        a.install()
        self.assertEqual(self.titles(), ["Plugins", "WorkFieldGIS", "Help"])
        self.assertEqual(self.sub_titles(a.parent), ["WFG A"])

    def test_second_plugin_joins_the_same_menu(self):
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.install()
        b = self.M.WfgSubmenu(self.iface, "WFG B", "mB")
        b.install()
        self.assertEqual(self.titles().count("WorkFieldGIS"), 1)
        self.assertIs(a.parent, b.parent)
        self.assertEqual(self.sub_titles(a.parent), ["WFG A", "WFG B"])

    def test_menu_made_by_another_wfg_plugin_is_found_by_title(self):
        other = QMenu("&WorkFieldGIS", self.win)          # e.g. an older plugin without the object name
        self.win.menuBar().addMenu(other)
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.install()
        self.assertIs(a.parent, other)
        self.assertIsNone(a.own_shared)

    def test_settle_moves_into_the_first_shared_menu(self):
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.install()
        a.add_action(QAction("run", self.win))
        # a plugin that does not look for the menu adds a second "WorkFieldGIS" in front of it
        first = QMenu("&WorkFieldGIS", self.win)
        first.setObjectName("mWorkFieldGisMenu")
        self.win.menuBar().insertMenu(self.win.menuBar().actions()[0], first)
        self.iface.initializationCompleted.emit()
        self.assertIs(a.parent, first)
        self.assertEqual(self.titles().count("WorkFieldGIS"), 1)

    def test_unload_keeps_the_menu_while_others_use_it(self):
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.install()
        b = self.M.WfgSubmenu(self.iface, "WFG B", "mB")
        b.install()
        a.remove()                                     # the plugin that made the menu goes first
        self.assertEqual(self.titles(), ["Plugins", "WorkFieldGIS", "Help"])
        self.assertEqual(self.sub_titles(b.parent), ["WFG B"])
        b.remove()                                     # the last one out removes the empty menu
        self.assertEqual(self.titles(), ["Plugins", "Help"])

    def test_unload_of_the_only_plugin_removes_the_menu(self):
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.install()
        a.remove()
        self.assertEqual(self.titles(), ["Plugins", "Help"])

    def test_reload_does_not_duplicate(self):
        for _ in range(3):
            a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
            a.install()
            a.remove()
        a = self.M.WfgSubmenu(self.iface, "WFG A", "mA")
        a.install()
        self.assertEqual(self.titles().count("WorkFieldGIS"), 1)
        self.assertEqual(self.sub_titles(a.parent), ["WFG A"])


if __name__ == "__main__":
    unittest.main()
