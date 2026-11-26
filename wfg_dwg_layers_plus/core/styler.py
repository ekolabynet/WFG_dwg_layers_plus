# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Stylizacja warstw — odtworzenie tego, co robi wbudowany dialog importu DWG.

Wszystko przez wlasciwosci definiowane danymi na kolumnie ``color``
(string 'R,G,B,A') i ``linewidth`` (milimetry). Dzieki temu jeden styl obsluguje
dowolna liczbe warstw CAD i nie trzeba nic renderowac na piechote.
"""

from qgis.core import (
    QgsFillSymbol,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsMessageLog,
    Qgis,
    QgsSimpleMarkerSymbolLayer,
    QgsNullSymbolRenderer,
    QgsPalLayerSettings,
    QgsProperty,
    QgsSingleSymbolRenderer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsTextFormat,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import Qt

from . import gpkg_schema as S
from .qgis_compat import (
    enum_value,
    label_property,
    render_unit,
    symbol_property,
)
from ..i18n import tr
from .log import warn_exception


class StyleOptions(object):
    """Parametry wygladu, ktore uzytkownik moze podkrecic w oknie importu."""

    def __init__(self):
        #: grubosc zastepcza dla encji, ktore nie maja wlasnej (mm).
        #: DWG czesto zostawia linewidth = 0 albo -1 (BYBLOCK) i wtedy
        #: wlasciwosc definiowana danymi jest nieprawidlowa, a QGIS podstawia
        #: swoja domyslna 0.26 mm — czyli grube linie tam, gdzie maja byc wlosowe
        self.line_width_mm = 0.10
        #: rozmiar znacznika punktow CAD (mm), gdy sa wlaczone
        self.point_size_mm = 0.8
        #: rozmiar znacznika wstawien blokow (mm)
        self.insert_size_mm = 1.2
        #: czy w ogole pokazywac tabele `points` (domyslnie nie, jak w QGIS)
        self.show_points = False
        #: kolor zastepczy, gdy encja nie ma wlasnego
        self.fallback_color = "0,0,0,255"
        #: Jak traktowac kolumne `width` polilinii (globalna szerokosc z CAD-a):
        #: "map"    - jak w CAD: szerokosc w jednostkach mapy (wierne, ale
        #:            polilinia o width 0.5 to pol metra grubosci na mapie),
        #: "mm"     - ta sama liczba jako grubosc pisaka w milimetrach
        #:            (najczestsza intencja projektanta: 0.05 / 0.1 / 0.3 / 0.5
        #:            to standardowe grubosci piora ISO),
        #: "ignore" - pomijaj `width`, uzywaj wylacznie `linewidth`.
        self.polyline_width_mode = "mm"
        #: dolny prog dla trybu "mm", zeby wartosci rzedu 0.004 nie znikaly
        self.min_polyline_mm = 0.05


POLYLINE_WIDTH_MODES = ("mm", "map", "ignore")


DEFAULT_STYLE = StyleOptions()


def _color_expr(opts):
    """Kolor encji z fallbackiem.

    Kolumna ``color`` bywa pusta albo rowna ``byblock`` (nierozwiazane
    dziedziczenie z bloku). Wlasciwosc definiowana danymi zwraca wtedy wartosc
    nieprawidlowa, a QGIS cicho wraca do koloru symbolu — stad "domyslny wyglad"
    na czesci warstw.
    """
    return (
        "CASE WHEN \"color\" IS NULL OR trim(\"color\") = '' "
        "OR lower(trim(\"color\")) = 'byblock' THEN '{0}' "
        "ELSE \"color\" END"
    ).format(opts.fallback_color)


def _line_width_expr(opts, field="linewidth"):
    """Grubosc pisaka w mm z fallbackiem; ``-1`` oznacza BYBLOCK."""
    return (
        'CASE WHEN "{0}" IS NULL OR "{0}" <= 0 THEN {1} ELSE "{0}" END'
    ).format(field, repr(float(opts.line_width_mm)))


def _set_dd(symbol_layer, prop_name, expression_or_field, is_field=False):
    prop = (
        QgsProperty.fromField(expression_or_field)
        if is_field
        else QgsProperty.fromExpression(expression_or_field)
    )
    symbol_layer.setDataDefinedProperty(symbol_property(prop_name), prop)


def style_hatches(layer, override_color=None, opts=None):
    opts = opts or DEFAULT_STYLE
    sl = QgsSimpleFillSymbolLayer()
    sl.setStrokeStyle(Qt.PenStyle.NoPen)
    if override_color is not None:
        sl.setColor(override_color)
    else:
        _set_dd(sl, "FillColor", _color_expr(opts))
    symbol = QgsFillSymbol([sl])
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def style_lines(layer, override_color=None, opts=None):
    opts = opts or DEFAULT_STYLE
    sl = QgsSimpleLineSymbolLayer()
    sl.setPenJoinStyle(Qt.PenJoinStyle.MiterJoin)
    sl.setWidthUnit(render_unit("Millimeters"))
    sl.setWidth(float(opts.line_width_mm))
    if override_color is not None:
        sl.setColor(override_color)
    else:
        _set_dd(sl, "StrokeColor", _color_expr(opts))
    _set_dd(sl, "StrokeWidth", _line_width_expr(opts))
    symbol = QgsLineSymbol([sl])
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def style_polylines(layer, override_color=None, opts=None):
    """Polilinie CAD mają dwie „grubości" i to jest sedno problemu.

    ``linewidth`` to grubość pisaka w milimetrach — rzecz czysto kartograficzna.
    ``width`` to GLOBALNA SZEROKOŚĆ polilinii w jednostkach rysunku, czyli
    realna szerokość w terenie. Wbudowany import QGIS renderuje ``width``
    w jednostkach mapy, wiernie wobec CAD-a — i polilinia o ``width`` 0,5
    wychodzi na pół metra szeroka, jak czarna belka.

    W praktyce projektanci nagminnie wpisują tam grubości piór ISO
    (0,05 / 0,10 / 0,30 / 0,50), więc domyślnie interpretujemy tę liczbę
    jako milimetry. Tryb ``map`` przywraca wierność CAD-owi.
    """
    opts = opts or DEFAULT_STYLE
    mode = getattr(opts, "polyline_width_mode", "mm")

    layers = []

    if mode != "ignore":
        wide = QgsSimpleLineSymbolLayer()
        wide.setPenJoinStyle(Qt.PenJoinStyle.MiterJoin)
        if mode == "map":
            wide.setWidthUnit(render_unit("MapUnits"))
            wide.setWidth(0.0)
            _set_dd(wide, "StrokeWidth", 'coalesce("width", 0)')
        else:
            wide.setWidthUnit(render_unit("Millimeters"))
            wide.setWidth(float(opts.line_width_mm))
            _set_dd(
                wide,
                "StrokeWidth",
                'max(coalesce("width", 0), {0})'.format(
                    repr(float(opts.min_polyline_mm))
                ),
            )
        wide.setDataDefinedProperty(
            symbol_property("LayerEnabled"),
            QgsProperty.fromExpression('coalesce("width", 0) > 0'),
        )
        layers.append(wide)

    mm = QgsSimpleLineSymbolLayer()
    mm.setPenJoinStyle(Qt.PenJoinStyle.MiterJoin)
    mm.setWidthUnit(render_unit("Millimeters"))
    mm.setWidth(float(opts.line_width_mm))
    _set_dd(mm, "StrokeWidth", _line_width_expr(opts))
    if mode != "ignore":
        mm.setDataDefinedProperty(
            symbol_property("LayerEnabled"),
            QgsProperty.fromExpression('coalesce("width", 0) = 0'),
        )
    layers.append(mm)

    for sl in layers:
        if override_color is not None:
            sl.setColor(override_color)
        else:
            _set_dd(sl, "StrokeColor", _color_expr(opts))

    layer.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol(layers)))


#: wyrazenia wyrownania przepisane z qgsdwgimportdialog.cpp
_ETYPE_MTEXT = 19

_HALI = (
    "CASE WHEN etype = {mtext} THEN"
    "  CASE WHEN textgen % 3 = 2 THEN 'Center'"
    "       WHEN textgen % 3 = 0 THEN 'Right'"
    "       ELSE 'Left' END"
    " ELSE"
    "  CASE WHEN alignh = 1 THEN 'Center'"
    "       WHEN alignh = 2 THEN 'Right'"
    "       ELSE 'Left' END"
    " END"
).format(mtext=_ETYPE_MTEXT)

_VALI = (
    "CASE WHEN etype = {mtext} THEN"
    "  CASE WHEN textgen < 4 THEN 'Top'"
    "       WHEN textgen < 7 THEN 'Half'"
    "       ELSE 'Bottom' END"
    " ELSE"
    "  CASE WHEN alignv = 1 THEN 'Bottom'"
    "       WHEN alignv = 2 THEN 'Half'"
    "       WHEN alignv = 3 THEN 'Top'"
    "       ELSE 'Base' END"
    " END"
).format(mtext=_ETYPE_MTEXT)


def style_texts(layer, override_color=None, opts=None):
    opts = opts or DEFAULT_STYLE
    layer.setRenderer(QgsNullSymbolRenderer())

    settings = QgsPalLayerSettings()
    settings.fieldName = "text"
    settings.isExpression = False
    settings.wrapChar = "\\P"

    fmt = QgsTextFormat()
    fmt.setSizeUnit(render_unit("MapUnits"))
    settings.setFormat(fmt)

    try:
        settings.placement = QgsPalLayerSettings.Placement.OverPoint
    except AttributeError:
        settings.placement = QgsPalLayerSettings.OverPoint

    props = settings.dataDefinedProperties()
    props.setProperty(label_property("Size"), QgsProperty.fromField("height"))
    if override_color is None:
        props.setProperty(
            label_property("Color"), QgsProperty.fromExpression(_color_expr(opts))
        )
    props.setProperty(
        label_property("MultiLineHeight"),
        QgsProperty.fromExpression(
            "CASE WHEN interlin < 0 THEN 1 ELSE interlin * 1.5 END"
        ),
    )
    props.setProperty(label_property("PositionX"), QgsProperty.fromExpression("$x"))
    props.setProperty(label_property("PositionY"), QgsProperty.fromExpression("$y"))
    props.setProperty(
        label_property("LabelRotation"), QgsProperty.fromExpression("360 - angle")
    )
    props.setProperty(label_property("AlwaysShow"), QgsProperty.fromExpression("1"))
    props.setProperty(label_property("Hali"), QgsProperty.fromExpression(_HALI))
    props.setProperty(label_property("Vali"), QgsProperty.fromExpression(_VALI))
    settings.setDataDefinedProperties(props)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


#: ksztalty rysowane samym obrysem — dla nich NoPen oznacza calkowita niewidocznosc
#: (QgsSimpleMarkerSymbolLayerBase::shapeIsFilled zwraca dla nich false)
_UNFILLED_SHAPES = frozenset(
    ("Cross", "Cross2", "Line", "ArrowHead", "HalfArc", "ThirdArc", "QuarterArc")
)


def _marker_shape(name):
    try:
        from qgis.core import Qgis

        return enum_value(Qgis, "MarkerShape." + name)
    except Exception:  # older QGIS API: next fallback  # nosec B110
        pass
    try:
        from qgis.core import QgsSimpleMarkerSymbolLayerBase

        return enum_value(
            QgsSimpleMarkerSymbolLayerBase, "Shape." + name, name
        )
    except Exception:  # older QGIS API: next fallback  # nosec B110
        pass
    return enum_value(QgsSimpleMarkerSymbolLayer, "Shape." + name, name)


def _marker(size_mm, shape="Circle", color=None, stroke=True):
    """Maly, jawnie zdefiniowany znacznik.

    Kluczowe: NIE zostawiamy domyslnego symbolu QGIS. Nowa warstwa punktowa
    dostaje losowy marker 2 mm, ktory na rysunku CAD wyglada jak kropy wielkosci
    domu — to wlasnie zrodlo "punktow o domyslnej, za duzej wielkosci".
    """
    sl = QgsSimpleMarkerSymbolLayer()
    # Ksztalt markera wedrowal miedzy wersjami QGIS:
    # QgsSimpleMarkerSymbolLayerBase.Circle -> ...Shape.Circle -> Qgis.MarkerShape.Circle
    try:
        sl.setShape(_marker_shape(shape))
    except Exception:
        warn_exception(tr("Nie udało się ustawić kształtu znaku {0}"), shape)
    sl.setSize(float(size_mm))
    sl.setSizeUnit(render_unit("Millimeters"))
    filled = shape not in _UNFILLED_SHAPES
    sl.setStrokeWidth(0.2 if (stroke or not filled) else 0.0)
    sl.setStrokeWidthUnit(render_unit("Millimeters"))
    if color is not None:
        # setColor jest swiadomy ksztaltu: dla ksztaltu bez wypelnienia
        # przekierowuje na setStrokeColor. setShape musi byc wczesniej — jest.
        sl.setColor(color)
    if not stroke and filled:
        # NoPen wolno wylaczyc tylko tam, gdzie zostaje wypelnienie.
        # Dla Cross/Cross2 wylaczenie pisaka skasowaloby caly znacznik.
        sl.setStrokeStyle(Qt.PenStyle.NoPen)
    return QgsMarkerSymbol([sl])


def style_points(layer, override_color=None, opts=None):
    """Punkty CAD: domyslnie niewidoczne, jak we wbudowanym imporcie."""
    opts = opts or DEFAULT_STYLE
    if not opts.show_points:
        layer.setRenderer(QgsNullSymbolRenderer())
        return
    symbol = _marker(opts.point_size_mm, "Cross2", override_color, stroke=True)
    if override_color is None:
        symbol.symbolLayer(0).setDataDefinedProperty(
            symbol_property("StrokeColor"),
            QgsProperty.fromExpression(_color_expr(opts)),
        )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


def style_inserts(layer, override_color=None, opts=None):
    """Punkty wstawien: maly znacznik obrocony zgodnie z katem wstawienia."""
    opts = opts or DEFAULT_STYLE
    symbol = _marker(opts.insert_size_mm, "Circle", override_color, stroke=False)
    sl = symbol.symbolLayer(0)
    sl.setDataDefinedProperty(
        symbol_property("Angle"),
        QgsProperty.fromExpression("180 - coalesce(\"angle\", 0) * 180.0 / pi()"),
    )
    if override_color is None:
        sl.setDataDefinedProperty(
            symbol_property("FillColor"),
            QgsProperty.fromExpression(_color_expr(opts)),
        )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))


_STYLERS = {
    S.T_HATCHES: style_hatches,
    S.T_LINES: style_lines,
    S.T_POLYLINES: style_polylines,
    S.T_TEXTS: style_texts,
    S.T_POINTS: style_points,
    S.T_INSERTS: style_inserts,
}


#: ile obiektow probkowac, zeby ustalic dominujacy kolor warstwy
SWATCH_SAMPLE = 30


def _no_geometry_flag():
    from qgis.core import QgsFeatureRequest

    try:
        from qgis.core import Qgis

        return enum_value(Qgis, "FeatureRequestFlag.NoGeometry")
    except Exception:  # older QGIS API: next fallback  # nosec B110
        pass
    return enum_value(QgsFeatureRequest, "Flag.NoGeometry", "NoGeometry")


def sample_color(layer, limit=SWATCH_SAMPLE):
    """Dominujacy kolor encji w warstwie — do próbki w legendzie.

    Kolor kazdego obiektu bierze sie z wlasciwosci definiowanej danymi, a QGIS
    rysuje w legendzie **statyczny** kolor symbolu, nie wynik wyrazenia. Dlatego
    bez tego kroku wszystkie warstwy maja w legendzie ten sam niebieski kwadrat,
    mimo ze na mapie kazda jest inna.

    Probkujemy garstke obiektow zamiast czytac cala tabele — przy 400 warstwach
    pelny przebieg bylby zabojczy, a do kwadracika w legendzie wiecej nie trzeba.
    """
    from collections import Counter
    from qgis.core import QgsFeatureRequest

    idx = layer.fields().indexOf(S.C_COLOR)
    if idx < 0:
        return None
    try:
        request = QgsFeatureRequest()
        request.setLimit(int(limit))
        request.setSubsetOfAttributes([idx])
        try:
            request.setFlags(_no_geometry_flag())
        except Exception:  # without the flag the request also reads geometry  # nosec B110
            pass
        counts = Counter()
        for feature in layer.getFeatures(request):
            value = feature[idx]
            if value is None:
                continue
            text = str(value).strip()
            if not text or text.lower() == S.BYBLOCK:
                continue
            counts[text] += 1
        if not counts:
            return None
        from . import gpkg_reader

        return gpkg_reader.parse_color(counts.most_common(1)[0][0])
    except Exception:
        return None


def _apply_swatch(layer, color):
    """Podmienia statyczny kolor symbolu, zostawiajac wlasciwosci danych.

    Wyrazenie definiowane danymi nadal wygrywa przy rysowaniu mapy; statyczny
    kolor decyduje tylko o miniaturze w legendzie i o tym, co zobaczysz, gdy
    encja nie ma wlasnego koloru.
    """
    if color is None or not color.isValid():
        return
    renderer = layer.renderer()
    if renderer is None or not hasattr(renderer, "symbol"):
        return
    symbol = renderer.symbol()
    if symbol is None:
        return
    # Pracujemy na kopii i oddajemy ja rendererowi. Modyfikowanie symbolu
    # zwroconego przez symbol() bywa ignorowane, bo renderer trzyma wlasna
    # kopie i nie wie, ze cos sie zmienilo.
    clone = symbol.clone()
    for i in range(clone.symbolLayerCount()):
        try:
            # setColor jest swiadomy rodzaju symbolu: dla wypelnien ustawia
            # wypelnienie, dla linii pisak, dla markerow bez wypelnienia obrys
            clone.symbolLayer(i).setColor(color)
        except Exception:  # symbol layer without a colour  # nosec B112
            continue
    try:
        renderer.setSymbol(clone)
    except Exception:
        warn_exception(tr("Nie udało się podmienić symbolu w legendzie"))


#: publiczny alias — miniatura w legendzie z gotowego koloru, bez probkowania
apply_swatch = _apply_swatch


def apply_style(layer, table, override_color=None, opts=None):
    """Nadaje warstwie styl wlasciwy dla tabeli zrodlowej."""
    fn = _STYLERS.get(table)
    if fn is None:
        return False
    try:
        fn(layer, override_color, opts or DEFAULT_STYLE)
        if override_color is None:
            _apply_swatch(layer, sample_color(layer))
    except Exception as exc:  # styl nie moze wywrocic calego importu...
        # ...ale cicha porazka zostawia warstwe z domyslnym rendererem QGIS,
        # co wyglada jak blad importu. Lepiej krzyknac do dziennika.
        QgsMessageLog.logMessage(
            tr("Nie udalo sie ostylowac warstwy {0} ({1}): {2}").format(
                layer.name(), table, exc
            ),
            "WFG DWG Layers+",
            Qgis.Warning,
        )
        return False
    layer.triggerRepaint()
    return True


def style_block_texts(layer):
    """Uproszczone etykietowanie dla tekstow wyciagnietych z blokow.

    Warstwy blokowe maja wlasny, plaski schemat atrybutow (bez ``alignh`` /
    ``textgen`` / ``interlin``), wiec nie mozna na nich uzyc pelnego stylu
    z tabeli ``texts`` — wyrazenia odwolywalyby sie do nieistniejacych pol.
    """
    layer.setRenderer(QgsNullSymbolRenderer())
    settings = QgsPalLayerSettings()
    settings.fieldName = "text"
    settings.isExpression = False
    fmt = QgsTextFormat()
    fmt.setSizeUnit(render_unit("MapUnits"))
    settings.setFormat(fmt)
    try:
        settings.placement = QgsPalLayerSettings.Placement.OverPoint
    except AttributeError:
        settings.placement = QgsPalLayerSettings.OverPoint
    props = settings.dataDefinedProperties()
    props.setProperty(
        label_property("Size"),
        QgsProperty.fromExpression('coalesce("height", 1)'),
    )
    props.setProperty(label_property("PositionX"), QgsProperty.fromExpression("$x"))
    props.setProperty(label_property("PositionY"), QgsProperty.fromExpression("$y"))
    props.setProperty(
        label_property("LabelRotation"),
        QgsProperty.fromExpression('360 - coalesce("angle", 0)'),
    )
    props.setProperty(label_property("AlwaysShow"), QgsProperty.fromExpression("1"))
    settings.setDataDefinedProperties(props)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def style_anchor(layer, opts=None):
    """Kotwice blokow: maly znacznik, nie domyslna kropa."""
    opts = opts or DEFAULT_STYLE
    symbol = _marker(opts.insert_size_mm, "Cross", stroke=True)
    symbol.symbolLayer(0).setDataDefinedProperty(
        symbol_property("Angle"),
        QgsProperty.fromExpression('coalesce("angle_deg", 0)'),
    )
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.triggerRepaint()


def style_block_layer(layer, kind, color=None, opts=None):
    """Styl warstwy zlozonych geometrii bloku."""
    opts = opts or DEFAULT_STYLE
    try:
        if kind == S.KIND_POLYGON:
            style_hatches(layer, color, opts)
        elif kind == S.KIND_LINE:
            style_lines(layer, color, opts)
        elif kind == S.KIND_TEXT:
            style_block_texts(layer)
        elif kind == S.KIND_POINT:
            # bez tego warstwa punktowa bloku zostawala z domyslnym,
            # dwumilimetrowym markerem QGIS
            symbol = _marker(opts.point_size_mm, "Cross2", color, stroke=True)
            if color is None:
                symbol.symbolLayer(0).setDataDefinedProperty(
                    symbol_property("StrokeColor"),
                    QgsProperty.fromExpression(_color_expr(opts)),
                )
            layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        if color is None and kind != S.KIND_TEXT:
            _apply_swatch(layer, sample_color(layer))
    except Exception as exc:
        QgsMessageLog.logMessage(
            tr("Nie udalo sie ostylowac warstwy bloku {0}: {1}").format(
                layer.name(), exc
            ),
            "WFG DWG Layers+",
            Qgis.Warning,
        )
        return False
    layer.triggerRepaint()
    return True
