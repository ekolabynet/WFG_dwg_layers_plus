# -*- coding: utf-8 -*-
"""Bloki (INSERT) jako zlozone geometrie: jeden obiekt na jedno wstawienie.

Cala logika dziala na samym GeoPackage, bez zadnych zewnetrznych bibliotek,
korzystajac z kontraktu ``blocks`` / ``inserts`` / kolumna ``block``:

* ``blocks.name`` -> ``blocks.handle`` (wstawienie wskazuje blok po NAZWIE),
* punkt bazowy bloku to geometria wiersza w ``blocks``, nie atrybut,
* encja z ``block = <handle>`` nalezy do definicji tego bloku,
* ``block = -1`` to przestrzen modelu.

WARUNEK: import musi byc zrobiony BEZ rozwijania blokow (tryb "Add Only Insert
Points"), inaczej w tabelach sa jednoczesnie definicje i ich splaszczone kopie
i policzylibysmy geometrie dwa razy.

Trzy rzeczy, ktorych nie robi wbudowany importer, a ktore sa tutaj:

1. ochrona przed cyklami (blok A wstawia B, B wstawia A),
2. dziedziczenie warstwy ``0`` z wstawienia,
3. rozwiniecie MINSERT (tablic wierszy/kolumn).
"""

import math

from qgis.core import (
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from . import gpkg_schema as S
from . import naming, styler
from .affine import insert_matrix, minsert_offsets
from .qgis_compat import field_type, vector_file_writer_action

#: domyslny limit zagniezdzenia blokow
MAX_DEPTH = 16
#: domyslny limit encji na jedno wstawienie (zabezpieczenie przed eksplozja)
MAX_ENTITIES_PER_INSERT = 50000

#: mapowanie tabeli zrodlowej na rodzaj geometrii warstwy wynikowej
_KIND_OF = {
    S.T_POINTS: S.KIND_POINT,
    S.T_LINES: S.KIND_LINE,
    S.T_POLYLINES: S.KIND_LINE,
    S.T_HATCHES: S.KIND_POLYGON,
    S.T_TEXTS: S.KIND_TEXT,
}

_MEMORY_TYPE = {
    S.KIND_POINT: ("MultiPointZ", "MultiPoint"),
    S.KIND_LINE: ("MultiCurveZ", "MultiLineStringZ", "MultiLineString"),
    S.KIND_POLYGON: ("MultiSurfaceZ", "MultiPolygonZ", "MultiPolygon"),
    S.KIND_TEXT: ("PointZ", "Point"),
}


class BlockOptions(object):
    def __init__(self):
        self.max_depth = MAX_DEPTH
        self.max_entities = MAX_ENTITIES_PER_INSERT
        self.create_anchors = True
        self.store_in_gpkg = True
        self.keep_curves = True
        #: True odtwarza kolejnosc wbudowanego importera QGIS (obrot przed skala)
        self.qgis_transform_order = False
        self.inherit_layer_zero = True
        self.expand_minsert = True
        #: wyglad warstw wynikowych (styler.StyleOptions); ustawiany przez runner
        self.style = None


class BlockResult(object):
    def __init__(self):
        self.layers = []       # (nazwa_bloku, kind, QgsVectorLayer)
        self.anchor_layer = None
        self.instances = 0
        self.parts = 0
        self.warnings = []


# ---------------------------------------------------------------------------
# odczyt definicji
# ---------------------------------------------------------------------------


class _Definition(object):
    """Zawartosc jednej definicji bloku, wczytana raz i trzymana w pamieci."""

    __slots__ = ("items", "inserts")

    def __init__(self):
        self.items = []      # (kind, QgsGeometry, layer, color, linewidth, extra)
        self.inserts = []    # slowniki z parametrami wstawien zagniezdzonych

    @property
    def size(self):
        return len(self.items)


def _val(feature, name, default=None):
    try:
        v = feature[name]
    except (KeyError, IndexError):
        return default
    if v is None:
        return default
    try:
        from qgis.PyQt.QtCore import QVariant

        if isinstance(v, QVariant) and v.isNull():
            return default
    except Exception:
        pass
    return v


def _num(feature, name, default=0.0):
    v = _val(feature, name, default)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _open(gpkg_path, table):
    layer = QgsVectorLayer(
        "{0}|layername={1}".format(gpkg_path, table), table, "ogr"
    )
    return layer if layer.isValid() else None


def read_block_index(gpkg_path):
    """Zwraca ``(name -> handle, name -> (bx, by, bz))``."""
    names = {}
    bases = {}
    layer = _open(gpkg_path, S.T_BLOCKS)
    if layer is None:
        return names, bases
    for feat in layer.getFeatures():
        name = _val(feat, S.C_NAME)
        handle = _val(feat, S.C_HANDLE)
        if name is None or handle is None:
            continue
        try:
            handle = int(handle)
        except (TypeError, ValueError):
            continue
        names[name] = handle
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            bases[name] = (0.0, 0.0, 0.0)
            continue
        pt = geom.constGet()
        try:
            z = pt.z() if hasattr(pt, "z") else 0.0
            if z != z:      # QgsPoint.z() zwraca NaN dla geometrii 2D
                z = 0.0
            bases[name] = (pt.x(), pt.y(), z)
        except Exception:
            p = geom.asPoint()
            bases[name] = (p.x(), p.y(), 0.0)
    return names, bases


def read_definitions(gpkg_path, feedback=None):
    """Wczytuje zawartosc wszystkich definicji blokow: ``handle -> _Definition``."""
    defs = {}

    for table in S.BLOCK_CONTENT_TABLES:
        layer = _open(gpkg_path, table)
        if layer is None:
            continue
        kind = _KIND_OF.get(table, S.KIND_POINT)
        req = QgsFeatureRequest()
        req.setFilterExpression(
            '"{0}" <> {1}'.format(S.C_BLOCK, S.MODEL_SPACE_BLOCK)
        )
        for feat in layer.getFeatures(req):
            if feedback is not None and feedback.isCanceled():
                return defs
            handle = _val(feat, S.C_BLOCK)
            if handle is None:
                continue
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            extra = None
            if kind == S.KIND_TEXT:
                extra = {
                    "text": _val(feat, "text", ""),
                    "height": _num(feat, "height", 1.0),
                    "angle": _num(feat, "angle", 0.0),
                }
            defs.setdefault(int(handle), _Definition()).items.append(
                (
                    kind,
                    QgsGeometry(geom),
                    _val(feat, S.C_LAYER, ""),
                    _val(feat, S.C_COLOR, ""),
                    _num(feat, S.C_LINEWIDTH, 0.0),
                    extra,
                )
            )

    # wstawienia zagniezdzone (te z block <> -1)
    layer = _open(gpkg_path, S.T_INSERTS)
    if layer is not None:
        req = QgsFeatureRequest()
        req.setFilterExpression(
            '"{0}" <> {1}'.format(S.C_BLOCK, S.MODEL_SPACE_BLOCK)
        )
        for feat in layer.getFeatures(req):
            handle = _val(feat, S.C_BLOCK)
            if handle is None:
                continue
            row = _insert_row(feat)
            if row is None:
                continue
            defs.setdefault(int(handle), _Definition()).inserts.append(row)

    return defs


def _insert_row(feat):
    geom = feat.geometry()
    if geom is None or geom.isEmpty():
        return None
    pt = geom.constGet()
    try:
        x, y = pt.x(), pt.y()
        z = pt.z() if hasattr(pt, "z") else 0.0
    except Exception:
        p = geom.asPoint()
        x, y, z = p.x(), p.y(), 0.0
    if z != z:  # NaN
        z = 0.0
    return {
        "handle": _val(feat, S.C_HANDLE, 0),
        "name": _val(feat, S.C_NAME, ""),
        "layer": _val(feat, S.C_LAYER, ""),
        "color": _val(feat, S.C_COLOR, ""),
        "linetype": _val(feat, S.C_LINETYPE, ""),
        "linewidth": _num(feat, S.C_LINEWIDTH, 0.0),
        "x": x,
        "y": y,
        "z": z,
        "xscale": _num(feat, "xscale", 1.0),
        "yscale": _num(feat, "yscale", 1.0),
        "zscale": _num(feat, "zscale", 1.0),
        "angle": _num(feat, "angle", 0.0),
        "colcount": _num(feat, "colcount", 1.0),
        "rowcount": _num(feat, "rowcount", 1.0),
        "colspace": _num(feat, "colspace", 0.0),
        "rowspace": _num(feat, "rowspace", 0.0),
    }


def read_top_inserts(gpkg_path, cad_layers=None):
    """Wstawienia w przestrzeni modelu (``space = 0 AND block = -1``)."""
    layer = _open(gpkg_path, S.T_INSERTS)
    if layer is None:
        return []
    expr = S.BASE_FILTER
    if cad_layers:
        quoted = ", ".join(S.sql_quote(l) for l in cad_layers)
        expr = '"{0}" IN ({1}) AND {2}'.format(S.C_LAYER, quoted, expr)
    req = QgsFeatureRequest()
    req.setFilterExpression(expr)
    out = []
    for feat in layer.getFeatures(req):
        row = _insert_row(feat)
        if row is not None:
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# rozwijanie
# ---------------------------------------------------------------------------


def _resolve(value, fallback):
    """Rozwiazuje ``byblock`` na wartosc ze wstawienia."""
    if value is None:
        return fallback
    if isinstance(value, str) and value.strip().lower() == S.BYBLOCK:
        return fallback
    return value


#: ile kopii MINSERT dostaje pelny budzet encji, zanim wlaczy sie limit laczny
_FULL_BUDGET_COPIES = 16


class _Expander(object):
    def __init__(self, defs, names, bases, options, result, feedback=None):
        self.defs = defs
        self.names = names
        self.bases = bases
        self.opt = options
        self.result = result
        self.feedback = feedback
        self._warned_budget = False
        self._warned_missing = set()

    def _warn_once(self, key, message):
        if key in self._warned_missing:
            return
        self._warned_missing.add(key)
        self.result.warnings.append(message)

    def expand(self, insert_row):
        """Zwraca ``{kind: [ (geom, layer, color, linewidth, extra), ... ]}``."""
        out = {}
        block_handle = self.names.get(insert_row["name"])
        if block_handle is None:
            self._warn_once(
                ("missing", insert_row["name"]),
                "Blok '{0}' nie ma definicji — pominiety.".format(insert_row["name"]),
            )
            return out
        base = self.bases.get(insert_row["name"], (0.0, 0.0, 0.0))

        offsets = self._offsets(insert_row)
        # Budzet liczymy na KAZDA kopie MINSERT osobno — inaczej tablica 10x10
        # zjadlaby limit na pierwszych kopiach i reszta zniknelaby bez slowa.
        # Jednoczesnie trzymamy limit laczny, zeby jedna patologiczna tablica
        # nie zamrozila QGIS-a na miliardach geometrii.
        remaining = self.opt.max_entities * min(len(offsets), _FULL_BUDGET_COPIES)

        for dx, dy in offsets:
            if self.feedback is not None and self.feedback.isCanceled():
                break
            if remaining <= 0:
                self._warn_budget()
                break
            budget = [min(self.opt.max_entities, remaining)]
            start = budget[0]
            matrix = insert_matrix(
                insert_row["x"] + dx,
                insert_row["y"] + dy,
                insert_row["z"],
                base[0],
                base[1],
                base[2],
                insert_row["xscale"],
                insert_row["yscale"],
                insert_row["zscale"],
                insert_row["angle"],
                parent=None,
                rotate_before_scale=self.opt.qgis_transform_order,
            )
            inherit = {
                "layer": insert_row["layer"],
                "color": insert_row["color"],
                "linewidth": insert_row["linewidth"],
            }
            self._collect(block_handle, matrix, 0, {block_handle}, out, inherit, budget)
            remaining -= start - budget[0]
        return out

    def _warn_budget(self):
        if self._warned_budget:
            return
        self._warned_budget = True
        self.result.warnings.append(
            "Przekroczono limit {0} encji na wstawienie — czesc geometrii "
            "blokow zostala pominieta. Podnies limit w oknie importu.".format(
                self.opt.max_entities
            )
        )

    def _offsets(self, row):
        if not self.opt.expand_minsert:
            return [(0.0, 0.0)]
        return minsert_offsets(
            row["colcount"], row["rowcount"],
            row["colspace"], row["rowspace"], row["angle"],
        )

    def _collect(self, block_handle, matrix, depth, visited, out, inherit, budget):
        definition = self.defs.get(block_handle)
        if definition is None:
            return
        qt = matrix.to_qtransform()

        for kind, geom, layer_name, color, linewidth, extra in definition.items:
            if budget[0] <= 0:
                self._warn_budget()
                return
            budget[0] -= 1
            g = QgsGeometry(geom)
            try:
                g.transform(qt, matrix.zt, matrix.zs)
            except TypeError:
                g.transform(qt)
            eff_layer = layer_name
            if self.opt.inherit_layer_zero and str(layer_name) == S.LAYER_ZERO:
                eff_layer = inherit["layer"] or layer_name
            eff_color = _resolve(color, inherit["color"])
            eff_lw = linewidth
            if eff_lw is None or eff_lw < 0.0:
                eff_lw = inherit["linewidth"]
            new_extra = extra
            if kind == S.KIND_TEXT and extra is not None:
                new_extra = dict(extra)
                # wysokosc tekstu skaluje sie jak blok, kat sie sumuje
                scale = math.sqrt(abs(matrix.determinant)) or 1.0
                new_extra["height"] = extra["height"] * scale
                new_extra["angle"] = extra["angle"] + matrix.rotation_deg
            out.setdefault(kind, []).append(
                (g, eff_layer, eff_color, eff_lw, new_extra)
            )

        for row in definition.inserts:
            child = self.names.get(row["name"])
            if child is None:
                continue
            if child in visited:
                self._warn_once(
                    ("cycle", row["name"]),
                    "Wykryto cykl w blokach ('{0}') — rekurencja przerwana.".format(
                        row["name"]
                    ),
                )
                continue
            if depth + 1 >= self.opt.max_depth:
                self._warn_once(
                    ("depth", row["name"]),
                    "Przekroczono limit zagniezdzenia blokow ({0}) przy '{1}'.".format(
                        self.opt.max_depth, row["name"]
                    ),
                )
                continue
            base = self.bases.get(row["name"], (0.0, 0.0, 0.0))
            child_inherit = {
                "layer": _resolve(row["layer"], inherit["layer"]),
                "color": _resolve(row["color"], inherit["color"]),
                "linewidth": row["linewidth"] if row["linewidth"] >= 0 else inherit["linewidth"],
            }
            for dx, dy in self._offsets(row):
                m = insert_matrix(
                    row["x"] + dx, row["y"] + dy, row["z"],
                    base[0], base[1], base[2],
                    row["xscale"], row["yscale"], row["zscale"], row["angle"],
                    parent=matrix,
                    rotate_before_scale=self.opt.qgis_transform_order,
                )
                self._collect(
                    child, m, depth + 1, visited | {child}, out, child_inherit, budget
                )


# ---------------------------------------------------------------------------
# warstwy wynikowe
# ---------------------------------------------------------------------------


def _base_fields():
    fields = QgsFields()
    fields.append(QgsField("insert_handle", field_type("Int")))
    fields.append(QgsField("block_name", field_type("QString")))
    fields.append(QgsField("cad_layer", field_type("QString")))
    fields.append(QgsField("xscale", field_type("Double")))
    fields.append(QgsField("yscale", field_type("Double")))
    fields.append(QgsField("zscale", field_type("Double")))
    fields.append(QgsField("angle_deg", field_type("Double")))
    fields.append(QgsField("x", field_type("Double")))
    fields.append(QgsField("y", field_type("Double")))
    fields.append(QgsField("n_parts", field_type("Int")))
    fields.append(QgsField(S.C_COLOR, field_type("QString")))
    fields.append(QgsField(S.C_LINEWIDTH, field_type("Double")))
    return fields


def _text_fields():
    fields = _base_fields()
    fields.append(QgsField("text", field_type("QString")))
    fields.append(QgsField("height", field_type("Double")))
    fields.append(QgsField("angle", field_type("Double")))
    return fields


def _make_memory_layer(name, kind, crs_authid, keep_curves):
    types = list(_MEMORY_TYPE.get(kind, ("PointZ",)))
    if not keep_curves:
        types = [t for t in types if "Curve" not in t and "Surface" not in t] or types
    fields = _text_fields() if kind == S.KIND_TEXT else _base_fields()
    for wkb in types:
        uri = wkb
        if crs_authid:
            uri += "?crs=" + crs_authid
            sep = "&"
        else:
            sep = "?"
        uri += sep + "index=yes"
        layer = QgsVectorLayer(uri, name, "memory")
        if layer.isValid():
            if not crs_authid:
                # bez jawnego CRS dostawca pamieciowy podstawia EPSG:4326,
                # a wspolrzedne sa w jednostkach rysunku — lepiej zostawic
                # uklad nieokreslony niz zadeklarowac falszywy
                from qgis.core import QgsCoordinateReferenceSystem

                layer.setCrs(QgsCoordinateReferenceSystem())
            layer.dataProvider().addAttributes(fields.toList())
            layer.updateFields()
            return layer
    return None


def _collect_geometry(parts, keep_curves):
    """Skleja czesci w jedna geometrie wieloczesciowa.

    ``QgsGeometry.collectGeometry`` przyjmuje typ PIERWSZEJ geometrii z listy,
    a kolejne dokladane czesci sa do niego dopasowywane. Gdyby pierwsza czescia
    byla zwykla linia, wszystkie luki zostalyby po cichu zsegmentyzowane —
    dlatego przy ``keep_curves`` przesuwamy czesc krzywoliniowa na poczatek,
    a bez niego segmentyzujemy wszystko jawnie.
    """
    geoms = [g for g in parts if g is not None and not g.isEmpty()]
    if not geoms:
        return None
    if keep_curves:
        for i, g in enumerate(geoms):
            try:
                curved = g.constGet().hasCurvedSegments()
            except Exception:
                curved = False
            if curved:
                if i:
                    geoms.insert(0, geoms.pop(i))
                break
    else:
        flat = []
        for g in geoms:
            try:
                if g.constGet().hasCurvedSegments():
                    g = QgsGeometry(g.constGet().segmentize())
            except Exception:
                pass
            flat.append(g)
        geoms = flat
    try:
        combined = QgsGeometry.collectGeometry(geoms)
    except Exception:
        return None
    if combined is None or combined.isEmpty():
        return None
    return combined


def build_block_layers(
    gpkg_path,
    inv,
    cad_layers,
    options,
    feedback=None,
    progress_cb=None,
    crs_authid=None,
):
    """Glowna funkcja: sklada bloki w zlozone geometrie i zwraca warstwy.

    :param crs_authid: uklad wybrany przez uzytkownika; ma pierwszenstwo nad
        ukladem odczytanym z GeoPackage
    :returns: :class:`BlockResult`
    """
    result = BlockResult()
    names, bases = read_block_index(gpkg_path)
    if not names:
        result.warnings.append("Brak definicji blokow w pliku.")
        return result

    defs = read_definitions(gpkg_path, feedback)
    if not defs:
        result.warnings.append(
            "Definicje blokow sa puste. Czy import zostal wykonany w trybie "
            "'Add Only Insert Points' (bez rozwijania blokow)?"
        )

    inserts = read_top_inserts(gpkg_path, cad_layers)
    if not inserts:
        result.warnings.append("Brak wstawien blokow w przestrzeni modelu.")
        return result

    crs = crs_authid or (inv.crs_authid if inv is not None else None)
    expander = _Expander(defs, names, bases, options, result, feedback)

    layers = {}      # (block_name, kind) -> QgsVectorLayer
    buffers = {}     # (block_name, kind) -> lista QgsFeature
    anchor_feats = []

    total = len(inserts) or 1
    for i, row in enumerate(inserts):
        if feedback is not None and feedback.isCanceled():
            break
        if progress_cb is not None and i % 50 == 0:
            progress_cb(int(100.0 * i / total), row.get("name", ""))

        collected = expander.expand(row)
        if not collected:
            continue
        result.instances += 1
        block_name = row["name"] or "blok"
        angle_deg = math.degrees(row["angle"] or 0.0)
        n_total = sum(len(v) for v in collected.values())
        result.parts += n_total

        for kind, items in collected.items():
            key = (block_name, kind)
            if key not in layers:
                lyr = _make_memory_layer(
                    naming.block_layer_name(block_name, kind),
                    kind,
                    crs,
                    options.keep_curves,
                )
                if lyr is None:
                    result.warnings.append(
                        "Nie udalo sie utworzyc warstwy dla bloku {0}/{1}".format(
                            block_name, kind
                        )
                    )
                    continue
                layers[key] = lyr
                buffers[key] = []
            lyr = layers.get(key)
            if lyr is None:
                continue

            if kind == S.KIND_TEXT:
                for geom, cad_layer, color, lw, extra in items:
                    feat = QgsFeature(lyr.fields())
                    feat.setGeometry(geom)
                    _fill_base(feat, row, block_name, cad_layer, angle_deg, 1, color, lw)
                    feat["text"] = (extra or {}).get("text", "")
                    feat["height"] = (extra or {}).get("height", 1.0)
                    feat["angle"] = (extra or {}).get("angle", 0.0)
                    buffers[key].append(feat)
            else:
                geom = _collect_geometry([it[0] for it in items], options.keep_curves)
                if geom is None:
                    continue
                first = items[0]
                feat = QgsFeature(lyr.fields())
                feat.setGeometry(geom)
                _fill_base(
                    feat, row, block_name,
                    first[1] or row["layer"], angle_deg, len(items),
                    first[2] or row["color"], first[3],
                )
                buffers[key].append(feat)

        if options.create_anchors:
            anchor_feats.append((row, block_name, angle_deg, n_total))

    # zapis buforow
    for key, feats in buffers.items():
        lyr = layers[key]
        if feats:
            if not lyr.dataProvider().addFeatures(feats):
                errors = []
                try:
                    errors = list(lyr.dataProvider().errors())
                except Exception:
                    pass
                result.warnings.append(
                    "Nie wszystkie obiekty trafily do warstwy {0}: {1}".format(
                        lyr.name(), "; ".join(errors) or "nieznany blad"
                    )
                )
            lyr.updateExtents()

    for (block_name, kind), lyr in sorted(layers.items()):
        if lyr.featureCount() == 0:
            continue
        styler.style_block_layer(lyr, kind, None, options.style)
        result.layers.append((block_name, kind, lyr))

    if options.create_anchors and anchor_feats:
        result.anchor_layer = _build_anchor_layer(anchor_feats, crs)
        if result.anchor_layer is not None:
            styler.style_anchor(result.anchor_layer, options.style)

    if options.store_in_gpkg:
        _persist(gpkg_path, result, options.style)

    if progress_cb is not None:
        progress_cb(100, "")
    return result


def _fill_base(feat, row, block_name, cad_layer, angle_deg, n_parts, color, linewidth):
    feat["insert_handle"] = int(row.get("handle") or 0)
    feat["block_name"] = block_name
    feat["cad_layer"] = cad_layer or ""
    feat["xscale"] = row["xscale"]
    feat["yscale"] = row["yscale"]
    feat["zscale"] = row["zscale"]
    feat["angle_deg"] = angle_deg
    feat["x"] = row["x"]
    feat["y"] = row["y"]
    feat["n_parts"] = int(n_parts)
    feat[S.C_COLOR] = color if isinstance(color, str) else ""
    feat[S.C_LINEWIDTH] = float(linewidth or 0.0)


def _build_anchor_layer(anchor_feats, crs):
    uri = "PointZ"
    if crs:
        uri += "?crs=" + crs
    layer = QgsVectorLayer(uri, "blk__anchor", "memory")
    if not layer.isValid():
        return None
    if not crs:
        from qgis.core import QgsCoordinateReferenceSystem

        layer.setCrs(QgsCoordinateReferenceSystem())
    layer.dataProvider().addAttributes(_base_fields().toList())
    layer.updateFields()

    from qgis.core import QgsPoint

    feats = []
    for row, block_name, angle_deg, n_total in anchor_feats:
        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry(QgsPoint(row["x"], row["y"], row["z"])))
        _fill_base(
            feat, row, block_name, row["layer"], angle_deg, n_total,
            row["color"], row["linewidth"],
        )
        feats.append(feat)
    layer.dataProvider().addFeatures(feats)
    layer.updateExtents()
    return layer


def _persist(gpkg_path, result, style_opts=None):
    """Przenosi warstwy pamieciowe do GeoPackage, zeby przetrwaly sesje."""
    from . import gpkg_reader

    ctx = QgsProject.instance().transformContext() or QgsCoordinateTransformContext()

    # Nazwy blokow potrafia sie zejsc po sanityzacji (np. 'Słup-1' i 'Slup 1'),
    # a CreateOrOverwriteLayer nadpisalby jedna druga bez slowa — stad allocator.
    # Jednoczesnie WLASNE tabele z poprzedniego przebiegu musza zostac
    # nadpisane, a nie obrosnac w _2, _3, ... przy kazdym powtorzeniu importu.
    planned = {naming.sanitize_table_name(mem.name()) for _, _, mem in result.layers}
    if result.anchor_layer is not None:
        planned.add(naming.sanitize_table_name(result.anchor_layer.name()))
    allocator = naming.NameAllocator(
        {
            t
            for t in gpkg_reader.existing_table_names(gpkg_path)
            if t not in planned
        }
    )
    replaced = []
    for block_name, kind, mem in result.layers:
        target = allocator.allocate(mem.name())
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = target
        opts.actionOnExistingFile = vector_file_writer_action("CreateOrOverwriteLayer")
        opts.layerOptions = ["GEOMETRY_NAME=geom", "SPATIAL_INDEX=YES"]
        opts.fileEncoding = "UTF-8"
        try:
            written = QgsVectorFileWriter.writeAsVectorFormatV3(
                mem, gpkg_path, ctx, opts
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append("Zapis {0}: {1}".format(target, exc))
            replaced.append((block_name, kind, mem))
            continue
        err = written[0] if isinstance(written, (tuple, list)) else written
        if err not in (QgsVectorFileWriter.NoError, 0):
            result.warnings.append("Zapis {0} nieudany.".format(target))
            replaced.append((block_name, kind, mem))
            continue
        new = QgsVectorLayer(
            "{0}|layername={1}".format(gpkg_path, target), mem.name(), "ogr"
        )
        if new.isValid():
            styler.style_block_layer(new, kind, None, style_opts)
            replaced.append((block_name, kind, new))
        else:
            replaced.append((block_name, kind, mem))
    result.layers = replaced

    if result.anchor_layer is not None:
        target = allocator.allocate(result.anchor_layer.name())
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = target
        opts.actionOnExistingFile = vector_file_writer_action("CreateOrOverwriteLayer")
        opts.fileEncoding = "UTF-8"
        try:
            QgsVectorFileWriter.writeAsVectorFormatV3(
                result.anchor_layer, gpkg_path, ctx, opts
            )
            new = QgsVectorLayer(
                "{0}|layername={1}".format(gpkg_path, target), "blk__anchor", "ogr"
            )
            if new.isValid():
                styler.style_anchor(new, style_opts)
                result.anchor_layer = new
        except Exception as exc:  # noqa: BLE001
            result.warnings.append("Zapis kotwic: {0}".format(exc))
