# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Kontrakt danych: schemat GeoPackage produkowanego przez wbudowany import DWG/DXF.

Zrodlo prawdy: src/app/dwg/qgsdwgimporter.cpp w repozytorium QGIS.
Schemat jest identyczny od 3.34 do master, dlatego mozna sie na nim oprzec.

Modul jest celowo czysto danymi (bez importow QGIS), zeby dalo sie go testowac
poza QGIS-em.
"""

# --- tabele -----------------------------------------------------------------

T_DRAWING = "drawing"
T_HEADERS = "headers"
T_LINETYPES = "linetypes"
T_LAYERS = "layers"
T_DIMSTYLES = "dimstyles"
T_TEXTSTYLES = "textstyles"
T_APPDATA = "appdata"
T_BLOCKS = "blocks"
T_POINTS = "points"
T_LINES = "lines"
T_POLYLINES = "polylines"
T_TEXTS = "texts"
T_HATCHES = "hatches"
T_INSERTS = "inserts"

#: tabele niosace geometrie encji rysunku (bez ``blocks``, ktore jest slownikiem)
ENTITY_TABLES = (T_POINTS, T_LINES, T_POLYLINES, T_TEXTS, T_HATCHES, T_INSERTS)

#: tabele przenoszone przy rozwijaniu blokow (``inserts`` obsluguje rekurencja)
BLOCK_CONTENT_TABLES = (T_HATCHES, T_LINES, T_POLYLINES, T_TEXTS, T_POINTS)

#: wszystkie tabele, ktore musza istniec, zeby uznac plik za GPKG z importu DWG
REQUIRED_TABLES = (T_LAYERS, T_BLOCKS)

# --- kolumny wspolne (makro ENTITY_ATTRIBUTES) ------------------------------

ENTITY_ATTRIBUTES = (
    "handle",
    "block",
    "etype",
    "space",
    "layer",
    "olinetype",
    "linetype",
    "color",
    "ocolor",
    "color24",
    "transparency",
    "lweight",
    "linewidth",
    "ltscale",
    "visible",
)

C_HANDLE = "handle"
C_BLOCK = "block"
C_ETYPE = "etype"
C_SPACE = "space"
C_LAYER = "layer"
C_COLOR = "color"
C_OCOLOR = "ocolor"
C_LINETYPE = "linetype"
C_LINEWIDTH = "linewidth"
C_FLAGS = "flags"
C_NAME = "name"

#: ``block = -1`` oznacza przestrzen modelu. NIGDY nie jest NULL.
MODEL_SPACE_BLOCK = -1

#: ``space = 0`` to przestrzen modelu, 1 to przestrzen papieru
MODEL_SPACE = 0

#: bazowy filtr obowiazkowy w kazdym zapytaniu o geometrie rysunku
BASE_FILTER = "space = {0} AND block = {1}".format(MODEL_SPACE, MODEL_SPACE_BLOCK)

#: wartosc kolumn layer/color/linetype oznaczajaca dziedziczenie z bloku
BYBLOCK = "byblock"

#: sentinel w kolumnie linewidth oznaczajacy BYBLOCK
LINEWIDTH_BYBLOCK = -1.0

#: nazwa warstwy CAD, ktora dziedziczy warstwe wstawienia bloku
LAYER_ZERO = "0"

# --- kolumny specyficzne ----------------------------------------------------

INSERT_COLUMNS = (
    "name",
    "xscale",
    "yscale",
    "zscale",
    "angle",
    "colcount",
    "rowcount",
    "colspace",
    "rowspace",
)

# --- typy geometrii ---------------------------------------------------------

KIND_POINT = "point"
KIND_LINE = "line"
KIND_POLYGON = "polygon"
KIND_TEXT = "text"

#: mapowanie tabela -> rodzaj geometrii uzywany do grupowania
TABLE_KIND = {
    T_POINTS: KIND_POINT,
    T_INSERTS: KIND_POINT,
    T_LINES: KIND_LINE,
    T_POLYLINES: KIND_LINE,
    T_HATCHES: KIND_POLYGON,
    T_TEXTS: KIND_TEXT,
}

#: domyslne sufiksy nazw warstw QGIS
DEFAULT_SUFFIXES = {
    T_POINTS: "_point",
    T_INSERTS: "_insert",
    T_LINES: "_line",
    T_POLYLINES: "_pline",
    T_HATCHES: "_hatch",
    T_TEXTS: "_text",
}

#: domyslne nazwy czterech grup geometrycznych, w kolejnosci rysowania
#: (pierwsza = na wierzchu legendy)
DEFAULT_GROUPS = {
    KIND_TEXT: "4_Teksty",
    KIND_POINT: "3_Punkty",
    KIND_LINE: "2_Linie",
    KIND_POLYGON: "1_Poligony",
}

#: kolejnosc dodawania grup do drzewa: pierwsza na gorze legendy
GROUP_ORDER = (KIND_TEXT, KIND_POINT, KIND_LINE, KIND_POLYGON)

#: nazwa piatej grupy uzywanej w trybie zlozonych geometrii blokow
DEFAULT_BLOCK_GROUP = "5_Bloki"

#: tabela pomocnicza z mapowaniem nazw tabel na oryginalne nazwy warstw CAD
MAP_TABLE = "dwgplus_layer_map"


# --- ENUM-y trybow ----------------------------------------------------------


class BlockMode(object):
    """Tryb obslugi blokow (INSERT)."""

    #: geometria blokow rozwinieta w przestrzen modelu (parytet z QGIS)
    EXPLODED = "exploded"
    #: bloki jako punkty wstawien z atrybutami
    INSERT_POINTS = "insert_points"
    #: jeden obiekt na wstawienie, geometria wieloczesciowa
    COMPOSITE = "composite"

    ALL = (EXPLODED, INSERT_POINTS, COMPOSITE)


class LayerMode(object):
    """Sposob tworzenia warstw QGIS."""

    #: filtr (subset string) na wspolnej tabeli GPKG
    FILTER = "filter"
    #: fizyczna tabela w GPKG na kazda pare (tabela, warstwa CAD)
    MATERIALIZE = "materialize"

    ALL = (FILTER, MATERIALIZE)


#: wartosci ``/DwgImport/lastBlockImportFlags`` we wbudowanym dialogu QGIS
QGIS_BLOCK_EXPAND_GEOMETRY = 1
QGIS_BLOCK_ADD_INSERT_POINTS = 2


def qgis_block_flags(block_mode):
    """Flagi wbudowanego importera QGIS odpowiadajace naszemu trybowi blokow.

    W trybie COMPOSITE rozwijanie MUSI byc wylaczone, inaczej w tabelach
    znajda sie zarowno definicje blokow, jak i ich splaszczone kopie
    (``expandInserts`` dopisuje, nie zastepuje) i policzylibysmy geometrie
    podwojnie.
    """
    if block_mode == BlockMode.EXPLODED:
        return QGIS_BLOCK_EXPAND_GEOMETRY
    if block_mode == BlockMode.INSERT_POINTS:
        return QGIS_BLOCK_ADD_INSERT_POINTS
    if block_mode == BlockMode.COMPOSITE:
        return QGIS_BLOCK_ADD_INSERT_POINTS
    raise ValueError("nieznany tryb blokow: {0!r}".format(block_mode))


def layer_visible_from_attrs(ocolor, flags):
    """Czy warstwa CAD jest widoczna.

    Nie ma osobnej kolumny: ujemny ``ocolor`` oznacza warstwe wylaczona,
    bit 1 w ``flags`` oznacza warstwe zamrozona.
    """
    try:
        ocolor = int(ocolor)
    except (TypeError, ValueError):
        ocolor = 0
    try:
        flags = int(flags)
    except (TypeError, ValueError):
        flags = 0
    return ocolor >= 0 and (flags & 1) == 0


def sql_quote(value):
    """Escapuje literal tekstowy do SQL-a (podwojenie apostrofow)."""
    return "'" + str(value).replace("'", "''") + "'"


def layer_filter(cad_layer):
    """Pelny subset string dla jednej warstwy CAD."""
    return "{0} = {1} AND {2}".format(C_LAYER, sql_quote(cad_layer), BASE_FILTER)
