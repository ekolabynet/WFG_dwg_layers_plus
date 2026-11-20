# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Odzyskiwanie przypisania encji do warstw CAD wprost z pliku DXF.

Po co. Wbudowany import DWG/DXF potrafi zgubić nazwę warstwy dla części encji
— najczęściej dla „ciężkiej" ``POLYLINE`` (tej z osobnymi encjami ``VERTEX``,
którą wypuszczają eksporty z systemów geodezyjnych). Wszystkie takie obiekty
lądują w GeoPackage na warstwie ``0``, choć w rysunku mają swoje warstwy.
Objaw jest łatwy do rozpoznania: ``inserts`` i ``texts`` mają dziesiątki
poprawnych nazw, a ``lines`` / ``polylines`` / ``hatches`` mają jedną.

Naprawa. Uchwyt encji (kod grupy 5) jest w rysunku unikalny i **przeżywa
import** — QGIS zapisuje go w kolumnie ``handle``, tyle że dziesiętnie, a DXF
trzyma go szesnastkowo. Wystarczy więc przejść plik DXF-a raz, zbudować
odwzorowanie ``uchwyt -> warstwa`` i przepisać je do GeoPackage. Geometrii nikt
nie rusza, importu nie trzeba powtarzać.

Czego ta naprawa nie zrobi. Encje powstałe z rozbicia bloków dzielą uchwyt
z definicją bloku (jeden uchwyt, wiele kopii na mapie), więc dostaną warstwę
z wnętrza bloku — zwykle ``0``. Dla treści blokowej właściwą drogą jest tryb
bloków złożonych, który bierze warstwę ze wstawienia.
"""

import os
import sqlite3

from . import gpkg_schema as S
from .encoding_fix import _connect, backup  # noqa: F401  (backup re-eksport)

#: encje złożone: mają części składowe zamknięte przez ``SEQEND``
COMPOSITE_TYPES = frozenset(("POLYLINE", "INSERT"))

#: części składowe encji złożonej — same nie są obiektami rysunku
SUB_TYPES = frozenset(("VERTEX", "ATTRIB", "ATTDEF"))

#: encje, których uchwyty w ogóle nas interesują
SKIP_TYPES = frozenset((
    "SECTION", "ENDSEC", "TABLE", "ENDTAB", "CLASS", "EOF", "BLOCK", "ENDBLK",
    "VERTEX", "SEQEND", "LAYER", "STYLE", "LTYPE", "DIMSTYLE", "VPORT",
    "APPID", "UCS", "VIEW", "BLOCK_RECORD",
))

#: tabele z geometrią, w których warto poprawiać przypisanie
TARGET_TABLES = (
    S.T_POLYLINES, S.T_LINES, S.T_HATCHES, S.T_POINTS, S.T_TEXTS, S.T_INSERTS,
)

BINARY_MAGIC = b"AutoCAD Binary DXF"


#: nazwy stron kodowych z naglowka DXF na nazwy Pythona
CODEPAGES = {
    "ANSI_1250": "cp1250",
    "ANSI_1251": "cp1251",
    "ANSI_1252": "cp1252",
    "ANSI_1253": "cp1253",
    "ANSI_1254": "cp1254",
    "ANSI_1257": "cp1257",
    "ANSI_852": "cp852",
    "UTF8": "utf-8",
    "UTF-8": "utf-8",
}


def _codepage_to_python(nazwa):
    return CODEPAGES.get((nazwa or "").strip().upper())


def _decode(raw, encoding=None):
    """Wartość DXF-a na napis. Rysunki bywają w cp1250, bywają w UTF-8.

    UTF-8 próbujemy **zawsze pierwszy**, mimo że w nagłówku bywa zadeklarowana
    inna strona kodowa. UTF-8 sam się weryfikuje: bajty spoza niego odrzuci.
    Odwrotna kolejność byłaby zgubna — cp1250 przyjmie prawie każdy bajt, więc
    rysunek R2007+ (a te są w UTF-8) z przestarzałym ``$DWGCODEPAGE`` zostałby
    odczytany podwójnie zakodowany. To dokładnie ta usterka, którą naprawia
    pozycja „Napraw kodowanie".
    """
    for enc in ["utf-8"] + ([encoding] if encoding else []) + ["cp1250"]:
        try:
            return raw.decode(enc).strip()
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1").strip()


class DxfScan(object):
    """Wynik przejścia po pliku DXF."""

    def __init__(self):
        #: uchwyt (int) -> nazwa warstwy
        self.handles = {}
        #: uchwyty encji leżących wewnątrz definicji bloków
        self.in_blocks = set()
        #: ile encji nie miało uchwytu — wtedy naprawa jest niemożliwa
        self.bez_uchwytu = 0
        #: nazwy warstw z tabeli LAYER
        self.defined = []
        #: ile encji w przestrzeni modelu, wg warstwy
        self.per_layer = {}
        #: ile przypisań odzyskano przez uchwyt SEQEND-a
        self.via_seqend = 0
        #: strona kodowa zadeklarowana w naglowku rysunku
        self.codepage = ""
        #: czy uzytkownik przerwal czytanie — wtedy mapa jest niepelna
        self.cancelled = False

    @property
    def count(self):
        return len(self.handles)

    @property
    def layer_count(self):
        return len(self.per_layer)


def scan_dxf(path, encoding=None, feedback=None, progress_cb=None):
    """Buduje odwzorowanie ``uchwyt -> warstwa``, czytając DXF-a strumieniowo.

    Plik czytamy parami linii (kod, wartość) i nie trzymamy go w pamięci, więc
    rysunek o wadze kilkuset megabajtów też przejdzie.
    """
    with open(path, "rb") as fh:
        if fh.read(len(BINARY_MAGIC)) == BINARY_MAGIC:
            raise ValueError(
                "To binarny DXF. Zapisz rysunek jako DXF tekstowy (ASCII)."
            )

    rozmiar = max(1, os.path.getsize(path))
    wynik = DxfScan()

    sekcja = None
    w_bloku = False
    czekam_na_sekcje = False
    czekam_na_warstwe = False
    czekam_na_kodowanie = False
    typ = None
    uchwyt = None
    warstwa = None
    przeczytane = 0
    ostatni_procent = -1

    # Encja zlozona (POLYLINE / INSERT z atrybutami) rozciaga sie na kilka
    # encji skladowych zamknietych przez SEQEND. Tu pamietamy warstwe tej
    # glownej — patrz komentarz przy SEQEND ponizej.
    stan = {"rodzic": None}

    def zapisz():
        if not typ:
            return
        # OBJECTS i TABLES tez maja uchwyty (DICTIONARY, XRECORD, LAYOUT),
        # ale nie sa encjami rysunku i tylko zawyzalyby statystyki
        if sekcja not in ("ENTITIES", "BLOCKS"):
            return

        if typ in COMPOSITE_TYPES:
            stan["rodzic"] = warstwa or "0"
        elif typ == "SEQEND":
            # STĄD BIERZE SIE CALA USTERKA. Wbudowany import zapisuje dla
            # ciezkiej POLYLINE uchwyt SEQEND-a, nie samej polilinii, i razem
            # z nim warstwe SEQEND-a — a ta jest zwykle "0". W bazie szukamy
            # wiec wlasnie uchwytu zamkniecia i podstawiamy pod niego warstwe
            # encji, ktora on zamyka.
            if uchwyt is not None and stan["rodzic"] is not None:
                wynik.handles[uchwyt] = stan["rodzic"]
                wynik.via_seqend += 1
                if w_bloku:
                    wynik.in_blocks.add(uchwyt)
            stan["rodzic"] = None
            return
        elif typ in SUB_TYPES:
            # VERTEX i ATTRIB naleza do encji nadrzednej i nie zmieniaja jej
            return

        if typ in SKIP_TYPES:
            return
        if uchwyt is None:
            wynik.bez_uchwytu += 1
            return
        wynik.handles[uchwyt] = warstwa or "0"
        if w_bloku:
            wynik.in_blocks.add(uchwyt)
        elif sekcja == "ENTITIES":
            nazwa = warstwa or "0"
            wynik.per_layer[nazwa] = wynik.per_layer.get(nazwa, 0) + 1

    with open(path, "rb") as fh:
        while True:
            linia_kodu = fh.readline()
            if not linia_kodu:
                break
            linia_wartosci = fh.readline()
            if not linia_wartosci:
                break
            przeczytane += len(linia_kodu) + len(linia_wartosci)

            if feedback is not None and feedback.isCanceled():
                wynik.cancelled = True
                break
            if progress_cb is not None:
                procent = int(przeczytane * 100 / rozmiar)
                if procent != ostatni_procent:
                    ostatni_procent = procent
                    progress_cb(procent)

            try:
                kod = int(linia_kodu.strip())
            except ValueError:
                continue
            wartosc = _decode(linia_wartosci, encoding)

            if kod == 0:
                zapisz()
                typ, uchwyt, warstwa = wartosc, None, None
                if wartosc == "SECTION":
                    czekam_na_sekcje = True
                elif wartosc == "ENDSEC":
                    sekcja, w_bloku = None, False
                elif wartosc == "BLOCK":
                    w_bloku = True
                elif wartosc == "ENDBLK":
                    w_bloku = False
                elif wartosc == "LAYER" and sekcja == "TABLES":
                    czekam_na_warstwe = True
            elif kod == 2:
                if czekam_na_sekcje:
                    sekcja = wartosc
                    czekam_na_sekcje = False
                elif czekam_na_warstwe:
                    wynik.defined.append(wartosc)
                    czekam_na_warstwe = False
            elif kod == 5 and uchwyt is None:
                try:
                    uchwyt = int(wartosc, 16)
                except ValueError:
                    uchwyt = None
            elif kod == 8:
                warstwa = wartosc
            elif kod == 9 and sekcja == "HEADER":
                czekam_na_kodowanie = wartosc == "$DWGCODEPAGE"
            elif kod == 3 and czekam_na_kodowanie:
                czekam_na_kodowanie = False
                wynik.codepage = wartosc
                if encoding is None:
                    encoding = _codepage_to_python(wartosc)
        zapisz()

    return wynik


# ---------------------------------------------------------------------------
# zestawienie z GeoPackage
# ---------------------------------------------------------------------------


class TableDiff(object):
    """Co naprawa zrobiłaby w jednej tabeli."""

    def __init__(self, table):
        self.table = table
        self.rows = 0            # wierszy w przestrzeni modelu
        self.matched = 0         # uchwyt znaleziony w DXF
        self.changed = 0         # i warstwa jest inna niż obecna
        self.from_blocks = 0     # uchwyt pochodzi z wnętrza definicji bloku
        self.mojibake = 0       # roznica polega wylacznie na kodowaniu
        self.layers_before = 0
        self.layers_after = 0
        self.przyklady = []      # (uchwyt, stara, nowa)

    @property
    def unmatched(self):
        return max(0, self.rows - self.matched)


class Plan(object):
    def __init__(self):
        self.tables = []
        self.warnings = []

    @property
    def changed(self):
        return sum(t.changed for t in self.tables)

    @property
    def mojibake(self):
        return sum(t.mojibake for t in self.tables)

    @property
    def tables_touched(self):
        return [t for t in self.tables if t.changed]


def plan(gpkg_path, scan, tables=None, sample=6, skip_block_content=True):
    """Zestawia rysunek z bazą i mówi, co się zmieni. Niczego nie zapisuje."""
    tables = tables or TARGET_TABLES
    out = Plan()
    conn = sqlite3.connect(
        "file:{0}?mode=ro".format(_uri(gpkg_path)), uri=True
    )
    try:
        for table in tables:
            diff = TableDiff(table)
            try:
                rows = conn.execute(
                    'SELECT "{0}", "{1}" FROM "{2}" WHERE {3}'.format(
                        S.C_HANDLE, S.C_LAYER, table, S.BASE_FILTER
                    )
                ).fetchall()
            except sqlite3.Error:
                continue
            przed, po = set(), set()
            for uchwyt, stara in rows:
                diff.rows += 1
                przed.add(stara)
                nowa = scan.handles.get(uchwyt)
                if nowa is None:
                    po.add(stara)
                    continue
                diff.matched += 1
                if uchwyt in scan.in_blocks:
                    diff.from_blocks += 1
                    if skip_block_content:
                        # apply_fix ich nie ruszy, wiec podglad tez nie moze
                        # ich liczyc — inaczej obiecalby zmiany, ktorych nie bedzie
                        po.add(stara)
                        continue
                po.add(nowa)
                if nowa != stara:
                    diff.changed += 1
                    if _same_but_for_encoding(stara, nowa):
                        diff.mojibake += 1
                    if len(diff.przyklady) < sample:
                        diff.przyklady.append((uchwyt, stara, nowa))
            diff.layers_before = len(przed)
            diff.layers_after = len(po)
            out.tables.append(diff)
    finally:
        conn.close()

    if not scan.handles:
        out.warnings.append(
            "Rysunek nie ma uchwytów encji (bardzo stary DXF) — "
            "po uchwycie nie da się nic dopasować."
        )
    elif not out.changed:
        out.warnings.append(
            "Nie ma czego poprawiać: przypisanie w bazie zgadza się z rysunkiem."
        )
    return out


def _existing_tables(conn):
    """Tabele, ktore w tym pliku naprawde sa."""
    try:
        return set(
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        )
    except sqlite3.Error:
        return set()


def _same_but_for_encoding(stara, nowa):
    """Czy te dwie nazwy roznia sie wylacznie podwojnym kodowaniem?

    Wazne pytanie: jesli baza nie ma jeszcze naprawionego kodowania, a rysunek
    czytamy poprawnie, to KAZDA nazwa z polskim znakiem wyjdzie jako roznica.
    Przepisanie ich rozjechaloby warstwe na dwie pisownie i uniewaznilo filtry
    w projekcie. Lepiej najpierw naprawic kodowanie.
    """
    if not stara or not nowa or stara == nowa:
        return False
    try:
        from .encoding_fix import repair
    except ImportError:
        return False
    return repair(stara) == nowa


def _uri(path):
    try:
        from urllib.request import pathname2url
    except ImportError:  # pragma: no cover
        from urllib import pathname2url
    return pathname2url(os.path.abspath(path))


def apply_fix(gpkg_path, scan, tables=None, make_backup=True,
              skip_block_content=True, feedback=None, progress_cb=None):
    """Przepisuje warstwy do GeoPackage. Zwraca ``(zmian, ścieżka_kopii)``.

    :param skip_block_content: nie ruszaj encji rozbitych z bloków — dzielą one
        uchwyt z definicją bloku, więc dostałyby warstwę z jego wnętrza,
        a nie tę, którą niesie wstawienie.
    """
    tables = tables or TARGET_TABLES
    if not scan.handles:
        return 0, None
    if getattr(scan, "cancelled", False):
        raise RuntimeError(
            "Czytanie rysunku zostało przerwane — mapa uchwytów jest niepełna. "
            "Uruchom sprawdzenie jeszcze raz."
        )

    kopia = backup(gpkg_path) if make_backup else None
    conn = _connect(gpkg_path)
    zmian = 0
    pominiete = []
    try:
        conn.execute(
            "CREATE TEMP TABLE dwgplus_handles "
            "(handle INTEGER PRIMARY KEY, layer TEXT)"
        )
        dane = (
            (h, w) for h, w in scan.handles.items()
            if not (skip_block_content and h in scan.in_blocks)
        )
        conn.executemany(
            "INSERT OR REPLACE INTO dwgplus_handles VALUES (?, ?)", dane
        )
        obecne = _existing_tables(conn)
        for i, table in enumerate(tables):
            if feedback is not None and feedback.isCanceled():
                # Zatwierdzenie polowy tabel wygladaloby jak sukces, a zostawiloby
                # rysunek w stanie nie do opisania. Albo calosc, albo nic.
                conn.rollback()
                return 0, kopia
            if table not in obecne:
                pominiete.append(table)
                continue
            try:
                # `IS NOT` zamiast `<>`: przy warstwie NULL w bazie zwykle
                # porownanie daje NULL, wiec EXISTS jest falszywe i wiersz —
                # dokladnie ten, dla ktorego ta naprawa istnieje — zostalby
                # po cichu pominiety
                kursor = conn.execute(
                    'UPDATE "{0}" SET "{1}" = ('
                    "  SELECT layer FROM dwgplus_handles h "
                    '  WHERE h.handle = "{0}"."{2}") '
                    "WHERE {3} AND EXISTS ("
                    "  SELECT 1 FROM dwgplus_handles h "
                    '  WHERE h.handle = "{0}"."{2}" '
                    '        AND h.layer IS NOT "{0}"."{1}")'
                    .format(table, S.C_LAYER, S.C_HANDLE, S.BASE_FILTER)
                )
                zmian += kursor.rowcount if kursor.rowcount > 0 else 0
            except sqlite3.Error as exc:
                raise RuntimeError(
                    "Nie udało się poprawić tabeli {0}: {1}".format(table, exc)
                )
            if progress_cb is not None:
                progress_cb(int((i + 1) * 100 / len(tables)))
        # Wyzwalacze RTree sa tu bezpieczne, bo nie ruszamy ani kolumny
        # geometrii, ani `fid`: jedne sa zadeklarowane AFTER UPDATE OF geom
        # i w ogole nie wstaja, drugie maja warunek OLD.fid != NEW.fid.
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS dwgplus_handles")
            conn.commit()
        except sqlite3.Error:
            pass
        conn.close()
    return zmian, kopia


def source_drawing(gpkg_path):
    """Ścieżka rysunku zapisana przez import w tabeli ``drawing``.

    Zwraca listę kandydatów: najpierw to, co zapisał import, potem plik obok
    GeoPackage o tej samej nazwie — rysunki lubią się przeprowadzać.
    """
    kandydaci = []
    try:
        conn = sqlite3.connect(
            "file:{0}?mode=ro".format(_uri(gpkg_path)), uri=True
        )
    except sqlite3.Error:
        conn = None
    if conn is not None:
        try:
            for row in conn.execute('SELECT * FROM "{0}"'.format(S.T_DRAWING)):
                for wartosc in row:
                    if isinstance(wartosc, bytes):
                        wartosc = _decode(wartosc)
                    if isinstance(wartosc, str) and wartosc.lower().endswith(
                        (".dxf", ".dwg")
                    ):
                        kandydaci.append(wartosc)
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    obok = os.path.splitext(gpkg_path)[0]
    for rozszerzenie in (".dxf", ".DXF", ".dwg", ".DWG"):
        kandydaci.append(obok + rozszerzenie)
    # zachowaj kolejność, usuń duplikaty
    widziane, out = set(), []
    for kandydat in kandydaci:
        if kandydat not in widziane:
            widziane.add(kandydat)
            out.append(kandydat)
    return out


def first_existing(paths):
    for path in paths:
        if path and os.path.exists(path):
            return path
    return ""
