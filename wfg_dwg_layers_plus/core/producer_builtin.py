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

from qgis.core import Qgis, QgsCoordinateReferenceSystem, QgsMessageLog, QgsProject, QgsSettings
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtWidgets import (
    QAbstractButton, QAction, QApplication, QDialog, QDialogButtonBox, QLineEdit, QMessageBox, QTableWidget,
)

from . import gpkg_schema as S
from ..i18n import tr
from .log import warn_exception

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
            warn_exception(tr("Nie udało się zapisać ustawienia importu QGIS {0}"), key)
    if use_curves is not None:
        for key in _CURVES_KEYS:
            try:
                settings.setValue(key, bool(use_curves))
            except Exception:
                warn_exception(tr("Nie udało się zapisać ustawienia importu QGIS {0}"), key)


def free_gpkg_path(path):
    """`path` if no such file exists, else `<stem>_2.gpkg`, `_3`… — the automatic mode never
    answers an "overwrite?" question on the user's behalf."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists("%s_%d%s" % (stem, n, ext)):
        n += 1
    return "%s_%d%s" % (stem, n, ext)


class _AutoDriver(object):
    """Fills the built-in DWG/DXF import dialog and presses Import and OK.

    The dialog has no API, so its widgets are found by object names and texts. Whatever
    cannot be found, the driver stops and leaves the dialog to the user — the worst case is
    the manual mode, never a wrong import."""

    def __init__(self, drawing, gpkg, crs_authid=None):
        self.drawing, self.gpkg, self.crs_authid = drawing, gpkg, crs_authid
        self.tries = 0
        self.done = False
        self.note = None

    def start(self):
        QTimer.singleShot(150, self._poll)

    def _log(self, msg, level=Qgis.Info):
        QgsMessageLog.logMessage(msg, "WFG DWG Layers+", level)

    def _poll(self):
        dlg = QApplication.activeModalWidget()
        if not isinstance(dlg, QDialog) or isinstance(dlg, QMessageBox):
            self.tries += 1
            if self.tries < 50:            # up to ~7 s for the dialog to show
                QTimer.singleShot(150, self._poll)
            return
        try:
            self._drive(dlg)
        except Exception as exc:  # noqa: BLE001  any surprise -> the user finishes by hand
            self.note = str(exc)
            self._log("auto import stopped: %s" % exc, Qgis.Warning)

    @staticmethod
    def _find_edit(dlg, *keys):
        for ed in dlg.findChildren(QLineEdit):
            name = ed.objectName().lower()
            if any(k in name for k in keys):
                return ed
        return None

    def _drive(self, dlg):
        ed_db = self._find_edit(dlg, "database", "package", "gpkg")
        ed_dwg = self._find_edit(dlg, "drawing", "dwg")
        if ed_db is None or ed_dwg is None:
            raise RuntimeError("fields not found: %s" % [e.objectName() for e in dlg.findChildren(QLineEdit)])
        ed_db.setText(self.gpkg)
        ed_db.editingFinished.emit()
        ed_dwg.setText(self.drawing)
        ed_dwg.editingFinished.emit()
        if self.crs_authid:
            try:
                from qgis.gui import QgsProjectionSelectionWidget
                for w in dlg.findChildren(QgsProjectionSelectionWidget):
                    w.setCrs(QgsCoordinateReferenceSystem(self.crs_authid))
            except Exception:  # noqa: BLE001
                warn_exception(
                    tr("Nie udało się ustawić układu współrzędnych {0} w oknie importu QGIS"),
                    self.crs_authid,
                )
        btn = None
        for b in dlg.findChildren(QAbstractButton):
            if "importdrawing" in b.objectName().lower():
                btn = b
                break
        if btn is None or not btn.isEnabled():
            raise RuntimeError("import button not found or disabled")
        btn.click()                         # synchronous: the drawing is read into the GeoPackage
        tables = [t for t in dlg.findChildren(QTableWidget) if t.rowCount()]
        if not tables:
            raise RuntimeError("no layer list after import")
        box = dlg.findChild(QDialogButtonBox)
        ok = box.button(QDialogButtonBox.StandardButton.Ok) if box is not None else None
        if ok is None or not ok.isEnabled():
            raise RuntimeError("OK button not available")
        self.done = True
        ok.click()


def run_builtin_import(iface, block_mode, use_curves=True, cleanup=True, auto=False,
                       drawing=None, gpkg=None, crs_authid=None):
    """Otwiera wbudowany dialog i zwraca sciezke do powstalego GeoPackage.

    :param auto: wypelnij okno (rysunek, GeoPackage, uklad) i nacisnij Import oraz OK
        bez udzialu uzytkownika; gdy sie nie uda, okno zostaje dla uzytkownika.
    :raises BuiltinImportError: gdy akcji nie ma albo nic nie zaimportowano
    """
    main_window = iface.mainWindow() if iface is not None else None
    action = find_action(main_window)
    if action is None:
        raise BuiltinImportError(
            tr("Nie znaleziono akcji wbudowanego importu DWG/DXF. "
            "Zaimportuj rysunek recznie (Projekt > Importuj/Eksportuj > "
            "Importuj warstwy z DWG/DXF), a potem wskaz powstaly plik .gpkg.")
        )

    preset_block_mode(block_mode, use_curves)

    project = QgsProject.instance()
    before_layers = set(project.mapLayers().keys())
    root = project.layerTreeRoot()
    before_nodes = list(root.children())

    driver = None
    if auto and drawing:
        target = free_gpkg_path(gpkg or os.path.splitext(drawing)[0] + ".gpkg")
        driver = _AutoDriver(drawing, target, crs_authid)
        driver.start()
    action.trigger()   # modalny — wraca po zamknieciu okna
    if driver is not None and not driver.done:
        QgsMessageLog.logMessage(
            "auto import fell back to the dialog: %s" % (driver.note or "dialog not found"),
            "WFG DWG Layers+", Qgis.Warning)

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
            tr("Import nie utworzyl zadnych warstw — anulowano okno albo rysunek "
            "jest pusty. Mozesz tez wskazac gotowy plik .gpkg recznie.")
        )
    return gpkg


def _cleanup(project, root, before_nodes, new_ids):
    """Usuwa warstwy i grupy dolozone przez wbudowany dialog."""
    for node in list(root.children()):
        if node not in before_nodes:
            try:
                root.removeChildNode(node)
            except Exception:
                warn_exception(tr("Nie udało się usunąć warstw dodanych przez wbudowany import"))
    if new_ids:
        try:
            project.removeMapLayers(new_ids)
        except Exception:
            warn_exception(tr("Nie udało się usunąć warstw dodanych przez wbudowany import"))


def _guess_from_settings():
    settings = QgsSettings()
    for key in _DB_KEYS:
        try:
            value = settings.value(key)
        except Exception:  # unreadable setting: try the next key  # nosec B112
            continue
        if value and str(value).lower().endswith(".gpkg") and os.path.exists(str(value)):
            return str(value)
    return None
