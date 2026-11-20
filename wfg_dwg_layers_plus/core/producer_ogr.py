# -*- coding: utf-8 -*-
"""Producent C/D (eksperymentalny): wlasny import DXF przez GDAL, DWG przez konwerter.

Po co, skoro jest wbudowany import? Bo sterownik ``DXF`` w GDAL jest wbudowany
zawsze (zero zaleznosci) i przy rozwijaniu blokow robi cztery rzeczy, ktorych
wbudowany importer QGIS nie robi w komplecie:

* rozwija bloki zagniezdzone rekurencyjnie w 3D (skala X/Y/Z + OCS),
* rozwija MINSERT (tablice wierszy/kolumn),
* ma ochrone przed cyklami,
* dziedziczy warstwe ``0`` z wstawienia.

Modul zapisuje wynik w TYM SAMYM schemacie GeoPackage, co wbudowany import,
dzieki czemu reszta wtyczki (drzewo, style, materializacja) dziala bez zmian.

Ograniczenia: tabele ``blocks`` i ``inserts`` nie powstaja (bloki sa juz
rozwiniete), wiec tryb zlozonych geometrii blokow nie jest tu dostepny.
DWG wymaga zewnetrznego konwertera (ODA File Converter albo ``dwg2dxf``
z LibreDWG) — zadnego z nich nie wolno redystrybuowac razem z wtyczka,
wiec sa tylko wykrywane.
"""

import os
import re
import shutil
import subprocess
import tempfile

from . import gpkg_schema as S

_ODA_CANDIDATES = (
    r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe",
    r"C:\Program Files\ODA\ODAFileConverter_title\ODAFileConverter.exe",
    "/usr/bin/ODAFileConverter",
    "/opt/ODAFileConverter/ODAFileConverter",
)


class OgrImportError(Exception):
    pass


# ---------------------------------------------------------------------------
# DWG -> DXF
# ---------------------------------------------------------------------------


def find_oda_converter():
    for path in _ODA_CANDIDATES:
        if os.path.exists(path):
            return path
    found = shutil.which("ODAFileConverter")
    if found:
        return found
    # instalator ODA lubi dokladac numer wersji do nazwy katalogu
    base = r"C:\Program Files\ODA"
    if os.path.isdir(base):
        try:
            for entry in sorted(os.listdir(base), reverse=True):
                candidate = os.path.join(base, entry, "ODAFileConverter.exe")
                if os.path.exists(candidate):
                    return candidate
        except OSError:
            pass
    return None


def find_libredwg():
    return shutil.which("dwg2dxf")


def dwg_converter_available():
    return bool(find_oda_converter() or find_libredwg())


def convert_dwg_to_dxf(dwg_path, out_dir=None, version="ACAD2018", timeout=600):
    """Konwertuje DWG na DXF zewnetrznym narzedziem. Zwraca sciezke do DXF."""
    out_dir = out_dir or tempfile.mkdtemp(prefix="dwgplus_")
    stem = os.path.splitext(os.path.basename(dwg_path))[0]
    target = os.path.join(out_dir, stem + ".dxf")

    libredwg = find_libredwg()
    if libredwg:
        cmd = [libredwg, "-o", target, dwg_path]
        try:
            subprocess.run(cmd, check=True, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as exc:  # noqa: BLE001
            raise OgrImportError("dwg2dxf nie zadzialal: {0}".format(exc))
        if os.path.exists(target):
            return target

    oda = find_oda_converter()
    if oda:
        src_dir = tempfile.mkdtemp(prefix="dwgplus_in_")
        shutil.copy2(dwg_path, os.path.join(src_dir, os.path.basename(dwg_path)))
        cmd = [oda, src_dir, out_dir, version, "DXF", "0", "1"]
        try:
            subprocess.run(cmd, check=False, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as exc:  # noqa: BLE001
            raise OgrImportError("ODA File Converter nie zadzialal: {0}".format(exc))
        if os.path.exists(target):
            return target

    raise OgrImportError(
        "Nie znaleziono konwertera DWG -> DXF. Zainstaluj ODA File Converter "
        "(bezplatny, wymaga rejestracji) albo LibreDWG (dwg2dxf), albo uzyj "
        "wbudowanego importu QGIS, ktory czyta DWG bezposrednio."
    )


# ---------------------------------------------------------------------------
# parsowanie stylu OGR
# ---------------------------------------------------------------------------

_HEX = re.compile(r"#([0-9A-Fa-f]{6})([0-9A-Fa-f]{2})?")
_PEN_W = re.compile(r"\bw:([0-9.]+)\s*([a-z]*)")
_LABEL_S = re.compile(r"\bs:([0-9.]+)\s*([a-z]*)")
_LABEL_A = re.compile(r"\ba:(-?[0-9.]+)")
_LABEL_P = re.compile(r"\bp:([0-9]+)")


def _color_from_style(style, default="0,0,0,255"):
    if not style:
        return default
    m = _HEX.search(style)
    if not m:
        return default
    r = int(m.group(1)[0:2], 16)
    g = int(m.group(1)[2:4], 16)
    b = int(m.group(1)[4:6], 16)
    a = int(m.group(2), 16) if m.group(2) else 255
    return "{0},{1},{2},{3}".format(r, g, b, a)


def _linewidth_from_style(style):
    if not style:
        return 0.0
    m = _PEN_W.search(style)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit == "g":       # jednostki mapy — nie mm
        return 0.0
    if unit == "pt":
        return value * 25.4 / 72.0
    if unit == "px":
        return value * 25.4 / 96.0
    return value          # domyslnie milimetry


def _text_from_style(style):
    """Zwraca (wysokosc, kat_stopnie, alignh, alignv)."""
    height, angle, p = 1.0, 0.0, 1
    if style:
        m = _LABEL_S.search(style)
        if m:
            height = float(m.group(1))
        m = _LABEL_A.search(style)
        if m:
            angle = float(m.group(1))
        m = _LABEL_P.search(style)
        if m:
            p = int(m.group(1))
    p = max(1, min(9, p))
    alignh = (p - 1) % 3          # 0 lewo, 1 srodek, 2 prawo
    band = (p - 1) // 3           # 0 dol, 1 srodek, 2 gora
    alignv = {0: 1, 1: 2, 2: 3}[band]
    return height, angle, alignh, alignv


# ---------------------------------------------------------------------------
# import DXF -> GPKG w schemacie QGIS
# ---------------------------------------------------------------------------

_ETYPE_TEXT = 25
_ETYPE_LINE = 17
_ETYPE_POINT = 20
_ETYPE_HATCH = 13

#: definicje kolumn tabel wynikowych (nazwa, typ OGR)
def _entity_field_defs(ogr):
    return [
        (S.C_HANDLE, ogr.OFTInteger),
        (S.C_BLOCK, ogr.OFTInteger),
        (S.C_ETYPE, ogr.OFTInteger),
        (S.C_SPACE, ogr.OFTInteger),
        (S.C_LAYER, ogr.OFTString),
        ("olinetype", ogr.OFTString),
        (S.C_LINETYPE, ogr.OFTString),
        (S.C_COLOR, ogr.OFTString),
        (S.C_OCOLOR, ogr.OFTInteger),
        ("color24", ogr.OFTInteger),
        ("transparency", ogr.OFTInteger),
        ("lweight", ogr.OFTInteger),
        (S.C_LINEWIDTH, ogr.OFTReal),
        ("ltscale", ogr.OFTReal),
        ("visible", ogr.OFTInteger),
    ]


def _extra_field_defs(ogr, table):
    if table in (S.T_LINES, S.T_POLYLINES):
        return [("width", ogr.OFTReal), ("thickness", ogr.OFTReal)]
    if table == S.T_TEXTS:
        return [
            ("thickness", ogr.OFTReal),
            ("height", ogr.OFTReal),
            ("text", ogr.OFTString),
            ("angle", ogr.OFTReal),
            ("widthscale", ogr.OFTReal),
            ("oblique", ogr.OFTReal),
            ("style", ogr.OFTString),
            ("textgen", ogr.OFTInteger),
            ("alignh", ogr.OFTInteger),
            ("alignv", ogr.OFTInteger),
            ("interlin", ogr.OFTReal),
        ]
    if table == S.T_HATCHES:
        return [("thickness", ogr.OFTReal), ("name", ogr.OFTString),
                ("solid", ogr.OFTInteger)]
    return [("thickness", ogr.OFTReal)]


def _route(geom_type, ogr, has_text):
    """Do ktorej tabeli trafia obiekt o danym typie geometrii."""
    flat = ogr.GT_Flatten(geom_type)
    if flat == ogr.wkbPoint:
        return S.T_TEXTS if has_text else S.T_POINTS
    if flat in (ogr.wkbLineString, ogr.wkbMultiLineString,
                ogr.wkbCircularString, ogr.wkbCompoundCurve,
                ogr.wkbMultiCurve):
        return S.T_LINES
    if flat in (ogr.wkbPolygon, ogr.wkbMultiPolygon,
                ogr.wkbCurvePolygon, ogr.wkbMultiSurface):
        return S.T_HATCHES
    return None


def import_dxf(
    dxf_path,
    gpkg_path,
    explode_blocks=True,
    feature_limit_per_block=1000000,
    crs_authid=None,
    feedback=None,
    progress_cb=None,
):
    """Czyta DXF sterownikiem GDAL i zapisuje GPKG w schemacie QGIS."""
    try:
        from osgeo import gdal, ogr, osr
    except ImportError as exc:  # noqa: BLE001
        raise OgrImportError("Brak modulu osgeo (GDAL): {0}".format(exc))

    # Wyjatki GDAL sa globalne dla calego procesu QGIS (od GDAL 3.7 obejmuja
    # tez osgeo.ogr i osgeo.osr), wiec ustawiamy je tylko na czas importu.
    had_exceptions = gdal.GetUseExceptions()
    gdal.UseExceptions()

    # Opcje konfiguracyjne GDAL sa GLOBALNE dla calego procesu QGIS.
    # Ustawiamy je tylko na czas odczytu i przywracamy poprzednie wartosci,
    # zeby nie zmieniac zachowania kazdego pozniejszego odczytu DXF w sesji.
    overrides = {
        "DXF_INLINE_BLOCKS": "TRUE" if explode_blocks else "FALSE",
        # bez scalania dostajemy jeden obiekt na kazda encje bloku,
        # z zachowanym kolorem — scalanie zlepiloby wszystko w jedna kolekcje
        "DXF_MERGE_BLOCK_GEOMETRIES": "FALSE",
        "DXF_FEATURE_LIMIT_PER_BLOCK": str(int(feature_limit_per_block)),
    }
    saved = {k: gdal.GetConfigOption(k) for k in overrides}
    for key, value in overrides.items():
        gdal.SetConfigOption(key, value)

    try:
        return _import_dxf_inner(
            gdal, ogr, osr, dxf_path, gpkg_path, crs_authid, feedback, progress_cb
        )
    finally:
        for key, value in saved.items():
            gdal.SetConfigOption(key, value)   # None kasuje opcje
        if not had_exceptions:
            try:
                gdal.DontUseExceptions()
            except Exception:
                pass


def _import_dxf_inner(
    gdal, ogr, osr, dxf_path, gpkg_path, crs_authid, feedback, progress_cb
):
    src = ogr.Open(dxf_path)
    if src is None:
        raise OgrImportError("GDAL nie otworzyl pliku: {0}".format(dxf_path))

    srs = None
    if crs_authid and crs_authid.upper().startswith("EPSG:"):
        srs = osr.SpatialReference()
        try:
            srs.ImportFromEPSG(int(crs_authid.split(":")[1]))
        except Exception:
            srs = None

    driver = ogr.GetDriverByName("GPKG")
    if driver is None:
        raise OgrImportError("GDAL bez obslugi GeoPackage.")

    # Nie kasujemy cudzych plikow: jesli cel istnieje, dokladamy sufiks.
    # Na Windowsie usuniecie pliku otwartego w projekcie i tak by sie nie udalo.
    gpkg_path = _free_path(gpkg_path)
    dst = driver.CreateDataSource(gpkg_path)
    if dst is None:
        raise OgrImportError("Nie mozna utworzyc {0}".format(gpkg_path))

    out_layers = {}
    geom_types = {
        S.T_POINTS: ogr.wkbPoint25D,
        S.T_TEXTS: ogr.wkbPoint25D,
        S.T_LINES: ogr.wkbMultiLineString25D,
        S.T_HATCHES: ogr.wkbMultiPolygon25D,
    }
    for table, gtype in geom_types.items():
        lyr = dst.CreateLayer(table, srs, gtype, ["GEOMETRY_NAME=geom"])
        for name, ftype in _entity_field_defs(ogr) + _extra_field_defs(ogr, table):
            lyr.CreateField(ogr.FieldDefn(name, ftype))
        out_layers[table] = lyr

    layers_seen = {}
    # przy wylaczonym wklejaniu blokow sterownik wystawia tez warstwe 'blocks',
    # a GetLayer(0) potrafi wskazac wlasnie ja — bierzemy 'entities' po nazwie
    src_layer = src.GetLayerByName("entities") or src.GetLayer(0)
    total = src_layer.GetFeatureCount() or 1

    # Transakcja jest wlasnoscia ZBIORU DANYCH, nie warstwy: w GPKG
    # OGRGeoPackageTableLayer.StartTransaction() deleguje do datasource,
    # wiec druga taka proba konczy sie bledem "Transaction already established".
    dst.StartTransaction()

    try:
        for i, feat in enumerate(src_layer):
            if feedback is not None and feedback.isCanceled():
                break
            if progress_cb is not None and i % 5000 == 0:
                progress_cb(int(100.0 * i / total), "")

            geom = feat.GetGeometryRef()
            if geom is None:
                continue
            style = feat.GetStyleString() or ""
            text = _field(feat, "Text")
            table = _route(geom.GetGeometryType(), ogr, bool(text))
            if table is None:
                continue

            cad_layer = _field(feat, "Layer") or "0"
            layers_seen.setdefault(cad_layer, _color_from_style(style))

            out = out_layers[table]
            out_feat = ogr.Feature(out.GetLayerDefn())
            out_feat.SetGeometry(_promote(geom, table, ogr))
            out_feat.SetField(S.C_HANDLE, _handle(_field(feat, "EntityHandle")))
            out_feat.SetField(S.C_BLOCK, S.MODEL_SPACE_BLOCK)
            out_feat.SetField(S.C_SPACE, int(_field(feat, "PaperSpace") or 0))
            out_feat.SetField(S.C_LAYER, cad_layer)
            out_feat.SetField(S.C_LINETYPE, _field(feat, "Linetype") or "")
            out_feat.SetField("olinetype", _field(feat, "Linetype") or "")
            out_feat.SetField(S.C_COLOR, _color_from_style(style))
            out_feat.SetField(S.C_OCOLOR, 256)
            out_feat.SetField("color24", -1)
            out_feat.SetField("transparency", 0)
            out_feat.SetField(S.C_LINEWIDTH, _linewidth_from_style(style))
            out_feat.SetField("visible", 1)

            if table == S.T_TEXTS:
                height, angle, alignh, alignv = _text_from_style(style)
                out_feat.SetField(S.C_ETYPE, _ETYPE_TEXT)
                out_feat.SetField("text", text)
                out_feat.SetField("height", height)
                out_feat.SetField("angle", angle)
                out_feat.SetField("alignh", alignh)
                out_feat.SetField("alignv", alignv)
                out_feat.SetField("interlin", -1.0)
                out_feat.SetField("widthscale", 1.0)
                out_feat.SetField("textgen", 0)
            elif table == S.T_LINES:
                out_feat.SetField(S.C_ETYPE, _ETYPE_LINE)
                out_feat.SetField("width", 0.0)
            elif table == S.T_HATCHES:
                out_feat.SetField(S.C_ETYPE, _ETYPE_HATCH)
                out_feat.SetField("solid", 1)
            else:
                out_feat.SetField(S.C_ETYPE, _ETYPE_POINT)

            out.CreateFeature(out_feat)
            out_feat = None
    finally:
        dst.CommitTransaction()

    _write_layers_table(dst, ogr, layers_seen)

    # pusta tabela polylines, zeby schemat byl kompletny dla reszty wtyczki
    if S.T_POLYLINES not in out_layers:
        lyr = dst.CreateLayer(
            S.T_POLYLINES, srs, ogr.wkbMultiLineString25D, ["GEOMETRY_NAME=geom"]
        )
        for name, ftype in _entity_field_defs(ogr) + _extra_field_defs(ogr, S.T_POLYLINES):
            lyr.CreateField(ogr.FieldDefn(name, ftype))

    dst = None
    src = None
    if progress_cb is not None:
        progress_cb(100, "")
    return gpkg_path


def _free_path(path):
    """Zwraca sciezke, ktora nie istnieje: ``x.gpkg`` -> ``x_2.gpkg`` -> ..."""
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    n = 2
    while os.path.exists("{0}_{1}{2}".format(stem, n, ext)):
        n += 1
    return "{0}_{1}{2}".format(stem, n, ext)


def _write_layers_table(dst, ogr, layers_seen):
    lyr = dst.CreateLayer(S.T_LAYERS, None, ogr.wkbNone)
    for name, ftype in (
        ("name", ogr.OFTString),
        ("linetype", ogr.OFTString),
        ("color", ogr.OFTString),
        ("ocolor", ogr.OFTInteger),
        ("color24", ogr.OFTInteger),
        ("transparency", ogr.OFTInteger),
        ("lweight", ogr.OFTInteger),
        ("linewidth", ogr.OFTReal),
        ("flags", ogr.OFTInteger),
    ):
        lyr.CreateField(ogr.FieldDefn(name, ftype))
    defn = lyr.GetLayerDefn()
    for name in sorted(layers_seen):
        feat = ogr.Feature(defn)
        feat.SetField("name", name)
        feat.SetField("color", layers_seen[name])
        feat.SetField("ocolor", 7)
        feat.SetField("color24", -1)
        feat.SetField("transparency", 0)
        feat.SetField("linewidth", 0.0)
        feat.SetField("flags", 0)
        lyr.CreateFeature(feat)
        feat = None

    # pusta tabela blocks — reszta wtyczki sprawdza jej obecnosc
    blk = dst.CreateLayer(S.T_BLOCKS, None, ogr.wkbPoint25D, ["GEOMETRY_NAME=geom"])
    for name, ftype in _entity_field_defs(ogr) + [
        ("name", ogr.OFTString), ("flags", ogr.OFTInteger),
        ("thickness", ogr.OFTReal),
    ]:
        blk.CreateField(ogr.FieldDefn(name, ftype))


def _promote(geom, table, ogr):
    """Dopasowuje geometrie do typu warstwy docelowej (multi + 2.5D)."""
    flat = ogr.GT_Flatten(geom.GetGeometryType())
    if table == S.T_LINES and flat in (
        ogr.wkbLineString, ogr.wkbCircularString, ogr.wkbCompoundCurve
    ):
        try:
            return ogr.ForceToMultiLineString(geom)
        except Exception:
            return geom
    if table == S.T_HATCHES and flat in (ogr.wkbPolygon, ogr.wkbCurvePolygon):
        try:
            return ogr.ForceToMultiPolygon(geom)
        except Exception:
            return geom
    return geom


def _field(feat, name):
    try:
        idx = feat.GetFieldIndex(name)
    except Exception:
        return None
    if idx < 0 or not feat.IsFieldSet(idx):
        return None
    return feat.GetField(idx)


def _handle(value):
    if not value:
        return 0
    try:
        return int(str(value), 16)
    except (TypeError, ValueError):
        return 0
