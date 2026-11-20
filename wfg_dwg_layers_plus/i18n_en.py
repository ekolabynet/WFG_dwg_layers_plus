# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
# © 2026 Piotr Mędrzycki
"""English texts of the plugin, keyed by the Polish source texts (i18n.tr)."""

EN = {
    'Atrybuty bloków':
        'Block attributes',
    'Konwersja DWG → DXF…':
        'Converting DWG → DXF…',
    'Ten plik nie ma pola BlockAttributes — GDAL nie zobaczył żadnych atrybutów bloków. Sprawdź, czy rysunek na pewno używa atrybutów, a nie zwykłych tekstów.':
        'This file has no BlockAttributes field — GDAL did not see any block attributes. Check that the drawing really uses attributes rather than plain texts.',
    'Plik nie istnieje: {0}':
        'File does not exist: {0}',
    'Nie udało się wczytać tabeli {0} z {1}':
        'Could not read table {0} from {1}',
    'Brak modułu osgeo (GDAL): {0}':
        'osgeo (GDAL) module missing: {0}',
    'GDAL nie otworzył pliku: {0}':
        'GDAL could not open the file: {0}',
    'Nie można otworzyć GeoPackage do zapisu: {0}':
        'Cannot open the GeoPackage for writing: {0}',
    'Nie podpięto złączenia do {0}':
        'Join not attached to {0}',
    'Przetworzono encji: {0}':
        'Entities processed: {0}',
    'Brak definicji blokow w pliku.':
        'No block definitions in the file.',
    "Definicje blokow sa puste. Czy import zostal wykonany w trybie 'Add Only Insert Points' (bez rozwijania blokow)?":
        "Block definitions are empty. Was the import run in 'Add Only Insert Points' mode (without expanding blocks)?",
    'Brak wstawien blokow w przestrzeni modelu.':
        'No block inserts in model space.',
    'Przekroczono limit {0} encji na wstawienie — czesc geometrii blokow zostala pominieta. Podnies limit w oknie importu.':
        'Limit of {0} entities per insert exceeded — part of the block geometry was skipped. Raise the limit in the import dialog.',
    "Blok '{0}' nie ma definicji — pominiety.":
        "Block '{0}' has no definition — skipped.",
    'Zapis {0} nieudany.':
        'Writing {0} failed.',
    "Wykryto cykl w blokach ('{0}') — rekurencja przerwana.":
        "Cycle detected in blocks ('{0}') — recursion stopped.",
    "Przekroczono limit zagniezdzenia blokow ({0}) przy '{1}'.":
        "Block nesting limit ({0}) exceeded at '{1}'.",
    'Nie wszystkie obiekty trafily do warstwy {0}: {1}':
        'Not all features reached layer {0}: {1}',
    'Zapis {0}: {1}':
        'Writing {0}: {1}',
    'Zapis kotwic: {0}':
        'Writing anchors: {0}',
    'Nie udalo sie utworzyc warstwy dla bloku {0}/{1}':
        'Could not create a layer for block {0}/{1}',
    'Nie ma takiego pliku: {0}':
        'No such file: {0}',
    'Nie udało się otworzyć tabeli {0}':
        'Could not open table {0}',
    'Nie udało się poprawić filtru warstwy {0}':
        'Could not fix the filter of layer {0}',
    'Przerwano.':
        'Cancelled.',
    'To nie jest GeoPackage z importu DWG/DXF — brakuje tabel: {0}':
        'This is not a GeoPackage from a DWG/DXF import — missing tables: {0}',
    '5_Bloki':
        '5_Blocks',
    '4_Teksty':
        '4_Texts',
    '3_Punkty':
        '3_Points',
    '2_Linie':
        '2_Lines',
    '1_Poligony':
        '1_Polygons',
    'Rysunek nie ma uchwytów encji (bardzo stary DXF) — po uchwycie nie da się nic dopasować.':
        'The drawing has no entity handles (very old DXF) — nothing can be matched by handle.',
    'Czytanie rysunku zostało przerwane — mapa uchwytów jest niepełna. Uruchom sprawdzenie jeszcze raz.':
        'Reading the drawing was interrupted — the handle map is incomplete. Run the check again.',
    'To binarny DXF. Zapisz rysunek jako DXF tekstowy (ASCII).':
        'This is a binary DXF. Save the drawing as a text (ASCII) DXF.',
    'Nie ma czego poprawiać: przypisanie w bazie zgadza się z rysunkiem.':
        'Nothing to fix: the layer assignment in the database matches the drawing.',
    'Nie udało się poprawić tabeli {0}: {1}':
        'Could not fix table {0}: {1}',
    'Nie mozna otworzyc tabeli {0}':
        'Cannot open table {0}',
    'Nie zapisano tabeli mapowania: {0}':
        'Mapping table not written: {0}',
    'Nie znaleziono akcji wbudowanego importu DWG/DXF. Zaimportuj rysunek recznie (Projekt > Importuj/Eksportuj > Importuj warstwy z DWG/DXF), a potem wskaz powstaly plik .gpkg.':
        'Built-in DWG/DXF import action not found. Import the drawing manually (Project > Import/Export > Import Layers from DWG/DXF), then select the resulting .gpkg file.',
    'Import nie utworzyl zadnych warstw — anulowano okno albo rysunek jest pusty. Mozesz tez wskazac gotowy plik .gpkg recznie.':
        'The import created no layers — the dialog was cancelled or the drawing is empty. You can also select a ready .gpkg file manually.',
    'Nie znaleziono konwertera DWG -> DXF. Zainstaluj ODA File Converter (bezplatny, wymaga rejestracji) albo LibreDWG (dwg2dxf), albo uzyj wbudowanego importu QGIS, ktory czyta DWG bezposrednio.':
        'No DWG -> DXF converter found. Install ODA File Converter (free, registration required) or LibreDWG (dwg2dxf), or use the built-in QGIS import, which reads DWG directly.',
    'GDAL bez obslugi GeoPackage.':
        'GDAL without GeoPackage support.',
    'GDAL nie otworzyl pliku: {0}':
        'GDAL could not open the file: {0}',
    'Nie mozna utworzyc {0}':
        'Cannot create {0}',
    'Brak modulu osgeo (GDAL): {0}':
        'osgeo (GDAL) module missing: {0}',
    'dwg2dxf nie zadzialal: {0}':
        'dwg2dxf failed: {0}',
    'ODA File Converter nie zadzialal: {0}':
        'ODA File Converter failed: {0}',
    'Nie ostylowano: {0} ({1}/{2})':
        'Not styled: {0} ({1}/{2})',
    'Przygotowanie zrodla...':
        'Preparing the source...',
    'Inwentaryzacja warstw...':
        'Taking inventory of layers...',
    'Budowa drzewa warstw...':
        'Building the layer tree...',
    'Gotowe.':
        'Done.',
    'brak warstw':
        'no layers',
    'Materializacja warstw...':
        'Materializing layers...',
    'Skladanie blokow...':
        'Assembling blocks...',
    'Uwaga: ten GeoPackage wyglada na zaimportowany z rozwinieciem blokow. Definicje blokow moga byc niekompletne — zaimportuj ponownie w trybie bez rozwijania.':
        'Note: this GeoPackage looks like it was imported with blocks expanded. Block definitions may be incomplete — import again without expanding blocks.',
    "Wskazany GeoPackage nie pochodzi z importu DWG/DXF (brak tabel 'layers' i 'blocks').":
        "The selected GeoPackage does not come from a DWG/DXF import (tables 'layers' and 'blocks' missing).",
    'Import zakonczony: {0}':
        'Import finished: {0}',
    'Konwersja DWG -> DXF...':
        'Converting DWG -> DXF...',
    'warstw: {0}':
        'layers: {0}',
    'zmaterializowanych tabel: {0}':
        'materialized tables: {0}',
    'blokow: {0} wstawien / {1} czesci':
        'blocks: {0} inserts / {1} parts',
    'Nie udalo sie ostylowac warstwy {0} ({1}): {2}':
        'Could not style layer {0} ({1}): {2}',
    'Nie udalo sie ostylowac warstwy bloku {0}: {1}':
        'Could not style block layer {0}: {1}',
    'Nie udalo sie utworzyc warstwy {0} / {1}':
        'Could not create layer {0} / {1}',
    'WFG DWG Layers+ — atrybuty bloków':
        'WFG DWG Layers+ — block attributes',
    'Biblioteka, której QGIS używa do czytania DWG/DXF, <b>nie obsługuje atrybutów bloków</b> — wartości rzędnych, numerów, opisów wpisanych jako ATTRIB nie ma w GeoPackage w ogóle. Ten moduł czyta je bezpośrednio z rysunku sterownikiem DXF w GDAL i skleja z importem po uchwycie encji (<i>handle</i>).':
        'The library QGIS uses to read DWG/DXF <b>does not support block attributes</b> — elevations, numbers and descriptions entered as ATTRIB are not in the GeoPackage at all. This module reads them directly from the drawing with the GDAL DXF driver and joins them to the import by entity handle (<i>handle</i>).',
    'Pliki':
        'Files',
    'rysunek .dxf (albo .dwg — wymaga konwertera)':
        'a .dxf drawing (or .dwg — requires a converter)',
    'Rysunek źródłowy:':
        'Source drawing:',
    'GeoPackage z importu':
        'GeoPackage from the import',
    'DXF deklarujący wersję R2018 powinien być w UTF-8, ale wiele CAD-ów zapisuje bajty w stronie kodowej systemu i nie poprawia nagłówka. Wtedy GDAL oddaje surowe bajty, a znaczniki atrybutów robią się nieczytelne. Ustawienie ma znaczenie tylko dla takich plików — poprawny UTF-8 przechodzi nietknięty.':
        'A DXF declaring version R2018 should be in UTF-8, but many CAD programs write bytes in the system code page and do not fix the header. GDAL then returns raw bytes and attribute tags become unreadable. This setting matters only for such files — valid UTF-8 passes through untouched.',
    'Kodowanie tekstu:':
        'Text encoding:',
    'Skanuj rysunek':
        'Scan drawing',
    'Co zrobić z wynikiem':
        'What to do with the result',
    'Tylko zaznaczone bloki (puste zaznaczenie = wszystkie)':
        'Selected blocks only (empty selection = all)',
    'Podepnij złączenia do warstw wstawień i kotwic w projekcie':
        'Attach joins to insert and anchor layers in the project',
    'Nieniszczące: atrybuty pojawią się jako dodatkowe pola warstw *_insert i blk__anchor. Złączenie można zdjąć we właściwościach warstwy albo przyciskiem poniżej.':
        'Non-destructive: attributes appear as extra fields of the *_insert and blk__anchor layers. The join can be removed in the layer properties or with the button below.',
    'Dodaj tabelę atrybutów do projektu':
        'Add the attribute table to the project',
    'Powyżej limitu rzadsze znaczniki są pomijane — ostrzeżenie trafia do dziennika.':
        'Above the limit, rarer tags are skipped — a warning goes to the log.',
    'Zdejmij złączenia':
        'Remove joins',
    'Zastosuj':
        'Apply',
    'Zamknij':
        'Close',
    'Wybierz rysunek':
        'Select drawing',
    'Rysunki CAD (*.dxf *.DXF *.dwg *.DWG);;Wszystkie pliki (*)':
        'CAD drawings (*.dxf *.DXF *.dwg *.DWG);;All files (*)',
    'Wybierz GeoPackage':
        'Select GeoPackage',
    'cp1250 — polska strona kodowa (domyślnie)':
        'cp1250 — Central European (Polish) code page (default)',
    'cp1252 — zachodnioeuropejska':
        'cp1252 — Western European',
    'Blok':
        'Block',
    'Wstawień':
        'Inserts',
    'Znaczniki':
        'Tags',
    'Maksimum kolumn:':
        'Maximum columns:',
    'Wskaż istniejący rysunek.':
        'Select an existing drawing.',
    'Znaleziono {0} wstawień z atrybutami, {1} bloków, {2} różnych znaczników.':
        'Found {0} inserts with attributes, {1} blocks, {2} distinct tags.',
    'Najpierw zeskanuj rysunek.':
        'Scan the drawing first.',
    'Wskaż istniejący GeoPackage.':
        'Select an existing GeoPackage.',
    'Przerwano — nic nie zapisano, poprzedni stan wycofany.':
        'Cancelled — nothing written, previous state restored.',
    'Zapis przerwany. Tabela atrybutów nie została utworzona, GeoPackage został wycofany do poprzedniego stanu.':
        'Writing interrupted. The attribute table was not created; the GeoPackage was rolled back to its previous state.',
    '(bez nazwy)':
        '(no name)',
    '  Rysunek nie jest w UTF-8 — teksty przekodowano jako {0}. Jeśli polskie znaki w znacznikach wyglądają źle, zmień kodowanie i zeskanuj ponownie.':
        '  The drawing is not in UTF-8 — texts were decoded as {0}. If accented characters in the tags look wrong, change the encoding and scan again.',
    'Zapisano {0} wierszy do tabeli {1}, kolumn atrybutów: {2}.':
        'Wrote {0} rows to table {1}, attribute columns: {2}.',
    'Zdjęto złączeń: {0} (tabela atrybutów usunięta z projektu; dane w GeoPackage zostają).':
        'Joins removed: {0} (attribute table removed from the project; data in the GeoPackage stays).',
    'Pominięto {0} rzadszych znaczników (limit kolumn): {1}':
        'Skipped {0} rarer tags (column limit): {1}',
    'Podpięto złączenia do {0} warstw.':
        'Joins attached to {0} layers.',
    'WFG DWG Layers+ — podziel warstwę wg koloru':
        'WFG DWG Layers+ — split layer by colour',
    'Część eksportów wrzuca całą kreskę na warstwę <b>0</b> i rozróżnia treść wyłącznie barwą. Podział „warstwa CAD × typ geometrii" daje wtedy jedną wielką warstwę. Tu dzielimy po tym, co w takim pliku naprawdę niesie znaczenie.':
        'Some exports put all linework on layer <b>0</b> and distinguish content by colour only. Splitting by "CAD layer × geometry type" then yields one huge layer. Here we split by what actually carries meaning in such a file.',
    'Źródło':
        'Source',
    'Warstwa CAD:':
        'CAD layer:',
    'grubość linii':
        'line weight',
    'typ encji (łuk / okrąg / odcinek)':
        'entity type (arc / circle / segment)',
    'Dziel według:':
        'Split by:',
    'Skanuj':
        'Scan',
    'Po podziale':
        'After splitting',
    'Usuń nierozdzieloną warstwę źródłową z projektu (np. 0_pline)':
        'Remove the unsplit source layer from the project (e.g. 0_pline)',
    'Inaczej ta sama geometria byłaby narysowana dwa razy. Usuwamy tylko warstwę z projektu — dane w GeoPackage zostają.':
        'Otherwise the same geometry would be drawn twice. Only the layer is removed from the project — data in the GeoPackage stays.',
    'Zapamiętaj nazwy dla tych kolorów (przydadzą się przy następnym pliku)':
        'Remember the names for these colours (useful for the next file)',
    'Podziel':
        'Split',
    'Nazwy w ostatniej kolumnie można edytować.':
        'Names in the last column can be edited.',
    'Kolor':
        'Colour',
    'Tabela':
        'Table',
    'Grubość':
        'Weight',
    'Typ':
        'Type',
    'Obiektów':
        'Features',
    'Nazwa warstwy':
        'Layer name',
    'Zaznacz przynajmniej jeden wymiar podziału.':
        'Select at least one split dimension.',
    'Utworzono warstw: {0}.':
        'Layers created: {0}.',
    'Znaleziono {0} kombinacji. Wpisz nazwy albo zostaw puste — wtedy powstaną nazwy automatyczne.':
        'Found {0} combinations. Enter names or leave them empty — automatic names will be used.',
    ' Usunięto nierozdzielonych: {0}.':
        ' Unsplit layers removed: {0}.',
    '{0}  ({1} kolorów, {2} obiektów)':
        '{0}  ({1} colours, {2} features)',
    'Puste = nazwa automatyczna: {0}':
        'Empty = automatic name: {0}',
    'WFG DWG Layers+ — napraw kodowanie':
        'WFG DWG Layers+ — fix encoding',
    'DXF w wersji R2007 i nowszej ma treść w UTF-8, ale wiele CAD-ów zostawia w nagłówku starą stronę kodową. Biblioteka czytająca stosuje ją posłusznie i <b>ę</b> zamienia się w <b>Ä™</b>, a <b>ś</b> w <b>Ĺ›</b>. To jest odwracalne bez straty — trzeba tylko zrobić konwersję w drugą stronę.':
        'DXF R2007 and newer stores text in UTF-8, but many CAD programs leave the old code page in the header. The reading library applies it obediently and <b>ę</b> turns into <b>Ä™</b>, <b>ś</b> into <b>Ĺ›</b>. This is reversible without loss — the conversion just has to be run the other way.',
    'Plik i kodowanie':
        'File and encoding',
    'Strona kodowa, przez którą tekst został błędnie przepuszczony. Dla rysunków z polskich CAD-ów to prawie zawsze cp1250.':
        'The code page the text was wrongly passed through. For drawings from Polish CAD programs it is almost always cp1250.',
    'Błędna strona kodowa:':
        'Wrong code page:',
    'Skanuj (podgląd zmian)':
        'Scan (preview changes)',
    'Co poprawić':
        'What to fix',
    'Dane w GeoPackage (nazwy warstw CAD, bloków, treść tekstów)':
        'Data in the GeoPackage (CAD layer names, block names, text content)',
    'Zrób kopię zapasową GeoPackage przed zapisem':
        'Back up the GeoPackage before writing',
    'Nazwy warstw i grup w projekcie oraz filtry warstw':
        'Layer and group names in the project, and layer filters',
    "Filtry odwołują się do wartości kolumny 'layer', więc poprawia się je razem z danymi. Osobno nie miałoby to sensu — poprawiony filtr na nienaprawionych danych nie pasowałby do niczego.":
        "Filters refer to values of the 'layer' column, so they are fixed together with the data. Fixing them separately would make no sense — a fixed filter on unfixed data would match nothing.",
    'Napraw':
        'Fix',
    'Pamiętaj zapisać projekt.':
        'Remember to save the project.',
    'cp1251 — cyrylica':
        'cp1251 — Cyrillic',
    'Gdzie':
        'Where',
    'Ile':
        'Count',
    'Przed':
        'Before',
    'Po':
        'After',
    'Nic nie wymaga naprawy — teksty wyglądają poprawnie.':
        'Nothing needs fixing — the texts look correct.',
    'Poprawiasz dane, ale nie projekt. Filtry warstw nadal będą wskazywać stare wartości i takie warstwy pokażą zero obiektów.\n\nKontynuować mimo to?':
        'You are fixing the data but not the project. Layer filters will still point to the old values and such layers will show zero features.\n\nContinue anyway?',
    'Do poprawy: {0} wartości w GeoPackage, {1} pozycji w projekcie.':
        'To fix: {0} values in the GeoPackage, {1} items in the project.',
    'Zakończ edycję tych warstw przed naprawą — ich bufor zapisałby stare wartości z powrotem:\n\n':
        'Stop editing these layers before fixing — their edit buffer would write the old values back:\n\n',
    'Zapisać poprawki do pliku\n{0}?\n\n{1}':
        'Save the fixes to the file\n{0}?\n\n{1}',
    'Kopia zapasowa zostanie utworzona obok.':
        'A backup will be created next to it.',
    'UWAGA: bez kopii zapasowej.':
        'WARNING: no backup.',
    'projekt: {0}':
        'project: {0}',
    'GeoPackage: poprawiono {0} wartości.':
        'GeoPackage: {0} values fixed.',
    'Projekt: warstw {0}, grup {1}, filtrów {2}.':
        'Project: {0} layers, {1} groups, {2} filters.',
    'Kopia zapasowa: {0}':
        'Backup: {0}',
    'WFG DWG Layers+ — import':
        'WFG DWG Layers+ — import',
    'Importuj':
        'Import',
    'plik .dwg / .dxf albo gotowy .gpkg z wbudowanego importu':
        '.dwg / .dxf file or a ready .gpkg from the built-in import',
    'Rysunek / GeoPackage:':
        'Drawing / GeoPackage:',
    'domyślnie obok pliku źródłowego':
        'default: next to the source file',
    'Wyjściowy GeoPackage:':
        'Output GeoPackage:',
    'Układ współrzędnych:':
        'Coordinate reference system:',
    'Zachowaj łuki (bez segmentyzacji)':
        'Keep arcs (no segmentation)',
    'Własny import przez GDAL (eksperymentalny; DXF bez zależności, DWG wymaga ODA File Converter lub LibreDWG)':
        'Own import via GDAL (experimental; DXF without dependencies, DWG requires ODA File Converter or LibreDWG)',
    'Warstwy CAD':
        'CAD layers',
    'Wczytaj listę warstw':
        'Load layer list',
    'filtruj po nazwie…':
        'filter by name…',
    'Struktura':
        'Structure',
    'Filtry na wspólnej tabeli (szybko)':
        'Filters on a shared table (fast)',
    'Osobne tabele w GeoPackage':
        'Separate tables in the GeoPackage',
    'Przy materializacji zamień łuki na odcinki':
        'Convert arcs to segments when materializing',
    'Przebuduj nazwy tabel (zamiast nadpisać te z poprzedniego importu)':
        'Rebuild table names (instead of overwriting those from the previous import)',
    'Domyślnie powtórzony import nadpisuje tabele utworzone poprzednio, więc plik nie puchnie. Zaznacz, jeśli zmieniłeś sufiksy i chcesz, żeby powstały tabele o nowych nazwach.':
        'By default a repeated import overwrites the tables created before, so the file does not grow. Check this if you changed the suffixes and want tables with new names.',
    'Numeruj grupy (stała kolejność w legendzie)':
        'Number the groups (fixed order in the legend)',
    'Pomijaj puste warstwy':
        'Skip empty layers',
    'Wczytuj warstwy wyłączone/zamrożone w CAD (odznaczone w legendzie)':
        'Load layers that are off/frozen in CAD (unchecked in the legend)',
    'Koloruj wg warstwy CAD, nie wg encji':
        'Colour by CAD layer, not by entity',
    'Grubość używana tam, gdzie encja CAD nie ma własnej (linewidth 0 albo -1 = BYBLOCK). Bez tego QGIS podstawia swoje domyślne 0,26 mm i linie wychodzą za grube.':
        'Width used where a CAD entity has none of its own (linewidth 0 or -1 = BYBLOCK). Without it QGIS uses its default 0.26 mm and lines come out too thick.',
    'Grubość zastępcza linii:':
        'Fallback line width:',
    'jako grubość pisaka w mm (zalecane)':
        'as pen width in mm (recommended)',
    'jako szerokość w terenie, wiernie jak CAD':
        'as width on the ground, true to CAD',
    'Polilinie CAD mają globalną szerokość (kolumna width) w jednostkach rysunku. QGIS renderuje ją wiernie — polilinia o width 0,5 wychodzi na pół metra szeroka, jak czarna belka. Projektanci zwykle wpisują tam grubości piór ISO (0,05 / 0,1 / 0,3 / 0,5), więc domyślnie traktujemy tę liczbę jako milimetry.':
        'CAD polylines have a global width (width column) in drawing units. QGIS renders it faithfully — a polyline with width 0.5 comes out half a metre wide, like a black bar. Designers usually enter ISO pen widths there (0.05 / 0.1 / 0.3 / 0.5), so by default we treat the number as millimetres.',
    'Szerokość polilinii:':
        'Polyline width:',
    'Pokazuj warstwy punktów CAD':
        'Show CAD point layers',
    'Domyślnie punkty CAD są niewidoczne — tak samo jak we wbudowanym imporcie QGIS.':
        'By default CAD points are invisible — the same as in the built-in QGIS import.',
    'Rozmiar punktów:':
        'Point size:',
    'Rozmiar wstawień i kotwic:':
        'Insert and anchor size:',
    'Bloki':
        'Blocks',
    'Rozbite na geometrie (jak dotąd)':
        'Exploded into geometry (as before)',
    'Punkty wstawień z atrybutami':
        'Insert points with attributes',
    'Złożone geometrie — jeden obiekt na wstawienie':
        'Composite geometry — one feature per insert',
    'Utwórz warstwę kotwic (punkt na wstawienie)':
        'Create an anchor layer (one point per insert)',
    'Zapisz warstwy bloków w GeoPackage':
        'Save block layers in the GeoPackage',
    'Rozwijaj tablice MINSERT':
        'Expand MINSERT arrays',
    'Dziedzicz warstwę 0 z wstawienia':
        'Inherit layer 0 from the insert',
    'Kolejność transformacji jak w QGIS (obrót przed skalą)':
        'Transformation order as in QGIS (rotation before scale)',
    'Limit zagnieżdżenia:':
        'Nesting limit:',
    'Limit encji na wstawienie:':
        'Entity limit per insert:',
    'Tryb złożonych geometrii wymaga importu <b>bez rozwijania bloków</b>. Wtyczka ustawia to za Ciebie w oknie wbudowanego importu.':
        'Composite geometry mode requires an import <b>without expanding blocks</b>. The plugin sets this for you in the built-in import dialog.',
    'Wybierz rysunek lub GeoPackage':
        'Select drawing or GeoPackage',
    'CAD i GeoPackage (*.dwg *.DWG *.dxf *.DXF *.gpkg);;Wszystkie pliki (*)':
        'CAD and GeoPackage (*.dwg *.DWG *.dxf *.DXF *.gpkg);;All files (*)',
    'Wyjściowy GeoPackage':
        'Output GeoPackage',
    'Nazwy grup i sufiksy':
        'Group names and suffixes',
    'Przywróć domyślne':
        'Restore defaults',
    'Wszystkie':
        'All',
    'Żadna':
        'None',
    'Tylko widoczne w CAD':
        'Only visible in CAD',
    'Warstwa CAD':
        'CAD layer',
    'Poligony':
        'Polygons',
    'Linie':
        'Lines',
    'Polilinie':
        'Polylines',
    'Punkty':
        'Points',
    'Teksty':
        'Texts',
    'Wstawienia':
        'Inserts',
    'Razem':
        'Total',
    'Wskaż plik źródłowy.':
        'Select a source file.',
    'Listę warstw można wczytać dopiero z GeoPackage. Uruchom import — po jego zakończeniu warstwy pojawią się automatycznie — albo wskaż gotowy plik .gpkg.':
        'The layer list can only be loaded from a GeoPackage. Run the import — the layers will appear automatically when it finishes — or select a ready .gpkg file.',
    'Wskaż istniejący plik źródłowy.':
        'Select an existing source file.',
    'Nie zaznaczono żadnej warstwy CAD. Zaznacz przynajmniej jedną albo użyj przycisku „Wszystkie”.':
        'No CAD layer selected. Select at least one or use the “All” button.',
    'Zaimportowano: {0}':
        'Imported: {0}',
    '<b>Grupy</b>':
        '<b>Groups</b>',
    'bloki':
        'blocks',
    '<b>Sufiksy</b>':
        '<b>Suffixes</b>',
    'Nie wykryto konwertera DWG → DXF. Pliki DXF zaimportują się bez niego; dla DWG użyj wbudowanego importu.':
        'No DWG → DXF converter detected. DXF files will import without it; for DWG use the built-in import.',
    'Warstw CAD: {0}, bloków: {1}, wstawień: {2}{3}':
        'CAD layers: {0}, blocks: {1}, inserts: {2}{3}',
    '  (import wygląda na wykonany z rozwijaniem bloków)':
        '  (the import looks like it was run with blocks expanded)',
    'Konwerter DWG wykryty: {0}':
        'DWG converter detected: {0}',
    'Blad importu: {0}':
        'Import error: {0}',
    'WFG DWG Layers+ — odzyskaj warstwy z rysunku':
        'WFG DWG Layers+ — recover layers from the drawing',
    'Wbudowany import gubi nazwę warstwy dla „ciężkiej" <b>POLYLINE</b> — tej z osobnymi encjami <b>VERTEX</b>, którą wypuszczają eksporty z systemów geodezyjnych. Zapisuje dla niej uchwyt i warstwę <b>SEQEND</b>-a, czyli encji zamykającej, a ta leży na warstwie <b>0</b>. Objaw: <i>inserts</i> i <i>texts</i> mają dziesiątki poprawnych nazw, a <i>polylines</i> jedną.<br><br>Uchwyt przeżywa import, więc wystarczy przeczytać rysunek i podstawić pod uchwyt zamknięcia warstwę polilinii, którą ono zamyka. Geometrii to nie dotyka i nie wymaga ponownego importu.':
        'The built-in import loses the layer name for the “heavy” <b>POLYLINE</b> — the one with separate <b>VERTEX</b> entities that exports from surveying systems produce. It stores the handle and layer of the <b>SEQEND</b>, the closing entity, which sits on layer <b>0</b>. Symptom: <i>inserts</i> and <i>texts</i> have dozens of proper names, <i>polylines</i> only one.<br><br>The handle survives the import, so it is enough to read the drawing and put the layer of the polyline it closes under the closing handle. Geometry is not touched and no new import is needed.',
    'plik DXF, z którego powstał import':
        'the DXF file the import was made from',
    'Rysunek DXF:':
        'DXF drawing:',
    'Sprawdź (podgląd zmian)':
        'Check (preview changes)',
    'Opcje':
        'Options',
    'Nie ruszaj encji rozbitych z bloków':
        'Leave entities exploded from blocks untouched',
    'Kopie rozbitego bloku dzielą jeden uchwyt z jego definicją, więc dostałyby warstwę z wnętrza bloku — zwykle 0 — zamiast tej, którą niesie wstawienie. Dla treści blokowej właściwą drogą jest tryb bloków złożonych w oknie importu.':
        'Copies of an exploded block share one handle with its definition, so they would get the layer from inside the block — usually 0 — instead of the one carried by the insert. For block content the right way is the composite block mode in the import dialog.',
    'Warstwy wczytane wcześniej mają filtr na starą wartość, więc teraz pokażą mniej obiektów. Uruchom import wtyczki jeszcze raz na tym samym GeoPackage — tym razem zobaczy wszystkie warstwy CAD.':
        'Layers loaded earlier have a filter on the old value, so they will now show fewer features. Run the plugin import again on the same GeoPackage — this time it will see all CAD layers.',
    'Dopasowanych':
        'Matched',
    'Do zmiany':
        'To change',
    'Warstw teraz':
        'Layers now',
    'Warstw po naprawie':
        'Layers after fix',
    'Rysunek znaleziony automatycznie — import zapisał jego ścieżkę w GeoPackage.':
        'Drawing found automatically — the import stored its path in the GeoPackage.',
    'Wskaż istniejący plik DXF.':
        'Select an existing DXF file.',
    'Źródłem jest DWG. Ta naprawa czyta tylko DXF-a — zapisz rysunek jako DXF (ASCII) i wskaż ten plik.':
        'The source is a DWG. This fix reads DXF only — save the drawing as DXF (ASCII) and select that file.',
    'Przykłady: ':
        'Examples: ',
    'W rysunku: {0} encji z uchwytem, {1} nazw warstw w przestrzeni modelu; {2} przypisań odzyskanych przez uchwyt SEQEND-a.':
        'In the drawing: {0} entities with a handle, {1} layer names in model space; {2} assignments recovered via the SEQEND handle.',
    'Do poprawy: {0} obiektów.':
        'To fix: {0} features.',
    'Przepisać przypisanie warstw do pliku\n{0}?\n\n{1}':
        'Rewrite the layer assignment in the file\n{0}?\n\n{1}',
    'Poprawiono przypisanie dla {0} obiektów.':
        'Layer assignment fixed for {0} features.',
    'Encji bez uchwytu: {0} — tych nie da się dopasować.':
        'Entities without a handle: {0} — these cannot be matched.',
    '{0} obiektów pochodzi z rozbicia bloków i zostanie pominiętych.':
        '{0} features come from exploded blocks and will be skipped.',
    'UWAGA: w {0} przypadkach nazwa w bazie różni się od rysunku wyłącznie kodowaniem polskich znaków. Uruchom najpierw „Napraw kodowanie”, a potem wróć tutaj.':
        'WARNING: in {0} cases the name in the database differs from the drawing only in the encoding of accented characters. Run “Fix encoding” first, then come back here.',
    'Import wskazuje na rysunek <i>{0}</i>, ale go tam nie ma. Wskaż plik ręcznie.':
        'The import points to the drawing <i>{0}</i>, but it is not there. Select the file manually.',
    'WFG DWG Layers+ — popraw wygląd':
        'WFG DWG Layers+ — fix appearance',
    'Nakłada style WFG DWG Layers+ na warstwy, które są już w projekcie — bez ponownego czytania rysunku. Przydatne, gdy część punktów albo linii wczytała się z domyślnym wyglądem QGIS.':
        'Applies WFG DWG Layers+ styles to layers already in the project — without reading the drawing again. Useful when some points or lines were loaded with the default QGIS look.',
    'Grubość dla encji bez własnej (linewidth 0 albo -1 = BYBLOCK). Bez tego QGIS podstawia swoje 0,26 mm.':
        'Width for entities without their own (linewidth 0 or -1 = BYBLOCK). Without it QGIS uses its 0.26 mm.',
    'puste = cały projekt':
        'empty = whole project',
    'Wpisz fragment nazwy grupy, żeby ograniczyć działanie tylko do niej.':
        'Enter part of a group name to limit the action to that group.',
    'Tylko grupa zawierająca:':
        'Only the group containing:',
    'Ostylowano warstw: {0}, pominięto: {1}':
        'Layers styled: {0}, skipped: {1}',
    'Importuj DWG/DXF jako warstwy…':
        'Import DWG/DXF as layers…',
    'Import DWG/DXF z warstwami nazwanymi jak w CAD, w czterech grupach':
        'DWG/DXF import with layers named as in CAD, in four groups',
    'Popraw wygląd wczytanych warstw…':
        'Fix appearance of loaded layers…',
    'Nakłada style WFG DWG Layers+ na warstwy już wczytane do projektu, bez ponownego importu rysunku':
        'Applies WFG DWG Layers+ styles to layers already loaded in the project, without importing the drawing again',
    'Wczytaj atrybuty bloków z rysunku…':
        'Load block attributes from the drawing…',
    'Odzyskuje wartości atrybutów bloków (ATTRIB), których wbudowany import DWG/DXF nie widzi, i skleja je z importem po uchwycie encji':
        'Recovers block attribute values (ATTRIB) that the built-in DWG/DXF import does not see, and joins them to the import by entity handle',
    'Napraw kodowanie…':
        'Fix encoding…',
    'Usuwa podwójne kodowanie polskich znaków w nazwach warstw, nazwach bloków i treści tekstów':
        'Removes double encoding of accented characters in layer names, block names and text content',
    'Odzyskaj warstwy z rysunku…':
        'Recover layers from the drawing…',
    'Gdy cała kreska wylądowała na warstwie 0, a w rysunku ma swoje warstwy — przepisuje przypisanie z DXF-a po uchwycie encji':
        'When all linework ended up on layer 0 although it has its own layers in the drawing — rewrites the assignment from the DXF by entity handle',
    'Podziel warstwę wg koloru…':
        'Split layer by colour…',
    'Dla rysunków, w których cała kreska leży na warstwie 0, a treść rozróżnia barwa':
        'For drawings in which all linework is on layer 0 and content is distinguished by colour',
    'O wtyczce…':
        'About…',
    'WFG DWG Layers+ — import DWG/DXF do QGIS z prawdziwymi warstwami.\n\n• nazwy warstw: <warstwa_CAD>_hatch / _line / _pline / _point / _text / _insert\n• cztery grupy wg typu geometrii\n• tryb filtrow (szybki) i materializacji do osobnych tabel GPKG\n• bloki jako zlozone geometrie: jeden obiekt na wstawienie, z rekurencja, MINSERT i dziedziczeniem warstwy 0\n• odzyskiwanie atrybutow blokow (ATTRIB), ktorych libdxfrw nie czyta w ogole\n• naprawa podwojnego kodowania polskich znakow\n• odzyskanie przypisania warstw z DXF-a, gdy import zgubil je\n  dla ciezkiej POLYLINE i cala kreska wylandowala na warstwie 0\n• podzial warstwy wg koloru, grubosci pisaka i typu encji\n\nWtyczka opiera sie na schemacie GeoPackage produkowanym przez wbudowany import DWG/DXF w QGIS.':
        'WFG DWG Layers+ — DWG/DXF import into QGIS with real layers.\n\n• layer names: <CAD_layer>_hatch / _line / _pline / _point / _text / _insert\n• four groups by geometry type\n• filter mode (fast) and materialization into separate GPKG tables\n• blocks as composite geometry: one feature per insert, with recursion, MINSERT and layer 0 inheritance\n• recovery of block attributes (ATTRIB), which libdxfrw does not read at all\n• fixing double encoding of accented characters\n• recovery of layer assignment from the DXF when the import lost it\n  for heavy POLYLINE and all linework landed on layer 0\n• splitting a layer by colour, pen weight and entity type\n\nThe plugin relies on the GeoPackage schema produced by the built-in QGIS DWG/DXF import.',
    'kolor':
        'colour',
    'pomijaj':
        'ignore',
    'teksty':
        'texts',
    'punkty':
        'points',
    'linie':
        'lines',
    'poligony':
        'polygons',
    'Anuluj':
        'Cancel',
}
