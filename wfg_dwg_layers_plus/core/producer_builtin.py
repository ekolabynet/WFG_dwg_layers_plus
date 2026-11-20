# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Producent A/B: skorzystanie z wbudowanego importu DWG/DXF w QGIS.

Kluczowe ograniczenie: ``QgsDwgImporter`` nie ma powiazan SIP. Klasa zyje
w ``src/app/dwg/``, kompiluje sie do ``qgis_app`` i nie jest wystawiona ani
w ``qgis.core``, ani w ``qgis.gui``. ``QgisInterface`` nie ma slotu
``dwgImport()``. Z Pythona nie da sie jej wywolac z parametrami.

Dlatego robimy to inaczej: odpalamy oryginalna akcje menu (modalny dialog),
a po jej zamknieciu wykrywamy sciezke GeoPackage z warstw, ktore dialog dodal
do projektu — i te tymczasowe warstwy usuwamy, bo wlasne drzewo zbudujemy sami.
"""

import os

from qgis.core import QgsProject, QgsSettings
from qgis.PyQt.QtWidgets import QAction

from . import gpkg_schema as S

ACTION_NAME = "mActionDwgImport"

_SETTINGS_KEYS = (
    "DwgImport/lastBlockImportFlags",
    "/DwgImport/lastBlockImportFlags",
)
_CURVES_KEYS = ("DwgImport/lastUseCurves", "/DwgImport/lastUseCurves")
#: klucz, pod ktorym wbudowany dialog zapisuje sciezke GeoPackage
#: (qgsdwgimportdialog.cpp: "/DwgImport/lastDatabaseFile")
_DB_KEYS = (
    "/DwgImport/lastDatabaseFile",
    "DwgImport/lastDatabaseFile",
)


class BuiltinImportError(Exception):
    pass


def find_action(main_window):
    """Znajduje akcje wbudowanego importu DWG/DXF po nazwie obiektu."""
    if main_window is None:
        return None
    for action in main_window.findChildren(QAction):
        try:
            if action.objectName() == ACTION_NAME:
                return action
        except RuntimeError:
            continue
    # zapasowo: po tekscie menu
    for action in main_window.findChildren(QAction):
        try:
            text = action.text().replace("&", "").lower()
        except RuntimeError:
            continue
        if "dwg" in text and "dxf" in text:
            return action
    return None


def is_available(main_window):
    return find_action(main_window) is not None


def preset_block_mode(block_mode, use_curves=None):
    """Ustawia domyslne wartosci w oknie wbudowanego importu.

    Dialog czyta te klucze przy otwarciu, wiec da sie w ten sposob podpowiedziec
    uzytkownikowi wlasciwy tryb — w szczegolnosci wylaczyc rozwijanie blokow,
    ktore jest warunkiem poprawnego dzialania trybu zlozonych geometrii.
    """
    settings = QgsSettings()
    flags = S.qgis_block_flags(block_mode)
    for key in _SETTINGS_KEYS:
        try:
            settings.setValue(key, flags)
        except Exception:
            pass
    if use_curves is not None:
        for key in _CURVES_KEYS:
            try:
                settings.setValue(key, bool(use_curves))
            except Exception:
                pass


def run_builtin_import(iface, block_mode, use_curves=True, cleanup=True):
    """Otwiera wbudowany dialog i zwraca sciezke do powstalego GeoPackage.

    :raises BuiltinImportError: gdy akcji nie ma albo nic nie zaimportowano
    """
    main_window = iface.mainWindow() if iface is not None else None
    action = find_action(main_window)
    if action is None:
        raise BuiltinImportError(
            "Nie znaleziono akcji wbudowanego importu DWG/DXF. "
            "Zaimportuj rysunek recznie (Projekt > Importuj/Eksportuj > "
            "Importuj warstwy z DWG/DXF), a potem wskaz powstaly plik .gpkg."
        )

    preset_block_mode(block_mode, use_curves)

    project = QgsProject.instance()
    before_layers = set(project.mapLayers().keys())
    root = project.layerTreeRoot()
    before_nodes = list(root.children())

    action.trigger()   # modalny — wraca po zamknieciu okna

    after = project.mapLayers()
    new_ids = [lid for lid in after if lid not in before_layers]

    gpkg = None
    for lid in new_ids:
        source = after[lid].source()
        candidate = source.split("|")[0]
        if candidate.lower().endswith(".gpkg") and os.path.exists(candidate):
            gpkg = candidate
            break

    if cleanup:
        _cleanup(project, root, before_nodes, new_ids)

    if gpkg is None:
        gpkg = _guess_from_settings()

    if gpkg is None:
        raise BuiltinImportError(
            "Import nie utworzyl zadnych warstw — anulowano okno albo rysunek "
            "jest pusty. Mozesz tez wskazac gotowy plik .gpkg recznie."
        )
    return gpkg


def _cleanup(project, root, before_nodes, new_ids):
    """Usuwa warstwy i grupy dolozone przez wbudowany dialog."""
    for node in list(root.children()):
        if node not in before_nodes:
            try:
                root.removeChildNode(node)
            except Exception:
                pass
    if new_ids:
        try:
            project.removeMapLayers(new_ids)
        except Exception:
            pass


def _guess_from_settings():
    settings = QgsSettings()
    for key in _DB_KEYS:
        try:
            value = settings.value(key)
        except Exception:
            continue
        if value and str(value).lower().endswith(".gpkg") and os.path.exists(str(value)):
            return str(value)
    return None
