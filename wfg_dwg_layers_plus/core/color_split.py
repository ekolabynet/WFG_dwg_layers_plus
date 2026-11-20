# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Podział warstwy CAD wg koloru, grubości i typu encji.

Po co. Część eksportów — zwłaszcza z systemów geodezyjnych — wrzuca całą
kreskę na warstwę ``0`` i rozróżnia treść wyłącznie **barwą**. Warstwa CAD
nie niesie wtedy żadnej informacji, więc podział „warstwa CAD × typ geometrii"
daje jedną wielką warstwę ``0_pline`` z kilkunastoma tysiącami obiektów.

Zanim sięgniesz po ten moduł, warto sprawdzić dwie rzeczy, bo bywają lepsze:

* czy kod obiektu nie siedzi w **XDATA** encji (kody grup 1000–1071) — QGIS ich
  nie zapisuje, ale da się je odczytać wprost z DXF-a i skleić po uchwycie,
* czy treść nie siedzi w **blokach**, gdzie warstwę niesie wstawienie.

Dopiero gdy obu nie ma, kolor jest jedynym sitem, jakie zostało.

Warstwy powstają jako filtry na wspólnej tabeli — bez kopiowania geometrii,
więc podział jest natychmiastowy i nic nie waży.
"""

import os
import sqlite3

try:
    from urllib.request import pathname2url
except ImportError:  # pragma: no cover — Python 2
    from urllib import pathname2url

from . import gpkg_schema as S

#: nazwy typów encji, które w praktyce warto rozdzielić
ETYPE_NAMES = {
    0: "3dface",
    1: "luk",
    3: "okrag",
    12: "elipsa",
    13: "szraf",
    17: "odcinek",
    18: "polilinia_lekka",
    20: "punkt",
    21: "polilinia",
    23: "solid",
    24: "splajn",
    25: "tekst",
}

#: tabele, które ma sens dzielić kolorem
SPLITTABLE = (S.T_POLYLINES, S.T_LINES, S.T_HATCHES, S.T_POINTS)


#: nazwy wymiarów podziału w kolejności, w jakiej trafiają do nazwy warstwy
DIM_COLOR = "color"
DIM_LWEIGHT = "lweight"
DIM_ETYPE = "etype"


def lweight_label(value):
    """Grubość DWG na czytelny opis.

    DWG trzyma grubość w setnych milimetra, a wartości ujemne to znaczniki
    dziedziczenia, nie liczby: -1 BYLAYER, -2 BYBLOCK, -3 domyślna.
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        return "gr?"
    if v == -1:
        return "gr_zwarstwy"
    if v == -2:
        return "gr_zbloku"
    if v == -3:
        return "gr_domyslna"
    if v < 0:
        return "gr{0}".format(v)
    return "gr{0}".format(("%g" % (v / 100.0)).replace(".", "-"))


class Bucket(object):
    """Jedna kombinacja rozróżniających wartości."""

    __slots__ = ("table", "color", "lweight", "etype", "count", "name", "dims")

    def __init__(self, table, color, lweight, etype, count, dims=None):
        self.table = table
        self.color = color
        self.lweight = lweight
        self.etype = etype
        self.count = count
        self.name = ""
        #: które wymiary są aktywne. Bez tego wartość NULL byłaby nie do
        #: odróżnienia od „nie dzielimy po tym wymiarze", a wtedy filtr
        #: kubełka zdegenerowałby się do całej warstwy CAD
        self.dims = tuple(dims) if dims is not None else tuple(
            d for d, v in (
                (DIM_COLOR, color), (DIM_LWEIGHT, lweight), (DIM_ETYPE, etype)
            ) if v is not None
        )

    @property
    def key(self):
        return (self.table, self.color, self.lweight, self.etype)

    #: klucz niezależny od tabeli — pod nim zapamiętujemy nazwy nadane przez
    #: użytkownika, żeby przy następnym opracowaniu nie trzeba było ich wpisywać
    @property
    def memory_key(self):
        parts = []
        for dim, value in (
            (DIM_COLOR, self.color),
            (DIM_LWEIGHT, self.lweight),
            (DIM_ETYPE, self.etype),
        ):
            if dim in self.dims:
                parts.append("{0}={1}".format(dim, value))
        return "|".join(parts)

    def auto_name(self):
        parts = []
        if DIM_COLOR in self.dims:
            if self.color is None:
                parts.append("kolor_brak")
            else:
                # kanał alfa tylko zaśmieca nazwę — w CAD jest zawsze 255
                skladowe = str(self.color).split(",")[:3]
                parts.append("kolor_" + "-".join(x.strip() for x in skladowe))
        if DIM_LWEIGHT in self.dims:
            parts.append(
                "gr_brak" if self.lweight is None else lweight_label(self.lweight)
            )
        if DIM_ETYPE in self.dims:
            parts.append(
                "typ_brak" if self.etype is None
                else ETYPE_NAMES.get(self.etype, "e{0}".format(self.etype))
            )
        return "_".join(parts) or "wszystko"

    def label(self):
        return self.name.strip() or self.auto_name()

    def filter_sql(self, cad_layer):
        parts = [S.layer_filter(cad_layer)]
        for dim, column, value, numeric in (
            (DIM_COLOR, S.C_COLOR, self.color, False),
            (DIM_LWEIGHT, "lweight", self.lweight, True),
            (DIM_ETYPE, S.C_ETYPE, self.etype, True),
        ):
            if dim not in self.dims:
                continue
            if value is None:
                parts.append('"{0}" IS NULL'.format(column))
            elif numeric:
                parts.append('"{0}" = {1}'.format(column, int(value)))
            else:
                parts.append('"{0}" = {1}'.format(column, S.sql_quote(value)))
        return " AND ".join(parts)

    def qcolor(self):
        from . import gpkg_reader

        return gpkg_reader.parse_color(self.color)


def _connect(gpkg_path):
    """Połączenie tylko do odczytu.

    Bez ``mode=ro`` literówka w ścieżce tworzyłaby pusty plik .gpkg, a my tu
    wyłącznie czytamy.
    """
    if not os.path.exists(gpkg_path):
        raise sqlite3.OperationalError(
            "Nie ma takiego pliku: {0}".format(gpkg_path)
        )
    return sqlite3.connect(
        "file:{0}?mode=ro".format(pathname2url(os.path.abspath(gpkg_path))),
        uri=True,
    )


def candidate_layers(gpkg_path, min_colors=2):
    """Warstwy CAD, które warto podzielić — mają więcej niż jeden kolor."""
    out = []
    try:
        conn = _connect(gpkg_path)
    except (sqlite3.Error, OSError):
        return out
    try:
        counts = {}
        for table in SPLITTABLE:
            try:
                rows = conn.execute(
                    'SELECT "{0}", COUNT(DISTINCT "{1}"), COUNT(*) FROM "{2}" '
                    "WHERE {3} GROUP BY \"{0}\"".format(
                        S.C_LAYER, S.C_COLOR, table, S.BASE_FILTER
                    )
                ).fetchall()
            except sqlite3.Error:
                continue
            for layer, n_colors, n_rows in rows:
                prev = counts.get(layer, (0, 0))
                counts[layer] = (max(prev[0], n_colors or 0), prev[1] + (n_rows or 0))
        out = sorted(
            (
                (layer, n_colors, n_rows)
                for layer, (n_colors, n_rows) in counts.items()
                if n_colors >= min_colors
            ),
            key=lambda r: -r[2],
        )
    finally:
        conn.close()
    return out


def scan(gpkg_path, cad_layer, tables=None, by_color=True,
         by_lweight=False, by_etype=False):
    """Zwraca listę :class:`Bucket` dla wskazanej warstwy CAD."""
    tables = tables or SPLITTABLE
    buckets = []
    dims = tuple(
        d for d, on in (
            (DIM_COLOR, by_color),
            (DIM_LWEIGHT, by_lweight),
            (DIM_ETYPE, by_etype),
        ) if on
    )
    conn = _connect(gpkg_path)
    try:
        for table in tables:
            cols, group = [], []
            if by_color:
                cols.append('"{0}"'.format(S.C_COLOR))
            if by_lweight:
                cols.append('"lweight"')
            if by_etype:
                cols.append('"{0}"'.format(S.C_ETYPE))
            if not cols:
                cols = ["NULL"]
            group = [c for c in cols if c != "NULL"]

            sql = 'SELECT {0}, COUNT(*) FROM "{1}" WHERE {2}'.format(
                ", ".join(cols), table, S.layer_filter(cad_layer)
            )
            if group:
                sql += " GROUP BY " + ", ".join(group)
            sql += " ORDER BY COUNT(*) DESC"
            try:
                rows = conn.execute(sql).fetchall()
            except sqlite3.Error:
                continue

            for row in rows:
                values = list(row[:-1])
                count = row[-1]
                if not count:
                    continue
                color = values.pop(0) if by_color else None
                lweight = values.pop(0) if by_lweight else None
                etype = values.pop(0) if by_etype else None
                buckets.append(
                    Bucket(table, color, lweight, etype, count, dims=dims)
                )
    finally:
        conn.close()
    return buckets


# ---------------------------------------------------------------------------
# budowa warstw
# ---------------------------------------------------------------------------


def _child_group(parent, name):
    """Podgrupa o danej nazwie. ``children()`` zwraca też warstwy, a one
    również mają ``name()``, więc sama nazwa nie wystarcza do rozpoznania."""
    from qgis.core import QgsLayerTree

    for node in parent.children():
        if QgsLayerTree.isGroup(node) and node.name() == name:
            return node
    return None


def _target_group(project, gpkg_path, tree_options):
    """Grupa rysunku, do której dołożymy podzielone warstwy.

    Szukamy najpierw grupy nazwanej jak plik — w projekcie z dwoma importami
    trafienie w „pierwszą grupę o nazwie 2_Linie" wsadziłoby warstwy do cudzego
    rysunku.
    """
    root = project.layerTreeRoot()
    stem = os.path.splitext(os.path.basename(gpkg_path))[0]
    kandydat = _child_group(root, stem)
    if kandydat is not None:
        return kandydat
    for group in root.findGroups(recursive=True):
        if group.name() == stem:
            return group

    nazwy_grup = set(tree_options.group_name(kind) for kind in S.GROUP_ORDER)
    for group in root.findGroups(recursive=True):
        if group.name() in nazwy_grup:
            rodzic = group.parent()
            if rodzic is not None:
                return rodzic
    return root


class SplitResult(object):
    def __init__(self):
        self.layers = []      # (kind, QgsVectorLayer)
        self.warnings = []

    @property
    def count(self):
        return len(self.layers)


def build_layers(gpkg_path, cad_layer, buckets, tree_options,
                 project=None, feedback=None):
    """Tworzy warstwy filtrowane i wkłada je do czterech grup geometrycznych."""
    from qgis.core import QgsProject, QgsVectorLayer

    from . import naming, styler

    project = project or QgsProject.instance()
    result = SplitResult()

    dwg_group = _target_group(project, gpkg_path, tree_options)

    grupy = {}
    for kind in S.GROUP_ORDER:
        nazwa = tree_options.group_name(kind)
        grupy[kind] = _child_group(dwg_group, nazwa) or dwg_group.addGroup(nazwa)

    pending = []
    for bucket in buckets:
        if feedback is not None and feedback.isCanceled():
            break
        nazwa = naming.display_name(
            bucket.label(), bucket.table, tree_options.suffixes
        )
        layer = QgsVectorLayer(
            "{0}|layername={1}".format(gpkg_path, bucket.table), nazwa, "ogr"
        )
        if not layer.isValid():
            result.warnings.append("Nie udało się otworzyć tabeli {0}".format(bucket.table))
            continue
        if not layer.setSubsetString(bucket.filter_sql(cad_layer)):
            result.warnings.append("Filtr odrzucony dla {0}".format(nazwa))
            continue
        styler.apply_style(layer, bucket.table, None, tree_options.style)
        # miniatura w legendzie prosto z koloru kubełka — tu znamy go dokładnie,
        # więc nie ma po co próbkować obiektów
        try:
            styler.apply_swatch(layer, bucket.qcolor())
        except Exception:
            pass
        kind = S.TABLE_KIND.get(bucket.table, S.KIND_LINE)
        pending.append((grupy[kind], layer, kind))

    if pending:
        project.addMapLayers([lyr for _, lyr, _ in pending], False)
        for group, layer, kind in pending:
            group.addLayer(layer)
            result.layers.append((kind, layer))

    return result


def remove_source_layers(gpkg_path, cad_layer, project=None):
    """Usuwa nierozdzielone warstwy tej warstwy CAD (np. ``0_pline``)."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    cel = S.layer_filter(cad_layer)
    target = os.path.normcase(os.path.abspath(gpkg_path))
    do_usuniecia = []
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        source = (layer.source() or "").split("|")[0]
        if os.path.normcase(os.path.abspath(source)) != target:
            continue
        try:
            if layer.subsetString().strip() == cel:
                do_usuniecia.append(layer.id())
        except Exception:
            continue
    if do_usuniecia:
        project.removeMapLayers(do_usuniecia)
    return len(do_usuniecia)
