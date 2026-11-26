# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Okno „Popraw wygląd wczytanych warstw" — bez ponownego importu."""

from qgis.core import QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ..core import restyle, styler
from ..i18n import tr
from ..core.log import warn_exception

SETTINGS_PREFIX = "wfg_dwg_layers_plus/"


class RestyleDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(RestyleDialog, self).__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle(tr("WFG DWG Layers+ — popraw wygląd"))
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)

        intro = QLabel(
            tr("Nakłada style WFG DWG Layers+ na warstwy, które są już w projekcie — "
            "bez ponownego czytania rysunku. Przydatne, gdy część punktów albo "
            "linii wczytała się z domyślnym wyglądem QGIS.")
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QFormLayout()

        self.sp_line_width = QDoubleSpinBox()
        self.sp_line_width.setRange(0.01, 5.0)
        self.sp_line_width.setSingleStep(0.05)
        self.sp_line_width.setDecimals(2)
        self.sp_line_width.setSuffix(" mm")
        self.sp_line_width.setToolTip(
            tr("Grubość dla encji bez własnej (linewidth 0 albo -1 = BYBLOCK). "
            "Bez tego QGIS podstawia swoje 0,26 mm.")
        )
        form.addRow(tr("Grubość zastępcza linii:"), self.sp_line_width)

        self.cmb_pline_width = QComboBox()
        self.cmb_pline_width.addItem(
            tr("jako grubość pisaka w mm (zalecane)"), "mm")
        self.cmb_pline_width.addItem(
            tr("jako szerokość w terenie, wiernie jak CAD"), "map")
        self.cmb_pline_width.addItem(tr("pomijaj"), "ignore")
        self.cmb_pline_width.setToolTip(
            tr("Polilinie CAD mają globalną szerokość (kolumna width) w jednostkach "
            "rysunku. QGIS renderuje ją wiernie — polilinia o width 0,5 wychodzi "
            "na pół metra szeroka, jak czarna belka. Projektanci zwykle wpisują "
            "tam grubości piór ISO (0,05 / 0,1 / 0,3 / 0,5), więc domyślnie "
            "traktujemy tę liczbę jako milimetry.")
        )
        form.addRow(tr("Szerokość polilinii:"), self.cmb_pline_width)

        self.cb_show_points = QCheckBox(tr("Pokazuj warstwy punktów CAD"))
        form.addRow("", self.cb_show_points)

        self.sp_point_size = QDoubleSpinBox()
        self.sp_point_size.setRange(0.1, 10.0)
        self.sp_point_size.setSingleStep(0.1)
        self.sp_point_size.setDecimals(1)
        self.sp_point_size.setSuffix(" mm")
        form.addRow(tr("Rozmiar punktów:"), self.sp_point_size)

        self.sp_insert_size = QDoubleSpinBox()
        self.sp_insert_size.setRange(0.1, 10.0)
        self.sp_insert_size.setSingleStep(0.1)
        self.sp_insert_size.setDecimals(1)
        self.sp_insert_size.setSuffix(" mm")
        form.addRow(tr("Rozmiar wstawień i kotwic:"), self.sp_insert_size)

        self.ed_group = QLineEdit()
        self.ed_group.setPlaceholderText(tr("puste = cały projekt"))
        self.ed_group.setToolTip(
            tr("Wpisz fragment nazwy grupy, żeby ograniczyć działanie tylko do niej.")
        )
        form.addRow(tr("Tylko grupa zawierająca:"), self.ed_group)

        root.addLayout(form)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Close,
            Qt.Orientation.Horizontal,
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText(tr("Zastosuj"))
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Zamknij"))
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._apply
        )
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._restore()

    def _options(self):
        opts = styler.StyleOptions()
        opts.line_width_mm = self.sp_line_width.value()
        opts.point_size_mm = self.sp_point_size.value()
        opts.insert_size_mm = self.sp_insert_size.value()
        opts.show_points = self.cb_show_points.isChecked()
        opts.polyline_width_mode = self.cmb_pline_width.currentData() or "mm"
        return opts

    def _apply(self):
        self._save()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = restyle.restyle_project(
                self._options(), only_group=self.ed_group.text().strip() or None
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        msg = tr("Ostylowano warstw: {0}, pominięto: {1}").format(
            result.styled, result.skipped
        )
        if result.details:
            msg += "\n" + "\n".join(result.details[:8])
        self.status.setText(msg)
        if self.iface is not None:
            try:
                view = self.iface.layerTreeView()
                for layer_id in result.layer_ids:
                    view.refreshLayerSymbology(layer_id)
            except Exception:
                warn_exception(tr("Nie udało się odświeżyć legendy"))
            try:
                self.iface.mapCanvas().refreshAllLayers()
            except Exception:
                warn_exception(tr("Nie udało się odświeżyć warstw na mapie"))

    def _save(self):
        s = QgsSettings()
        s.setValue(SETTINGS_PREFIX + "lineWidth", self.sp_line_width.value())
        s.setValue(SETTINGS_PREFIX + "pointSize", self.sp_point_size.value())
        s.setValue(SETTINGS_PREFIX + "insertSize", self.sp_insert_size.value())
        s.setValue(SETTINGS_PREFIX + "showPoints", self.cb_show_points.isChecked())
        s.setValue(SETTINGS_PREFIX + "plineWidthMode",
                   self.cmb_pline_width.currentData())

    def _restore(self):
        s = QgsSettings()

        def number(key, default):
            try:
                return float(s.value(SETTINGS_PREFIX + key, default))
            except (TypeError, ValueError):
                return default

        self.sp_line_width.setValue(number("lineWidth", 0.10))
        self.sp_point_size.setValue(number("pointSize", 0.8))
        self.sp_insert_size.setValue(number("insertSize", 1.2))
        mode = str(s.value(SETTINGS_PREFIX + "plineWidthMode", "mm"))
        index = self.cmb_pline_width.findData(mode)
        self.cmb_pline_width.setCurrentIndex(index if index >= 0 else 0)
        value = s.value(SETTINGS_PREFIX + "showPoints", False)
        if isinstance(value, str):
            value = value.lower() in ("1", "true", "yes")
        self.cb_show_points.setChecked(bool(value))
