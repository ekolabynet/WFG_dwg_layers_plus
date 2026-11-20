# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Ponowne nadanie stylów warstwom, które są już w projekcie.

Po co: przy dużym rysunku ponowny import trwa. Jeśli chcesz tylko zmienić
grubość zastępczą linii albo rozmiar punktów, nie ma powodu czytać DXF-a od
nowa — wystarczy przejść po drzewie warstw i nałożyć style jeszcze raz.

Rozpoznanie typu warstwy idzie trzema drogami, w tej kolejności:

1. ``layername=<tabela>`` w źródle — działa w trybie filtrów,
2. tabela ``dwgplus_layer_map`` w GeoPackage — działa po materializacji,
3. sufiks nazwy warstwy (``_hatch``, ``_line``, ``_pline``, ``_point``,
   ``_text``, ``_insert``) — działa zawsze, także po ręcznym przemianowaniu.
"""

import re

from qgis.core import QgsProject, QgsVectorLayer

from . import gpkg_schema as S
from . import styler

_LAYERNAME_RE = re.compile(r"layername=([^|]+)", re.IGNORECASE)

#: odwrócenie DEFAULT_SUFFIXES — sufiks nazwy -> tabela źródłowa
_SUFFIX_TO_TABLE = {v: k for k, v in S.DEFAULT_SUFFIXES.items()}

#: Sufiksy nazw warstw blokowych -> rodzaj geometrii.
#: UWAGA: warstwy blokowe nazywaja sie "blk_<blok>_<kind>", gdzie <kind> to
#: STALA KIND_* ("polygon"), a nie sufiks warstwy CAD ("_hatch"). Pomylenie
#: tych dwoch swiatow sprawialo, ze warstwy "blk_*_polygon" nie byly
#: rozpoznawane i zostawaly z domyslnym niebieskim wypelnieniem QGIS.
_BLOCK_SUFFIX_TO_KIND = {
    "_" + S.KIND_LINE: S.KIND_LINE,
    "_" + S.KIND_POLYGON: S.KIND_POLYGON,
    "_" + S.KIND_POINT: S.KIND_POINT,
    "_" + S.KIND_TEXT: S.KIND_TEXT,
    # aliasy na wypadek recznego przemianowania warstw
    "_hatch": S.KIND_POLYGON,
    "_pline": S.KIND_LINE,
}


class RestyleResult(object):
    def __init__(self):
        self.styled = 0
        self.skipped = 0
        self.anchors = 0
        self.details = []
        self.layer_ids = []   # warstwy, ktorym trzeba odswiezyc legende


def source_table(layer):
    """Nazwa tabeli GPKG, na której siedzi warstwa (albo None)."""
    match = _LAYERNAME_RE.search(layer.source() or "")
    return match.group(1) if match else None


def _table_from_name(name):
    for suffix, table in _SUFFIX_TO_TABLE.items():
        if name.endswith(suffix):
            return table
    return None


def _block_kind_from_name(name):
    for suffix, kind in _BLOCK_SUFFIX_TO_KIND.items():
        if name.endswith(suffix):
            return kind
    return None


def classify(layer, mapping=None):
    """Zwraca ``("entity", tabela)``, ``("block", kind)``, ``("anchor", None)``
    albo ``(None, None)`` dla warstwy spoza importu."""
    name = layer.name()

    if name.startswith("blk__anchor") or name.endswith("__anchor"):
        return "anchor", None

    if name.startswith("blk_"):
        kind = _block_kind_from_name(name)
        if kind is not None:
            return "block", kind

    table = source_table(layer)
    if table in S.ENTITY_TABLES:
        return "entity", table

    if mapping and table:
        src = mapping.get(table)
        if src in S.ENTITY_TABLES:
            return "entity", src

    table = _table_from_name(name)
    if table is not None:
        return "entity", table

    return None, None


def _mapping_for(layer):
    """``nazwa_tabeli -> tabela zrodlowa`` z ``dwgplus_layer_map``, jeśli jest."""
    source = layer.source() or ""
    gpkg = source.split("|")[0]
    if not gpkg.lower().endswith(".gpkg"):
        return {}
    try:
        from . import materializer

        return {
            table: src
            for (_cad, src), table in materializer.read_mapping(gpkg).items()
        }
    except Exception:
        return {}


def restyle_project(style_options=None, project=None, only_group=None):
    """Nakłada style na wszystkie rozpoznane warstwy w projekcie."""
    project = project or QgsProject.instance()
    opts = style_options or styler.StyleOptions()
    result = RestyleResult()

    root = project.layerTreeRoot()
    mapping_cache = {}

    for node in root.findLayers():
        layer = node.layer()
        if layer is None or not isinstance(layer, QgsVectorLayer):
            continue

        if only_group:
            path = []
            parent = node.parent()
            while parent is not None and parent is not root:
                path.append(parent.name())
                parent = parent.parent()
            if only_group.lower() not in " / ".join(path).lower():
                continue

        gpkg = (layer.source() or "").split("|")[0]
        # Tylko warstwy z GeoPackage. Bez tego heurystyka po nazwie moglaby
        # zlapac przypadkowa warstwe uzytkownika konczaca sie np. na "_text"
        # i podmienic jej renderer.
        if not gpkg.lower().endswith(".gpkg"):
            result.skipped += 1
            continue
        if gpkg not in mapping_cache:
            mapping_cache[gpkg] = _mapping_for(layer)

        kind, what = classify(layer, mapping_cache[gpkg])
        if kind is None:
            result.skipped += 1
            continue

        ok = False
        if kind == "entity":
            ok = styler.apply_style(layer, what, None, opts)
        elif kind == "block":
            ok = styler.style_block_layer(layer, what, None, opts)
        elif kind == "anchor":
            try:
                styler.style_anchor(layer, opts)
                ok = True
                result.anchors += 1
            except Exception as exc:  # noqa: BLE001
                result.details.append("{0}: {1}".format(layer.name(), exc))

        if ok:
            result.styled += 1
            result.layer_ids.append(layer.id())
        else:
            result.skipped += 1
            result.details.append(
                "Nie ostylowano: {0} ({1}/{2})".format(layer.name(), kind, what)
            )

    return result
