# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""WFG DWG Layers+ — import DWG/DXF do QGIS z prawdziwymi warstwami per warstwa CAD."""


def classFactory(iface):  # noqa: N802  (nazwa wymagana przez QGIS)
    from .plugin import DwgLayersPlusPlugin

    return DwgLayersPlusPlugin(iface)
