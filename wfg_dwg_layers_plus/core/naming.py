# -*- coding: utf-8 -*-
"""Nazewnictwo warstw QGIS i sanityzacja nazw tabel GeoPackage.

Czysty Python — testowalny poza QGIS-em.
"""

import hashlib
import re

from . import gpkg_schema as S

#: GPKG toleruje unicode w nazwach tabel, ale nie warto ryzykowac przy
#: eksporcie do innych formatow — zostawiamy litery ASCII, cyfry i podkreslenie
_SAFE_RE = re.compile(r"[^0-9A-Za-z_]+")

_PL_MAP = {
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
}

MAX_TABLE_NAME = 60


def display_name(cad_layer, table, suffixes=None):
    """Nazwa warstwy w legendzie QGIS: ``<warstwa_CAD><sufiks>``.

    Zachowuje oryginalna nazwe CAD ze wszystkimi znakami — legenda nie ma
    zadnych ograniczen.
    """
    suffixes = suffixes or S.DEFAULT_SUFFIXES
    return "{0}{1}".format(cad_layer, suffixes.get(table, "_" + table))


def transliterate(text):
    """Zamienia polskie znaki diakrytyczne na odpowiedniki ASCII."""
    return "".join(_PL_MAP.get(ch, ch) for ch in text)


def sanitize_table_name(name, prefix="l_"):
    """Bezpieczna nazwa tabeli GPKG z dowolnej nazwy warstwy CAD.

    - polskie znaki -> ASCII
    - wszystko poza [0-9A-Za-z_] -> ``_``
    - zwiniete powtorzone podkreslenia, obciete z brzegow
    - nazwa nie moze zaczynac sie cyfra -> prefiks
    - przyciecie do MAX_TABLE_NAME z doklejonym hashem, jesli bylo za dlugie
    """
    raw = str(name)
    out = _SAFE_RE.sub("_", transliterate(raw))
    out = re.sub(r"_+", "_", out).strip("_")
    if not out:
        out = "layer"
    if out[0].isdigit():
        out = prefix + out
    if len(out) > MAX_TABLE_NAME:
        digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:6]
        out = out[: MAX_TABLE_NAME - 7] + "_" + digest
    return out


class NameAllocator(object):
    """Rozdziela unikalne nazwy tabel, uwzgledniajac nieczulosc GPKG na wielkosc liter."""

    def __init__(self, taken=None):
        self._taken = set()
        for t in taken or ():
            self._taken.add(str(t).lower())

    def allocate(self, candidate):
        base = sanitize_table_name(candidate)
        name = base
        n = 2
        while name.lower() in self._taken:
            suffix = "_{0}".format(n)
            trimmed = base[: MAX_TABLE_NAME - len(suffix)]
            name = trimmed + suffix
            n += 1
        self._taken.add(name.lower())
        return name


def table_name_for(cad_layer, table, allocator, suffixes=None):
    """Nazwa fizycznej tabeli GPKG dla pary (warstwa CAD, tabela zrodlowa)."""
    suffixes = suffixes or S.DEFAULT_SUFFIXES
    return allocator.allocate(
        "{0}{1}".format(cad_layer, suffixes.get(table, "_" + table))
    )


def block_layer_name(block_name, kind):
    """Nazwa warstwy dla zlozonych geometrii bloku."""
    return "blk_{0}_{1}".format(block_name, kind)
