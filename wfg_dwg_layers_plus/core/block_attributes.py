# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Atrybuty bloków (ATTRIB) — odzyskiwanie danych, których QGIS gubi.

Dlaczego to osobny moduł, a nie część importu:

Biblioteka ``libdxfrw``, której QGIS używa i do DWG, i do DXF, **nie zna
atrybutów bloków**. W jej enumie typów encji ``ATTDEF`` i ``ATTRIB`` są
zakomentowane, a ``DRW_Interface`` nie ma żadnego ``addAttrib``. W czytniku DXF
atrybuty wpadają do zbiorczego ``else``, który przewija plik do następnej encji;
w czytniku DWG lądują w ``default:``. Wartość nie przekracza granicy między
biblioteką a QGIS-em — w powstałym GeoPackage nie ma jej w żadnej tabeli.
(Tabela ``appdata`` jest tworzona i nigdy nie zapisywana, a i tak dotyczy danych
grupy 102, nie atrybutów bloku.)

Sterownik ``DXF`` w GDAL — wbudowany zawsze, zero zależności — atrybuty czyta,
ale tylko przy **wyłączonym** wklejaniu bloków (``DXF_INLINE_BLOCKS=FALSE``).
Wtedy wstawienia są punktami z polami ``BlockName``, ``EntityHandle``
i ``BlockAttributes`` (lista łańcuchów w formacie ``"ZNACZNIK wartość"``).

Klucz do sklejenia obu światów: QGIS zapisuje w tabeli ``inserts`` kolumnę
``handle`` — ten sam uchwyt encji z grupy 5, tylko dziesiętnie zamiast
szesnastkowo. Stąd ``int(EntityHandle, 16)`` daje bezpośrednie dopasowanie.
"""

import os
import re

from . import naming

#: nazwa tabeli z atrybutami w GeoPackage
TABLE = "dwgplus_block_attributes"

#: prefiks kolumn, żeby nie zderzyć się z polami tabeli `inserts`
COLUMN_PREFIX = "att_"

#: górny limit kolumn — powyżej tego znaczniki są obcinane wg częstości
MAX_COLUMNS = 60

_SAFE = re.compile(r"[^0-9A-Za-z_]+")

#: Domyślne kodowanie tekstu w rysunkach robionych w polskich CAD-ach.
#: DXF-y deklarujące wersję R2018 powinny być w UTF-8, ale wiele programów
#: zapisuje bajty w stronie kodowej systemu i nie poprawia nagłówka.
DEFAULT_ENCODING = "cp1250"

#: zakres zastępczych par surogatów, którymi Python oznacza bajty nie do zdekodowania
_SURROGATE_LO = 0xDC80
_SURROGATE_HI = 0xDCFF


def to_text(value, encoding=DEFAULT_ENCODING):
    """Sprowadza to, co zwraca GDAL, do poprawnego tekstu.

    Sterownik DXF nie transkoduje łańcuchów, gdy nie potrafi ich odczytać jako
    UTF-8. Wiązania Pythona oddają wtedy albo obiekt ``bytes``, albo ``str``
    z osieroconymi surogatami (``surrogateescape``). Bez tego kroku
    ``str(b"KOTA_WYKO\xd1CZENIE 102,9")`` daje literał repr-a — i znacznik
    atrybutu robi się z niego ``b'KOTA_WYKO\xd1CZENIE``.

    Tekst już poprawny przechodzi tędy nietknięty.
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        if not any(_SURROGATE_LO <= ord(ch) <= _SURROGATE_HI for ch in value):
            return value          # zwykły, poprawny tekst — nie ruszamy
        try:
            raw = value.encode("utf-8", "surrogateescape")
        except (UnicodeEncodeError, LookupError):
            return value
    else:
        return str(value)

    for enc in (encoding, "utf-8", "cp1250", "cp1252", "latin-1"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", errors="replace")


class AttributeScan(object):
    """Wynik skanu rysunku."""

    def __init__(self):
        self.rows = {}        # handle (int) -> {"block": str, "att": {tag: value}}
        self.blocks = {}      # nazwa bloku -> {"count": int, "tags": {tag: liczba}}
        self.errors = []
        self.dxf_path = None
        self.encoding = DEFAULT_ENCODING
        #: True, gdy GDAL oddał choć jeden łańcuch wymagający przekodowania
        self.recoded = False

    @property
    def total(self):
        return len(self.rows)

    def tags(self):
        """Wszystkie znaczniki, od najczęstszego."""
        counts = {}
        for info in self.blocks.values():
            for tag, n in info["tags"].items():
                counts[tag] = counts.get(tag, 0) + n
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    def block_rows(self):
        return sorted(
            (
                (name, info["count"], sorted(info["tags"]))
                for name, info in self.blocks.items()
            ),
            key=lambda r: (-r[1], r[0].lower()),
        )


class AttributeError_(Exception):
    pass


def sanitize_tag(tag):
    # polskie znaki najpierw na ASCII, zeby RZEDNA nie zrobila sie z RZ_DNA
    out = _SAFE.sub("_", naming.transliterate(str(tag))).strip("_")
    if not out:
        out = "tag"
    if out[0].isdigit():
        out = "t_" + out
    return COLUMN_PREFIX + out


def _split_attribute(entry, encoding=DEFAULT_ENCODING):
    """GDAL zwraca ``"ZNACZNIK wartość"``; spacje w znaczniku zamienia na ``_``."""
    text = to_text(entry, encoding)
    if " " not in text:
        return text, ""
    tag, value = text.split(" ", 1)
    return tag, value


def scan(dxf_path, feedback=None, progress_cb=None, block_filter=None,
         encoding=DEFAULT_ENCODING):
    """Czyta atrybuty bloków z DXF-a (albo DWG-a przez konwerter)."""
    try:
        from osgeo import gdal, ogr
    except ImportError as exc:  # noqa: BLE001
        raise AttributeError_("Brak modułu osgeo (GDAL): {0}".format(exc))

    if not os.path.exists(dxf_path):
        raise AttributeError_("Plik nie istnieje: {0}".format(dxf_path))

    path = dxf_path
    if os.path.splitext(path)[1].lower() == ".dwg":
        from . import producer_ogr

        if progress_cb:
            progress_cb(0, "Konwersja DWG → DXF…")
        path = producer_ogr.convert_dwg_to_dxf(path)

    scan_result = AttributeScan()
    scan_result.dxf_path = path
    scan_result.encoding = encoding

    # Przed GDAL 3.7 gdal.UseExceptions() obejmowalo TYLKO modul gdal, wiec
    # wywolania ogr.* nadal cicho zwracalyby None / kody bledow. QGIS 3.28-3.34
    # wozi zwykle GDAL 3.4-3.6, wiec przelaczamy oba modulu osobno.
    had_exceptions = gdal.GetUseExceptions()
    had_ogr_exceptions = ogr.GetUseExceptions()
    gdal.UseExceptions()
    ogr.UseExceptions()
    saved = {}
    # Atrybuty istnieją TYLKO przy wyłączonym wklejaniu bloków — przy
    # INLINE_BLOCKS=TRUE GDAL zamienia ATTRIB na zwykły tekst i gubi znacznik.
    overrides = {"DXF_INLINE_BLOCKS": "FALSE", "DXF_MERGE_BLOCK_GEOMETRIES": "FALSE"}
    for key, value in overrides.items():
        saved[key] = gdal.GetConfigOption(key)
        gdal.SetConfigOption(key, value)

    try:
        src = ogr.Open(path)
        if src is None:
            raise AttributeError_("GDAL nie otworzył pliku: {0}".format(path))
        # UWAGA: przy DXF_INLINE_BLOCKS=FALSE sterownik wystawia DWIE warstwy,
        # 'blocks' i 'entities', a GetLayer(0) to 'blocks'. Wstawienia
        # z atrybutami są w 'entities'.
        layer = src.GetLayerByName("entities") or src.GetLayer(0)
        defn = layer.GetLayerDefn()
        idx_handle = defn.GetFieldIndex("EntityHandle")
        idx_block = defn.GetFieldIndex("BlockName")
        idx_att = defn.GetFieldIndex("BlockAttributes")
        if idx_att < 0:
            raise AttributeError_(
                "Ten plik nie ma pola BlockAttributes — GDAL nie zobaczył "
                "żadnych atrybutów bloków. Sprawdź, czy rysunek na pewno "
                "używa atrybutów, a nie zwykłych tekstów."
            )

        # Swiadomie NIE wolamy GetFeatureCount(): sterownik DXF musialby
        # sparsowac caly plik, zeby ja podac, a zaraz potem parsuje go jeszcze
        # raz w petli. Przy wielkim rysunku to podwojony czas. Zamiast tego
        # raportujemy postep licznikiem (pasek w trybie nieokreslonym).
        for i, feat in enumerate(layer):
            if feedback is not None and feedback.isCanceled():
                break
            if progress_cb is not None and i % 5000 == 0:
                progress_cb(-1, "Przetworzono encji: {0}".format(i))

            if idx_att < 0 or not feat.IsFieldSet(idx_att):
                continue
            values = feat.GetFieldAsStringList(idx_att)
            if not values:
                continue

            block = to_text(
                feat.GetField(idx_block) if idx_block >= 0 else "", encoding
            )
            if block_filter and block not in block_filter:
                continue

            handle_hex = to_text(
                feat.GetField(idx_handle) if idx_handle >= 0 else "", encoding
            )
            handle = _handle_to_int(handle_hex)
            if handle is None:
                continue

            attrs = {}
            for entry in values:
                tag, value = _split_attribute(entry, encoding)
                if tag:
                    attrs[tag] = value
            if not attrs:
                continue
            if not scan_result.recoded and any(
                isinstance(v, bytes) for v in values
            ):
                scan_result.recoded = True

            scan_result.rows[handle] = {"block": block or "", "att": attrs}
            info = scan_result.blocks.setdefault(
                block or "", {"count": 0, "tags": {}}
            )
            info["count"] += 1
            for tag in attrs:
                info["tags"][tag] = info["tags"].get(tag, 0) + 1
    finally:
        for key, value in saved.items():
            gdal.SetConfigOption(key, value)
        if not had_exceptions:
            try:
                gdal.DontUseExceptions()
            except Exception:
                pass
        if not had_ogr_exceptions:
            try:
                ogr.DontUseExceptions()
            except Exception:
                pass

    if progress_cb is not None:
        progress_cb(100, "")
    return scan_result


def _handle_to_int(value):
    """``EntityHandle`` z GDAL-a jest szesnastkowy, ``inserts.handle`` dziesiętny."""
    if not value:
        return None
    try:
        return int(str(value).strip(), 16)
    except (TypeError, ValueError):
        return None


def choose_columns(scan_result, max_columns=MAX_COLUMNS):
    """Znaczniki → nazwy kolumn, z deduplikacją i limitem."""
    chosen = []
    used = set()
    dropped = []
    for tag, _count in scan_result.tags():
        if len(chosen) >= max_columns:
            dropped.append(tag)
            continue
        name = sanitize_tag(tag)
        base = name
        n = 2
        while name.lower() in used:
            name = "{0}_{1}".format(base, n)
            n += 1
        used.add(name.lower())
        chosen.append((tag, name))
    return chosen, dropped


def _is_numeric(values):
    """Czy wszystkie wartosci znacznika bezpiecznie sa liczbami.

    Ostroznie: numery inwentaryzacyjne typu "007" tez parsuja sie jako float,
    a zamiana na 7.0 gubi zera wiodace bezpowrotnie. Odrzucamy tez zapisy,
    ktore float() przyjmuje, a czlowiek by nie uznal za liczbe ("1_0", "nan",
    "inf", notacja szesnastkowa).
    """
    seen = False
    for value in values:
        text = str(value).strip().replace(",", ".")
        if not text:
            continue
        if "_" in text:
            return False
        if text.lstrip("+-").lower() in ("nan", "inf", "infinity"):
            return False
        body = text.lstrip("+-")
        # zero wiodace przed cyfra to identyfikator, nie liczba ("007", "01")
        if len(body) > 1 and body[0] == "0" and body[1] not in (".", ","):
            return False
        try:
            float(text)
        except ValueError:
            return False
        seen = True
    return seen


def write_table(gpkg_path, scan_result, columns, feedback=None):
    """Zapisuje szeroką tabelę atrybutów do GeoPackage. Zwraca liczbę wierszy."""
    try:
        from osgeo import gdal, ogr
    except ImportError as exc:  # noqa: BLE001
        raise AttributeError_("Brak modułu osgeo (GDAL): {0}".format(exc))

    had_exceptions = gdal.GetUseExceptions()
    had_ogr_exceptions = ogr.GetUseExceptions()
    gdal.UseExceptions()
    ogr.UseExceptions()
    try:
        ds = ogr.Open(gpkg_path, 1)
        if ds is None:
            raise AttributeError_(
                "Nie można otworzyć GeoPackage do zapisu: {0}".format(gpkg_path)
            )
        # Uchwyt warstwy uniewaznia sie po DeleteLayer — dotkniecie go potem
        # konczy sie segfaultem, wiec zrzucamy referencje przed usunieciem.
        existing = ds.GetLayerByName(TABLE) is not None
        if existing:
            for i in range(ds.GetLayerCount()):
                if ds.GetLayer(i).GetName() == TABLE:
                    ds.DeleteLayer(i)
                    break

        out = ds.CreateLayer(TABLE, None, ogr.wkbNone)
        out.CreateField(ogr.FieldDefn("insert_handle", ogr.OFTInteger64))
        out.CreateField(ogr.FieldDefn("block_name", ogr.OFTString))

        numeric = {}
        for tag, column in columns:
            values = [
                row["att"].get(tag)
                for row in scan_result.rows.values()
                if row["att"].get(tag) not in (None, "")
            ]
            numeric[tag] = _is_numeric(values)
            out.CreateField(
                ogr.FieldDefn(column, ogr.OFTReal if numeric[tag] else ogr.OFTString)
            )

        defn = out.GetLayerDefn()
        ds.StartTransaction()
        written = 0
        cancelled = False
        try:
            for handle, row in scan_result.rows.items():
                if feedback is not None and feedback.isCanceled():
                    cancelled = True
                    break
                feat = ogr.Feature(defn)
                feat.SetField("insert_handle", int(handle))
                feat.SetField("block_name", row["block"])
                for tag, column in columns:
                    value = row["att"].get(tag)
                    if value in (None, ""):
                        continue
                    if numeric[tag]:
                        try:
                            feat.SetField(column, float(str(value).replace(",", ".")))
                        except ValueError:
                            pass
                    else:
                        feat.SetField(column, str(value))
                if out.CreateFeature(feat) != 0:
                    raise AttributeError_(
                        "GDAL odrzucil wiersz dla uchwytu {0}".format(handle)
                    )
                feat = None
                written += 1
        except BaseException:
            # Bez wycofania zostawilibysmy polowicznie zapisana tabele w miejscu
            # kompletnej, ktora przed chwila skasowalismy.
            ds.RollbackTransaction()
            raise
        else:
            if cancelled:
                ds.RollbackTransaction()
                written = 0
            else:
                ds.CommitTransaction()

        if written:
            ds.ExecuteSQL(
                'CREATE INDEX IF NOT EXISTS idx_{0}_handle ON "{0}" '
                "(insert_handle)".format(TABLE)
            )
        ds = None
        return written
    finally:
        if not had_exceptions:
            try:
                gdal.DontUseExceptions()
            except Exception:
                pass
        if not had_ogr_exceptions:
            try:
                ogr.DontUseExceptions()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# podpięcie do warstw w projekcie
# ---------------------------------------------------------------------------

#: pola łączące: warstwy z tabeli `inserts` mają `handle`,
#: warstwy blokowe i kotwice mają `insert_handle`
_TARGET_FIELDS = ("handle", "insert_handle")


class JoinResult(object):
    def __init__(self):
        self.table_layer = None
        self.joined = []
        self.skipped = 0
        self.errors = []


def load_table_layer(gpkg_path, name=None):
    """Wczytuje tabelę atrybutów jako warstwę QGIS (bez geometrii)."""
    from qgis.core import QgsVectorLayer

    layer = QgsVectorLayer(
        "{0}|layername={1}".format(gpkg_path, TABLE), name or "Atrybuty bloków", "ogr"
    )
    return layer if layer.isValid() else None


def _target_field(layer):
    names = {f.name().lower(): f.name() for f in layer.fields()}
    for candidate in _TARGET_FIELDS:
        if candidate in names:
            return names[candidate]
    return None


def attach_joins(gpkg_path, project=None, prefix="", table_layer=None):
    """Podpina złączenie po uchwycie do wszystkich warstw wstawień i kotwic.

    Złączenie jest nieniszczące — nie zmienia danych w GeoPackage, a użytkownik
    może je zdjąć we właściwościach warstwy.
    """
    from qgis.core import QgsProject, QgsVectorLayer, QgsVectorLayerJoinInfo

    project = project or QgsProject.instance()
    result = JoinResult()

    layer = table_layer or load_table_layer(gpkg_path)
    if layer is None:
        result.errors.append(
            "Nie udało się wczytać tabeli {0} z {1}".format(TABLE, gpkg_path)
        )
        return result

    if not project.mapLayer(layer.id()):
        project.addMapLayer(layer, False)
    result.table_layer = layer

    gpkg_norm = os.path.normcase(os.path.abspath(gpkg_path))

    for candidate in list(project.mapLayers().values()):
        if not isinstance(candidate, QgsVectorLayer):
            continue
        if candidate.id() == layer.id():
            continue
        source = (candidate.source() or "").split("|")[0]
        if os.path.normcase(os.path.abspath(source)) != gpkg_norm:
            continue

        name = candidate.name()
        is_insert = name.endswith("_insert")
        is_block = name.startswith("blk_")
        if not (is_insert or is_block):
            continue

        target = _target_field(candidate)
        if target is None:
            result.skipped += 1
            continue

        # nie dokładaj drugi raz tego samego złączenia
        if any(j.joinLayerId() == layer.id() for j in candidate.vectorJoins()):
            continue

        info = QgsVectorLayerJoinInfo()
        info.setJoinLayer(layer)
        info.setJoinFieldName("insert_handle")
        info.setTargetFieldName(target)
        info.setUsingMemoryCache(True)
        info.setPrefix(prefix)
        if candidate.addJoin(info):
            result.joined.append(candidate.name())
        else:
            result.errors.append("Nie podpięto złączenia do {0}".format(candidate.name()))

    return result


def table_layer_ids(project=None):
    """Identyfikatory warstw wskazujących na tabelę atrybutów."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    needle = "layername={0}".format(TABLE)
    return {
        lid
        for lid, lyr in project.mapLayers().items()
        if isinstance(lyr, QgsVectorLayer) and needle in (lyr.source() or "")
    }


def detach_joins(project=None, remove_table_layer=True):
    """Zdejmuje złączenia założone przez ten moduł.

    Domyślnie usuwa też samą tabelę atrybutów z projektu. Bez tego zostawałaby
    zarejestrowana, ale niewidoczna w panelu warstw — nie do usunięcia z GUI.
    """
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    removed = 0
    table_ids = table_layer_ids(project)
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        for join in list(layer.vectorJoins()):
            if join.joinLayerId() in table_ids:
                layer.removeJoin(join.joinLayerId())
                removed += 1
    if remove_table_layer and table_ids:
        project.removeMapLayers(list(table_ids))
    return removed


def reset(project=None):
    """Sprząta stan po poprzednim przebiegu.

    Konieczne przed ponownym zapisem: ``write_table`` kasuje i odtwarza tabelę,
    a stara warstwa QGIS wskazuje wtedy na nieistniejący już byt i — co gorsza —
    trzyma w pamięci podręczną kopię starych wartości złączenia. Nowa warstwa
    dostaje nowy identyfikator, więc zabezpieczenie przed podwójnym złączeniem
    by jej nie rozpoznało i użytkownik oglądałby stare dane.
    """
    return detach_joins(project, remove_table_layer=True)


def guess_dxf_for(gpkg_path):
    """Domyślna ścieżka rysunku obok GeoPackage (ta sama nazwa, inne rozszerzenie)."""
    stem = os.path.splitext(gpkg_path)[0]
    for ext in (".dxf", ".DXF", ".dwg", ".DWG"):
        candidate = stem + ext
        if os.path.exists(candidate):
            return candidate
    return ""


def gpkg_from_project(project=None):
    """Najczęściej używany GeoPackage wśród warstw projektu."""
    from qgis.core import QgsProject, QgsVectorLayer

    project = project or QgsProject.instance()
    counts = {}
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        source = (layer.source() or "").split("|")[0]
        if source.lower().endswith(".gpkg") and os.path.exists(source):
            counts[source] = counts.get(source, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]
