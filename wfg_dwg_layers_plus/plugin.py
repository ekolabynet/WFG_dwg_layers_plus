# -*- coding: utf-8 -*-
"""Rejestracja wtyczki w QGIS."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

MENU = "WFG DWG Layers+"
OLD_SETTINGS_PREFIX = "dwg_layers_plus/"
SETTINGS_PREFIX = "wfg_dwg_layers_plus/"


def migrate_settings():
    """Przenosi ustawienia z pakietu dwg_layers_plus (do 1.5.2) do wfg_dwg_layers_plus.

    Kopiuje tylko klucze, których w nowym miejscu jeszcze nie ma; stare zostają,
    dopóki stara wtyczka może być zainstalowana obok."""
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

    def initGui(self):  # noqa: N802
        try:
            migrate_settings()
        except Exception:  # ustawienia nie mogą zatrzymać startu wtyczki
            pass
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        action = QAction(icon, "Importuj DWG/DXF jako warstwy…", self.iface.mainWindow())
        action.setObjectName("dwgLayersPlusImport")
        action.setStatusTip(
            "Import DWG/DXF z warstwami nazwanymi jak w CAD, w czterech grupach"
        )
        action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(MENU, action)
        self.iface.addToolBarIcon(action)
        self.actions.append(action)

        restyle = QAction(
            icon, "Popraw wygląd wczytanych warstw…", self.iface.mainWindow()
        )
        restyle.setObjectName("dwgLayersPlusRestyle")
        restyle.setStatusTip(
            "Nakłada style WFG DWG Layers+ na warstwy już wczytane do projektu, "
            "bez ponownego importu rysunku"
        )
        restyle.triggered.connect(self.run_restyle)
        self.iface.addPluginToVectorMenu(MENU, restyle)
        self.actions.append(restyle)

        attrs = QAction(
            icon, "Wczytaj atrybuty bloków z rysunku…", self.iface.mainWindow()
        )
        attrs.setObjectName("dwgLayersPlusAttributes")
        attrs.setStatusTip(
            "Odzyskuje wartości atrybutów bloków (ATTRIB), których wbudowany "
            "import DWG/DXF nie widzi, i skleja je z importem po uchwycie encji"
        )
        attrs.triggered.connect(self.run_attributes)
        self.iface.addPluginToVectorMenu(MENU, attrs)
        self.actions.append(attrs)

        enc = QAction(icon, "Napraw kodowanie…", self.iface.mainWindow())
        enc.setObjectName("dwgLayersPlusEncoding")
        enc.setStatusTip(
            "Usuwa podwójne kodowanie polskich znaków w nazwach warstw, "
            "nazwach bloków i treści tekstów"
        )
        enc.triggered.connect(self.run_encoding)
        self.iface.addPluginToVectorMenu(MENU, enc)
        self.actions.append(enc)

        layerfix = QAction(
            icon, "Odzyskaj warstwy z rysunku…", self.iface.mainWindow()
        )
        layerfix.setObjectName("dwgLayersPlusLayerFix")
        layerfix.setStatusTip(
            "Gdy cała kreska wylądowała na warstwie 0, a w rysunku ma swoje "
            "warstwy — przepisuje przypisanie z DXF-a po uchwycie encji"
        )
        layerfix.triggered.connect(self.run_layer_fix)
        self.iface.addPluginToVectorMenu(MENU, layerfix)
        self.actions.append(layerfix)

        split = QAction(icon, "Podziel warstwę wg koloru…", self.iface.mainWindow())
        split.setObjectName("dwgLayersPlusColorSplit")
        split.setStatusTip(
            "Dla rysunków, w których cała kreska leży na warstwie 0, "
            "a treść rozróżnia barwa"
        )
        split.triggered.connect(self.run_color_split)
        self.iface.addPluginToVectorMenu(MENU, split)
        self.actions.append(split)

        about = QAction(icon, "O wtyczce…", self.iface.mainWindow())
        about.triggered.connect(self.show_about)
        self.iface.addPluginToVectorMenu(MENU, about)
        self.actions.append(about)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu(MENU, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        from .gui.import_dialog import ImportDialog

        # okno tworzymy za kazdym razem — stan i tak wraca z QgsSettings,
        # a dzieki temu nie trzyma referencji do usunietych warstw
        self.dialog = ImportDialog(self.iface)
        self.dialog.exec_() if hasattr(self.dialog, "exec_") else self.dialog.exec()

    def run_restyle(self):
        from .gui.restyle_dialog import RestyleDialog

        dialog = RestyleDialog(self.iface)
        dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()

    def run_attributes(self):
        from .gui.attributes_dialog import AttributesDialog

        dialog = AttributesDialog(self.iface)
        dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()

    def run_encoding(self):
        from .gui.encoding_dialog import EncodingDialog

        dialog = EncodingDialog(self.iface)
        dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()

    def run_layer_fix(self):
        from .gui.layer_fix_dialog import LayerFixDialog

        dialog = LayerFixDialog(self.iface)
        dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()

    def run_color_split(self):
        from .gui.color_split_dialog import ColorSplitDialog

        dialog = ColorSplitDialog(self.iface)
        dialog.exec_() if hasattr(dialog, "exec_") else dialog.exec()

    def show_about(self):
        from qgis.PyQt.QtWidgets import QMessageBox

        QMessageBox.information(
            self.iface.mainWindow(),
            "WFG DWG Layers+",
            "WFG DWG Layers+ — import DWG/DXF do QGIS z prawdziwymi warstwami.\n\n"
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
            "wbudowany import DWG/DXF w QGIS.",
        )
