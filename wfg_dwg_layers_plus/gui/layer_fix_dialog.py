# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Okno „Odzyskaj warstwy z rysunku" — naprawa przypisania encji do warstw."""

import os
from html import escape

from qgis.core import QgsFeedback, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
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
from ..core import layer_fix as LF
from ..i18n import tr

SETTINGS_PREFIX = "wfg_dwg_layers_plus/layerfix/"


class LayerFixDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(LayerFixDialog, self).__init__(parent or iface.mainWindow())
        self.iface = iface
        self.scan = None
        self.plan = None
        self._ostatni_gpkg = ""
        self.feedback = QgsFeedback()

        self.setWindowTitle(tr("WFG DWG Layers+ — odzyskaj warstwy z rysunku"))
        self.setMinimumWidth(860)
        self.setMinimumHeight(620)
        self._build_ui()
        self._prefill()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(
            tr("Wbudowany import gubi nazwę warstwy dla „ciężkiej\" "
            "<b>POLYLINE</b> — tej z osobnymi encjami <b>VERTEX</b>, którą "
            "wypuszczają eksporty z systemów geodezyjnych. Zapisuje dla niej "
            "uchwyt i warstwę <b>SEQEND</b>-a, czyli encji zamykającej, a ta "
            "leży na warstwie <b>0</b>. Objaw: <i>inserts</i> i <i>texts</i> "
            "mają dziesiątki poprawnych nazw, a <i>polylines</i> jedną.<br><br>"
            "Uchwyt przeżywa import, więc wystarczy przeczytać rysunek "
            "i podstawić pod uchwyt zamknięcia warstwę polilinii, którą ono "
            "zamyka. Geometrii to nie dotyka i nie wymaga ponownego importu.")
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        box = QGroupBox(tr("Pliki"))
        form = QFormLayout(box)

        row = QHBoxLayout()
        self.ed_gpkg = QLineEdit()
        self.ed_gpkg.setPlaceholderText(tr("GeoPackage z importu"))
        self.ed_gpkg.editingFinished.connect(self._guess_dxf)
        self.ed_gpkg.textChanged.connect(self._guess_dxf)
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(self._pick_gpkg)
        row.addWidget(self.ed_gpkg)
        row.addWidget(btn)
        form.addRow("GeoPackage:", row)

        row2 = QHBoxLayout()
        self.ed_dxf = QLineEdit()
        self.ed_dxf.setPlaceholderText(tr("plik DXF, z którego powstał import"))
        btn2 = QPushButton("…")
        btn2.setFixedWidth(32)
        btn2.clicked.connect(self._pick_dxf)
        row2.addWidget(self.ed_dxf)
        row2.addWidget(btn2)
        form.addRow(tr("Rysunek DXF:"), row2)

        self.lbl_hint = QLabel("")
        self.lbl_hint.setWordWrap(True)
        form.addRow("", self.lbl_hint)

        root.addWidget(box)

        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton(tr("Sprawdź (podgląd zmian)"))
        self.btn_scan.clicked.connect(self._scan)
        scan_row.addWidget(self.btn_scan)
        scan_row.addStretch(1)
        root.addLayout(scan_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [tr("Tabela"), tr("Obiektów"), tr("Dopasowanych"), tr("Do zmiany"), tr("Warstw teraz"),
             tr("Warstw po naprawie")]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table, 1)

        self.przyklady = QLabel("")
        self.przyklady.setWordWrap(True)
        self.przyklady.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self.przyklady)

        opts = QGroupBox(tr("Opcje"))
        olay = QVBoxLayout(opts)
        self.cb_backup = QCheckBox(tr("Zrób kopię zapasową GeoPackage przed zapisem"))
        self.cb_backup.setChecked(True)
        olay.addWidget(self.cb_backup)
        self.cb_skip_blocks = QCheckBox(
            tr("Nie ruszaj encji rozbitych z bloków")
        )
        self.cb_skip_blocks.setChecked(True)
        self.cb_skip_blocks.setToolTip(
            tr("Kopie rozbitego bloku dzielą jeden uchwyt z jego definicją, więc "
            "dostałyby warstwę z wnętrza bloku — zwykle 0 — zamiast tej, którą "
            "niesie wstawienie. Dla treści blokowej właściwą drogą jest tryb "
            "bloków złożonych w oknie importu.")
        )
        self.cb_skip_blocks.toggled.connect(self._reskan_podgladu)
        olay.addWidget(self.cb_skip_blocks)
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
        self._guess_dxf()

    def _guess_dxf(self):
        """Podpowiada rysunek dla wskazanego GeoPackage.

        Rysunek podmieniamy zawsze, gdy zmienia sie GeoPackage. Wczesniej
        wystarczylo, ze pole rysunku wskazywalo istniejacy plik, i po wpisaniu
        sciezki do innej bazy w oknie zostawal rysunek z poprzedniej — czyli
        zestawienie dwoch niezwiazanych ze soba opracowan.
        """
        gpkg = self.ed_gpkg.text().strip()
        if not gpkg or not os.path.exists(gpkg):
            return
        if os.path.normcase(gpkg) == os.path.normcase(self._ostatni_gpkg or ""):
            return
        self._ostatni_gpkg = gpkg
        self.scan = self.plan = None
        self.btn_apply.setEnabled(False)
        kandydaci = LF.source_drawing(gpkg)
        znaleziony = LF.first_existing(kandydaci)
        if znaleziony:
            self.ed_dxf.setText(znaleziony)
            self.lbl_hint.setText(
                tr("Rysunek znaleziony automatycznie — import zapisał jego ścieżkę "
                "w GeoPackage.")
            )
        elif kandydaci:
            self.lbl_hint.setText(
                tr("Import wskazuje na rysunek <i>{0}</i>, ale go tam nie ma. "
                "Wskaż plik ręcznie.").format(
                    escape(os.path.basename(kandydaci[0]))
                )
            )

    def _pick_gpkg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz GeoPackage"), self.ed_gpkg.text(), "GeoPackage (*.gpkg)"
        )
        if path:
            self.ed_gpkg.setText(path)
            self._guess_dxf()

    def _pick_dxf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz rysunek"), self.ed_dxf.text(), "DXF (*.dxf *.DXF)"
        )
        if path:
            self.ed_dxf.setText(path)

    def _scan(self):
        gpkg = self.ed_gpkg.text().strip()
        dxf = self.ed_dxf.text().strip()
        if not gpkg or not os.path.exists(gpkg):
            QMessageBox.warning(self, "WFG DWG Layers+", tr("Wskaż istniejący GeoPackage."))
            return
        if not dxf or not os.path.exists(dxf):
            QMessageBox.warning(self, "WFG DWG Layers+", tr("Wskaż istniejący plik DXF."))
            return
        if dxf.lower().endswith(".dwg"):
            QMessageBox.warning(
                self, "WFG DWG Layers+",
                tr("Źródłem jest DWG. Ta naprawa czyta tylko DXF-a — zapisz "
                "rysunek jako DXF (ASCII) i wskaż ten plik."),
            )
            return

        self.feedback = QgsFeedback()
        self.btn_scan.setEnabled(False)
        # _progress wola processEvents(), wiec bez blokady mozna by kliknac
        # „Napraw" w srodku skanu — ze starym planem i nowa sciezka
        self.buttons.setEnabled(False)
        self.progress.setVisible(True)
        blad = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.scan = LF.scan_dxf(
                dxf, feedback=self.feedback, progress_cb=self._progress
            )
            self.plan = LF.plan(
                gpkg, self.scan,
                skip_block_content=self.cb_skip_blocks.isChecked(),
            )
        except Exception as exc:  # noqa: BLE001
            self.scan = self.plan = None
            blad = str(exc)
        finally:
            QApplication.restoreOverrideCursor()
            self.progress.setVisible(False)
            self.btn_scan.setEnabled(True)
            self.buttons.setEnabled(True)

        if blad is not None:
            self.btn_apply.setEnabled(False)
            QMessageBox.warning(self, "WFG DWG Layers+", blad)
            return
        self._populate()

    def _reskan_podgladu(self):
        """Przelicza podgląd bez ponownego czytania rysunku.

        Sam plan idzie po bazie i trwa chwilę; ponowne przejście przez DXF-a
        o wadze kilkuset megabajtów byłoby zabójcze przy każdym kliknięciu
        w pole wyboru.
        """
        if self.scan is None:
            return
        gpkg = self.ed_gpkg.text().strip()
        if not gpkg or not os.path.exists(gpkg):
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.plan = LF.plan(
                gpkg, self.scan,
                skip_block_content=self.cb_skip_blocks.isChecked(),
            )
        except Exception:  # noqa: BLE001
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._populate()

    def _populate(self):
        wiersze = [d for d in self.plan.tables if d.rows]
        self.table.setRowCount(len(wiersze))
        for r, d in enumerate(wiersze):
            for c, tekst in enumerate((
                d.table, str(d.rows), str(d.matched), str(d.changed),
                str(d.layers_before), str(d.layers_after),
            )):
                item = QTableWidgetItem(tekst)
                if c:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(r, c, item)

        proby = []
        for d in wiersze:
            for uchwyt, stara, nowa in d.przyklady[:2]:
                proby.append(
                    "{0}: <b>{1}</b> → <b>{2}</b>".format(
                        d.table, escape(str(stara)), escape(str(nowa))
                    )
                )
        self.przyklady.setText(
            tr("Przykłady: ") + "; ".join(proby[:6]) if proby else ""
        )

        zblokow = sum(d.from_blocks for d in wiersze)
        czesci = [
            tr("W rysunku: {0} encji z uchwytem, {1} nazw warstw w przestrzeni "
            "modelu; {2} przypisań odzyskanych przez uchwyt SEQEND-a.")
            .format(self.scan.count, self.scan.layer_count,
                    self.scan.via_seqend),
            tr("Do poprawy: {0} obiektów.").format(self.plan.changed),
        ]
        if self.scan.bez_uchwytu:
            czesci.append(
                tr("Encji bez uchwytu: {0} — tych nie da się dopasować.")
                .format(self.scan.bez_uchwytu)
            )
        if zblokow and self.cb_skip_blocks.isChecked():
            czesci.append(
                tr("{0} obiektów pochodzi z rozbicia bloków i zostanie pominiętych.")
                .format(zblokow)
            )
        czesci.extend(self.plan.warnings)

        # Gdy jedyna roznica miedzy baza a rysunkiem jest podwojne kodowanie,
        # przepisanie nazw rozjechaloby warstwe na dwie pisownie: naprawione
        # tam, gdzie uchwyt sie znalazl, i uszkodzone w reszcie. Filtry warstw
        # w projekcie przestalyby pasowac do jednych i drugich.
        podejrzane = self.plan.mojibake
        zablokowane = podejrzane and podejrzane >= self.plan.changed * 0.5
        if podejrzane:
            czesci.append(
                tr("UWAGA: w {0} przypadkach nazwa w bazie różni się od rysunku "
                "wyłącznie kodowaniem polskich znaków. Uruchom najpierw "
                "„Napraw kodowanie”, a potem wróć tutaj.")
                .format(podejrzane)
            )
        self.status.setText(" ".join(czesci))
        self.btn_apply.setEnabled(bool(self.plan.changed) and not zablokowane)

    def _apply(self):
        if self.scan is None or self.plan is None:
            return
        gpkg = self.ed_gpkg.text().strip()

        w_edycji = EF.editable_layers(gpkg)
        if w_edycji:
            QMessageBox.warning(
                self, "WFG DWG Layers+",
                tr("Zakończ edycję tych warstw przed naprawą — ich bufor "
                "zapisałby stare wartości z powrotem:\n\n")
                + "\n".join(l.name() for l in w_edycji[:10]),
            )
            return

        odp = QMessageBox.question(
            self, "WFG DWG Layers+",
            tr("Przepisać przypisanie warstw do pliku\n{0}?\n\n{1}").format(
                os.path.basename(gpkg),
                tr("Kopia zapasowa zostanie utworzona obok.")
                if self.cb_backup.isChecked() else tr("UWAGA: bez kopii zapasowej."),
            ),
        )
        if odp != QMessageBox.StandardButton.Yes:
            return

        self.feedback = QgsFeedback()
        self.progress.setVisible(True)
        self.buttons.setEnabled(False)
        self.btn_scan.setEnabled(False)
        blad = None
        zmian, kopia = 0, None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            EF.release_layers(gpkg)
            zmian, kopia = LF.apply_fix(
                gpkg, self.scan,
                make_backup=self.cb_backup.isChecked(),
                skip_block_content=self.cb_skip_blocks.isChecked(),
                feedback=self.feedback, progress_cb=self._progress,
            )
        except Exception as exc:  # noqa: BLE001
            blad = str(exc)
        finally:
            # Przeladowanie musi isc takze po bledzie — inaczej warstwy
            # zostalyby z uchwytami zwolnionymi przez release_layers
            try:
                EF.reload_layers(gpkg)
                if self.iface is not None:
                    self.iface.mapCanvas().refreshAllLayers()
            except Exception:
                pass
            QApplication.restoreOverrideCursor()
            self.progress.setVisible(False)
            self.buttons.setEnabled(True)
            self.btn_scan.setEnabled(True)

        if blad is not None:
            QMessageBox.warning(self, "WFG DWG Layers+", blad)
            return

        QgsSettings().setValue(SETTINGS_PREFIX + "gpkg", gpkg)

        komunikat = [tr("Poprawiono przypisanie dla {0} obiektów.").format(zmian)]
        if kopia:
            komunikat.append(tr("Kopia zapasowa: {0}").format(os.path.basename(kopia)))
        komunikat.append("")
        komunikat.append(
            tr("Warstwy wczytane wcześniej mają filtr na starą wartość, więc teraz "
            "pokażą mniej obiektów. Uruchom import wtyczki jeszcze raz na tym "
            "samym GeoPackage — tym razem zobaczy wszystkie warstwy CAD.")
        )
        tekst = "\n".join(komunikat)
        self.status.setText(tekst)
        QMessageBox.information(self, "WFG DWG Layers+", tekst)
        self._reskan_podgladu()

    def _progress(self, pct, message=""):
        if pct is None or pct < 0:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(max(0, min(100, int(pct))))
        if message:
            self.status.setText(str(message))
        QApplication.processEvents()
