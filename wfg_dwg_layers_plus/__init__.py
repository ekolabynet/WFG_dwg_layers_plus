# -*- coding: utf-8 -*-
"""WFG DWG Layers+ — import DWG/DXF do QGIS z prawdziwymi warstwami per warstwa CAD."""


def classFactory(iface):  # noqa: N802  (nazwa wymagana przez QGIS)
    from .plugin import DwgLayersPlusPlugin

    return DwgLayersPlusPlugin(iface)
