# -*- coding: utf-8 -*-
"""Budowa drzewa warstw: cztery grupy geometryczne, nazwy '<warstwa_CAD>_<sufiks>'."""

import os

from qgis.core import QgsProject, QgsVectorLayer

from . import gpkg_schema as S
from . import naming, styler


class TreeOptions(object):
    """Ustawienia budowy drzewa."""

    def __init__(self):
        self.group_names = dict(S.DEFAULT_GROUPS)
        self.suffixes = dict(S.DEFAULT_SUFFIXES)
        self.block_group_name = S.DEFAULT_BLOCK_GROUP
        self.root_group_name = None      # None -> nazwa pliku
        self.numbered_groups = True
        self.skip_empty = True
        self.import_invisible = True     # wczytuj, ale odznacz w legendzie
        self.color_by_cad_layer = False
        self.collapse_groups = True
        self.block_mode = S.BlockMode.EXPLODED
        self.layer_mode = S.LayerMode.FILTER
        self.style = styler.StyleOptions()

    def group_name(self, kind):
        name = self.group_names.get(kind, kind)
        if not self.numbered_groups:
            # odetnij prefiks 'N_' jesli jest
            if len(name) > 2 and name[0].isdigit() and name[1] == "_":
                return name[2:]
        return name


class BuildResult(object):
    def __init__(self):
        self.root_group = None
        self.layers = []          # lista QgsVectorLayer dodanych do projektu
        self.skipped = 0
        self.warnings = []

    @property
    def count(self):
        return len(self.layers)


def _tables_for_mode(options):
    """Ktore tabele trafiaja do drzewa przy danym trybie blokow."""
    tables = [S.T_HATCHES, S.T_LINES, S.T_POLYLINES, S.T_POINTS, S.T_TEXTS]
    if options.block_mode in (S.BlockMode.INSERT_POINTS, S.BlockMode.COMPOSITE):
        tables.append(S.T_INSERTS)
    return tables


def build_tree(
    gpkg_path,
    inv,
    cad_layers,
    options,
    project=None,
    feedback=None,
    materialized=None,
):
    """Tworzy grupy i warstwy w drzewie projektu.

    :param inv: wynik :func:`gpkg_reader.inventory`
    :param cad_layers: lista nazw warstw CAD do zaimportowania
    :param materialized: opcjonalny slownik ``(cad_layer, table) -> nazwa_tabeli``
        z modulu :mod:`materializer`; gdy podany, warstwy wskazuja na fizyczne
        tabele zamiast na filtr
    :returns: :class:`BuildResult`
    """
    project = project or QgsProject.instance()
    root = project.layerTreeRoot()
    result = BuildResult()

    root_name = options.root_group_name or os.path.splitext(
        os.path.basename(gpkg_path)
    )[0]

    # Warstwy dodajemy jedna paczka (addMapLayers) zamiast po jednej — przy
    # setkach warstw to roznica rzedu wielkosci. Sygnalow drzewa NIE blokujemy:
    # QgsLayerTreeModel sluchaja i po ich zablokowaniu legenda rozjechalaby sie
    # ze stanem projektu.
    dwg_group = root.insertGroup(0, root_name)
    result.root_group = dwg_group

    groups = {}
    for kind in S.GROUP_ORDER:
        groups[kind] = dwg_group.addGroup(options.group_name(kind))

    wanted = set(cad_layers)
    tables = _tables_for_mode(options)
    pending = []   # (grupa, warstwa QGIS, widocznosc)

    for info in inv.layers:
        if info.name not in wanted:
            continue
        if feedback is not None and feedback.isCanceled():
            break
        visible = info.visible
        if not visible and not options.import_invisible:
            continue
        override = info.qcolor() if options.color_by_cad_layer else None

        for table in tables:
            if options.skip_empty and not info.count(table):
                result.skipped += 1
                continue
            layer = _make_layer(
                gpkg_path, info, table, options, materialized
            )
            if layer is None or not layer.isValid():
                result.warnings.append(
                    "Nie udalo sie utworzyc warstwy {0} / {1}".format(
                        info.name, table
                    )
                )
                continue
            styler.apply_style(layer, table, override, options.style)
            kind = S.TABLE_KIND.get(table, S.KIND_POINT)
            pending.append((groups[kind], layer, visible))

    if pending:
        project.addMapLayers([lyr for _, lyr, _ in pending], False)
        for group, layer, visible in pending:
            node = group.addLayer(layer)
            if node is not None and not visible:
                node.setItemVisibilityChecked(False)
            result.layers.append(layer)

    # usun puste grupy, zeby legenda nie byla zasmiecona
    for kind in list(groups):
        grp = groups[kind]
        if not grp.children():
            dwg_group.removeChildNode(grp)
        elif options.collapse_groups:
            grp.setExpanded(False)

    if options.collapse_groups:
        dwg_group.setExpanded(True)

    return result


def _make_layer(gpkg_path, info, table, options, materialized):
    name = naming.display_name(info.name, table, options.suffixes)

    if materialized:
        phys = materialized.get((info.name, table))
        if phys:
            uri = "{0}|layername={1}".format(gpkg_path, phys)
            return QgsVectorLayer(uri, name, "ogr")

    uri = "{0}|layername={1}".format(gpkg_path, table)
    layer = QgsVectorLayer(uri, name, "ogr")
    if not layer.isValid():
        return None
    layer.setSubsetString(S.layer_filter(info.name))
    return layer


def add_block_group(dwg_group, block_layers, options, project=None):
    """Dodaje piata grupe ze zlozonymi geometriami blokow.

    :param block_layers: lista krotek ``(nazwa_bloku, kind, QgsVectorLayer)``
    """
    if not block_layers:
        return None
    project = project or QgsProject.instance()
    group = dwg_group.addGroup(options.block_group_name)

    by_block = {}
    for block_name, kind, layer in block_layers:
        by_block.setdefault(block_name, []).append((kind, layer))

    project.addMapLayers([lyr for _, _, lyr in block_layers], False)
    for block_name in sorted(by_block):
        sub = group.addGroup(block_name)
        # kolejnosc: poligony na spodzie, teksty na wierzchu
        order = {S.KIND_TEXT: 0, S.KIND_POINT: 1, S.KIND_LINE: 2, S.KIND_POLYGON: 3}
        for kind, layer in sorted(by_block[block_name], key=lambda kv: order.get(kv[0], 9)):
            sub.addLayer(layer)
        sub.setExpanded(False)
    group.setExpanded(False)
    return group


def remove_group_by_node(node, project=None):
    """Usuwa wezel grupy razem z warstwami (sprzatanie po nieudanym imporcie)."""
    if node is None:
        return
    project = project or QgsProject.instance()
    ids = [
        child.layerId()
        for child in node.findLayers()
        if child.layerId()
    ]
    parent = node.parent()
    if parent is not None:
        parent.removeChildNode(node)
    if ids:
        project.removeMapLayers(ids)
