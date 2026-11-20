# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Spiecie calosci: zrodlo -> GPKG -> drzewo warstw (+ bloki)."""

import os

from qgis.core import Qgis, QgsFeedback, QgsMessageLog, QgsProject

from . import blocks as blocks_mod
from . import gpkg_reader, gpkg_schema as S, materializer, producer_builtin
from . import producer_ogr, tree_builder

LOG_TAG = "WFG DWG Layers+"


def log(message, level=Qgis.Info):
    QgsMessageLog.logMessage(str(message), LOG_TAG, level)


class RunConfig(object):
    def __init__(self):
        self.source_path = None          # DWG / DXF / GPKG
        self.gpkg_path = None            # docelowy / zrodlowy GeoPackage
        self.crs_authid = None
        self.use_curves = True
        self.cad_layers = []             # nazwy warstw CAD do zaimportowania
        self.tree = tree_builder.TreeOptions()
        self.block = blocks_mod.BlockOptions()
        self.segmentize_on_materialize = False
        #: False = wymus nowe nazwy tabel zamiast nadpisac poprzednie
        self.reuse_table_names = True
        self.use_own_importer = False    # producent C/D zamiast wbudowanego


class RunResult(object):
    def __init__(self):
        self.gpkg_path = None
        self.inventory = None
        self.tree = None
        self.blocks = None
        self.materialized = None
        self.messages = []

    def summary(self):
        parts = []
        if self.tree is not None:
            parts.append("warstw: {0}".format(self.tree.count))
        if self.materialized is not None:
            parts.append("zmaterializowanych tabel: {0}".format(self.materialized.written))
        if self.blocks is not None and self.blocks.instances:
            parts.append(
                "blokow: {0} wstawien / {1} czesci".format(
                    self.blocks.instances, self.blocks.parts
                )
            )
        return ", ".join(parts) or "brak warstw"


def default_gpkg_for(source_path):
    stem, ext = os.path.splitext(source_path)
    if ext.lower() == ".gpkg":
        return source_path
    return stem + ".gpkg"


def prepare_gpkg(config, iface=None, feedback=None, progress_cb=None):
    """Doprowadza do istnienia GeoPackage w schemacie QGIS i zwraca jego sciezke."""
    source = config.source_path or ""
    ext = os.path.splitext(source)[1].lower()

    if ext == ".gpkg":
        if not gpkg_reader.looks_like_dwg_gpkg(source):
            raise gpkg_reader.GpkgReadError(
                "Wskazany GeoPackage nie pochodzi z importu DWG/DXF "
                "(brak tabel 'layers' i 'blocks')."
            )
        return source

    if config.use_own_importer:
        target = config.gpkg_path or default_gpkg_for(source)
        dxf = source
        if ext == ".dwg":
            if progress_cb:
                progress_cb(0, "Konwersja DWG -> DXF...")
            dxf = producer_ogr.convert_dwg_to_dxf(source)
        # import_dxf moze zwrocic inna sciezke, jesli cel byl juz zajety
        return producer_ogr.import_dxf(
            dxf,
            target,
            crs_authid=config.crs_authid,
            feedback=feedback,
            progress_cb=progress_cb,
        )

    # producent B: wbudowany dialog QGIS
    return producer_builtin.run_builtin_import(
        iface, config.tree.block_mode, config.use_curves
    )


def run(config, iface=None, feedback=None, progress_cb=None):
    """Wykonuje pelny import. Zwraca :class:`RunResult`."""
    feedback = feedback or QgsFeedback()
    result = RunResult()

    def report(pct, msg=""):
        if progress_cb is not None:
            progress_cb(pct, msg)

    report(0, "Przygotowanie zrodla...")
    gpkg = prepare_gpkg(config, iface, feedback, progress_cb)
    result.gpkg_path = gpkg
    config.gpkg_path = gpkg

    report(15, "Inwentaryzacja warstw...")
    inv = gpkg_reader.inventory(gpkg, feedback)
    result.inventory = inv

    # Pusta lista = "uzytkownik nie wybieral" (np. import prosto z DWG, gdzie
    # wyboru dokonuje wbudowany dialog). Okno pilnuje, zeby swiadome odznaczenie
    # wszystkiego nie trafilo tutaj jako "wszystko".
    cad_layers = config.cad_layers or [l.name for l in inv.non_empty()]

    materialized = None
    if config.tree.layer_mode == S.LayerMode.MATERIALIZE:
        report(25, "Materializacja warstw...")
        materialized = materializer.materialize(
            gpkg, inv, cad_layers, config.tree, feedback,
            config.segmentize_on_materialize,
            lambda p, m: report(25 + int(p * 0.35), m),
            reuse_previous=config.reuse_table_names,
        )
        result.materialized = materialized
        for err in materialized.errors:
            log(err, Qgis.Warning)
            result.messages.append(err)

    # bloki dziedzicza ten sam wyglad co reszta importu
    config.block.style = config.tree.style

    report(60, "Budowa drzewa warstw...")
    tree = tree_builder.build_tree(
        gpkg, inv, cad_layers, config.tree,
        QgsProject.instance(), feedback,
        materialized.mapping if materialized else None,
    )
    result.tree = tree
    for warning in tree.warnings:
        log(warning, Qgis.Warning)

    if config.tree.block_mode == S.BlockMode.COMPOSITE:
        report(75, "Skladanie blokow...")
        if inv.expanded:
            msg = (
                "Uwaga: ten GeoPackage wyglada na zaimportowany z rozwinieciem "
                "blokow. Definicje blokow moga byc niekompletne — zaimportuj "
                "ponownie w trybie bez rozwijania."
            )
            log(msg, Qgis.Warning)
            result.messages.append(msg)
        blk = blocks_mod.build_block_layers(
            gpkg, inv, cad_layers, config.block, feedback,
            lambda p, m: report(75 + int(p * 0.2), m),
            crs_authid=config.crs_authid,
        )
        result.blocks = blk
        for warning in set(blk.warnings):
            log(warning, Qgis.Warning)
        entries = list(blk.layers)
        if blk.anchor_layer is not None:
            entries.append(("_kotwice", S.KIND_POINT, blk.anchor_layer))
        if entries:
            tree_builder.add_block_group(
                tree.root_group, entries, config.tree, QgsProject.instance()
            )

    report(100, "Gotowe.")
    log("Import zakonczony: {0}".format(result.summary()))
    return result
