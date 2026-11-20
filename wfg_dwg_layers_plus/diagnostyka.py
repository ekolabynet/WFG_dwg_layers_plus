# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Diagnostyka stylów WFG DWG Layers+.

Jak użyć:
  1. QGIS → Wtyczki → Konsola Pythona
  2. wklej całą zawartość tego pliku i naciśnij Enter
     (albo: exec(open(r"C:\\sciezka\\do\\diagnostyka.py", encoding="utf-8").read()))

Skrypt nie zmienia niczego w projekcie. Zapisuje raport tekstowy obok pliku
projektu (albo w katalogu tymczasowym) i wypisuje ścieżkę — ten plik można
odesłać. Raport zawiera tylko metadane stylów i statystyki kolumn, nie zawiera
geometrii ani treści rysunku.
"""

import os
import tempfile

from qgis.core import (
    Qgis,
    QgsProject,
    QgsVectorLayer,
)

MAX_LAYERS = 400


def _unit_name(value):
    for holder in ("Qgis", "QgsUnitTypes"):
        try:
            mod = __import__("qgis.core", fromlist=[holder])
            owner = getattr(mod, holder)
        except Exception:
            continue
        for attr in dir(owner):
            if attr.startswith("Render") and getattr(owner, attr, None) == value:
                return attr
    return str(value)


def _dd_report(props, owner_enum=None):
    out = []
    try:
        keys = props.propertyKeys()
    except Exception:
        return out
    for key in keys:
        try:
            prop = props.property(key)
            if prop is None or not prop.isActive():
                continue
            out.append("        [{0}] {1}".format(key, prop.asExpression()))
        except Exception:
            continue
    return out


def _symbol_report(symbol, lines):
    if symbol is None:
        lines.append("      (brak symbolu)")
        return
    lines.append("      symbol: {0}, warstw: {1}".format(
        type(symbol).__name__, symbol.symbolLayerCount()))
    for i in range(symbol.symbolLayerCount()):
        sl = symbol.symbolLayer(i)
        desc = "      [{0}] {1}".format(i, type(sl).__name__)
        for getter, unit_getter, label in (
            ("width", "widthUnit", "width"),
            ("size", "sizeUnit", "size"),
            ("strokeWidth", "strokeWidthUnit", "strokeWidth"),
        ):
            if hasattr(sl, getter):
                try:
                    value = getattr(sl, getter)()
                    unit = ""
                    if hasattr(sl, unit_getter):
                        unit = " " + _unit_name(getattr(sl, unit_getter)())
                    desc += "  {0}={1}{2}".format(label, value, unit)
                except Exception:
                    pass
        try:
            desc += "  color={0}".format(sl.color().name())
        except Exception:
            pass
        lines.append(desc)
        try:
            lines.extend(_dd_report(sl.dataDefinedProperties()))
        except Exception:
            pass


def _field_stats(layer, lines):
    names = [f.name() for f in layer.fields()]
    for field in ("linewidth", "width", "color", "height", "angle"):
        if field not in names:
            continue
        idx = layer.fields().indexOf(field)
        try:
            if field == "color":
                values = layer.uniqueValues(idx, 6)
                lines.append("      {0}: przykłady {1}".format(
                    field, sorted(str(v) for v in values)))
            else:
                mn = layer.minimumValue(idx)
                mx = layer.maximumValue(idx)
                lines.append("      {0}: min={1} max={2}".format(field, mn, mx))
        except Exception as exc:
            lines.append("      {0}: nie odczytano ({1})".format(field, exc))


def run(only_group=None, path=None):
    project = QgsProject.instance()
    lines = []
    lines.append("WFG DWG Layers+ — raport diagnostyczny stylów")
    lines.append("QGIS {0} ({1})".format(Qgis.QGIS_VERSION, Qgis.QGIS_RELEASE_NAME))
    lines.append("projekt: {0}".format(project.fileName() or "(niezapisany)"))
    lines.append("=" * 78)

    root = project.layerTreeRoot()
    nodes = root.findLayers()
    shown = 0

    for node in nodes:
        layer = node.layer()
        if layer is None or not isinstance(layer, QgsVectorLayer):
            continue
        parents = []
        parent = node.parent()
        while parent is not None and parent is not root:
            parents.append(parent.name())
            parent = parent.parent()
        path_txt = " / ".join(reversed(parents))
        if only_group and only_group.lower() not in path_txt.lower():
            continue
        shown += 1
        if shown > MAX_LAYERS:
            lines.append("... (obcięto, więcej niż {0} warstw)".format(MAX_LAYERS))
            break

        lines.append("")
        lines.append("WARSTWA: {0}".format(layer.name()))
        lines.append("   grupa: {0}".format(path_txt or "(korzeń)"))
        lines.append("   źródło: {0}".format(layer.source()))
        lines.append("   dostawca: {0}, geometria: {1}".format(
            layer.providerType(), layer.wkbType()))
        try:
            lines.append("   filtr: {0}".format(layer.subsetString() or "(brak)"))
        except Exception:
            pass
        lines.append("   obiektów: {0}".format(layer.featureCount()))
        lines.append("   CRS: {0}".format(layer.crs().authid() or "(nieokreślony)"))
        lines.append("   widoczna w legendzie: {0}".format(node.isVisible()))

        renderer = layer.renderer()
        lines.append("   renderer: {0}".format(
            type(renderer).__name__ if renderer else "(brak)"))
        if renderer is not None and hasattr(renderer, "symbol"):
            try:
                _symbol_report(renderer.symbol(), lines)
            except Exception as exc:
                lines.append("      (nie odczytano symbolu: {0})".format(exc))

        try:
            labeling = layer.labeling()
            lines.append("   etykiety: {0}, włączone: {1}".format(
                type(labeling).__name__ if labeling else "(brak)",
                layer.labelsEnabled()))
        except Exception:
            pass

        _field_stats(layer, lines)

    lines.append("")
    lines.append("Przeanalizowano warstw: {0}".format(shown))

    if path is None:
        base = os.path.dirname(project.fileName()) or tempfile.gettempdir()
        path = os.path.join(base, "wfg_dwg_layers_plus_diagnostyka.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print("\n".join(lines[:60]))
    print("")
    print("=" * 78)
    print("Pełny raport zapisany w:")
    print(path)
    print("=" * 78)
    return path


run()
