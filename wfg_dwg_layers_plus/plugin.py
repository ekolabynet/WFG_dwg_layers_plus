# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Rejestracja wtyczki w QGIS."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from .i18n import LANG, SOURCE, tr
from .core.log import warn_exception
from .wfg_menu import WfgSubmenu

MENU = "WFG DWG Layers+"
OLD_SETTINGS_PREFIX = "dwg_layers_plus/"
SETTINGS_PREFIX = "wfg_dwg_layers_plus/"


def migrate_settings():
    """Copy settings of the old package dwg_layers_plus (up to 1.5.2) to wfg_dwg_layers_plus.

    Only keys missing under the new prefix are copied; the old keys stay while
    the old plugin may still be installed next to the new one."""
    from qgis.core import QgsSettings
    settings = QgsSettings()
    copied = 0
    for key in settings.allKeys():
        if key.startswith(OLD_SETTINGS_PREFIX):
            new_key = SETTINGS_PREFIX + key[len(OLD_SETTINGS_PREFIX):]
            if not settings.contains(new_key):
                settings.setValue(new_key, settings.value(key))
                copied += 1
    return copied


class DwgLayersPlusPlugin(object):
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.dialog = None
        self.provider = None
        self.add_layer_action = None
        self.submenu = None

    def initProcessing(self):  # noqa: N802
        """The plugin's tools in the Processing Toolbox (models, batch runs)."""
        if self.provider is not None:          # QGIS may call it before initGui (qgis_process)
            return
        from qgis.core import QgsApplication
        from .processing_provider import DwgLayersPlusProvider

        self.provider = DwgLayersPlusProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):  # noqa: N802
        try:
            migrate_settings()
        except Exception:  # settings must never stop the plugin from loading
            warn_exception(tr("Nie udało się przenieść ustawień z poprzedniej nazwy wtyczki"))
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
        # the plugin's submenu in the shared menu "WorkFieldGIS" of the WFG plugins (before 1.9.8: Vector menu)
        self.submenu = WfgSubmenu(self.iface, MENU, "mWfgDwgLayersPlusMenu", icon)

        action = QAction(icon, tr("Importuj DWG/DXF jako warstwy…"), self.iface.mainWindow())
        action.setObjectName("dwgLayersPlusImport")
        action.setStatusTip(
            tr("Import DWG/DXF z warstwami nazwanymi jak w CAD, w czterech grupach")
        )
        action.triggered.connect(self.run)
        self.submenu.add_action(action)
        self.iface.addToolBarIcon(action)
        self.actions.append(action)

        restyle = QAction(
            icon, tr("Popraw wygląd wczytanych warstw…"), self.iface.mainWindow()
        )
        restyle.setObjectName("dwgLayersPlusRestyle")
        restyle.setStatusTip(
            tr("Nakłada style WFG DWG Layers+ na warstwy już wczytane do projektu, "
            "bez ponownego importu rysunku")
        )
        restyle.triggered.connect(self.run_restyle)
        self.submenu.add_action(restyle)
        self.actions.append(restyle)

        attrs = QAction(
            icon, tr("Wczytaj atrybuty bloków z rysunku…"), self.iface.mainWindow()
        )
        attrs.setObjectName("dwgLayersPlusAttributes")
        attrs.setStatusTip(
            tr("Odzyskuje wartości atrybutów bloków (ATTRIB), których wbudowany "
            "import DWG/DXF nie widzi, i skleja je z importem po uchwycie encji")
        )
        attrs.triggered.connect(self.run_attributes)
        self.submenu.add_action(attrs)
        self.actions.append(attrs)

        enc = QAction(icon, tr("Napraw kodowanie…"), self.iface.mainWindow())
        enc.setObjectName("dwgLayersPlusEncoding")
        enc.setStatusTip(
            tr("Usuwa podwójne kodowanie polskich znaków w nazwach warstw, "
            "nazwach bloków i treści tekstów")
        )
        enc.triggered.connect(self.run_encoding)
        self.submenu.add_action(enc)
        self.actions.append(enc)

        layerfix = QAction(
            icon, tr("Odzyskaj warstwy z rysunku…"), self.iface.mainWindow()
        )
        layerfix.setObjectName("dwgLayersPlusLayerFix")
        layerfix.setStatusTip(
            tr("Gdy cała kreska wylądowała na warstwie 0, a w rysunku ma swoje "
            "warstwy — przepisuje przypisanie z DXF-a po uchwycie encji")
        )
        layerfix.triggered.connect(self.run_layer_fix)
        self.submenu.add_action(layerfix)
        self.actions.append(layerfix)

        split = QAction(icon, tr("Podziel warstwę wg koloru…"), self.iface.mainWindow())
        split.setObjectName("dwgLayersPlusColorSplit")
        split.setStatusTip(
            tr("Dla rysunków, w których cała kreska leży na warstwie 0, "
            "a treść rozróżnia barwa")
        )
        split.triggered.connect(self.run_color_split)
        self.submenu.add_action(split)
        self.actions.append(split)

        # Layer > Add Layer > Add DWG/DXF+ Layers… (and the Manage Layers toolbar), next to the other sources
        self.add_layer_action = QAction(icon, tr("Dodaj warstwy DWG/DXF+…"), self.iface.mainWindow())
        self.add_layer_action.setObjectName("wfgDwgLayersPlusAddLayer")
        self.add_layer_action.setStatusTip(
            tr("Import DWG/DXF z warstwami nazwanymi jak w CAD, w czterech grupach"))
        self.add_layer_action.triggered.connect(self.run)
        try:
            self.iface.insertAddLayerAction(self.add_layer_action)
        except AttributeError:
            self.iface.addLayerMenu().addAction(self.add_layer_action)

        self.initProcessing()

        about = QAction(icon, tr("O wtyczce…"), self.iface.mainWindow())
        about.triggered.connect(self.show_about)
        self.submenu.add_separator()
        self.submenu.add_action(about)
        self.actions.append(about)
        self.submenu.install()

    def unload(self):
        for action in self.actions:
            self.iface.removeToolBarIcon(action)
        self.actions = []
        if self.submenu is not None:
            self.submenu.remove()
            self.submenu = None
        if self.add_layer_action is not None:
            try:
                self.iface.removeAddLayerAction(self.add_layer_action)
            except AttributeError:
                self.iface.addLayerMenu().removeAction(self.add_layer_action)
            self.add_layer_action = None
        if self.provider is not None:
            from qgis.core import QgsApplication
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        from .gui.import_dialog import ImportDialog

        # okno tworzymy za kazdym razem — stan i tak wraca z QgsSettings,
        # a dzieki temu nie trzyma referencji do usunietych warstw
        self.dialog = ImportDialog(self.iface)
        self.dialog.exec()

    def run_restyle(self):
        from .gui.restyle_dialog import RestyleDialog

        dialog = RestyleDialog(self.iface)
        dialog.exec()

    def run_attributes(self):
        from .gui.attributes_dialog import AttributesDialog

        dialog = AttributesDialog(self.iface)
        dialog.exec()

    def run_encoding(self):
        from .gui.encoding_dialog import EncodingDialog

        dialog = EncodingDialog(self.iface)
        dialog.exec()

    def run_layer_fix(self):
        from .gui.layer_fix_dialog import LayerFixDialog

        dialog = LayerFixDialog(self.iface)
        dialog.exec()

    def run_color_split(self):
        from .gui.color_split_dialog import ColorSplitDialog

        dialog = ColorSplitDialog(self.iface)
        dialog.exec()

    def show_about(self):
        from qgis.PyQt.QtWidgets import QMessageBox

        QMessageBox.information(
            self.iface.mainWindow(),
            "WFG DWG Layers+",
            tr("WFG DWG Layers+ — import DWG/DXF do QGIS z prawdziwymi warstwami.\n\n"
            "• nazwy warstw: <warstwa_CAD>_hatch / _line / _pline / _point / "
            "_text / _insert\n"
            "• cztery grupy wg typu geometrii\n"
            "• tryb filtrow (szybki) i materializacji do osobnych tabel GPKG\n"
            "• bloki jako zlozone geometrie: jeden obiekt na wstawienie, "
            "z rekurencja, MINSERT i dziedziczeniem warstwy 0\n"
            "• odzyskiwanie atrybutow blokow (ATTRIB), ktorych libdxfrw nie "
            "czyta w ogole\n"
            "• naprawa podwojnego kodowania polskich znakow\n"
            "• odzyskanie przypisania warstw z DXF-a, gdy import zgubil je\n"
            "  dla ciezkiej POLYLINE i cala kreska wylandowala na warstwie 0\n"
            "• podzial warstwy wg koloru, grubosci pisaka i typu encji\n\n"
            "Wtyczka opiera sie na schemacie GeoPackage produkowanym przez "
            "wbudowany import DWG/DXF w QGIS.")
            + "\n\n" + tr("Język wtyczki: {0} (wg QGIS: {1})").format(LANG, SOURCE),
        )
