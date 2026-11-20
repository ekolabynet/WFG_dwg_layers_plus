# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Processing provider: the plugin's tools in the Processing Toolbox, usable in models and batch runs.

The algorithms run without dialogs on the same core as the menu items. They change the
project (layer tree, joins), so they run in the main thread (NoThreading).
The built-in DWG/DXF import has no Python API, so here DXF/DWG go through the
plugin's own GDAL import; a GeoPackage made earlier by the built-in import works too.
"""
import os

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingOutputNumber,
    QgsProcessingOutputString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterCrs,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFile,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterNumber,
    QgsProcessingProvider,
)
from qgis.PyQt.QtGui import QIcon

from .i18n import tr

ICON = os.path.join(os.path.dirname(__file__), "icon.png")


def _no_threading_flag():
    """Qgis.ProcessingAlgorithmFlag.NoThreading (3.36+, QGIS 4) or the older QgsProcessingAlgorithm flag."""
    try:
        from qgis.core import Qgis
        return Qgis.ProcessingAlgorithmFlag.NoThreading
    except AttributeError:
        return QgsProcessingAlgorithm.FlagNoThreading


def _file_behavior():
    try:
        return QgsProcessingParameterFile.Behavior.File
    except AttributeError:
        return QgsProcessingParameterFile.File


def _number_type(kind):
    try:
        return getattr(QgsProcessingParameterNumber.Type, kind)
    except AttributeError:
        return getattr(QgsProcessingParameterNumber, kind)


def _progress(feedback):
    def cb(pct, msg=""):
        if pct is not None:
            feedback.setProgress(float(pct))
        if msg:
            feedback.pushInfo(str(msg))
    return cb


class _Base(QgsProcessingAlgorithm):
    def createInstance(self):
        return type(self)()

    def flags(self):
        return super().flags() | _no_threading_flag()

    def icon(self):
        return QIcon(ICON)

    def _check_not_edited(self, gpkg):
        from .core import encoding_fix as EF
        edited = EF.editable_layers(gpkg)
        if edited:
            raise QgsProcessingException(
                tr("Zakończ edycję tych warstw przed naprawą — ich bufor zapisałby stare wartości z powrotem:\n\n")
                + "\n".join(lay.name() for lay in edited[:10]))


class ImportAlgorithm(_Base):
    INPUT, OUTPUT_GPKG, CRS, IMPORTER, LAYER_MODE, BLOCK_MODE, SKIP_EMPTY, NUMBERED = (
        "INPUT", "OUTPUT_GPKG", "CRS", "IMPORTER", "LAYER_MODE", "BLOCK_MODE", "SKIP_EMPTY", "NUMBERED")
    OUTPUT, LAYERS = "OUTPUT", "LAYERS"

    def name(self):
        return "import_dwg_dxf"

    def displayName(self):
        return tr("Importuj DWG/DXF jako warstwy")

    def shortHelpString(self):
        return tr("Każda warstwa CAD staje się osobną warstwą QGIS „&lt;warstwa_CAD&gt;_&lt;typ&gt;” w czterech grupach wg typu "
                  "geometrii. Źródło: DXF, DWG albo GeoPackage z wbudowanego importu QGIS.") + "<br><br>" + tr(
                  "Import rysunku: wbudowany import QGIS uruchamiany automatycznie (okno wypełnia się i zamyka samo), "
                  "wbudowany import z jego oknem do zatwierdzenia albo własny import przez GDAL (DWG wymaga ODA File "
                  "Converter albo LibreDWG). Wbudowany import wymaga otwartego QGIS — w qgis_process wtyczka "
                  "przechodzi na GDAL. Bloki złożone i punkty wstawień — tylko z wbudowanym importem.")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.INPUT, tr("Rysunek / GeoPackage:"), _file_behavior(),
            fileFilter=tr("CAD i GeoPackage (*.dwg *.DWG *.dxf *.DXF *.gpkg);;Wszystkie pliki (*)")))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT_GPKG, tr("Wyjściowy GeoPackage (domyślnie obok pliku źródłowego)"),
            "GeoPackage (*.gpkg)", optional=True, createByDefault=False))
        self.addParameter(QgsProcessingParameterCrs(self.CRS, tr("Układ współrzędnych:"), optional=True))
        self.addParameter(QgsProcessingParameterEnum(
            self.IMPORTER, tr("Import rysunku (DWG/DXF)"),
            [tr("Wbudowany import QGIS — automatycznie"),
             tr("Wbudowany import QGIS — z jego oknem do zatwierdzenia"),
             tr("Własny import przez GDAL")], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.LAYER_MODE, tr("Struktura"),
            [tr("Filtry na wspólnej tabeli (szybko)"), tr("Osobne tabele w GeoPackage")], defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(
            self.BLOCK_MODE, tr("Bloki"),
            [tr("Rozbite na geometrie (jak dotąd)"),
             tr("Punkty wstawień z atrybutami (tylko wbudowany import)"),
             tr("Złożone geometrie — jeden obiekt na wstawienie (tylko wbudowany import)")],
            defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(self.SKIP_EMPTY, tr("Pomijaj puste warstwy"), True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.NUMBERED, tr("Numeruj grupy (stała kolejność w legendzie)"), True))
        self.addOutput(QgsProcessingOutputString(self.OUTPUT, tr("GeoPackage")))
        self.addOutput(QgsProcessingOutputNumber(self.LAYERS, tr("Liczba warstw")))

    def processAlgorithm(self, parameters, context, feedback):
        from .core import gpkg_schema as S, runner

        source = self.parameterAsFile(parameters, self.INPUT, context)
        if not source or not os.path.isfile(source):
            raise QgsProcessingException(tr("Wskaż istniejący plik źródłowy."))
        ext = os.path.splitext(source)[1].lower()
        block_mode = (S.BlockMode.EXPLODED, S.BlockMode.INSERT_POINTS, S.BlockMode.COMPOSITE)[
            self.parameterAsEnum(parameters, self.BLOCK_MODE, context)]
        importer = self.parameterAsEnum(parameters, self.IMPORTER, context)
        iface = None
        if ext != ".gpkg" and importer in (0, 1):
            try:
                from qgis.utils import iface
            except ImportError:
                iface = None
            if iface is None:
                feedback.pushWarning(tr("Wbudowany import QGIS wymaga otwartego okna QGIS — używam własnego "
                                        "importu przez GDAL."))
                importer = 2
        if ext != ".gpkg" and importer == 2 and block_mode != S.BlockMode.EXPLODED:
            raise QgsProcessingException(tr(
                "Własny import przez GDAL rozbija bloki na geometrie. Wybierz „Rozbite na geometrie” albo wbudowany "
                "import QGIS."))

        config = runner.RunConfig()
        config.source_path = source
        config.use_own_importer = ext != ".gpkg" and importer == 2
        config.builtin_auto = importer == 0
        out = self.parameterAsFileOutput(parameters, self.OUTPUT_GPKG, context)
        config.gpkg_path = out or None
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        config.crs_authid = crs.authid() if crs.isValid() else None
        config.tree.layer_mode = (S.LayerMode.FILTER, S.LayerMode.MATERIALIZE)[
            self.parameterAsEnum(parameters, self.LAYER_MODE, context)]
        config.tree.block_mode = block_mode
        config.tree.skip_empty = self.parameterAsBool(parameters, self.SKIP_EMPTY, context)
        config.tree.numbered_groups = self.parameterAsBool(parameters, self.NUMBERED, context)

        try:
            result = runner.run(config, iface, feedback, _progress(feedback))
        except Exception as exc:  # noqa: BLE001
            raise QgsProcessingException(tr("Blad importu: {0}").format(exc))
        for msg in result.messages:
            feedback.reportError(str(msg), False)
        feedback.pushInfo(tr("Zaimportowano: {0}").format(result.summary()))
        return {self.OUTPUT: result.gpkg_path, self.LAYERS: result.tree.count if result.tree else 0}


class RecoverLayersAlgorithm(_Base):
    GPKG, DXF, BACKUP, SKIP_BLOCKS = "GPKG", "DXF", "BACKUP", "SKIP_BLOCKS"
    CHANGED, BACKUP_PATH = "CHANGED", "BACKUP_PATH"

    def name(self):
        return "recover_layers"

    def displayName(self):
        return tr("Odzyskaj warstwy z rysunku")

    def shortHelpString(self):
        return tr("Gdy cała kreska wylądowała na warstwie 0, a w rysunku ma swoje warstwy — przepisuje przypisanie "
                  "z DXF-a po uchwycie encji") + ". " + tr(
                  "Rysunek DXF może zostać pusty: wtyczka weźmie ścieżkę zapisaną przez import w GeoPackage.")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.GPKG, tr("GeoPackage z importu"), _file_behavior(), extension="gpkg"))
        self.addParameter(QgsProcessingParameterFile(
            self.DXF, tr("Rysunek DXF:"), _file_behavior(), extension="dxf", optional=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.BACKUP, tr("Zrób kopię zapasową GeoPackage przed zapisem"), True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.SKIP_BLOCKS, tr("Nie ruszaj encji rozbitych z bloków"), True))
        self.addOutput(QgsProcessingOutputNumber(self.CHANGED, tr("Poprawione obiekty")))
        self.addOutput(QgsProcessingOutputString(self.BACKUP_PATH, tr("Kopia zapasowa")))

    def processAlgorithm(self, parameters, context, feedback):
        from .core import encoding_fix as EF, layer_fix as LF

        gpkg = self.parameterAsFile(parameters, self.GPKG, context)
        if not gpkg or not os.path.isfile(gpkg):
            raise QgsProcessingException(tr("Wskaż istniejący GeoPackage."))
        dxf = self.parameterAsFile(parameters, self.DXF, context) or LF.first_existing(LF.source_drawing(gpkg))
        if not dxf or not os.path.isfile(dxf):
            raise QgsProcessingException(tr("Wskaż istniejący plik DXF."))
        if dxf.lower().endswith(".dwg"):
            raise QgsProcessingException(tr(
                "Źródłem jest DWG. Ta naprawa czyta tylko DXF-a — zapisz rysunek jako DXF (ASCII) i wskaż ten plik."))
        feedback.pushInfo(tr("Rysunek DXF:") + " " + dxf)
        skip = self.parameterAsBool(parameters, self.SKIP_BLOCKS, context)
        scan = LF.scan_dxf(dxf, feedback=feedback, progress_cb=_progress(feedback))
        plan = LF.plan(gpkg, scan, skip_block_content=skip)
        for warning in plan.warnings:
            feedback.pushInfo(str(warning))
        if plan.mojibake:
            raise QgsProcessingException(tr(
                "UWAGA: w {0} przypadkach nazwa w bazie różni się od rysunku wyłącznie kodowaniem polskich znaków. "
                "Uruchom najpierw „Napraw kodowanie”, a potem wróć tutaj.").format(plan.mojibake))
        if not plan.changed:
            feedback.pushInfo(tr("Nie ma czego poprawiać: przypisanie w bazie zgadza się z rysunkiem."))
            return {self.CHANGED: 0, self.BACKUP_PATH: ""}
        self._check_not_edited(gpkg)
        try:
            EF.release_layers(gpkg)
            changed, backup = LF.apply_fix(
                gpkg, scan, make_backup=self.parameterAsBool(parameters, self.BACKUP, context),
                skip_block_content=skip, feedback=feedback, progress_cb=_progress(feedback))
        finally:
            EF.reload_layers(gpkg)
        feedback.pushInfo(tr("Poprawiono przypisanie dla {0} obiektów.").format(changed))
        return {self.CHANGED: changed, self.BACKUP_PATH: backup or ""}


ENCODINGS = ("cp1250", "cp1252", "latin-1", "cp1251")


class FixEncodingAlgorithm(_Base):
    GPKG, ENCODING, BACKUP, PROJECT = "GPKG", "ENCODING", "BACKUP", "PROJECT"
    CHANGED, BACKUP_PATH = "CHANGED", "BACKUP_PATH"

    def name(self):
        return "fix_encoding"

    def displayName(self):
        return tr("Napraw kodowanie")

    def shortHelpString(self):
        return tr("Usuwa podwójne kodowanie polskich znaków w nazwach warstw, nazwach bloków i treści tekstów")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(
            self.GPKG, tr("GeoPackage z importu"), _file_behavior(), extension="gpkg"))
        self.addParameter(QgsProcessingParameterEnum(
            self.ENCODING, tr("Błędna strona kodowa:"),
            [tr("cp1250 — polska strona kodowa (domyślnie)"), tr("cp1252 — zachodnioeuropejska"), "latin-1",
             tr("cp1251 — cyrylica")], defaultValue=0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.BACKUP, tr("Zrób kopię zapasową GeoPackage przed zapisem"), True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.PROJECT, tr("Nazwy warstw i grup w projekcie oraz filtry warstw"), True))
        self.addOutput(QgsProcessingOutputNumber(self.CHANGED, tr("Poprawione wartości")))
        self.addOutput(QgsProcessingOutputString(self.BACKUP_PATH, tr("Kopia zapasowa")))

    def processAlgorithm(self, parameters, context, feedback):
        from .core import encoding_fix as EF

        gpkg = self.parameterAsFile(parameters, self.GPKG, context)
        if not gpkg or not os.path.isfile(gpkg):
            raise QgsProcessingException(tr("Wskaż istniejący GeoPackage."))
        enc = ENCODINGS[self.parameterAsEnum(parameters, self.ENCODING, context)]
        self._check_not_edited(gpkg)
        try:
            EF.release_layers(gpkg)
            changed, backup = EF.apply_gpkg(gpkg, enc, self.parameterAsBool(parameters, self.BACKUP, context),
                                            feedback, _progress(feedback))
        finally:
            EF.reload_layers(gpkg)
        feedback.pushInfo(tr("GeoPackage: poprawiono {0} wartości.").format(changed))
        if self.parameterAsBool(parameters, self.PROJECT, context):
            res = EF.apply_project(encoding=enc, fix_filters=True)
            feedback.pushInfo(tr("Projekt: warstw {0}, grup {1}, filtrów {2}.").format(
                res.layers, res.groups, res.filters))
        return {self.CHANGED: changed, self.BACKUP_PATH: backup or ""}


class BlockAttributesAlgorithm(_Base):
    DXF, GPKG, ENCODING, MAX_COLUMNS, JOIN = "DXF", "GPKG", "ENCODING", "MAX_COLUMNS", "JOIN"
    ROWS = "ROWS"

    def name(self):
        return "block_attributes"

    def displayName(self):
        return tr("Wczytaj atrybuty bloków z rysunku")

    def shortHelpString(self):
        return tr("Odzyskuje wartości atrybutów bloków (ATTRIB), których wbudowany import DWG/DXF nie widzi, "
                  "i skleja je z importem po uchwycie encji")

    def initAlgorithm(self, config=None):
        from .core import block_attributes as BA
        self.addParameter(QgsProcessingParameterFile(
            self.DXF, tr("Rysunek źródłowy:"), _file_behavior(),
            fileFilter=tr("Rysunki CAD (*.dxf *.DXF *.dwg *.DWG);;Wszystkie pliki (*)")))
        self.addParameter(QgsProcessingParameterFile(
            self.GPKG, tr("GeoPackage z importu"), _file_behavior(), extension="gpkg"))
        self.addParameter(QgsProcessingParameterEnum(
            self.ENCODING, tr("Kodowanie tekstu:"),
            [tr("cp1250 — polska strona kodowa (domyślnie)"), tr("cp1252 — zachodnioeuropejska"), "latin-1",
             tr("cp1251 — cyrylica")], defaultValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_COLUMNS, tr("Maksimum kolumn:"), _number_type("Integer"), BA.MAX_COLUMNS, False, 1, 500))
        self.addParameter(QgsProcessingParameterBoolean(
            self.JOIN, tr("Podepnij złączenia do warstw wstawień i kotwic w projekcie"), True))
        self.addOutput(QgsProcessingOutputNumber(self.ROWS, tr("Zapisane wiersze")))

    def processAlgorithm(self, parameters, context, feedback):
        from .core import block_attributes as BA

        dxf = self.parameterAsFile(parameters, self.DXF, context)
        gpkg = self.parameterAsFile(parameters, self.GPKG, context)
        if not dxf or not os.path.isfile(dxf):
            raise QgsProcessingException(tr("Wskaż istniejący rysunek."))
        if not gpkg or not os.path.isfile(gpkg):
            raise QgsProcessingException(tr("Wskaż istniejący GeoPackage."))
        enc = ENCODINGS[self.parameterAsEnum(parameters, self.ENCODING, context)]
        try:
            scan = BA.scan(dxf, feedback=feedback, progress_cb=_progress(feedback), encoding=enc)
        except Exception as exc:  # noqa: BLE001
            raise QgsProcessingException(str(exc))
        columns, dropped = BA.choose_columns(scan, self.parameterAsInt(parameters, self.MAX_COLUMNS, context))
        BA.reset()
        written = BA.write_table(gpkg, scan, columns, feedback)
        feedback.pushInfo(tr("Zapisano {0} wierszy do tabeli {1}, kolumn atrybutów: {2}.").format(
            written, BA.TABLE, len(columns)))
        if dropped:
            feedback.pushInfo(tr("Pominięto {0} rzadszych znaczników (limit kolumn): {1}").format(
                len(dropped), ", ".join(dropped[:8])))
        if written and self.parameterAsBool(parameters, self.JOIN, context):
            join = BA.attach_joins(gpkg, table_layer=BA.load_table_layer(gpkg))
            feedback.pushInfo(tr("Podpięto złączenia do {0} warstw.").format(len(join.joined)))
            for err in join.errors[:5]:
                feedback.reportError(str(err), False)
        return {self.ROWS: written}


class DwgLayersPlusProvider(QgsProcessingProvider):
    def id(self):
        return "wfgdwglayersplus"

    def name(self):
        return "WFG DWG Layers+"

    def icon(self):
        return QIcon(ICON)

    def loadAlgorithms(self):
        for alg in (ImportAlgorithm(), RecoverLayersAlgorithm(), FixEncodingAlgorithm(), BlockAttributesAlgorithm()):
            self.addAlgorithm(alg)
