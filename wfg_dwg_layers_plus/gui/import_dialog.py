# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Okno importu WFG DWG Layers+."""

import os

from qgis.core import QgsFeedback, QgsSettings
from qgis.gui import QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import gpkg_reader, gpkg_schema as S, producer_ogr, runner, styler

SETTINGS_PREFIX = "wfg_dwg_layers_plus/"


class ImportDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(ImportDialog, self).__init__(parent or iface.mainWindow())
        self.iface = iface
        self.inventory = None
        self.feedback = QgsFeedback()
        self.result_obj = None

        self.setWindowTitle("WFG DWG Layers+ — import")
        self.setMinimumWidth(760)
        self.setMinimumHeight(620)
        self._build_ui()
        self._restore_settings()
        self._update_enabled()

    # -- budowa UI ----------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(self._source_box())
        root.addWidget(self._layers_box(), 1)

        columns = QHBoxLayout()
        columns.addWidget(self._structure_box(), 1)
        columns.addWidget(self._blocks_box(), 1)
        root.addLayout(columns)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, Qt.Orientation.Horizontal
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Importuj")
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self._on_reject)
        root.addWidget(self.buttons)

    def _source_box(self):
        box = QGroupBox("Źródło")
        form = QFormLayout(box)

        row = QHBoxLayout()
        self.ed_source = QLineEdit()
        self.ed_source.setPlaceholderText(
            "plik .dwg / .dxf albo gotowy .gpkg z wbudowanego importu"
        )
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(self._pick_source)
        row.addWidget(self.ed_source)
        row.addWidget(btn)
        form.addRow("Rysunek / GeoPackage:", row)

        row2 = QHBoxLayout()
        self.ed_gpkg = QLineEdit()
        self.ed_gpkg.setPlaceholderText("domyślnie obok pliku źródłowego")
        btn2 = QPushButton("…")
        btn2.setFixedWidth(32)
        btn2.clicked.connect(self._pick_gpkg)
        row2.addWidget(self.ed_gpkg)
        row2.addWidget(btn2)
        form.addRow("Wyjściowy GeoPackage:", row2)

        self.crs_widget = QgsProjectionSelectionWidget()
        form.addRow("Układ współrzędnych:", self.crs_widget)

        self.cb_curves = QCheckBox("Zachowaj łuki (bez segmentyzacji)")
        self.cb_curves.setChecked(True)
        form.addRow("", self.cb_curves)

        self.cb_own_importer = QCheckBox(
            "Własny import przez GDAL (eksperymentalny; DXF bez zależności, "
            "DWG wymaga ODA File Converter lub LibreDWG)"
        )
        self.cb_own_importer.toggled.connect(self._update_enabled)
        form.addRow("", self.cb_own_importer)

        self.lbl_converter = QLabel("")
        self.lbl_converter.setWordWrap(True)
        form.addRow("", self.lbl_converter)

        return box

    def _layers_box(self):
        box = QGroupBox("Warstwy CAD")
        lay = QVBoxLayout(box)

        top = QHBoxLayout()
        self.btn_scan = QPushButton("Wczytaj listę warstw")
        self.btn_scan.clicked.connect(self._scan)
        top.addWidget(self.btn_scan)
        self.ed_filter = QLineEdit()
        self.ed_filter.setPlaceholderText("filtruj po nazwie…")
        self.ed_filter.textChanged.connect(self._apply_filter)
        top.addWidget(self.ed_filter, 1)
        for label, slot in (
            ("Wszystkie", lambda: self._set_all(True)),
            ("Żadna", lambda: self._set_all(False)),
            ("Tylko widoczne w CAD", self._select_visible),
        ):
            b = QPushButton(label)
            b.clicked.connect(slot)
            top.addWidget(b)
        lay.addLayout(top)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Warstwa CAD", "Poligony", "Linie", "Polilinie", "Punkty",
             "Teksty", "Wstawienia", "Razem"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.table)

        return box

    def _structure_box(self):
        box = QGroupBox("Struktura")
        lay = QVBoxLayout(box)

        self.rb_filter = QRadioButton("Filtry na wspólnej tabeli (szybko)")
        self.rb_materialize = QRadioButton("Osobne tabele w GeoPackage")
        self.rb_filter.setChecked(True)
        self.rb_materialize.toggled.connect(self._update_enabled)
        lay.addWidget(self.rb_filter)
        lay.addWidget(self.rb_materialize)

        self.cb_segmentize = QCheckBox("Przy materializacji zamień łuki na odcinki")
        lay.addWidget(self.cb_segmentize)

        self.cb_rebuild_names = QCheckBox(
            "Przebuduj nazwy tabel (zamiast nadpisać te z poprzedniego importu)"
        )
        self.cb_rebuild_names.setToolTip(
            "Domyślnie powtórzony import nadpisuje tabele utworzone poprzednio, "
            "więc plik nie puchnie. Zaznacz, jeśli zmieniłeś sufiksy i chcesz, "
            "żeby powstały tabele o nowych nazwach."
        )
        lay.addWidget(self.cb_rebuild_names)

        self.cb_numbered = QCheckBox("Numeruj grupy (stała kolejność w legendzie)")
        self.cb_numbered.setChecked(True)
        lay.addWidget(self.cb_numbered)

        self.cb_skip_empty = QCheckBox("Pomijaj puste warstwy")
        self.cb_skip_empty.setChecked(True)
        lay.addWidget(self.cb_skip_empty)

        self.cb_import_invisible = QCheckBox(
            "Wczytuj warstwy wyłączone/zamrożone w CAD (odznaczone w legendzie)"
        )
        self.cb_import_invisible.setChecked(True)
        lay.addWidget(self.cb_import_invisible)

        self.cb_color_by_layer = QCheckBox("Koloruj wg warstwy CAD, nie wg encji")
        lay.addWidget(self.cb_color_by_layer)

        look = QFormLayout()
        look.setContentsMargins(0, 6, 0, 0)

        self.sp_line_width = QDoubleSpinBox()
        self.sp_line_width.setRange(0.01, 5.0)
        self.sp_line_width.setSingleStep(0.05)
        self.sp_line_width.setDecimals(2)
        self.sp_line_width.setSuffix(" mm")
        self.sp_line_width.setValue(0.10)
        self.sp_line_width.setToolTip(
            "Grubość używana tam, gdzie encja CAD nie ma własnej (linewidth 0 "
            "albo -1 = BYBLOCK). Bez tego QGIS podstawia swoje domyślne 0,26 mm "
            "i linie wychodzą za grube."
        )
        look.addRow("Grubość zastępcza linii:", self.sp_line_width)

        self.cmb_pline_width = QComboBox()
        self.cmb_pline_width.addItem(
            "jako grubość pisaka w mm (zalecane)", "mm")
        self.cmb_pline_width.addItem(
            "jako szerokość w terenie, wiernie jak CAD", "map")
        self.cmb_pline_width.addItem("pomijaj", "ignore")
        self.cmb_pline_width.setToolTip(
            "Polilinie CAD mają globalną szerokość (kolumna width) w jednostkach "
            "rysunku. QGIS renderuje ją wiernie — polilinia o width 0,5 wychodzi "
            "na pół metra szeroka, jak czarna belka. Projektanci zwykle wpisują "
            "tam grubości piór ISO (0,05 / 0,1 / 0,3 / 0,5), więc domyślnie "
            "traktujemy tę liczbę jako milimetry."
        )
        look.addRow("Szerokość polilinii:", self.cmb_pline_width)

        self.cb_show_points = QCheckBox("Pokazuj warstwy punktów CAD")
        self.cb_show_points.setToolTip(
            "Domyślnie punkty CAD są niewidoczne — tak samo jak we wbudowanym "
            "imporcie QGIS."
        )
        look.addRow("", self.cb_show_points)

        self.sp_point_size = QDoubleSpinBox()
        self.sp_point_size.setRange(0.1, 10.0)
        self.sp_point_size.setSingleStep(0.1)
        self.sp_point_size.setDecimals(1)
        self.sp_point_size.setSuffix(" mm")
        self.sp_point_size.setValue(0.8)
        look.addRow("Rozmiar punktów:", self.sp_point_size)

        self.sp_insert_size = QDoubleSpinBox()
        self.sp_insert_size.setRange(0.1, 10.0)
        self.sp_insert_size.setSingleStep(0.1)
        self.sp_insert_size.setDecimals(1)
        self.sp_insert_size.setSuffix(" mm")
        self.sp_insert_size.setValue(1.2)
        look.addRow("Rozmiar wstawień i kotwic:", self.sp_insert_size)

        lay.addLayout(look)

        self.advanced = _AdvancedNames()
        lay.addWidget(self.advanced)

        lay.addStretch(1)
        return box

    def _blocks_box(self):
        box = QGroupBox("Bloki")
        lay = QVBoxLayout(box)

        self.rb_exploded = QRadioButton("Rozbite na geometrie (jak dotąd)")
        self.rb_inserts = QRadioButton("Punkty wstawień z atrybutami")
        self.rb_composite = QRadioButton(
            "Złożone geometrie — jeden obiekt na wstawienie"
        )
        self.rb_exploded.setChecked(True)
        for rb in (self.rb_exploded, self.rb_inserts, self.rb_composite):
            rb.toggled.connect(self._update_enabled)
            lay.addWidget(rb)

        self.composite_panel = QWidget()
        form = QFormLayout(self.composite_panel)
        form.setContentsMargins(18, 4, 0, 0)

        self.cb_anchors = QCheckBox("Utwórz warstwę kotwic (punkt na wstawienie)")
        self.cb_anchors.setChecked(True)
        form.addRow("", self.cb_anchors)

        self.cb_store = QCheckBox("Zapisz warstwy bloków w GeoPackage")
        self.cb_store.setChecked(True)
        form.addRow("", self.cb_store)

        self.cb_minsert = QCheckBox("Rozwijaj tablice MINSERT")
        self.cb_minsert.setChecked(True)
        form.addRow("", self.cb_minsert)

        self.cb_layer0 = QCheckBox("Dziedzicz warstwę 0 z wstawienia")
        self.cb_layer0.setChecked(True)
        form.addRow("", self.cb_layer0)

        self.cb_qgis_order = QCheckBox(
            "Kolejność transformacji jak w QGIS (obrót przed skalą)"
        )
        form.addRow("", self.cb_qgis_order)

        self.sp_depth = QSpinBox()
        self.sp_depth.setRange(1, 64)
        self.sp_depth.setValue(16)
        form.addRow("Limit zagnieżdżenia:", self.sp_depth)

        self.sp_entities = QSpinBox()
        self.sp_entities.setRange(1000, 10000000)
        self.sp_entities.setSingleStep(1000)
        self.sp_entities.setValue(50000)
        form.addRow("Limit encji na wstawienie:", self.sp_entities)

        lay.addWidget(self.composite_panel)

        note = QLabel(
            "Tryb złożonych geometrii wymaga importu <b>bez rozwijania bloków</b>. "
            "Wtyczka ustawia to za Ciebie w oknie wbudowanego importu."
        )
        note.setWordWrap(True)
        lay.addWidget(note)

        lay.addStretch(1)
        return box

    # -- reakcje ------------------------------------------------------------

    def _pick_source(self):
        start = self.ed_source.text() or QgsSettings().value(
            SETTINGS_PREFIX + "lastDir", ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz rysunek lub GeoPackage", start,
            "CAD i GeoPackage (*.dwg *.DWG *.dxf *.DXF *.gpkg);;Wszystkie pliki (*)",
        )
        if not path:
            return
        self.ed_source.setText(path)
        if not self.ed_gpkg.text():
            self.ed_gpkg.setText(runner.default_gpkg_for(path))
        QgsSettings().setValue(SETTINGS_PREFIX + "lastDir", os.path.dirname(path))
        self._update_enabled()
        if path.lower().endswith(".gpkg"):
            self._scan()

    def _pick_gpkg(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Wyjściowy GeoPackage", self.ed_gpkg.text(), "GeoPackage (*.gpkg)"
        )
        if path:
            if not path.lower().endswith(".gpkg"):
                path += ".gpkg"
            self.ed_gpkg.setText(path)

    def _update_enabled(self):
        composite = self.rb_composite.isChecked()
        self.composite_panel.setEnabled(composite)
        self.cb_segmentize.setEnabled(self.rb_materialize.isChecked())
        self.cb_rebuild_names.setEnabled(self.rb_materialize.isChecked())

        own = self.cb_own_importer.isChecked()
        if own:
            if producer_ogr.dwg_converter_available():
                which = producer_ogr.find_oda_converter() or producer_ogr.find_libredwg()
                self.lbl_converter.setText(
                    "Konwerter DWG wykryty: {0}".format(which)
                )
            else:
                self.lbl_converter.setText(
                    "Nie wykryto konwertera DWG → DXF. Pliki DXF zaimportują się "
                    "bez niego; dla DWG użyj wbudowanego importu."
                )
            if composite:
                self.rb_exploded.setChecked(True)
        else:
            self.lbl_converter.setText("")
        self.rb_composite.setEnabled(not own)

    def _scan(self):
        source = self.ed_source.text().strip()
        if not source:
            self._warn("Wskaż plik źródłowy.")
            return
        if not source.lower().endswith(".gpkg"):
            self._warn(
                "Listę warstw można wczytać dopiero z GeoPackage. Uruchom import "
                "— po jego zakończeniu warstwy pojawią się automatycznie — albo "
                "wskaż gotowy plik .gpkg."
            )
            return
        try:
            inv = gpkg_reader.inventory(source)
        except gpkg_reader.GpkgReadError as exc:
            self._warn(str(exc))
            return
        self._populate(inv)

    def _populate(self, inv):
        self.inventory = inv
        rows = inv.non_empty() if self.cb_skip_empty.isChecked() else inv.layers
        self.table.setRowCount(len(rows))
        order = [S.T_HATCHES, S.T_LINES, S.T_POLYLINES, S.T_POINTS,
                 S.T_TEXTS, S.T_INSERTS]
        for r, info in enumerate(rows):
            item = QTableWidgetItem(info.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # domyslnie zaznaczamy wszystko; od zawezenia do warstw widocznych
            # w CAD jest osobny przycisk
            item.setCheckState(Qt.CheckState.Checked)
            color = info.qcolor()
            if color is not None:
                item.setForeground(QBrush(QColor(color)))
            item.setData(Qt.ItemDataRole.UserRole, info.name)
            self.table.setItem(r, 0, item)
            for c, table in enumerate(order, start=1):
                n = info.count(table)
                cell = QTableWidgetItem(str(n) if n else "")
                cell.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, cell)
            total = QTableWidgetItem(str(info.total))
            total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(r, 7, total)
        self.status.setText(
            "Warstw CAD: {0}, bloków: {1}, wstawień: {2}{3}".format(
                len(rows), len(inv.block_names), inv.insert_count,
                "  (import wygląda na wykonany z rozwijaniem bloków)"
                if inv.expanded else "",
            )
        )

    def _apply_filter(self, text):
        needle = (text or "").strip().lower()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            hidden = bool(needle) and needle not in item.text().lower()
            self.table.setRowHidden(r, hidden)

    def _set_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            self.table.item(r, 0).setCheckState(state)

    def _select_visible(self):
        if self.inventory is None:
            return
        for r in range(self.table.rowCount()):
            name = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
            info = self.inventory.by_name(name)
            self.table.item(r, 0).setCheckState(
                Qt.CheckState.Checked if (info and info.visible) else Qt.CheckState.Unchecked
            )

    def selected_layers(self):
        out = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out

    # -- uruchomienie -------------------------------------------------------

    def build_config(self):
        cfg = runner.RunConfig()
        cfg.source_path = self.ed_source.text().strip()
        cfg.gpkg_path = self.ed_gpkg.text().strip() or None
        cfg.use_curves = self.cb_curves.isChecked()
        cfg.use_own_importer = self.cb_own_importer.isChecked()
        cfg.segmentize_on_materialize = self.cb_segmentize.isChecked()
        cfg.reuse_table_names = not self.cb_rebuild_names.isChecked()
        crs = self.crs_widget.crs()
        cfg.crs_authid = crs.authid() if crs is not None and crs.isValid() else None
        cfg.cad_layers = self.selected_layers()

        t = cfg.tree
        t.layer_mode = (
            S.LayerMode.MATERIALIZE if self.rb_materialize.isChecked()
            else S.LayerMode.FILTER
        )
        if self.rb_composite.isChecked():
            t.block_mode = S.BlockMode.COMPOSITE
        elif self.rb_inserts.isChecked():
            t.block_mode = S.BlockMode.INSERT_POINTS
        else:
            t.block_mode = S.BlockMode.EXPLODED
        t.numbered_groups = self.cb_numbered.isChecked()
        t.skip_empty = self.cb_skip_empty.isChecked()
        t.import_invisible = self.cb_import_invisible.isChecked()
        t.color_by_cad_layer = self.cb_color_by_layer.isChecked()

        st = styler.StyleOptions()
        st.line_width_mm = self.sp_line_width.value()
        st.point_size_mm = self.sp_point_size.value()
        st.insert_size_mm = self.sp_insert_size.value()
        st.show_points = self.cb_show_points.isChecked()
        st.polyline_width_mode = self.cmb_pline_width.currentData() or "mm"
        t.style = st
        self.advanced.apply_to(t)

        b = cfg.block
        b.create_anchors = self.cb_anchors.isChecked()
        b.store_in_gpkg = self.cb_store.isChecked()
        b.expand_minsert = self.cb_minsert.isChecked()
        b.inherit_layer_zero = self.cb_layer0.isChecked()
        b.qgis_transform_order = self.cb_qgis_order.isChecked()
        b.max_depth = self.sp_depth.value()
        b.max_entities = self.sp_entities.value()
        b.keep_curves = self.cb_curves.isChecked()
        return cfg

    def _on_accept(self):
        source = self.ed_source.text().strip()
        if not source or not os.path.exists(source):
            self._warn("Wskaż istniejący plik źródłowy.")
            return
        if self.table.rowCount() and not self.selected_layers():
            self._warn(
                "Nie zaznaczono żadnej warstwy CAD. Zaznacz przynajmniej jedną "
                "albo użyj przycisku „Wszystkie”."
            )
            return

        cfg = self.build_config()
        self._save_settings()

        self.feedback = QgsFeedback()
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.buttons.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            self.result_obj = runner.run(
                cfg, self.iface, self.feedback, self._progress
            )
        except Exception as exc:  # noqa: BLE001
            # kursor zdejmuje blok finally — podwojne restoreOverrideCursor()
            # zdjeloby kursor ustawiony przez sam QGIS
            self.progress.setVisible(False)
            self.buttons.setEnabled(True)
            runner.log("Blad importu: {0}".format(exc))
            self._warn(str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        self.progress.setVisible(False)
        self.buttons.setEnabled(True)

        # po udanym imporcie odswiez liste warstw, zeby dalo sie powtorzyc
        if self.result_obj.inventory is not None:
            self._populate(self.result_obj.inventory)
            self.ed_source.setText(self.result_obj.gpkg_path)

        msg = "Zaimportowano: {0}".format(self.result_obj.summary())
        extra = self.result_obj.messages
        if self.result_obj.blocks is not None:
            extra = extra + sorted(set(self.result_obj.blocks.warnings))[:5]
        if extra:
            msg += "\n\n" + "\n".join(extra)
        QMessageBox.information(self, "WFG DWG Layers+", msg)
        self.accept()

    def _on_reject(self):
        self.feedback.cancel()
        self.reject()

    def _progress(self, pct, message=""):
        self.progress.setValue(max(0, min(100, int(pct))))
        if message:
            self.status.setText(str(message))
        QApplication.processEvents()

    def _warn(self, text):
        QMessageBox.warning(self, "WFG DWG Layers+", text)

    # -- ustawienia ---------------------------------------------------------

    def _save_settings(self):
        s = QgsSettings()
        s.setValue(SETTINGS_PREFIX + "curves", self.cb_curves.isChecked())
        s.setValue(SETTINGS_PREFIX + "materialize", self.rb_materialize.isChecked())
        s.setValue(SETTINGS_PREFIX + "numbered", self.cb_numbered.isChecked())
        s.setValue(SETTINGS_PREFIX + "skipEmpty", self.cb_skip_empty.isChecked())
        s.setValue(SETTINGS_PREFIX + "importInvisible",
                   self.cb_import_invisible.isChecked())
        s.setValue(SETTINGS_PREFIX + "colorByLayer",
                   self.cb_color_by_layer.isChecked())
        s.setValue(SETTINGS_PREFIX + "blockMode", self._block_mode_index())
        s.setValue(SETTINGS_PREFIX + "ownImporter",
                   self.cb_own_importer.isChecked())
        s.setValue(SETTINGS_PREFIX + "lineWidth", self.sp_line_width.value())
        s.setValue(SETTINGS_PREFIX + "pointSize", self.sp_point_size.value())
        s.setValue(SETTINGS_PREFIX + "insertSize", self.sp_insert_size.value())
        s.setValue(SETTINGS_PREFIX + "showPoints", self.cb_show_points.isChecked())
        s.setValue(SETTINGS_PREFIX + "plineWidthMode",
                   self.cmb_pline_width.currentData())
        self.advanced.save(s, SETTINGS_PREFIX)

    def _block_mode_index(self):
        if self.rb_composite.isChecked():
            return 2
        if self.rb_inserts.isChecked():
            return 1
        return 0

    def _restore_settings(self):
        s = QgsSettings()

        def flag(key, default=False):
            v = s.value(SETTINGS_PREFIX + key, default)
            if isinstance(v, str):
                return v.lower() in ("1", "true", "yes")
            return bool(v)

        self.cb_curves.setChecked(flag("curves", True))
        if flag("materialize"):
            self.rb_materialize.setChecked(True)
        self.cb_numbered.setChecked(flag("numbered", True))
        self.cb_skip_empty.setChecked(flag("skipEmpty", True))
        self.cb_import_invisible.setChecked(flag("importInvisible", True))
        self.cb_color_by_layer.setChecked(flag("colorByLayer", False))
        self.cb_own_importer.setChecked(flag("ownImporter", False))
        self.cb_show_points.setChecked(flag("showPoints", False))

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
        try:
            idx = int(s.value(SETTINGS_PREFIX + "blockMode", 0))
        except (TypeError, ValueError):
            idx = 0
        [self.rb_exploded, self.rb_inserts, self.rb_composite][
            max(0, min(2, idx))
        ].setChecked(True)
        self.advanced.restore(s, SETTINGS_PREFIX)


class _AdvancedNames(QGroupBox):
    """Nazwy grup i sufiksy — zwiniete, bo rzadko sie je zmienia."""

    def __init__(self, parent=None):
        super(_AdvancedNames, self).__init__("Nazwy grup i sufiksy", parent)
        self.setCheckable(True)
        self.setChecked(False)
        grid = QGridLayout(self)
        self.group_edits = {}
        self.suffix_edits = {}

        grid.addWidget(QLabel("<b>Grupy</b>"), 0, 0, 1, 2)
        labels = {S.KIND_TEXT: "teksty", S.KIND_POINT: "punkty",
                  S.KIND_LINE: "linie", S.KIND_POLYGON: "poligony"}
        for r, kind in enumerate(S.GROUP_ORDER, start=1):
            grid.addWidget(QLabel(labels.get(kind, kind)), r, 0)
            ed = QLineEdit(S.DEFAULT_GROUPS[kind])
            self.group_edits[kind] = ed
            grid.addWidget(ed, r, 1)
        r = len(S.GROUP_ORDER) + 1
        grid.addWidget(QLabel("bloki"), r, 0)
        self.ed_block_group = QLineEdit(S.DEFAULT_BLOCK_GROUP)
        grid.addWidget(self.ed_block_group, r, 1)

        grid.addWidget(QLabel("<b>Sufiksy</b>"), 0, 2, 1, 2)
        for i, table in enumerate(
            [S.T_HATCHES, S.T_LINES, S.T_POLYLINES, S.T_POINTS,
             S.T_TEXTS, S.T_INSERTS], start=1
        ):
            grid.addWidget(QLabel(table), i, 2)
            ed = QLineEdit(S.DEFAULT_SUFFIXES[table])
            self.suffix_edits[table] = ed
            grid.addWidget(ed, i, 3)

        btn = QPushButton("Przywróć domyślne")
        btn.clicked.connect(self.reset)
        grid.addWidget(btn, r + 1, 0, 1, 4)


    def reset(self):
        for kind, ed in self.group_edits.items():
            ed.setText(S.DEFAULT_GROUPS[kind])
        for table, ed in self.suffix_edits.items():
            ed.setText(S.DEFAULT_SUFFIXES[table])
        self.ed_block_group.setText(S.DEFAULT_BLOCK_GROUP)

    def apply_to(self, tree_options):
        if not self.isChecked():
            return
        for kind, ed in self.group_edits.items():
            text = ed.text().strip()
            if text:
                tree_options.group_names[kind] = text
        for table, ed in self.suffix_edits.items():
            tree_options.suffixes[table] = ed.text()
        text = self.ed_block_group.text().strip()
        if text:
            tree_options.block_group_name = text

    def save(self, settings, prefix):
        settings.setValue(prefix + "advanced", self.isChecked())
        for kind, ed in self.group_edits.items():
            settings.setValue(prefix + "group/" + kind, ed.text())
        for table, ed in self.suffix_edits.items():
            settings.setValue(prefix + "suffix/" + table, ed.text())
        settings.setValue(prefix + "group/blocks", self.ed_block_group.text())

    def restore(self, settings, prefix):
        v = settings.value(prefix + "advanced", False)
        self.setChecked(str(v).lower() in ("1", "true", "yes"))
        for kind, ed in self.group_edits.items():
            ed.setText(str(settings.value(
                prefix + "group/" + kind, S.DEFAULT_GROUPS[kind])))
        for table, ed in self.suffix_edits.items():
            ed.setText(str(settings.value(
                prefix + "suffix/" + table, S.DEFAULT_SUFFIXES[table])))
        self.ed_block_group.setText(str(settings.value(
            prefix + "group/blocks", S.DEFAULT_BLOCK_GROUP)))
