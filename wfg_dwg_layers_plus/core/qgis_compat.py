# -*- coding: utf-8 -*-
"""Warstwa zgodnosci dla enumow QGIS, ktore zmienily miejsce w 3.30-3.40.

QGIS przeniosl wiele enumow z ``QgsFoo.PropertyBar`` do ``QgsFoo.Property.Bar``
(i analogicznie jednostki renderowania do ``Qgis.RenderUnit``). Stare formy sa
wciaz dostepne jako aliasy, ale sypia ostrzezeniami deprecacji i w kolejnych
wydaniach znikaja. Ten modul pobiera je defensywnie.
"""


def enum_value(owner, *candidates):
    """Zwraca pierwsza istniejaca wartosc enuma z listy sciezek.

    Sciezki podaje sie jako stringi z kropkami, np. ``"Property.FillColor"``
    albo ``"PropertyFillColor"``.
    """
    for path in candidates:
        obj = owner
        ok = True
        for part in path.split("."):
            if not hasattr(obj, part):
                ok = False
                break
            obj = getattr(obj, part)
        if ok:
            return obj
    raise AttributeError(
        "Nie znaleziono zadnej z wartosci {0} w {1}".format(candidates, owner)
    )


def symbol_property(name):
    """``QgsSymbolLayer.Property.<name>`` z fallbackiem na stara forme."""
    from qgis.core import QgsSymbolLayer

    return enum_value(QgsSymbolLayer, "Property." + name, "Property" + name)


def label_property(name):
    """``QgsPalLayerSettings.Property.<name>`` z fallbackiem."""
    from qgis.core import QgsPalLayerSettings

    return enum_value(QgsPalLayerSettings, "Property." + name, name)


def render_unit(name):
    """Jednostka renderowania: ``Millimeters`` / ``MapUnits`` / ``Points``."""
    from qgis.core import QgsUnitTypes

    try:
        from qgis.core import Qgis

        return enum_value(Qgis, "RenderUnit." + name)
    except Exception:
        pass
    return enum_value(
        QgsUnitTypes,
        "RenderUnit.Render" + name,
        "Render" + name,
    )


def wkb_type(name):
    """Typ geometrii WKB: ``Qgis.WkbType.<name>`` lub ``QgsWkbTypes.<name>``."""
    try:
        from qgis.core import Qgis

        return enum_value(Qgis, "WkbType." + name)
    except Exception:
        pass
    from qgis.core import QgsWkbTypes

    return enum_value(QgsWkbTypes, name)


def geometry_type(name):
    """``Qgis.GeometryType.<name>`` / ``QgsWkbTypes.<name>Geometry``."""
    try:
        from qgis.core import Qgis

        return enum_value(Qgis, "GeometryType." + name)
    except Exception:
        pass
    from qgis.core import QgsWkbTypes

    return enum_value(QgsWkbTypes, name + "Geometry")


def field_type(name):
    """Typ pola dla ``QgsField``.

    Kolejnosc ma znaczenie i jest odwrotna, niz sugeruje intuicja.
    ``QgsField(QString, QMetaType::Type, ...)` istnieje dopiero od QGIS 3.38;
    w 3.28-3.36 sip zna wylacznie wariant z ``QVariant::Type`` i odrzuca
    wartosc typu ``QMetaType.Type`` z ``TypeError``, mimo zgodnych wartosci
    liczbowych. Jednoczesnie shim ``qgis.PyQt`` pod Qt6 aliasuje
    ``QVariant.Int`` na ``QMetaType.Type.Int``, wiec sciezka przez QVariant
    jest poprawna na obu Qt.
    """
    try:
        from qgis.PyQt.QtCore import QVariant

        # QVariant nazywa typy inaczej niz QMetaType: nie ma QVariant.QString,
        # jest QVariant.String (shim Qt6 w QGIS aliasuje ja na QMetaType.Type.QString)
        return enum_value(QVariant, _QVARIANT_NAMES.get(name, name), name)
    except Exception:
        pass
    from qgis.PyQt.QtCore import QMetaType

    return enum_value(QMetaType, "Type." + name, name)


#: nazwy typow w QVariant rozne od tych w QMetaType
_QVARIANT_NAMES = {
    "QString": "String",
    "QDate": "Date",
    "QTime": "Time",
    "QDateTime": "DateTime",
    "QByteArray": "ByteArray",
}


def vector_file_writer_action(name):
    """``QgsVectorFileWriter.ActionOnExistingFile.<name>`` z fallbackiem."""
    from qgis.core import QgsVectorFileWriter

    return enum_value(
        QgsVectorFileWriter,
        "ActionOnExistingFile." + name,
        name,
    )
