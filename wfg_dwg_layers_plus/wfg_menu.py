# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""The shared top menu "WorkFieldGIS" of the WFG plugins; each plugin adds its own submenu to it.

The same agreement as in WFG Urban Environment Toolset, WFG Woksele, WFG Tree Assessment and
the GeoDataBook Manager: the menu is found by its object name ``mWorkFieldGisMenu`` (or by its
title), and made right before Help only by the first WFG plugin that finds none. Plugins load
one after another, so the later ones find it; after QGIS has loaded every plugin a submenu that
ended up in a second "WorkFieldGIS" moves to the first one. When a plugin is unloaded it takes
its submenu away; the last one out removes the then empty shared menu.

This file is self-contained (Qt only), so the same copy can live in every WFG plugin.
"""
from qgis.PyQt.QtWidgets import QMenu

SHARED_TITLE = "&WorkFieldGIS"
SHARED_OBJECT = "mWorkFieldGisMenu"
HELP_OBJECT = "mHelpMenu"


def _plain(text):
    return (text or "").replace("&", "").strip()


def shared_menus(bar):
    """The "WorkFieldGIS" menus of a menu bar, in their order."""
    out = []
    for action in bar.actions():
        menu = action.menu()
        if menu is not None and (menu.objectName() == SHARED_OBJECT
                                 or _plain(menu.title()) == _plain(SHARED_TITLE)):
            out.append(menu)
    return out


class WfgSubmenu(object):
    """This plugin's submenu in the shared "WorkFieldGIS" menu."""

    def __init__(self, iface, title, object_name, icon=None):
        self.iface = iface
        self.menu = QMenu(title, iface.mainWindow())
        self.menu.setObjectName(object_name)
        if icon is not None:
            self.menu.setIcon(icon)
        self.parent = None        # the shared menu that holds the submenu
        self.own_shared = None    # the shared menu when this plugin made it

    def add_action(self, action):
        self.menu.addAction(action)
        return action

    def add_separator(self):
        self.menu.addSeparator()

    def install(self):
        bar = self.iface.mainWindow().menuBar()
        found = shared_menus(bar)
        if found:
            parent = found[0]
        else:
            parent = QMenu(SHARED_TITLE, self.iface.mainWindow())
            parent.setObjectName(SHARED_OBJECT)
            help_action = next((a for a in bar.actions()
                                if a.menu() is not None and a.menu().objectName() == HELP_OBJECT), None)
            if help_action is not None:
                bar.insertMenu(help_action, parent)
            else:
                bar.addMenu(parent)
            self.own_shared = parent
        parent.addMenu(self.menu)
        self.parent = parent
        try:            # a WFG plugin loaded later may have made its own "WorkFieldGIS"
            self.iface.initializationCompleted.connect(self.settle)
        except (AttributeError, TypeError):
            pass

    def settle(self):
        """After QGIS has loaded every plugin: one "WorkFieldGIS" menu, the first one."""
        if self.own_shared is None:
            return
        bar = self.iface.mainWindow().menuBar()
        others = [m for m in shared_menus(bar) if m is not self.own_shared]
        if not others:
            return
        self.own_shared.removeAction(self.menu.menuAction())
        others[0].addMenu(self.menu)
        self.parent = others[0]
        self._drop_own_shared(bar)

    def _drop_own_shared(self, bar):
        if self.own_shared is not None and not self.own_shared.actions():
            bar.removeAction(self.own_shared.menuAction())
            self.own_shared.deleteLater()
            self.own_shared = None

    def remove(self):
        try:
            self.iface.initializationCompleted.disconnect(self.settle)
        except (AttributeError, TypeError, RuntimeError):
            pass
        try:
            if self.parent is not None:
                self.parent.removeAction(self.menu.menuAction())
                if not self.parent.actions():     # the last WFG plugin out: no empty menu left behind
                    self.iface.mainWindow().menuBar().removeAction(self.parent.menuAction())
                    self.parent.deleteLater()
        except RuntimeError:      # another plugin already deleted the shared menu
            pass
        self.parent = None
        self.own_shared = None    # left to the other plugins when they still have entries in it
        self.menu.deleteLater()
