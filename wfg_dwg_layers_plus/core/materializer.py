# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Materializacja: zapis kazdej pary (warstwa CAD, tabela) jako fizycznej tabeli GPKG."""

import sqlite3

from qgis.core import (
    QgsCoordinateTransformContext,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from . import gpkg_schema as S
from . import gpkg_reader, naming
from .qgis_compat import vector_file_writer_action


class MaterializeResult(object):
    def __init__(self):
        self.mapping = {}      # (cad_layer, table) -> nazwa tabeli GPKG
        self.errors = []
        self.written = 0


def materialize(
    gpkg_path,
    inv,
    cad_layers,
    options,
    feedback=None,
    segmentize=False,
    progress_cb=None,
    reuse_previous=True,
):
    """Zapisuje wybrane pary do osobnych tabel w tym samym GeoPackage.

    Nazwy tabel przechodza przez sanityzacje (polskie znaki, spacje, kolizje
    wielkosci liter, limit dlugosci), a mapowanie ``tabela -> oryginalna nazwa
    warstwy CAD`` jest zapisywane w tabeli pomocniczej, zeby ponowny import byl
    idempotentny i zeby dalo sie odtworzyc nazwy po przeniesieniu pliku.
    """
    result = MaterializeResult()
    # Idempotencja: jesli ten GeoPackage byl juz materializowany, uzywamy tych
    # samych nazw tabel (nadpisujac je), zamiast dokladac foo_hatch_2, _3, ...
    previous = read_mapping(gpkg_path) if reuse_previous else {}
    # Allocator widzi WSZYSTKIE istniejace tabele. Nazwy z poprzedniego przebiegu
    # i tak omijaja allocator (bierzemy je wprost z `previous`), a odjecie ich
    # tutaj tylko otwieraloby droge do nadpisania cudzej tabeli o tej samej
    # nazwie po sanityzacji.
    allocator = naming.NameAllocator(gpkg_reader.existing_table_names(gpkg_path))
    ctx = QgsProject.instance().transformContext() or QgsCoordinateTransformContext()

    wanted = set(cad_layers)
    tables = [S.T_HATCHES, S.T_LINES, S.T_POLYLINES, S.T_POINTS, S.T_TEXTS]
    if options.block_mode in (S.BlockMode.INSERT_POINTS, S.BlockMode.COMPOSITE):
        tables.append(S.T_INSERTS)

    jobs = []
    for info in inv.layers:
        if info.name not in wanted:
            continue
        for table in tables:
            if info.count(table):
                jobs.append((info, table))

    total = len(jobs) or 1
    for i, (info, table) in enumerate(jobs):
        if feedback is not None and feedback.isCanceled():
            break
        if progress_cb is not None:
            progress_cb(int(100.0 * i / total), "{0} / {1}".format(info.name, table))

        src = QgsVectorLayer(
            "{0}|layername={1}".format(gpkg_path, table), "src", "ogr"
        )
        if not src.isValid():
            result.errors.append("Nie mozna otworzyc tabeli {0}".format(table))
            continue
        src.setSubsetString(S.layer_filter(info.name))

        target = previous.get((info.name, table))
        if target is None:
            target = naming.table_name_for(
                info.name, table, allocator, options.suffixes
            )

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = target
        opts.actionOnExistingFile = vector_file_writer_action("CreateOrOverwriteLayer")
        opts.layerOptions = ["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES"]
        opts.fileEncoding = "UTF-8"
        if segmentize:
            # zamiana lukow na odcinki: writer sam to zrobi, gdy wymusimy
            # prosty typ geometrii
            try:
                opts.overrideGeometryType = _linear_type(src.wkbType())
            except Exception:
                pass
        if feedback is not None:
            opts.feedback = feedback

        try:
            written = QgsVectorFileWriter.writeAsVectorFormatV3(
                src, gpkg_path, ctx, opts
            )
        except AttributeError:
            written = QgsVectorFileWriter.writeAsVectorFormatV2(
                src, gpkg_path, ctx, opts
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append("{0}/{1}: {2}".format(info.name, table, exc))
            continue

        err = written[0] if isinstance(written, (tuple, list)) else written
        if err not in (QgsVectorFileWriter.NoError, 0):
            msg = written[1] if isinstance(written, (tuple, list)) and len(written) > 1 else ""
            result.errors.append("{0}/{1}: {2}".format(info.name, table, msg))
            continue

        result.mapping[(info.name, table)] = target
        result.written += 1

    _write_mapping_table(gpkg_path, result.mapping, result.errors)
    if progress_cb is not None:
        progress_cb(100, "")
    return result


def _linear_type(wkb):
    """Odpowiednik liniowy typu krzywoliniowego (do segmentyzacji)."""
    from .qgis_compat import wkb_type

    curved = {
        "CompoundCurveZ": "LineStringZ",
        "CompoundCurve": "LineString",
        "CurvePolygonZ": "PolygonZ",
        "CurvePolygon": "Polygon",
        "MultiCurveZ": "MultiLineStringZ",
        "MultiSurfaceZ": "MultiPolygonZ",
    }
    for name, target in curved.items():
        try:
            if wkb == wkb_type(name):
                return wkb_type(target)
        except AttributeError:
            continue
    return wkb


def _write_mapping_table(gpkg_path, mapping, errors):
    if not mapping:
        return
    try:
        conn = sqlite3.connect(gpkg_path)
    except sqlite3.Error as exc:
        errors.append("Nie zapisano tabeli mapowania: {0}".format(exc))
        return
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS {0} ("
            "table_name TEXT PRIMARY KEY, "
            "cad_layer TEXT NOT NULL, "
            "source_table TEXT NOT NULL)".format(S.MAP_TABLE)
        )
        conn.executemany(
            "INSERT OR REPLACE INTO {0} (table_name, cad_layer, source_table) "
            "VALUES (?, ?, ?)".format(S.MAP_TABLE),
            [(t, cad, src) for (cad, src), t in mapping.items()],
        )
        conn.commit()
    except sqlite3.Error as exc:
        errors.append("Nie zapisano tabeli mapowania: {0}".format(exc))
    finally:
        conn.close()


def read_mapping(gpkg_path):
    """Odczytuje wczesniej zapisane mapowanie nazw tabel."""
    try:
        conn = sqlite3.connect(gpkg_path)
    except sqlite3.Error:
        return {}
    try:
        rows = conn.execute(
            "SELECT cad_layer, source_table, table_name FROM {0}".format(S.MAP_TABLE)
        ).fetchall()
        return {(cad, src): tbl for cad, src, tbl in rows}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
