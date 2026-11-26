# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Inwentaryzacja GeoPackage z importu DWG/DXF.

Kluczowa decyzja wydajnosciowa: zamiast tworzyc setki warstw QGIS i pytac je
o ``featureCount()`` (co przy 200 warstwach CAD x 6 tabel oznacza 1200 zapytan
COUNT), robimy JEDNO zapytanie grupujace na tabele. Szesc zapytan zamiast 1200.
"""

import os
import sqlite3

from . import gpkg_schema as S
from ..i18n import tr


class CadLayerInfo(object):
    """Jedna warstwa CAD wraz z liczba obiektow w rozbiciu na tabele."""

    __slots__ = ("name", "color", "ocolor", "flags", "linewidth", "counts")

    def __init__(self, name, color=None, ocolor=0, flags=0, linewidth=0.0):
        self.name = name
        self.color = color
        self.ocolor = ocolor
        self.flags = flags
        self.linewidth = linewidth
        self.counts = {}

    @property
    def visible(self):
        return S.layer_visible_from_attrs(self.ocolor, self.flags)

    @property
    def total(self):
        return sum(self.counts.values())

    def count(self, table):
        return self.counts.get(table, 0)

    def tables(self):
        """Tabele, w ktorych ta warstwa ma jakiekolwiek obiekty."""
        return [t for t in S.ENTITY_TABLES if self.counts.get(t)]

    def qcolor(self):
        """Kolor warstwy jako QColor albo None."""
        return parse_color(self.color)

    def __repr__(self):
        return "<CadLayerInfo {0!r} total={1}>".format(self.name, self.total)


def parse_color(text):
    """Kolumna ``color`` to string 'R,G,B,A'. Zwraca QColor albo None."""
    if not text:
        return None
    parts = str(text).split(",")
    if len(parts) < 3:
        return None
    try:
        vals = [int(float(p)) for p in parts[:4]]
    except (TypeError, ValueError):
        return None
    while len(vals) < 4:
        vals.append(255)
    try:
        from qgis.PyQt.QtGui import QColor
    except ImportError:
        return None
    return QColor(*[max(0, min(255, v)) for v in vals])


class GpkgInventory(object):
    """Wynik inwentaryzacji pliku GPKG."""

    def __init__(self, path):
        self.path = path
        self.layers = []            # lista CadLayerInfo, posortowana po nazwie
        self.tables = set()         # tabele faktycznie obecne w pliku
        self.block_names = []       # nazwy blokow z tabeli `blocks`
        self.insert_count = 0       # liczba wstawien w przestrzeni modelu
        self.expanded = False       # czy import byl z rozwinieciem blokow
        self.crs_authid = None

    def by_name(self, name):
        for lay in self.layers:
            if lay.name == name:
                return lay
        return None

    def non_empty(self):
        return [lay for lay in self.layers if lay.total > 0]

    def pairs(self, cad_layers=None):
        """Generuje pary (warstwa CAD, tabela) o niezerowej liczbie obiektow."""
        wanted = set(cad_layers) if cad_layers is not None else None
        for lay in self.layers:
            if wanted is not None and lay.name not in wanted:
                continue
            for table in lay.tables():
                yield lay, table


class GpkgReadError(Exception):
    pass


def _connect(path):
    if not os.path.exists(path):
        raise GpkgReadError(tr("Plik nie istnieje: {0}").format(path))
    uri = "file:{0}?mode=ro".format(path.replace("?", "%3f").replace("#", "%23"))
    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        # niektore buildy sqlite nie wspieraja URI — probujemy zwyklej sciezki
        return sqlite3.connect(path)


def _existing_tables(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )
    return {row[0] for row in cur.fetchall()}


def looks_like_dwg_gpkg(path):
    """Szybki test, czy plik wyglada na GPKG z importu DWG/DXF."""
    try:
        conn = _connect(path)
    except Exception:
        return False
    try:
        tables = _existing_tables(conn)
        return all(t in tables for t in S.REQUIRED_TABLES)
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def inventory(path, feedback=None):
    """Czyta caly potrzebny stan z GPKG w kilku zapytaniach.

    :raises GpkgReadError: gdy plik nie jest GeoPackage z importu DWG/DXF
    """
    conn = _connect(path)
    inv = GpkgInventory(path)
    try:
        present = _existing_tables(conn)
        missing = [t for t in S.REQUIRED_TABLES if t not in present]
        if missing:
            raise GpkgReadError(
                tr("To nie jest GeoPackage z importu DWG/DXF — brakuje tabel: {0}").format(
                    ", ".join(missing)
                )
            )
        inv.tables = present & set(S.ENTITY_TABLES + (S.T_BLOCKS, S.T_LAYERS))

        # --- warstwy CAD ---
        index = {}
        cur = conn.execute(
            "SELECT name, color, ocolor, flags, linewidth FROM {0}".format(S.T_LAYERS)  # nosec B608
        )
        for name, color, ocolor, flags, linewidth in cur.fetchall():
            if name is None:
                continue
            info = CadLayerInfo(name, color, ocolor or 0, flags or 0, linewidth or 0.0)
            index[name] = info

        # --- liczby obiektow: jedno zapytanie na tabele ---
        for table in S.ENTITY_TABLES:
            if table not in present:
                continue
            if feedback is not None and feedback.isCanceled():
                raise GpkgReadError(tr("Przerwano."))
            sql = "SELECT {0}, COUNT(*) FROM {1} WHERE {2} GROUP BY {0}".format(  # nosec B608
                S.C_LAYER, table, S.BASE_FILTER
            )
            try:
                rows = conn.execute(sql).fetchall()
            except sqlite3.Error:
                continue
            for cad_layer, n in rows:
                if cad_layer is None:
                    cad_layer = ""
                info = index.get(cad_layer)
                if info is None:
                    # warstwa obecna w geometriach, ale nie w tabeli `layers`
                    info = CadLayerInfo(cad_layer)
                    index[cad_layer] = info
                info.counts[table] = int(n)

        inv.layers = sorted(index.values(), key=lambda info: info.name.lower())

        # --- bloki ---
        if S.T_BLOCKS in present:
            try:
                rows = conn.execute(
                    "SELECT DISTINCT name FROM {0} WHERE name IS NOT NULL "  # nosec B608
                    "ORDER BY name".format(S.T_BLOCKS)
                ).fetchall()
                inv.block_names = [r[0] for r in rows]
            except sqlite3.Error:
                pass

        if S.T_INSERTS in present:
            try:
                inv.insert_count = conn.execute(
                    "SELECT COUNT(*) FROM {0} WHERE {1}".format(  # nosec B608
                        S.T_INSERTS, S.BASE_FILTER
                    )
                ).fetchone()[0]
            except sqlite3.Error:
                pass

        inv.expanded = _detect_expanded(conn, present)
        inv.crs_authid = _detect_crs(conn)
        return inv
    finally:
        conn.close()


def _detect_expanded(conn, present):
    """Heurystyka: czy import rozwijal bloki.

    Po rozwinieciu w tabelach sa i oryginaly (``block = handle``), i splaszczone
    kopie (``block = -1``) pochodzace z definicji blokow. Jesli sa definicje
    blokow i jednoczesnie wstawienia nie maja odpowiednika w przestrzeni modelu,
    import byl bez rozwijania. Test jest przyblizony i sluzy tylko do
    ostrzezenia uzytkownika.
    """
    if S.T_BLOCKS not in present or S.T_INSERTS not in present:
        return False
    try:
        n_defs = conn.execute(
            "SELECT COUNT(*) FROM {0}".format(S.T_BLOCKS)  # nosec B608
        ).fetchone()[0]
        if not n_defs:
            return False
        n_inserts = conn.execute(
            "SELECT COUNT(*) FROM {0} WHERE {1}".format(S.T_INSERTS, S.BASE_FILTER)  # nosec B608
        ).fetchone()[0]
        if not n_inserts:
            return True
        # jesli sa wstawienia w przestrzeni modelu i jednoczesnie duzo geometrii
        # z block = -1 na warstwach uzywanych tylko wewnatrz blokow — rozwiniete
        n_block_geom = 0
        for t in S.BLOCK_CONTENT_TABLES:
            if t not in present:
                continue
            n_block_geom += conn.execute(
                "SELECT COUNT(*) FROM {0} WHERE {1} <> {2}".format(  # nosec B608
                    t, S.C_BLOCK, S.MODEL_SPACE_BLOCK
                )
            ).fetchone()[0]
        return n_block_geom == 0
    except sqlite3.Error:
        return False


def _detect_crs(conn):
    try:
        row = conn.execute(
            "SELECT srs_id FROM gpkg_contents WHERE srs_id IS NOT NULL LIMIT 1"
        ).fetchone()
        if row and row[0] and int(row[0]) > 0:
            return "EPSG:{0}".format(int(row[0]))
    except sqlite3.Error:
        pass
    return None


def existing_table_names(path):
    """Nazwy wszystkich tabel w pliku — potrzebne, by unikac kolizji."""
    try:
        conn = _connect(path)
    except Exception:
        return set()
    try:
        return _existing_tables(conn)
    finally:
        conn.close()
