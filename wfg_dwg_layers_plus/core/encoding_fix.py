# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Naprawa podwójnego kodowania tekstu („mojibake") w GeoPackage z importu DWG/DXF.

Skąd się to bierze. DXF w wersji R2007 i nowszej ma treść w UTF-8 i nagłówkowa
strona kodowa ``$DWGCODEPAGE`` powinna być wtedy ignorowana. Wiele CAD-ów
zostawia w nagłówku starą wartość (u nas ``ANSI_1250``), a biblioteka czytająca
posłusznie ją stosuje — czyta bajty UTF-8 tak, jakby były w cp1250. Efekt:

    ę  →  bajty C4 99  →  odczytane jako cp1250  →  "Ä™"
    ś  →  bajty C5 9B  →                          →  "Ĺ›"
    ł  →  bajty C5 82  →                          →  "Ĺ‚"

Kluczowe: **to jest odwracalne bez straty**. Wystarczy zakodować napis z powrotem
do bajtów tą samą stroną kodową i odczytać jako UTF-8. Warunek — każdy znak
uszkodzonego napisu musi dać się zapisać w tej stronie kodowej; jeśli nie, znaczy
że po drodze coś już przepadło i wtedy zostawiamy napis w spokoju.

Naprawa musi objąć trzy rzeczy naraz, inaczej projekt się rozjedzie:

1. dane w GeoPackage (nazwy warstw CAD, nazwy bloków, treść tekstów),
2. filtry warstw w projekcie — odwołują się do starych wartości kolumny ``layer``,
3. nazwy warstw i grup w legendzie.
"""

import os
import re
import shutil
import sqlite3
from ..i18n import tr

#: znaki, które w praktyce pojawiają się tylko w uszkodzonym tekście.
#: Bez tego testu zwykły, poprawny napis mógłby przypadkiem przejść przez
#: konwersję i zostać zepsuty.
_MARKERS = set("ÂÃÄÅĂĹŃÎÐÑ×Ø")

#: znaki, które muszą się pojawić w wyniku, żeby uznać naprawę za udaną
_POLISH = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

DEFAULT_ENCODING = "cp1250"

#: kolumny, których nigdy nie ruszamy — bywają tekstowe, ale niosą liczby
_SKIP_COLUMNS = {"color", "ocolor", "color24"}

_LITERAL = re.compile(r"'((?:[^']|'')*)'")

#: Funkcje, których żąda GeoPackage w wyzwalaczach indeksu przestrzennego.
#:
#: To jest pułapka, na której ta funkcja początkowo wykładała się w komplecie.
#: Wyzwalacze RTree są zadeklarowane jako ``AFTER UPDATE ON <tabela>``, a nie
#: ``AFTER UPDATE OF geom``, więc SQLite kompiluje ich treść przy KAŻDYM
#: ``UPDATE`` na tabeli i rozwiązuje nazwy funkcji już na etapie przygotowania
#: zapytania — mimo że warunek ``WHEN OLD.fid != NEW.fid`` sprawia, że ciało
#: nigdy się nie wykona. Zwykłe połączenie ``sqlite3`` nie zna funkcji GPKG,
#: więc zapytanie nie daje się nawet skompilować.
#:
#: Podstawiamy więc atrapy. Są bezpieczne: nie ruszamy ani geometrii, ani ``fid``,
#: więc żaden z wyzwalaczy nie ma prawa się uruchomić.
_GPKG_TRIGGER_FUNCS = (
    "ST_IsEmpty", "ST_MinX", "ST_MaxX", "ST_MinY", "ST_MaxY",
)


def _connect(path, timeout=60.0):
    """Połączenie z GeoPackage gotowe do zapisu.

    Hojny ``timeout``, bo QGIS trzyma ten sam plik otwarty do odczytu i przy
    trwającym rysowaniu mapy blokada potrafi się utrzymać kilka sekund.
    """
    conn = sqlite3.connect(path, timeout=timeout)
    for name in _GPKG_TRIGGER_FUNCS:
        try:
            conn.create_function(name, 1, lambda value: None)
        except sqlite3.Error:
            pass
    return conn


def looks_broken(text):
    """Czy napis wygląda na podwójnie zakodowany."""
    if not text or not isinstance(text, str):
        return False
    return any(ch in _MARKERS for ch in text)


def repair(text, encoding=DEFAULT_ENCODING):
    """Zwraca naprawiony napis albo ``None``, gdy naprawa się nie udała.

    Świadomie jesteśmy ostrożni: wynik uznajemy tylko wtedy, gdy naprawdę się
    zmienił, zawiera polskie znaki i nie wprowadził znaków zastępczych.
    """
    if not looks_broken(text):
        return None
    try:
        candidate = text.encode(encoding).decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
        return None
    if candidate == text or "�" in candidate:
        return None
    if not any(ch in _POLISH for ch in candidate):
        return None
    return candidate


def repair_or_same(text, encoding=DEFAULT_ENCODING):
    fixed = repair(text, encoding)
    return text if fixed is None else fixed


def repair_sql_literals(expression, encoding=DEFAULT_ENCODING):
    """Naprawia literały tekstowe wewnątrz wyrażenia SQL (filtru warstwy)."""
    if not expression:
        return expression

    def _sub(match):
        inner = match.group(1)
        fixed = repair(inner.replace("''", "'"), encoding)
        if fixed is None:
            return match.group(0)
        return "'" + fixed.replace("'", "''") + "'"

    return _LITERAL.sub(_sub, expression)


# ---------------------------------------------------------------------------
# GeoPackage
# ---------------------------------------------------------------------------


class ScanResult(object):
    def __init__(self):
        self.columns = {}     # (tabela, kolumna) -> {"count": int, "samples": [(przed, po)]}
        self.total = 0
        self.errors = []

    def rows(self):
        return sorted(
            (
                (table, column, info["count"], info["samples"])
                for (table, column), info in self.columns.items()
            ),
            key=lambda r: (-r[2], r[0], r[1]),
        )


def _text_columns(conn, table):
    try:
        info = conn.execute('PRAGMA table_info("{0}")'.format(table)).fetchall()
    except sqlite3.Error:
        return []
    out = []
    for row in info:
        name, ctype = row[1], (row[2] or "").upper()
        if name in _SKIP_COLUMNS:
            continue
        if "CHAR" in ctype or "TEXT" in ctype or "CLOB" in ctype or ctype == "":
            out.append(name)
    return out


def _user_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%' "
        "AND name NOT LIKE 'rtree_%'"
    ).fetchall()
    return [r[0] for r in rows]


def scan_gpkg(path, encoding=DEFAULT_ENCODING, sample_limit=3, feedback=None):
    """Znajduje wszystkie kolumny tekstowe z uszkodzonymi wartościami."""
    result = ScanResult()
    conn = _connect(path)
    try:
        for table in _user_tables(conn):
            if feedback is not None and feedback.isCanceled():
                break
            for column in _text_columns(conn, table):
                try:
                    cur = conn.execute(
                        'SELECT "{0}" FROM "{1}" WHERE "{0}" IS NOT NULL'.format(
                            column, table
                        )
                    )
                except sqlite3.Error:
                    continue
                count = 0
                samples = []
                for (value,) in cur:
                    if not isinstance(value, str):
                        continue
                    fixed = repair(value, encoding)
                    if fixed is None:
                        continue
                    count += 1
                    if len(samples) < sample_limit:
                        samples.append((value, fixed))
                if count:
                    result.columns[(table, column)] = {
                        "count": count,
                        "samples": samples,
                    }
                    result.total += count
    finally:
        conn.close()
    return result


def backup(path):
    """Kopia zapasowa obok pliku. Zwraca ścieżkę albo None."""
    target = path + ".bak"
    n = 2
    while os.path.exists(target):
        target = "{0}.bak{1}".format(path, n)
        n += 1
    shutil.copy2(path, target)
    return target


def apply_gpkg(path, encoding=DEFAULT_ENCODING, make_backup=True,
               feedback=None, progress_cb=None):
    """Poprawia wartości w GeoPackage. Zwraca ``(liczba_zmian, sciezka_kopii)``."""
    backup_path = backup(path) if make_backup else None

    conn = _connect(path)
    changed = 0
    try:
        tables = _user_tables(conn)
        total_tables = len(tables) or 1
        conn.execute("BEGIN")
        for i, table in enumerate(tables):
            if feedback is not None and feedback.isCanceled():
                conn.execute("ROLLBACK")
                return 0, backup_path
            if progress_cb is not None:
                progress_cb(int(100.0 * i / total_tables), table)

            for column in _text_columns(conn, table):
                try:
                    cur = conn.execute(
                        'SELECT rowid, "{0}" FROM "{1}" WHERE "{0}" IS NOT NULL'.format(
                            column, table
                        )
                    )
                except sqlite3.Error:
                    continue
                updates = []
                for rowid, value in cur:
                    if not isinstance(value, str):
                        continue
                    fixed = repair(value, encoding)
                    if fixed is not None:
                        updates.append((fixed, rowid))
                if not updates:
                    continue
                conn.executemany(
                    'UPDATE "{0}" SET "{1}" = ? WHERE rowid = ?'.format(table, column),
                    updates,
                )
                changed += len(updates)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()

    if progress_cb is not None:
        progress_cb(100, "")
    return changed, backup_path


# ---------------------------------------------------------------------------
# projekt QGIS
# ---------------------------------------------------------------------------


class ProjectResult(object):
    def __init__(self):
        self.layers = 0
        self.groups = 0
        self.filters = 0
        self.details = []


def scan_project(project=None, encoding=DEFAULT_ENCODING):
    """Podgląd zmian w projekcie: ``[(rodzaj, przed, po), ...]``."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    out = []
    for layer in project.mapLayers().values():
        fixed = repair(layer.name(), encoding)
        if fixed is not None:
            out.append(("warstwa", layer.name(), fixed))
        if isinstance(layer, QgsVectorLayer):
            try:
                subset = layer.subsetString()
            except Exception:
                subset = ""
            if subset:
                new_subset = repair_sql_literals(subset, encoding)
                if new_subset != subset:
                    out.append(("filtr", subset, new_subset))
    for group in project.layerTreeRoot().findGroups(recursive=True):
        fixed = repair(group.name(), encoding)
        if fixed is not None:
            out.append(("grupa", group.name(), fixed))
    return out


def apply_project(project=None, encoding=DEFAULT_ENCODING, fix_filters=True):
    """Poprawia nazwy warstw i grup oraz — opcjonalnie — filtry warstw.

    Filtry poprawiamy TYLKO razem z danymi w GeoPackage. Osobno nie ma to sensu:
    filtr odwołuje się do wartości kolumny ``layer``, więc naprawiony filtr na
    nienaprawionych danych nie pasowałby do niczego.
    """
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    result = ProjectResult()

    for layer in project.mapLayers().values():
        fixed = repair(layer.name(), encoding)
        if fixed is not None:
            layer.setName(fixed)
            result.layers += 1
        if fix_filters and isinstance(layer, QgsVectorLayer):
            try:
                subset = layer.subsetString()
            except Exception:
                continue
            if not subset:
                continue
            new_subset = repair_sql_literals(subset, encoding)
            if new_subset != subset:
                if layer.setSubsetString(new_subset):
                    result.filters += 1
                else:
                    result.details.append(
                        tr("Nie udało się poprawić filtru warstwy {0}").format(layer.name())
                    )

    for group in project.layerTreeRoot().findGroups(recursive=True):
        fixed = repair(group.name(), encoding)
        if fixed is not None:
            group.setName(fixed)
            result.groups += 1

    project.setDirty(True)
    return result


def layers_on_gpkg(gpkg_path, project=None):
    """Warstwy projektu wskazujące na dany GeoPackage."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    target = os.path.normcase(os.path.abspath(gpkg_path))
    out = []
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        source = (layer.source() or "").split("|")[0]
        if os.path.normcase(os.path.abspath(source)) == target:
            out.append(layer)
    return out


def editable_layers(gpkg_path, project=None):
    """Warstwy w trybie edycji — zapis przy nich otwartych to proszenie się o kłopoty.

    Bufor edycji przetrwałby ``reload()`` i przy zatwierdzeniu nadpisałby
    naprawione wartości starymi.
    """
    return [
        layer for layer in layers_on_gpkg(gpkg_path, project)
        if layer.isEditable()
    ]


def release_layers(gpkg_path, project=None):
    """Zwalnia uchwyty do pliku przed zapisem.

    ``QgsVectorLayer.reload()`` unieważnia pulę połączeń dostawcy OGR i zamyka
    plik. Bez tego trwający odczyt potrafi zablokować nasz zapis.
    """
    released = 0
    for layer in layers_on_gpkg(gpkg_path, project):
        try:
            layer.reload()
            released += 1
        except Exception:
            continue
    return released


def reload_layers(gpkg_path=None, project=None):
    """Odświeża warstwy po zapisie, żeby zobaczyły nowe wartości."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    layers = (
        layers_on_gpkg(gpkg_path, project) if gpkg_path
        else [l for l in project.mapLayers().values()
              if isinstance(l, QgsVectorLayer)]
    )
    for layer in layers:
        try:
            layer.reload()
            layer.triggerRepaint()
        except Exception:
            continue
    return len(layers)


def gpkg_paths_in_project(project=None):
    """Wszystkie GeoPackage używane przez warstwy projektu."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    out = []
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        source = (layer.source() or "").split("|")[0]
        if source.lower().endswith(".gpkg") and os.path.exists(source):
            if source not in out:
                out.append(source)
    return out
