# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Okno „Napraw kodowanie" — usuwa podwójne kodowanie polskich znaków."""

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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core import encoding_fix as EF
from ..i18n import tr

SETTINGS_PREFIX = "wfg_dwg_layers_plus/enc/"


class EncodingDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(EncodingDialog, self).__init__(parent or iface.mainWindow())
        self.iface = iface
        self.scan_gpkg = None
        self.scan_proj = []
        self.feedback = QgsFeedback()

        self.setWindowTitle(tr("WFG DWG Layers+ — napraw kodowanie"))
        self.setMinimumWidth(820)
        self.setMinimumHeight(600)
        self._build_ui()
        self._prefill()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(
            tr("DXF w wersji R2007 i nowszej ma treść w UTF-8, ale wiele CAD-ów "
            "zostawia w nagłówku starą stronę kodową. Biblioteka czytająca "
            "stosuje ją posłusznie i <b>ę</b> zamienia się w <b>Ä™</b>, a "
            "<b>ś</b> w <b>Ĺ›</b>. To jest odwracalne bez straty — trzeba tylko "
            "zrobić konwersję w drugą stronę.")
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        box = QGroupBox(tr("Plik i kodowanie"))
        form = QFormLayout(box)

        row = QHBoxLayout()
        self.ed_gpkg = QLineEdit()
        self.ed_gpkg.setPlaceholderText(tr("GeoPackage z importu"))
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(self._pick_gpkg)
        row.addWidget(self.ed_gpkg)
        row.addWidget(btn)
        form.addRow("GeoPackage:", row)

        self.cmb_encoding = QComboBox()
        for label, value in (
            (tr("cp1250 — polska strona kodowa (domyślnie)"), "cp1250"),
            (tr("cp1252 — zachodnioeuropejska"), "cp1252"),
            ("latin-1", "latin-1"),
            (tr("cp1251 — cyrylica"), "cp1251"),
        ):
            self.cmb_encoding.addItem(label, value)
        self.cmb_encoding.setToolTip(
            tr("Strona kodowa, przez którą tekst został błędnie przepuszczony. "
            "Dla rysunków z polskich CAD-ów to prawie zawsze cp1250.")
        )
        form.addRow(tr("Błędna strona kodowa:"), self.cmb_encoding)

        root.addWidget(box)

        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton(tr("Skanuj (podgląd zmian)"))
        self.btn_scan.clicked.connect(self._scan)
        scan_row.addWidget(self.btn_scan)
        scan_row.addStretch(1)
        root.addLayout(scan_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [tr("Gdzie"), tr("Ile"), tr("Przed"), tr("Po")]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        opts = QGroupBox(tr("Co poprawić"))
        olay = QVBoxLayout(opts)

        self.cb_data = QCheckBox(tr("Dane w GeoPackage (nazwy warstw CAD, bloków, treść tekstów)"))
        self.cb_data.setChecked(True)
        olay.addWidget(self.cb_data)

        self.cb_backup = QCheckBox(tr("Zrób kopię zapasową GeoPackage przed zapisem"))
        self.cb_backup.setChecked(True)
        olay.addWidget(self.cb_backup)

        self.cb_project = QCheckBox(
            tr("Nazwy warstw i grup w projekcie oraz filtry warstw")
        )
        self.cb_project.setChecked(True)
        self.cb_project.setToolTip(
            tr("Filtry odwołują się do wartości kolumny 'layer', więc poprawia się "
            "je razem z danymi. Osobno nie miałoby to sensu — poprawiony filtr "
            "na nienaprawionych danych nie pasowałby do niczego.")
        )
        olay.addWidget(self.cb_project)

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
        self.btn_apply.setText(tr("Napraw"))
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
            paths = EF.gpkg_paths_in_project()
            gpkg = paths[0] if paths else ""
        self.ed_gpkg.setText(gpkg)

        enc = str(settings.value(SETTINGS_PREFIX + "encoding", EF.DEFAULT_ENCODING))
        idx = self.cmb_encoding.findData(enc)
        self.cmb_encoding.setCurrentIndex(idx if idx >= 0 else 0)

    def _pick_gpkg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz GeoPackage"), self.ed_gpkg.text(), "GeoPackage (*.gpkg)"
        )
        if path:
            self.ed_gpkg.setText(path)

    def _encoding(self):
        return self.cmb_encoding.currentData() or EF.DEFAULT_ENCODING

    def _scan(self):
        gpkg = self.ed_gpkg.text().strip()
        enc = self._encoding()

        self.feedback = QgsFeedback()
        self.btn_scan.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.scan_gpkg = None
            if gpkg and os.path.exists(gpkg):
                self.scan_gpkg = EF.scan_gpkg(gpkg, enc, feedback=self.feedback)
            self.scan_proj = EF.scan_project(encoding=enc)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.progress.setVisible(False)
            self.progress.setRange(0, 100)
            self.btn_scan.setEnabled(True)

        self._populate()

    def _populate(self):
        wiersze = []
        if self.scan_gpkg is not None:
            for table, column, count, samples in self.scan_gpkg.rows():
                before, after = (samples[0] if samples else ("", ""))
                wiersze.append(
                    ("{0}.{1}".format(table, column), str(count), before, after)
                )
        rodzaje = {}
        for rodzaj, before, after in self.scan_proj:
            rodzaje.setdefault(rodzaj, []).append((before, after))
        for rodzaj, pary in sorted(rodzaje.items()):
            before, after = pary[0]
            wiersze.append(
                (tr("projekt: {0}").format(rodzaj), str(len(pary)), before, after)
            )

        self.table.setRowCount(len(wiersze))
        for r, kolumny in enumerate(wiersze):
            for c, tekst in enumerate(kolumny):
                item = QTableWidgetItem(tekst)
                if c == 1:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(r, c, item)

        w_gpkg = self.scan_gpkg.total if self.scan_gpkg else 0
        w_proj = len(self.scan_proj)
        self.status.setText(
            tr("Do poprawy: {0} wartości w GeoPackage, {1} pozycji w projekcie.")
            .format(w_gpkg, w_proj)
            if (w_gpkg or w_proj)
            else tr("Nic nie wymaga naprawy — teksty wyglądają poprawnie.")
        )
        self.btn_apply.setEnabled(bool(w_gpkg or w_proj))

    def _apply(self):
        enc = self._encoding()
        gpkg = self.ed_gpkg.text().strip()
        komunikaty = []

        if self.cb_data.isChecked():
            if not gpkg or not os.path.exists(gpkg):
                QMessageBox.warning(
                    self, "WFG DWG Layers+", tr("Wskaż istniejący GeoPackage.")
                )
                return

            w_edycji = EF.editable_layers(gpkg)
            if w_edycji:
                QMessageBox.warning(
                    self, "WFG DWG Layers+",
                    tr("Zakończ edycję tych warstw przed naprawą — ich bufor "
                    "zapisałby stare wartości z powrotem:\n\n")
                    + "\n".join(l.name() for l in w_edycji[:10]),
                )
                return

            if not self.cb_project.isChecked() and self.scan_proj:
                odp = QMessageBox.question(
                    self, "WFG DWG Layers+",
                    tr("Poprawiasz dane, ale nie projekt. Filtry warstw nadal będą "
                    "wskazywać stare wartości i takie warstwy pokażą zero "
                    "obiektów.\n\nKontynuować mimo to?"),
                )
                if odp != QMessageBox.StandardButton.Yes:
                    return
            odp = QMessageBox.question(
                self,
                "WFG DWG Layers+",
                tr("Zapisać poprawki do pliku\n{0}?\n\n{1}").format(
                    os.path.basename(gpkg),
                    tr("Kopia zapasowa zostanie utworzona obok.")
                    if self.cb_backup.isChecked()
                    else tr("UWAGA: bez kopii zapasowej."),
                ),
            )
            if odp != QMessageBox.StandardButton.Yes:
                return

        self.feedback = QgsFeedback()
        self.progress.setVisible(True)
        # _progress woła processEvents(), więc bez blokady użytkownik mógłby
        # wejść w naprawę drugi raz w środku otwartej transakcji
        self.buttons.setEnabled(False)
        self.btn_scan.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if self.cb_data.isChecked():
                # QGIS trzyma ten plik otwarty; bez zwolnienia uchwytów zapis
                # potrafi polec na zablokowanej bazie
                EF.release_layers(gpkg)
                zmian, kopia = EF.apply_gpkg(
                    gpkg, enc, self.cb_backup.isChecked(),
                    self.feedback, self._progress,
                )
                komunikaty.append(
                    tr("GeoPackage: poprawiono {0} wartości.").format(zmian)
                )
                if kopia:
                    komunikaty.append(
                        tr("Kopia zapasowa: {0}").format(os.path.basename(kopia))
                    )

            if self.cb_project.isChecked():
                wynik = EF.apply_project(encoding=enc, fix_filters=True)
                komunikaty.append(
                    tr("Projekt: warstw {0}, grup {1}, filtrów {2}.").format(
                        wynik.layers, wynik.groups, wynik.filters
                    )
                )
                komunikaty.extend(wynik.details[:5])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            return
        finally:
            # Przeładowanie MUSI iść także po błędzie: jeśli dane zostały już
            # poprawione, a poprawianie projektu poległo, warstwy z niepoprawionym
            # filtrem pokazywałyby zero obiektów bez śladu przyczyny.
            try:
                EF.reload_layers()
                if self.iface is not None:
                    self.iface.mapCanvas().refreshAllLayers()
            except Exception:
                pass
            QApplication.restoreOverrideCursor()
            self.progress.setVisible(False)
            self.buttons.setEnabled(True)
            self.btn_scan.setEnabled(True)

        settings = QgsSettings()
        settings.setValue(SETTINGS_PREFIX + "gpkg", gpkg)
        settings.setValue(SETTINGS_PREFIX + "encoding", enc)

        komunikaty.append("")
        komunikaty.append(tr("Pamiętaj zapisać projekt."))
        tekst = "\n".join(komunikaty)
        self.status.setText(tekst)
        QMessageBox.information(self, "WFG DWG Layers+", tekst)
        self._scan()

    def _progress(self, pct, message=""):
        if pct is None or pct < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(pct))))
        if message:
            self.status.setText(str(message))
        QApplication.processEvents()
