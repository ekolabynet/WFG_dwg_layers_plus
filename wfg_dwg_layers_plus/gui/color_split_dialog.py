# -*- coding: utf-8 -*-
"""Okno „Podziel warstwę wg koloru" — dla rysunków, gdzie treść niesie barwa."""

import os

from qgis.core import QgsFeedback, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QColor
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
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..core import color_split as CS
from ..core import gpkg_schema as S
from ..core import encoding_fix as EF
from ..core import tree_builder

SETTINGS_PREFIX = "wfg_dwg_layers_plus/split/"


class ColorSplitDialog(QDialog):
    def __init__(self, iface, parent=None):
        super(ColorSplitDialog, self).__init__(parent or iface.mainWindow())
        self.iface = iface
        self.buckets = []
        self.feedback = QgsFeedback()

        self.setWindowTitle("WFG DWG Layers+ — podziel warstwę wg koloru")
        self.setMinimumWidth(860)
        self.setMinimumHeight(620)
        self._build_ui()
        self._prefill()

    # -- UI -----------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        intro = QLabel(
            "Część eksportów wrzuca całą kreskę na warstwę <b>0</b> i rozróżnia "
            "treść wyłącznie barwą. Podział „warstwa CAD × typ geometrii\" daje "
            "wtedy jedną wielką warstwę. Tu dzielimy po tym, co w takim pliku "
            "naprawdę niesie znaczenie."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        box = QGroupBox("Źródło")
        form = QFormLayout(box)

        row = QHBoxLayout()
        self.ed_gpkg = QLineEdit()
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.clicked.connect(self._pick_gpkg)
        row.addWidget(self.ed_gpkg)
        row.addWidget(btn)
        form.addRow("GeoPackage:", row)

        self.cmb_layer = QComboBox()
        self.cmb_layer.setEditable(True)
        form.addRow("Warstwa CAD:", self.cmb_layer)

        wymiary = QHBoxLayout()
        self.cb_color = QCheckBox("kolor")
        self.cb_color.setChecked(True)
        self.cb_lweight = QCheckBox("grubość linii")
        self.cb_etype = QCheckBox("typ encji (łuk / okrąg / odcinek)")
        for cb in (self.cb_color, self.cb_lweight, self.cb_etype):
            wymiary.addWidget(cb)
        wymiary.addStretch(1)
        form.addRow("Dziel według:", wymiary)

        root.addWidget(box)

        scan_row = QHBoxLayout()
        self.btn_scan = QPushButton("Skanuj")
        self.btn_scan.clicked.connect(self._scan)
        scan_row.addWidget(self.btn_scan)
        scan_row.addWidget(QLabel("Nazwy w ostatniej kolumnie można edytować."))
        scan_row.addStretch(1)
        root.addLayout(scan_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Kolor", "Tabela", "Grubość", "Typ", "Obiektów", "Nazwa warstwy"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        opts = QGroupBox("Po podziale")
        olay = QVBoxLayout(opts)
        self.cb_remove = QCheckBox(
            "Usuń nierozdzieloną warstwę źródłową z projektu (np. 0_pline)"
        )
        self.cb_remove.setChecked(True)
        self.cb_remove.setToolTip(
            "Inaczej ta sama geometria byłaby narysowana dwa razy. "
            "Usuwamy tylko warstwę z projektu — dane w GeoPackage zostają."
        )
        olay.addWidget(self.cb_remove)
        self.cb_remember = QCheckBox(
            "Zapamiętaj nazwy dla tych kolorów (przydadzą się przy następnym pliku)"
        )
        self.cb_remember.setChecked(True)
        olay.addWidget(self.cb_remember)
        root.addWidget(opts)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Close,
            Qt.Orientation.Horizontal,
        )
        self.btn_apply = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.btn_apply.setText("Podziel")
        self.btn_apply.setEnabled(False)
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setText("Zamknij")
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
        self._fill_layers()

    def _pick_gpkg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz GeoPackage", self.ed_gpkg.text(), "GeoPackage (*.gpkg)"
        )
        if path:
            self.ed_gpkg.setText(path)
            self._fill_layers()

    def _fill_layers(self):
        self.cmb_layer.clear()
        gpkg = self.ed_gpkg.text().strip()
        if not gpkg or not os.path.exists(gpkg):
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            kandydaci = CS.candidate_layers(gpkg)
        except Exception:
            kandydaci = []
        finally:
            QApplication.restoreOverrideCursor()
        for layer, n_colors, n_rows in kandydaci:
            self.cmb_layer.addItem(
                "{0}  ({1} kolorów, {2} obiektów)".format(layer, n_colors, n_rows),
                layer,
            )
        if not kandydaci:
            self.cmb_layer.addItem("0", "0")

    def _cad_layer(self):
        data = self.cmb_layer.currentData()
        if data:
            return data
        return self.cmb_layer.currentText().split("  (")[0].strip()

    def _remembered(self, bucket):
        settings = QgsSettings()
        return str(
            settings.value(SETTINGS_PREFIX + "names/" + bucket.memory_key, "") or ""
        )

    def _scan(self):
        gpkg = self.ed_gpkg.text().strip()
        if not gpkg or not os.path.exists(gpkg):
            QMessageBox.warning(self, "WFG DWG Layers+", "Wskaż istniejący GeoPackage.")
            return
        if not (self.cb_color.isChecked() or self.cb_lweight.isChecked()
                or self.cb_etype.isChecked()):
            QMessageBox.warning(
                self, "WFG DWG Layers+", "Zaznacz przynajmniej jeden wymiar podziału."
            )
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.buckets = CS.scan(
                gpkg, self._cad_layer(),
                by_color=self.cb_color.isChecked(),
                by_lweight=self.cb_lweight.isChecked(),
                by_etype=self.cb_etype.isChecked(),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        for bucket in self.buckets:
            bucket.name = self._remembered(bucket)
        self._populate()

    def _populate(self):
        self.table.setRowCount(len(self.buckets))
        for r, bucket in enumerate(self.buckets):
            kolor = QTableWidgetItem(str(bucket.color or ""))
            qc = bucket.qcolor()
            if qc is not None and qc.isValid():
                kolor.setBackground(QBrush(qc))
                # czarny tekst na ciemnym tle byłby nieczytelny
                jasnosc = (qc.red() * 299 + qc.green() * 587 + qc.blue() * 114) / 1000
                kolor.setForeground(
                    QBrush(QColor(255, 255, 255) if jasnosc < 128 else QColor(0, 0, 0))
                )
            kolor.setFlags(kolor.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, kolor)

            for c, tekst in (
                (1, bucket.table),
                (2, "" if bucket.lweight is None else str(bucket.lweight)),
                (3, "" if bucket.etype is None
                    else CS.ETYPE_NAMES.get(bucket.etype, str(bucket.etype))),
                (4, str(bucket.count)),
            ):
                item = QTableWidgetItem(tekst)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 4:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(r, c, item)

            nazwa = QTableWidgetItem(bucket.name or "")
            nazwa.setToolTip(
                "Puste = nazwa automatyczna: {0}".format(bucket.auto_name())
            )
            self.table.setItem(r, 5, nazwa)

        self.status.setText(
            "Znaleziono {0} kombinacji. Wpisz nazwy albo zostaw puste — "
            "wtedy powstaną nazwy automatyczne.".format(len(self.buckets))
        )
        self.btn_apply.setEnabled(bool(self.buckets))

    def _tree_options(self):
        """Ustawienia drzewa takie, jakich użył import tego rysunku.

        Świeże ``TreeOptions()`` miałyby domyślne nazwy grup i sufiksy, więc
        w projekcie zbudowanym z własnymi nazwami podział założyłby obok
        komplet nowych, pustych grup.
        """
        settings = QgsSettings()
        prefix = "wfg_dwg_layers_plus/"
        options = tree_builder.TreeOptions()

        def flaga(klucz, domyslnie):
            wartosc = settings.value(prefix + klucz, domyslnie)
            if isinstance(wartosc, str):
                return wartosc.lower() in ("true", "1", "yes")
            return bool(wartosc)

        options.numbered_groups = flaga("numbered", True)
        for kind in S.GROUP_ORDER:
            options.group_names[kind] = str(
                settings.value(prefix + "group/" + kind, S.DEFAULT_GROUPS[kind])
            )
        for table, sufiks in S.DEFAULT_SUFFIXES.items():
            options.suffixes[table] = str(
                settings.value(prefix + "suffix/" + table, sufiks)
            )
        # bez tego warstwy punktowe powstałyby z pustym rendererem — import
        # domyślnie punktów nie pokazuje, ale tu użytkownik prosi o nie wprost
        options.style.show_points = True
        try:
            options.style.line_width_mm = float(
                settings.value(prefix + "lineWidth", options.style.line_width_mm)
            )
            options.style.point_size_mm = float(
                settings.value(prefix + "pointSize", options.style.point_size_mm)
            )
        except (TypeError, ValueError):
            pass
        tryb = settings.value(prefix + "plineWidthMode", "")
        if tryb in ("mm", "map", "ignore"):
            options.style.polyline_width_mode = tryb
        return options

    def _collect_names(self):
        for r, bucket in enumerate(self.buckets):
            item = self.table.item(r, 5)
            bucket.name = item.text().strip() if item else ""

    def _apply(self):
        if not self.buckets:
            return
        self._collect_names()
        gpkg = self.ed_gpkg.text().strip()
        cad_layer = self._cad_layer()

        options = self._tree_options()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            wynik = CS.build_layers(
                gpkg, cad_layer, self.buckets, options, feedback=self.feedback
            )
            usunieto = 0
            if self.cb_remove.isChecked():
                usunieto = CS.remove_source_layers(gpkg, cad_layer)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "WFG DWG Layers+", str(exc))
            return
        finally:
            QApplication.restoreOverrideCursor()

        if self.cb_remember.isChecked():
            settings = QgsSettings()
            for bucket in self.buckets:
                if bucket.name:
                    settings.setValue(
                        SETTINGS_PREFIX + "names/" + bucket.memory_key, bucket.name
                    )
        QgsSettings().setValue(SETTINGS_PREFIX + "gpkg", gpkg)

        komunikat = "Utworzono warstw: {0}.".format(wynik.count)
        if usunieto:
            komunikat += " Usunięto nierozdzielonych: {0}.".format(usunieto)
        if wynik.warnings:
            komunikat += "\n" + "\n".join(wynik.warnings[:5])
        self.status.setText(komunikat)
        QMessageBox.information(self, "WFG DWG Layers+", komunikat)
