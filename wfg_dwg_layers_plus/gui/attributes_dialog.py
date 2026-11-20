# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Okno „Wczytaj atrybuty bloków" — odzyskanie danych, których libdxfrw gubi."""

import os

from qgis.core import QgsFeedback, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core import block_attributes as BA
from ..i18n import tr

SETTINGS_PREFIX = "wfg_dwg_layers_plus/attr/"


class AttributesDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(AttributesDialog, self).__init__(parent or iface.mainWindow())
        self.iface = iface
        self.scan_result = None
        self.feedback = QgsFeedback()

        self.setWindowTitle(tr("WFG DWG Layers+ — atrybuty bloków"))
        self.setMinimumWidth(720)
        self.setMinimumHeight(560)
        self._build_ui()
        self._prefill()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(
            tr("Biblioteka, której QGIS używa do czytania DWG/DXF, <b>nie obsługuje "
            "atrybutów bloków</b> — wartości rzędnych, numerów, opisów wpisanych "
            "jako ATTRIB nie ma w GeoPackage w ogóle. Ten moduł czyta je "
            "bezpośrednio z rysunku sterownikiem DXF w GDAL i skleja z importem "
            "po uchwycie encji (<i>handle</i>).")
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        box = QGroupBox(tr("Pliki"))
        form = QFormLayout(box)

        row = QHBoxLayout()
        self.ed_dxf = QLineEdit()
        self.ed_dxf.setPlaceholderText(tr("rysunek .dxf (albo .dwg — wymaga konwertera)"))
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(self._pick_dxf)
        row.addWidget(self.ed_dxf)
        row.addWidget(btn)
        form.addRow(tr("Rysunek źródłowy:"), row)

        row2 = QHBoxLayout()
        self.ed_gpkg = QLineEdit()
        self.ed_gpkg.setPlaceholderText(tr("GeoPackage z importu"))
        btn2 = QPushButton("…")
        btn2.setFixedWidth(32)
        btn2.clicked.connect(self._pick_gpkg)
        row2.addWidget(self.ed_gpkg)
        row2.addWidget(btn2)
        form.addRow("GeoPackage:", row2)

        self.cmb_encoding = QComboBox()
        for label, value in (
            (tr("cp1250 — polska strona kodowa (domyślnie)"), "cp1250"),
            ("utf-8", "utf-8"),
            (tr("cp1252 — zachodnioeuropejska"), "cp1252"),
            ("latin-1", "latin-1"),
        ):
            self.cmb_encoding.addItem(label, value)
        self.cmb_encoding.setToolTip(
            tr("DXF deklarujący wersję R2018 powinien być w UTF-8, ale wiele "
            "CAD-ów zapisuje bajty w stronie kodowej systemu i nie poprawia "
            "nagłówka. Wtedy GDAL oddaje surowe bajty, a znaczniki atrybutów "
            "robią się nieczytelne. Ustawienie ma znaczenie tylko dla takich "
            "plików — poprawny UTF-8 przechodzi nietknięty.")
        )
        form.addRow(tr("Kodowanie tekstu:"), self.cmb_encoding)

        root.addWidget(box)

        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton(tr("Skanuj rysunek"))
        self.btn_scan.clicked.connect(self._scan)
        scan_row.addWidget(self.btn_scan)
        scan_row.addStretch(1)
        root.addLayout(scan_row)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("Blok"), tr("Wstawień"), tr("Znaczniki")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        opts = QGroupBox(tr("Co zrobić z wynikiem"))
        olay = QVBoxLayout(opts)

        self.cb_only_selected = QCheckBox(
            tr("Tylko zaznaczone bloki (puste zaznaczenie = wszystkie)")
        )
        olay.addWidget(self.cb_only_selected)

        self.cb_join = QCheckBox(
            tr("Podepnij złączenia do warstw wstawień i kotwic w projekcie")
        )
        self.cb_join.setChecked(True)
        self.cb_join.setToolTip(
            tr("Nieniszczące: atrybuty pojawią się jako dodatkowe pola warstw "
            "*_insert i blk__anchor. Złączenie można zdjąć we właściwościach "
            "warstwy albo przyciskiem poniżej.")
        )
        olay.addWidget(self.cb_join)

        self.cb_add_layer = QCheckBox(tr("Dodaj tabelę atrybutów do projektu"))
        self.cb_add_layer.setChecked(True)
        olay.addWidget(self.cb_add_layer)

        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel(tr("Maksimum kolumn:")))
        self.sp_columns = QSpinBox()
        self.sp_columns.setRange(1, 500)
        self.sp_columns.setValue(BA.MAX_COLUMNS)
        self.sp_columns.setToolTip(
            tr("Powyżej limitu rzadsze znaczniki są pomijane — ostrzeżenie trafia "
            "do dziennika.")
        )
        limit_row.addWidget(self.sp_columns)
        limit_row.addStretch(1)
        self.btn_detach = QPushButton(tr("Zdejmij złączenia"))
        self.btn_detach.clicked.connect(self._detach)
        limit_row.addWidget(self.btn_detach)
        olay.addLayout(limit_row)

        root.addWidget(opts)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Close,
            Qt.Orientation.Horizontal,
        )
        self.btn_apply = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_apply.setText(tr("Zastosuj"))
        self.btn_apply.setEnabled(False)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setText(tr("Zamknij"))
        self.buttons.accepted.connect(self._apply)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    # -- dane ---------------------------------------------------------------

    def _prefill(self):
        settings = QgsSettings()
        gpkg = str(settings.value(SETTINGS_PREFIX + "gpkg", "") or "")
        if not gpkg or not os.path.exists(gpkg):
            gpkg = BA.gpkg_from_project()
        self.ed_gpkg.setText(gpkg)

        dxf = str(settings.value(SETTINGS_PREFIX + "dxf", "") or "")
        if (not dxf or not os.path.exists(dxf)) and gpkg:
            dxf = BA.guess_dxf_for(gpkg)
        self.ed_dxf.setText(dxf)

        enc = str(settings.value(SETTINGS_PREFIX + "encoding", BA.DEFAULT_ENCODING))
        idx = self.cmb_encoding.findData(enc)
        self.cmb_encoding.setCurrentIndex(idx if idx >= 0 else 0)

    def _pick_dxf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz rysunek"), self.ed_dxf.text(),
            tr("Rysunki CAD (*.dxf *.DXF *.dwg *.DWG);;Wszystkie pliki (*)"),
        )
        if path:
            self.ed_dxf.setText(path)

    def _pick_gpkg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz GeoPackage"), self.ed_gpkg.text(), "GeoPackage (*.gpkg)"
        )
        if path:
            self.ed_gpkg.setText(path)

    def _scan(self):
        dxf = self.ed_dxf.text().strip()
        if not dxf or not os.path.exists(dxf):
            QMessageBox.warning(self, "WFG DWG Layers+", tr("Wskaż istniejący rysunek."))
            return

        self.feedback = QgsFeedback()
        self.progress.setVisible(True)
        # _progress woła processEvents(), więc bez blokady użytkownik mógłby
        # wystartować drugi skan w środku pierwszego
        self.btn_scan.setEnabled(False)
        self.btn_apply.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.scan_result = BA.scan(
                dxf, self.feedback, self._progress,
                encoding=self.cmb_encoding.currentData() or BA.DEFAULT_ENCODING,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            self.scan_result = None
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.progress.setVisible(False)
            self.progress.setRange(0, 100)
            self.btn_scan.setEnabled(True)

        rows = self.scan_result.block_rows()
        self.table.setRowCount(len(rows))
        for r, (name, count, tags) in enumerate(rows):
            item = QTableWidgetItem(name or tr("(bez nazwy)"))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.table.setItem(r, 0, item)
            cell = QTableWidgetItem(str(count))
            cell.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(r, 1, cell)
            self.table.setItem(r, 2, QTableWidgetItem(", ".join(tags)))

        tags = self.scan_result.tags()
        komunikat = (
            tr("Znaleziono {0} wstawień z atrybutami, {1} bloków, {2} różnych "
            "znaczników.").format(self.scan_result.total, len(rows), len(tags))
        )
        if self.scan_result.recoded:
            komunikat += (
                tr("  Rysunek nie jest w UTF-8 — teksty przekodowano jako {0}. "
                "Jeśli polskie znaki w znacznikach wyglądają źle, zmień "
                "kodowanie i zeskanuj ponownie.").format(self.scan_result.encoding)
            )
        self.status.setText(komunikat)
        self.btn_apply.setEnabled(self.scan_result.total > 0)

    def _selected_blocks(self):
        if not self.cb_only_selected.isChecked():
            return None
        names = set()
        for item in self.table.selectedItems():
            if item.column() == 0:
                names.add(item.data(Qt.ItemDataRole.UserRole))
        return names or None

    def _apply(self):
        if self.scan_result is None:
            QMessageBox.warning(self, "WFG DWG Layers+", tr("Najpierw zeskanuj rysunek."))
            return
        gpkg = self.ed_gpkg.text().strip()
        if not gpkg or not os.path.exists(gpkg):
            QMessageBox.warning(self, "WFG DWG Layers+", tr("Wskaż istniejący GeoPackage."))
            return

        wanted = self._selected_blocks()
        scan_result = self.scan_result
        if wanted:
            filtered = BA.AttributeScan()
            filtered.dxf_path = scan_result.dxf_path
            for handle, row in scan_result.rows.items():
                if row["block"] in wanted:
                    filtered.rows[handle] = row
                    info = filtered.blocks.setdefault(
                        row["block"], {"count": 0, "tags": {}}
                    )
                    info["count"] += 1
                    for tag in row["att"]:
                        info["tags"][tag] = info["tags"].get(tag, 0) + 1
            scan_result = filtered

        columns, dropped = BA.choose_columns(scan_result, self.sp_columns.value())

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # najpierw sprzątamy po poprzednim przebiegu, inaczej powtórne
            # „Zastosuj" zostawiłoby stare złączenie z podręczną kopią danych
            BA.reset()
            written = BA.write_table(gpkg, scan_result, columns, self.feedback)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        if written == 0 and scan_result.total:
            self.status.setText(
                tr("Przerwano — nic nie zapisano, poprzedni stan wycofany.")
            )
            QMessageBox.information(
                self, "WFG DWG Layers+",
                tr("Zapis przerwany. Tabela atrybutów nie została utworzona, "
                "GeoPackage został wycofany do poprzedniego stanu."),
            )
            return

        messages = [
            tr("Zapisano {0} wierszy do tabeli {1}, kolumn atrybutów: {2}.").format(
                written, BA.TABLE, len(columns)
            )
        ]
        if dropped:
            messages.append(
                tr("Pominięto {0} rzadszych znaczników (limit kolumn): {1}").format(
                    len(dropped), ", ".join(dropped[:8])
                )
            )

        table_layer = None
        if self.cb_join.isChecked() or self.cb_add_layer.isChecked():
            table_layer = BA.load_table_layer(gpkg)

        if self.cb_join.isChecked():
            join = BA.attach_joins(gpkg, table_layer=table_layer)
            messages.append(
                tr("Podpięto złączenia do {0} warstw.").format(len(join.joined))
            )
            messages.extend(join.errors[:5])
            table_layer = join.table_layer or table_layer

        if self.cb_add_layer.isChecked() and table_layer is not None:
            from qgis.core import QgsProject

            project = QgsProject.instance()
            if not project.mapLayer(table_layer.id()):
                project.addMapLayer(table_layer, True)
            elif project.layerTreeRoot().findLayer(table_layer.id()) is None:
                project.layerTreeRoot().addLayer(table_layer)

        settings = QgsSettings()
        settings.setValue(SETTINGS_PREFIX + "dxf", self.ed_dxf.text().strip())
        settings.setValue(SETTINGS_PREFIX + "gpkg", gpkg)
        settings.setValue(
            SETTINGS_PREFIX + "encoding", self.cmb_encoding.currentData()
        )

        self.status.setText("\n".join(messages))
        QMessageBox.information(self, "WFG DWG Layers+", "\n".join(messages))

    def _detach(self):
        removed = BA.detach_joins()
        self.status.setText(
            tr("Zdjęto złączeń: {0} (tabela atrybutów usunięta z projektu; "
            "dane w GeoPackage zostają).").format(removed)
        )

    def _progress(self, pct, message=""):
        if pct is None or pct < 0:
            # tryb nieokreślony — nie znamy z góry liczby encji w rysunku
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(pct))))
        if message:
            self.status.setText(str(message))
        QApplication.processEvents()
