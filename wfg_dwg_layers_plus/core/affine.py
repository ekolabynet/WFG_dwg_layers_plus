# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""Transformacje afiniczne 2.5D dla rozwijania blokow.

Czysty Python, bez Qt — dzieki temu logike da sie przetestowac poza QGIS-em.
Konwencja jest zgodna z ``QTransform`` (wektor wierszowy):

    x' = a*x + c*y + e
    y' = b*x + d*y + f

czyli ``QTransform(a, b, c, d, e, f)``.

Skladanie: ``A.then(B)`` = najpierw A, potem B.

Wspolrzedna Z jest niesiona osobno jako para (skala, przesuniecie), bo
``QgsGeometry.transform`` przyjmuje ja w tej postaci:  ``z' = z*zScale + zTranslate``.
"""

import math


class Affine(object):
    """Macierz afiniczna 2D + liniowa transformacja Z."""

    __slots__ = ("a", "b", "c", "d", "e", "f", "zs", "zt")

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0, zs=1.0, zt=0.0):
        self.a = float(a)
        self.b = float(b)
        self.c = float(c)
        self.d = float(d)
        self.e = float(e)
        self.f = float(f)
        self.zs = float(zs)
        self.zt = float(zt)

    # --- konstruktory -------------------------------------------------------

    @classmethod
    def identity(cls):
        return cls()

    @classmethod
    def translation(cls, dx, dy, dz=0.0):
        return cls(1.0, 0.0, 0.0, 1.0, float(dx), float(dy), 1.0, float(dz))

    @classmethod
    def scaling(cls, sx, sy, sz=1.0):
        return cls(float(sx), 0.0, 0.0, float(sy), 0.0, 0.0, float(sz), 0.0)

    @classmethod
    def rotation(cls, radians):
        cos = math.cos(radians)
        sin = math.sin(radians)
        # wektor wierszowy: [x y] * [[cos, sin], [-sin, cos]]
        return cls(cos, sin, -sin, cos, 0.0, 0.0, 1.0, 0.0)

    # --- skladanie ----------------------------------------------------------

    def then(self, other):
        """Zwraca transformacje: najpierw ``self``, potem ``other``."""
        a = self.a * other.a + self.b * other.c
        b = self.a * other.b + self.b * other.d
        c = self.c * other.a + self.d * other.c
        d = self.c * other.b + self.d * other.d
        e = self.e * other.a + self.f * other.c + other.e
        f = self.e * other.b + self.f * other.d + other.f
        # z' = (z*zs1 + zt1) * zs2 + zt2
        zs = self.zs * other.zs
        zt = self.zt * other.zs + other.zt
        return Affine(a, b, c, d, e, f, zs, zt)

    # --- uzycie -------------------------------------------------------------

    def apply(self, x, y, z=0.0):
        return (
            self.a * x + self.c * y + self.e,
            self.b * x + self.d * y + self.f,
            self.zs * z + self.zt,
        )

    @property
    def determinant(self):
        return self.a * self.d - self.b * self.c

    @property
    def is_mirrored(self):
        return self.determinant < 0.0

    @property
    def rotation_deg(self):
        """Kat obrotu skladowej liniowej w stopniach (przyblizenie)."""
        return math.degrees(math.atan2(self.b, self.a))

    def to_qtransform(self):
        """Konwersja do ``QTransform`` (import lokalny, zeby modul byl testowalny)."""
        from qgis.PyQt.QtGui import QTransform

        return QTransform(self.a, self.b, self.c, self.d, self.e, self.f)

    def __eq__(self, other):
        if not isinstance(other, Affine):
            return NotImplemented
        return all(
            abs(getattr(self, k) - getattr(other, k)) < 1e-9
            for k in self.__slots__
        )

    def __repr__(self):
        return (
            "Affine(a={0:.6g}, b={1:.6g}, c={2:.6g}, d={3:.6g}, "
            "e={4:.6g}, f={5:.6g}, zs={6:.6g}, zt={7:.6g})"
        ).format(self.a, self.b, self.c, self.d, self.e, self.f, self.zs, self.zt)


def insert_matrix(
    insert_x,
    insert_y,
    insert_z,
    base_x,
    base_y,
    base_z,
    xscale,
    yscale,
    zscale,
    angle_rad,
    parent=None,
    rotate_before_scale=False,
):
    """Macierz przeksztalcenia definicji bloku na jego wstawienie.

    Kolejnosc CAD-owa (domyslna):
        odejmij punkt bazowy -> skaluj -> obroc -> przesun w punkt wstawienia

    ``rotate_before_scale=True`` odtwarza kolejnosc uzywana przez wbudowany
    importer QGIS (``translate.scale.rotateRadians.translate(-base)``), ktory
    obraca przed skalowaniem. Dla skali jednorodnej obie kolejnosci daja ten sam
    wynik; dla niejednorodnej roznia sie i CAD-owa jest ta poprawna.
    """
    xscale = float(xscale) if xscale else 1.0
    yscale = float(yscale) if yscale else 1.0
    zscale = float(zscale) if zscale else 1.0
    if xscale == 0.0:
        xscale = 1.0
    if yscale == 0.0:
        yscale = 1.0
    if zscale == 0.0:
        zscale = 1.0

    # odjecie punktu bazowego, lacznie z Z (z' = z - base_z)
    m = Affine(1.0, 0.0, 0.0, 1.0, -float(base_x), -float(base_y), 1.0, -float(base_z))
    scale = Affine.scaling(xscale, yscale, zscale)
    rot = Affine.rotation(float(angle_rad or 0.0))
    shift = Affine.translation(float(insert_x), float(insert_y), 0.0)

    if rotate_before_scale:
        m = m.then(rot).then(scale)
    else:
        m = m.then(scale).then(rot)

    m = m.then(shift)
    m = m.then(Affine(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, float(insert_z)))

    if parent is not None:
        m = m.then(parent)
    return m


#: gorne ograniczenie liczby kopii MINSERT — chroni przed uszkodzonym plikiem,
#: w ktorym colcount/rowcount sa absurdalne (albo nieskonczone)
MAX_MINSERT_COPIES = 100000


def minsert_offsets(colcount, rowcount, colspace, rowspace, angle_rad,
                    max_copies=MAX_MINSERT_COPIES):
    """Przesuniecia siatki MINSERT, obrocone o kat wstawienia.

    Wbudowany importer QGIS zapisuje kolumny ``colcount``/``rowcount``/
    ``colspace``/``rowspace``, ale nigdy ich nie czyta — tablica wstawien
    materializuje sie u niego tylko raz. Tutaj rozwijamy ja poprawnie.

    Zwraca liste par ``(dx, dy)`` w ukladzie mapy; zawsze co najmniej [(0, 0)].
    """
    try:
        cols = max(1, int(colcount or 1))
        rows = max(1, int(rowcount or 1))
    except (TypeError, ValueError, OverflowError):
        cols, rows = 1, 1
    # twardy limit, zanim cokolwiek zmaterializujemy w pamieci
    cols = min(cols, max_copies)
    rows = min(rows, max(1, max_copies // cols))
    try:
        cs = float(colspace or 0.0)
        rs = float(rowspace or 0.0)
    except (TypeError, ValueError, OverflowError):
        cs = rs = 0.0
    if cols == 1 and rows == 1:
        return [(0.0, 0.0)]
    cos = math.cos(float(angle_rad or 0.0))
    sin = math.sin(float(angle_rad or 0.0))
    out = []
    for r in range(rows):
        for c in range(cols):
            dx = c * cs
            dy = r * rs
            out.append((dx * cos - dy * sin, dx * sin + dy * cos))
    return out
