# -*- coding: utf-8 -*-
"""Testy logiki, ktora nie potrzebuje QGIS-a.

Uruchomienie poza QGIS-em:

    python -m pytest wfg_dwg_layers_plus/test/test_core.py
    (albo)  python wfg_dwg_layers_plus/test/test_core.py
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from wfg_dwg_layers_plus.core import gpkg_schema as S  # noqa: E402
from wfg_dwg_layers_plus.core import naming  # noqa: E402
from wfg_dwg_layers_plus.core.affine import (  # noqa: E402
    Affine,
    insert_matrix,
    minsert_offsets,
)


def close(a, b, tol=1e-9):
    return abs(a - b) < tol


class TestAffine(unittest.TestCase):
    def test_identity(self):
        m = Affine.identity()
        self.assertEqual(m.apply(3, 4, 5), (3.0, 4.0, 5.0))

    def test_translation(self):
        m = Affine.translation(10, -5, 2)
        self.assertEqual(m.apply(1, 1, 1), (11.0, -4.0, 3.0))

    def test_rotation_90(self):
        m = Affine.rotation(math.pi / 2)
        x, y, _ = m.apply(1, 0)
        self.assertTrue(close(x, 0.0))
        self.assertTrue(close(y, 1.0))

    def test_then_order_is_first_self_then_other(self):
        # najpierw przesuniecie o (1,0), potem skala x2 -> (4,0)
        m = Affine.translation(1, 0).then(Affine.scaling(2, 2))
        x, y, _ = m.apply(1, 0)
        self.assertTrue(close(x, 4.0))
        self.assertTrue(close(y, 0.0))

    def test_mirror_detected(self):
        self.assertTrue(Affine.scaling(-1, 1).is_mirrored)
        self.assertFalse(Affine.scaling(1, 1).is_mirrored)
        self.assertFalse(Affine.scaling(-1, -1).is_mirrored)


class TestInsertMatrix(unittest.TestCase):
    def test_base_point_maps_to_insertion_point(self):
        m = insert_matrix(100, 200, 5, 10, 20, 1, 2, 3, 4, math.pi / 3)
        x, y, z = m.apply(10, 20, 1)
        self.assertTrue(close(x, 100.0))
        self.assertTrue(close(y, 200.0))
        self.assertTrue(close(z, 5.0))

    def test_uniform_scale_and_rotation(self):
        # blok z punktem bazowym (0,0), punkt (1,0), skala 2, obrot 90 st.
        m = insert_matrix(0, 0, 0, 0, 0, 0, 2, 2, 1, math.pi / 2)
        x, y, _ = m.apply(1, 0)
        self.assertTrue(close(x, 0.0))
        self.assertTrue(close(y, 2.0))

    def test_z_scaling(self):
        m = insert_matrix(0, 0, 100, 0, 0, 10, 1, 1, 3, 0)
        _, _, z = m.apply(0, 0, 20)
        # (20 - 10) * 3 + 100
        self.assertTrue(close(z, 130.0))

    def test_mirror_x(self):
        m = insert_matrix(0, 0, 0, 0, 0, 0, -1, 1, 1, 0)
        x, y, _ = m.apply(5, 7)
        self.assertTrue(close(x, -5.0))
        self.assertTrue(close(y, 7.0))
        self.assertTrue(m.is_mirrored)

    def test_order_matters_for_nonuniform_scale(self):
        cad = insert_matrix(0, 0, 0, 0, 0, 0, 2, 1, 1, math.pi / 2)
        qgis = insert_matrix(
            0, 0, 0, 0, 0, 0, 2, 1, 1, math.pi / 2, rotate_before_scale=True
        )
        self.assertNotEqual(cad.apply(1, 0)[:2], qgis.apply(1, 0)[:2])
        # skala CAD-owa: (1,0) -> skalowanie (2,0) -> obrot 90 st. -> (0,2)
        x, y, _ = cad.apply(1, 0)
        self.assertTrue(close(x, 0.0))
        self.assertTrue(close(y, 2.0))

    def test_uniform_scale_orders_agree(self):
        a = insert_matrix(3, 4, 0, 1, 1, 0, 2, 2, 1, 0.7)
        b = insert_matrix(3, 4, 0, 1, 1, 0, 2, 2, 1, 0.7, rotate_before_scale=True)
        self.assertEqual(a.apply(5, 6)[:2][0].__round__(9),
                         b.apply(5, 6)[:2][0].__round__(9))

    def test_nested_composition(self):
        # blok zewnetrzny: skala 3, blok wewnetrzny: skala 2 -> lacznie 6
        outer = insert_matrix(0, 0, 0, 0, 0, 0, 3, 3, 1, 0)
        inner = insert_matrix(0, 0, 0, 0, 0, 0, 2, 2, 1, 0, parent=outer)
        x, _, _ = inner.apply(1, 0)
        self.assertTrue(close(x, 6.0))

    def test_zero_scale_is_normalised(self):
        m = insert_matrix(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        x, y, _ = m.apply(2, 3)
        self.assertTrue(close(x, 2.0))
        self.assertTrue(close(y, 3.0))


class TestMinsert(unittest.TestCase):
    def test_single(self):
        self.assertEqual(minsert_offsets(1, 1, 10, 10, 0), [(0.0, 0.0)])

    def test_grid_3x2(self):
        offsets = minsert_offsets(3, 2, 10, 5, 0)
        self.assertEqual(len(offsets), 6)
        self.assertIn((0.0, 0.0), offsets)
        self.assertTrue(any(close(dx, 20.0) and close(dy, 5.0)
                            for dx, dy in offsets))

    def test_grid_rotated(self):
        offsets = minsert_offsets(2, 1, 10, 0, math.pi / 2)
        self.assertEqual(len(offsets), 2)
        dx, dy = offsets[1]
        self.assertTrue(close(dx, 0.0))
        self.assertTrue(close(dy, 10.0))

    def test_zero_counts_are_safe(self):
        self.assertEqual(minsert_offsets(0, 0, 1, 1, 0), [(0.0, 0.0)])
        self.assertEqual(minsert_offsets(None, None, None, None, None),
                         [(0.0, 0.0)])


class TestNaming(unittest.TestCase):
    def test_display_name(self):
        self.assertEqual(
            naming.display_name("z_5_zabawka", S.T_HATCHES), "z_5_zabawka_hatch"
        )
        self.assertEqual(
            naming.display_name("z_5_przejścia", S.T_LINES), "z_5_przejścia_line"
        )

    def test_transliterate(self):
        self.assertEqual(naming.transliterate("rzędne łąka ŚĆ"), "rzedne laka SC")

    def test_sanitize_polish_and_spaces(self):
        self.assertEqual(
            naming.sanitize_table_name("z_8_wyk_rzędne kanałów wodnych_text"),
            "z_8_wyk_rzedne_kanalow_wodnych_text",
        )

    def test_sanitize_leading_digit(self):
        self.assertTrue(naming.sanitize_table_name("5_zabawka").startswith("l_"))

    def test_sanitize_empty(self):
        self.assertEqual(naming.sanitize_table_name("###"), "layer")

    def test_sanitize_length(self):
        long_name = "a" * 200
        out = naming.sanitize_table_name(long_name)
        self.assertLessEqual(len(out), naming.MAX_TABLE_NAME)

    def test_allocator_case_insensitive_collision(self):
        alloc = naming.NameAllocator()
        first = alloc.allocate("Warstwa")
        second = alloc.allocate("warstwa")
        self.assertNotEqual(first.lower(), second.lower())
        self.assertTrue(second.endswith("_2"))

    def test_allocator_respects_existing(self):
        alloc = naming.NameAllocator(["mur_line"])
        self.assertNotEqual(alloc.allocate("mur_line"), "mur_line")

    def test_block_layer_name(self):
        self.assertEqual(naming.block_layer_name("lawka", S.KIND_LINE), "blk_lawka_line")


class TestSchema(unittest.TestCase):
    def test_sql_quote_escapes(self):
        self.assertEqual(S.sql_quote("O'Brien"), "'O''Brien'")

    def test_layer_filter(self):
        self.assertEqual(
            S.layer_filter("mur"),
            "layer = 'mur' AND space = 0 AND block = -1",
        )

    def test_visibility_rule(self):
        self.assertTrue(S.layer_visible_from_attrs(7, 0))
        self.assertFalse(S.layer_visible_from_attrs(-7, 0))    # warstwa wylaczona
        self.assertFalse(S.layer_visible_from_attrs(7, 1))     # zamrozona
        self.assertTrue(S.layer_visible_from_attrs(7, 4))      # zablokowana != ukryta

    def test_block_flags_composite_disables_expansion(self):
        self.assertEqual(
            S.qgis_block_flags(S.BlockMode.COMPOSITE),
            S.QGIS_BLOCK_ADD_INSERT_POINTS,
        )
        self.assertEqual(
            S.qgis_block_flags(S.BlockMode.EXPLODED),
            S.QGIS_BLOCK_EXPAND_GEOMETRY,
        )

    def test_every_entity_table_has_a_kind_and_suffix(self):
        for table in S.ENTITY_TABLES:
            self.assertIn(table, S.TABLE_KIND)
            self.assertIn(table, S.DEFAULT_SUFFIXES)

    def test_group_order_covers_all_kinds(self):
        self.assertEqual(set(S.GROUP_ORDER), set(S.DEFAULT_GROUPS))
        self.assertEqual(set(S.TABLE_KIND.values()), set(S.GROUP_ORDER))


class TestLayerFix(unittest.TestCase):
    """Odzyskiwanie warstw z DXF-a po uchwycie encji."""

    def _dxf(self, tresc):
        import tempfile

        fh = tempfile.NamedTemporaryFile(
            "w", suffix=".dxf", delete=False, encoding="cp1250"
        )
        fh.write(tresc)
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        return fh.name

    def _pary(self, *items):
        return "".join("{0}\n{1}\n".format(k, v) for k, v in items)

    def test_reads_layers_and_skips_vertices(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        path = self._dxf(
            self._pary((0, "SECTION"), (2, "ENTITIES"))
            + self._pary(
                (0, "POLYLINE"), (5, "1A"), (8, "skarpa umocniona"),
                (0, "VERTEX"), (5, "1D"), (8, "0"),
                (0, "SEQEND"), (5, "1F"), (8, "0"),
                (0, "ENDSEC"), (0, "EOF"),
            )
        )
        scan = LF.scan_dxf(path)
        self.assertEqual(scan.handles[0x1A], "skarpa umocniona")
        # VERTEX to czesc skladowa polilinii, nie osobny obiekt
        self.assertNotIn(0x1D, scan.handles)
        # SEQEND jest w mapie celowo — pod jego uchwytem import zapisuje
        # polilinie — ale z warstwa polilinii, nie wlasna
        self.assertEqual(scan.handles[0x1F], "skarpa umocniona")
        self.assertEqual(scan.layer_count, 1)

    def test_marks_entities_inside_block_definitions(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        path = self._dxf(
            self._pary(
                (0, "SECTION"), (2, "BLOCKS"), (0, "BLOCK"), (2, "drzewo"),
                (0, "HATCH"), (5, "2A"), (8, "0"),
                (0, "ENDBLK"), (0, "ENDSEC"),
            )
            + self._pary(
                (0, "SECTION"), (2, "ENTITIES"),
                (0, "INSERT"), (5, "3A"), (8, "ziele\u0144"),
                (0, "ENDSEC"), (0, "EOF"),
            )
        )
        scan = LF.scan_dxf(path)
        self.assertIn(0x2A, scan.in_blocks)
        self.assertNotIn(0x3A, scan.in_blocks)
        # nazwa z cp1250 ma wrocic jako poprawny polski napis
        self.assertEqual(scan.handles[0x3A], "ziele\u0144")

    def test_seqend_handle_carries_the_polyline_layer(self):
        """Sedno usterki: wbudowany import zapisuje dla ciezkiej POLYLINE
        uchwyt SEQEND-a i warstwe SEQEND-a (czyli "0"). Mapa musi wiec pod
        uchwytem zamkniecia oddawac warstwe polilinii, ktora on zamyka."""
        from wfg_dwg_layers_plus.core import layer_fix as LF

        path = self._dxf(
            self._pary((0, "SECTION"), (2, "ENTITIES"))
            + self._pary(
                (0, "POLYLINE"), (5, "19F3DB"), (8, "312-budynek"),
                (0, "VERTEX"), (5, "19F3DC"), (8, "0"),
                (0, "VERTEX"), (5, "19F3DD"), (8, "0"),
                (0, "SEQEND"), (5, "19F3DE"), (8, "0"),
                (0, "ENDSEC"), (0, "EOF"),
            )
        )
        scan = LF.scan_dxf(path)
        self.assertEqual(scan.handles[0x19F3DE], "312-budynek")
        self.assertEqual(scan.handles[0x19F3DB], "312-budynek")
        self.assertEqual(scan.via_seqend, 1)
        # polilinia liczy sie raz, nie dwa razy przez swoje zamkniecie
        self.assertEqual(scan.per_layer, {"312-budynek": 1})

    def test_seqend_without_a_parent_is_ignored(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        path = self._dxf(
            self._pary(
                (0, "SECTION"), (2, "ENTITIES"),
                (0, "SEQEND"), (5, "2B"), (8, "0"),
                (0, "ENDSEC"), (0, "EOF"),
            )
        )
        scan = LF.scan_dxf(path)
        self.assertEqual(scan.handles, {})

    def test_binary_dxf_is_rejected_clearly(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF
        import tempfile

        fh = tempfile.NamedTemporaryFile("wb", suffix=".dxf", delete=False)
        fh.write(LF.BINARY_MAGIC + b"\r\n\x1a\x00")
        fh.close()
        self.addCleanup(os.unlink, fh.name)
        with self.assertRaises(ValueError):
            LF.scan_dxf(fh.name)


class TestLayerFixApply(unittest.TestCase):
    """Przepisanie warstw do GeoPackage — na bazie z wyzwalaczami RTree."""

    def setUp(self):
        import sqlite3
        import tempfile

        self.gpkg = tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False).name
        self.addCleanup(self._sprzatnij)
        conn = sqlite3.connect(self.gpkg)
        for tabela in ("polylines", "lines"):
            conn.execute(
                'CREATE TABLE "{0}" (fid INTEGER PRIMARY KEY, geom BLOB, '
                "handle INTEGER, block INTEGER, etype INTEGER, space INTEGER, "
                "layer TEXT)".format(tabela)
            )
            conn.execute(
                'CREATE VIRTUAL TABLE "rtree_{0}_geom" USING rtree'
                "(id, minx, maxx, miny, maxy)".format(tabela)
            )
            # wyzwalacz jak w specyfikacji GPKG: AFTER UPDATE ON tabeli,
            # z cialem odwolujacym sie do funkcji przestrzennych
            conn.execute(
                'CREATE TRIGGER "rtree_{0}_geom_update3" AFTER UPDATE ON "{0}" '
                "WHEN OLD.fid != NEW.fid AND (NEW.geom NOTNULL "
                "AND NOT ST_IsEmpty(NEW.geom)) BEGIN "
                'INSERT OR REPLACE INTO "rtree_{0}_geom" VALUES (NEW.fid, '
                "ST_MinX(NEW.geom), ST_MaxX(NEW.geom), "
                "ST_MinY(NEW.geom), ST_MaxY(NEW.geom)); END".format(tabela)
            )
        conn.executemany(
            "INSERT INTO polylines (handle, block, etype, space, layer) "
            "VALUES (?, -1, 21, 0, ?)",
            [(0x1A, "0"), (0x1B, None), (0x1C, "0")],
        )
        conn.commit()
        conn.close()

    def _sprzatnij(self):
        import glob

        for path in [self.gpkg] + glob.glob(self.gpkg + ".bak*"):
            if os.path.exists(path):
                os.unlink(path)

    def _scan(self, mapa, w_blokach=()):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        scan = LF.DxfScan()
        scan.handles.update(mapa)
        scan.in_blocks.update(w_blokach)
        return scan

    def test_null_layer_row_is_repaired(self):
        """Wiersz z warstwa NULL to dokladnie ten przypadek, dla ktorego to
        narzedzie istnieje. Zwykle `<>` dawaloby tu NULL i wiersz zostalby
        po cichu pominiety."""
        import sqlite3

        from wfg_dwg_layers_plus.core import layer_fix as LF

        scan = self._scan({0x1B: "219-dzialka"})
        zmian, _ = LF.apply_fix(self.gpkg, scan, make_backup=False)
        self.assertEqual(zmian, 1)
        conn = sqlite3.connect(self.gpkg)
        self.assertEqual(
            conn.execute(
                "SELECT layer FROM polylines WHERE handle = ?", (0x1B,)
            ).fetchone()[0],
            "219-dzialka",
        )
        conn.close()

    def test_preview_matches_what_apply_will_do(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        scan = self._scan({0x1A: "skarpa", 0x1C: "skarpa"}, w_blokach=[0x1C])
        podglad = LF.plan(self.gpkg, scan, skip_block_content=True)
        zmian, _ = LF.apply_fix(
            self.gpkg, scan, make_backup=False, skip_block_content=True
        )
        # obietnica z podgladu musi sie zgadzac co do obiektu
        self.assertEqual(podglad.changed, zmian)
        self.assertEqual(zmian, 1)

    def test_missing_table_does_not_abort_the_whole_repair(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        scan = self._scan({0x1A: "skarpa"})
        zmian, _ = LF.apply_fix(
            self.gpkg, scan, tables=("polylines", "nie_ma_takiej"),
            make_backup=False,
        )
        self.assertEqual(zmian, 1)

    def test_cancelled_scan_is_refused(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        scan = self._scan({0x1A: "skarpa"})
        scan.cancelled = True
        with self.assertRaises(RuntimeError):
            LF.apply_fix(self.gpkg, scan, make_backup=False)

    def test_mojibake_difference_is_recognised_not_rewritten_blindly(self):
        from wfg_dwg_layers_plus.core import layer_fix as LF

        # zwykle polaczenie sqlite3 nie skompiluje tu UPDATE-a: wyzwalacz RTree
        # jest zadeklarowany AFTER UPDATE ON tabeli, wiec SQLite rozwiazuje
        # nazwy funkcji przestrzennych juz przy przygotowaniu zapytania
        conn = LF._connect(self.gpkg)
        # nazwa uszkodzona podwojnym kodowaniem, jak po imporcie z zla strona
        uszkodzona = "zieleń".encode("utf-8").decode("cp1250")
        conn.execute(
            "UPDATE polylines SET layer = ? WHERE handle = ?",
            (uszkodzona, 0x1A),
        )
        conn.commit()
        conn.close()
        scan = self._scan({0x1A: "zieleń"})
        podglad = LF.plan(self.gpkg, scan)
        self.assertEqual(podglad.changed, 1)
        self.assertEqual(podglad.mojibake, 1)


class TestColorSplit(unittest.TestCase):
    """Kubelki podzialu po kolorze."""

    def test_null_value_becomes_is_null_not_a_missing_predicate(self):
        from wfg_dwg_layers_plus.core import color_split as CS

        bucket = CS.Bucket("polylines", None, None, None, 5, dims=(CS.DIM_COLOR,))
        filtr = bucket.filter_sql("0")
        # bez tego filtr zdegenerowalby sie do calej warstwy CAD
        self.assertIn("IS NULL", filtr)
        self.assertNotEqual(filtr, S.layer_filter("0"))

    def test_name_carries_every_active_dimension(self):
        from wfg_dwg_layers_plus.core import color_split as CS

        bucket = CS.Bucket(
            "lines", "255,0,0,255", -1, 3, 7,
            dims=(CS.DIM_COLOR, CS.DIM_LWEIGHT, CS.DIM_ETYPE),
        )
        nazwa = bucket.auto_name()
        self.assertIn("255-0-0", nazwa)
        self.assertNotIn("255-0-0-255", nazwa)   # kanal alfa tylko zasmieca
        self.assertIn("okrag", nazwa)

    def test_lweight_sentinels_are_named_not_shown_as_numbers(self):
        from wfg_dwg_layers_plus.core import color_split as CS

        self.assertEqual(CS.lweight_label(-1), "gr_zwarstwy")
        self.assertEqual(CS.lweight_label(25), "gr0-25")


if __name__ == "__main__":
    unittest.main(verbosity=2)
