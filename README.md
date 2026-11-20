# WFG DWG Layers+

**English** · [Polski](#polski)

QGIS plugin of the WFG (WorkFieldGIS) family that fixes what hurts most in DWG/DXF import: **every CAD layer becomes
its own QGIS layer, arranged in four groups by geometry type**, and blocks can be imported as single features instead
of loose lines. The interface follows the QGIS language: Polish in Polish QGIS, English otherwise.

### What it does

The built-in import (*Project → Import/Export → Import Layers from DWG/DXF*) writes one table per geometry type and
shows CAD layers only as filters. WFG DWG Layers+ reads the same GeoPackage and builds a tree:

```
my_drawing/
├── 4_Texts/      <cad_layer>_text
├── 3_Points/     <cad_layer>_point, <cad_layer>_insert
├── 2_Lines/      <cad_layer>_line, <cad_layer>_pline
├── 1_Polygons/   <cad_layer>_hatch
└── 5_Blocks/     blk_<block>_line / _hatch / _point / _text, blk__anchor   (composite block mode)
```

Menu *Vector → WFG DWG Layers+*:

| Item | What for |
|---|---|
| Import DWG/DXF as layers… | the tree above; filter mode (fast) or separate GPKG tables; blocks exploded, as insert points or as composite geometry (one feature per insert, nested blocks, MINSERT, layer 0 inheritance) |
| Fix appearance of loaded layers… | applies the styles to layers already in the project (fallback line width, pen width vs ground width of polylines, legend colours) |
| Load block attributes from the drawing… | ATTRIB values (elevations, numbers) that the built-in import does not read at all; joined by entity handle |
| Fix encoding… | reverses double encoding of accented characters (`Ä™` → `ę`), in the data and in project filters, with a backup |
| Recover layers from the drawing… | heavy POLYLINE that landed on layer 0: the layer is rewritten from the DXF by handle, geometry untouched |
| Split layer by colour… | drawings that really keep everything on layer 0 and separate content by colour, pen weight or entity type |

Also in *Layer → Add Layer → Add DWG/DXF+ Layer…* (and on the Manage Layers toolbar), next to the other data sources.

**Processing Toolbox** (provider *WFG DWG Layers+*, for models and batch runs): *Import DWG/DXF as layers*,
*Recover layers from the drawing*, *Fix encoding*, *Load block attributes from the drawing*. The built-in DWG/DXF
import has no Python API, so in Processing a DXF/DWG goes through the plugin's own GDAL import (blocks exploded);
for composite blocks import with the built-in dialog first and give the resulting GeoPackage to the algorithm.

### Installation

1. Download `wfg_dwg_layers_plus-v<version>.zip` (Releases) or build it with `./make_zip.sh`.
2. QGIS → *Plugins → Manage and Install Plugins → Install from ZIP*.
3. Requirements: QGIS 3.28 or newer (QGIS 4 too). DXF needs nothing else. DWG goes through the built-in import; the
   optional own GDAL import of DWG needs ODA File Converter or LibreDWG (`dwg2dxf`), installed separately.

Tested on Linux (QGIS 4). Reports from Windows and macOS are welcome in the issue tracker.

### Language

Texts in the code are Polish (source language); `i18n.tr()` returns English from `i18n_en.py` unless QGIS runs in
Polish. `WFG_LANG=en` or `WFG_LANG=pl` forces the language. `test/test_i18n.py` checks that every text has a
translation with the same placeholders.

### License

Mozilla Public License 2.0 (`wfg_dwg_layers_plus/LICENSE`), © 2026 Piotr Mędrzycki. MPL-2.0 is compatible with
GPL-2.0-or-later (QGIS). Versions up to 1.5.2 were released under GPL-2.0-or-later.

---

<a id="polski"></a>

# WFG DWG Layers+ (po polsku)

Interfejs wtyczki jest w języku QGIS: po polsku w polskim QGIS, w pozostałych po angielsku.

**Gdzie jest wtyczka:** menu *Wektor → WFG DWG Layers+*, *Warstwa → Dodaj warstwę → Dodaj warstwę DWG/DXF+…*
(także na pasku Zarządzanie warstwami) oraz **Przybornik Processing** → *WFG DWG Layers+*: Importuj DWG/DXF jako
warstwy, Odzyskaj warstwy z rysunku, Napraw kodowanie, Wczytaj atrybuty bloków z rysunku — do modeli i przetwarzania
wsadowego. Wbudowany import DWG/DXF nie ma API w Pythonie, więc w Processing DXF/DWG idzie przez własny import GDAL
(bloki rozwinięte); do bloków złożonych najpierw zaimportuj rysunek oknem wbudowanym i podaj algorytmowi powstały GeoPackage.

Wtyczka QGIS z rodziny WFG (WorkFieldGIS), która naprawia to, co w imporcie DWG/DXF najbardziej uwiera: **warstwy nazywają się jak w CAD-zie i leżą w czterech grupach wg typu geometrii**, a bloki można zaimportować jako pojedyncze obiekty zamiast luźnych linii.

## Co dokładnie robi

Wbudowany import QGIS (*Projekt → Importuj/Eksportuj → Importuj warstwy z DWG/DXF*) tworzy jedną zbiorczą tabelę na typ geometrii i wyświetla warstwy CAD jako filtry o nazwach `lines`, `hatches`, `polylines`… Grupą jest nazwa warstwy CAD, a nie warstwą.

WFG DWG Layers+ czyta ten sam GeoPackage i buduje drzewo tak:

```
mój_rysunek/
├── 4_Teksty/
│   ├── z_8_wyk_RZĘDNE_plac zabaw_fin_text
│   └── z_8_wyk_rzędne kanałów wodnych_text
├── 3_Punkty/
│   ├── z_5_dfa_kosze na śmieci_insert
│   └── z_5_zabawka_point
├── 2_Linie/
│   ├── z_5_dfa_stojaki_pline
│   ├── z_5_przejścia_line
│   └── z_P_płyty kamienne w nawierzchni_pline
├── 1_Poligony/
│   ├── z_5_zabawka_hatch
│   └── z_k_h_hanse_hatch
└── 5_Bloki/                (tylko w trybie złożonych geometrii)
    ├── ławka/
    │   ├── blk_ławka_line
    │   └── blk_ławka_hatch
    └── _kotwice/
        └── blk__anchor
```

## Instalacja

1. Pobierz `wfg_dwg_layers_plus-v<wersja>.zip` z zakładki [Releases](https://github.com/ekolabynet/WFG_dwg_layers_plus/releases)
   albo zbuduj go sam: `./make_zip.sh`.
2. QGIS → *Wtyczki → Zarządzaj wtyczkami → Zainstaluj z pliku ZIP*.
3. Wskaż plik i kliknij *Zainstaluj wtyczkę*.
4. Wtyczka pojawi się w menu *Wektor → WFG DWG Layers+* oraz na pasku narzędzi.

Wymagania: QGIS 3.28 lub nowszy (także QGIS 4). Żadnych bibliotek do doinstalowania.

Praca prosto z repozytorium (poprawka to `git pull`, nie nowy zip):

    # QGIS 4; dla QGIS 3 zamień QGIS4 na QGIS3
    ln -s "$PWD/wfg_dwg_layers_plus" \
          ~/.local/share/QGIS/QGIS4/profiles/default/python/plugins/wfg_dwg_layers_plus

### Przejście z „DWG Layers+” (do 1.5.2) na „WFG DWG Layers+” (od 1.6.0)

Od 1.6.0 pakiet nazywa się `wfg_dwg_layers_plus`, więc QGIS widzi go jako nową wtyczkę.

1. *Wtyczki → Zarządzaj* → stara „DWG Layers+” → *Odinstaluj* (inaczej menu będzie podwójne).
2. Zainstaluj nową z ZIP.

Ustawienia okien (ścieżki, kodowanie, zapamiętane nazwy warstw z podziału wg koloru) przenoszą się
same przy pierwszym uruchomieniu: klucze `dwg_layers_plus/…` są kopiowane do `wfg_dwg_layers_plus/…`.
Tabele w GeoPackage (`dwgplus_layer_map`, `dwgplus_block_attributes`) **nie zmieniły nazw** — bazy
z wcześniejszych importów działają bez zmian.

## Jak używać

### Ścieżka podstawowa (DWG albo DXF)

1. *Wektor → WFG DWG Layers+ → Importuj DWG/DXF jako warstwy…*
2. Wskaż rysunek, ustaw układ współrzędnych, wybierz tryb bloków.
3. *Importuj* — otworzy się wbudowane okno importu QGIS z już ustawionym trybem bloków. Wskaż w nim plik i potwierdź.
4. Wtyczka posprząta po nim tymczasowe warstwy i zbuduje własne drzewo.

### Ścieżka z gotowym GeoPackage

Jeśli rysunek już zaimportowałeś, wskaż po prostu plik `.gpkg`. Wtedy działa też przycisk **Wczytaj listę warstw** — dostaniesz tabelę z liczbą obiektów w rozbiciu na typy i możesz wybrać, co wciągnąć.

## Tryby

### Warstwy

| Tryb | Jak działa | Kiedy |
|---|---|---|
| **Filtry** (domyślny) | jedna tabela GPKG, każda warstwa QGIS to `subset string` | codzienna praca, szybkie wczytanie, setki warstw |
| **Osobne tabele** | fizyczna tabela w GPKG na każdą parę (warstwa CAD × typ) | eksport, publikacja, dalsza obróbka |

Powtórzony import **nadpisuje** tabele z poprzedniego przebiegu (mapowanie trzyma tabela `dwgplus_layer_map`), więc plik nie puchnie; checkbox *Przebuduj nazwy tabel* wymusza nowe nazwy, gdy zmienisz sufiksy.

Przy materializacji nazwy tabel przechodzą sanityzację (polskie znaki → ASCII, spacje → `_`, deduplikacja niewrażliwa na wielkość liter, limit 60 znaków). Mapowanie `tabela → oryginalna nazwa warstwy CAD` ląduje w tabeli `dwgplus_layer_map`.

### Bloki

| Tryb | Wynik |
|---|---|
| **Rozbite** | geometria bloków rozwinięta w przestrzeń modelu — zachowanie identyczne z dzisiejszym |
| **Punkty wstawień** | bloki jako punkty z nazwą, skalą i obrotem |
| **Złożone geometrie** | **jeden obiekt na jedno wstawienie**, geometria wieloczęściowa |

Tryb złożonych geometrii wymaga importu **bez** rozwijania bloków — wtyczka ustawia to sama w oknie wbudowanego importu (`Add Only Insert Points`).

Warstwy wynikowe: `blk_<nazwa>_line`, `blk_<nazwa>_hatch`, `blk_<nazwa>_point`, `blk_<nazwa>_text`, plus opcjonalna `blk__anchor` — jeden punkt na wstawienie, wygodny do etykietowania i zliczania („ile ławek jest w projekcie”).

Atrybuty każdego obiektu: `insert_handle`, `block_name`, `cad_layer`, `xscale`, `yscale`, `zscale`, `angle_deg`, `x`, `y`, `n_parts`, `color`, `linewidth`.

## Trzy rzeczy, których nie robi wbudowany import

1. **MINSERT** — kolumny `colcount`/`rowcount`/`colspace`/`rowspace` są zapisywane do GeoPackage, ale nigdy nie czytane, więc tablica wstawień 5×4 materializuje się jeden raz. Tutaj rozwija się poprawnie (checkbox *Rozwijaj tablice MINSERT*).
2. **Dziedziczenie warstwy `0`** — encja leżąca w bloku na warstwie `0` powinna przejąć warstwę wstawienia. Bez tego geometria trafia do niewłaściwej warstwy CAD.
3. **Ochrona przed cyklami** — blok A wstawiający B wstawiający A. Wtyczka pilnuje zbioru odwiedzonych bloków i limitu zagnieżdżenia.

Dodatkowo: wbudowany importer składa macierz wstawienia jako `translate · scale · rotate · translate(-base)`, czyli **obraca przed skalowaniem**, podczas gdy AutoCAD skaluje przed obrotem. Dla skali jednorodnej to bez różnicy; dla `xscale ≠ yscale` w połączeniu z obrotem wyniki się rozjeżdżają. Wtyczka domyślnie używa kolejności CAD-owej, a checkbox *Kolejność transformacji jak w QGIS* pozwala wrócić do starego zachowania, gdyby okazało się potrzebne.

## Import własny (eksperymentalny)

Checkbox *Własny import przez GDAL* pomija wbudowany dialog:

- **DXF** — sterownik `DXF` w GDAL jest wbudowany zawsze, zero zależności. Bloki rozwija rekurencyjnie w 3D, rozwija MINSERT, ma ochronę przed cyklami i dziedziczy warstwę `0`.
- **DWG** — GDAL bez pakietu ODA nie czyta DWG, więc potrzebny jest konwerter: **ODA File Converter** (bezpłatny, wymaga rejestracji) albo **`dwg2dxf`** z LibreDWG. Wtyczka wykrywa oba automatycznie; żadnego nie wolno redystrybuować, więc trzeba je zainstalować osobno.

W tym trybie nie ma tabel `blocks`/`inserts` (bloki są już rozwinięte), więc tryb złożonych geometrii jest niedostępny.

## Wygląd i typowe „domyślne" style

Kolumna `linewidth` w GeoPackage bywa `0` albo `-1` (BYBLOCK), a `color` bywa pusta albo równa `byblock`. QGIS w takiej sytuacji **po cichu wraca do własnego symbolu** — czyli linii 0,26 mm w losowym kolorze. Stąd wrażenie, że część warstw wczytała się „domyślnie".

WFG DWG Layers+ podstawia wtedy wartości zastępcze, konfigurowalne w sekcji wyglądu okna importu:

| Ustawienie | Domyślnie | Po co |
|---|---|---|
| Grubość zastępcza linii | 0,10 mm | zamiast QGIS-owych 0,26 mm dla encji bez własnej grubości |
| Rozmiar punktów | 0,8 mm | punkty CAD mają jawny mały krzyżyk zamiast domyślnego markera 2 mm |
| Rozmiar wstawień i kotwic | 1,2 mm | to samo dla `*_insert` i `blk__anchor` |
| Pokazuj punkty CAD | nie | jak we wbudowanym imporcie |
| Szerokość polilinii | grubość pisaka w mm | patrz niżej |

### Dwie „grubości" polilinii

Polilinia CAD ma dwie różne rzeczy, które łatwo pomylić:

- **`linewidth`** — grubość pisaka w milimetrach, rzecz czysto kartograficzna,
- **`width`** — *globalna szerokość* polilinii w jednostkach rysunku, czyli realna szerokość w terenie.

Wbudowany import QGIS renderuje `width` w jednostkach mapy, wiernie wobec CAD-a. Polilinia o `width = 0,5` wychodzi wtedy na **pół metra szeroka** — czarna belka przez pół rysunku. Tyle że projektanci nagminnie wpisują tam grubości piór ISO (0,05 / 0,10 / 0,30 / 0,50), bo tak wygląda intuicyjne „ustaw grubość linii".

Dlatego domyślnie tę liczbę traktujemy jako **milimetry**. Przełącznik *Szerokość polilinii* ma trzy stany:

| Tryb | Zachowanie |
|---|---|
| grubość pisaka w mm | domyślny; `width = 0,5` → linia 0,5 mm |
| szerokość w terenie | wiernie jak CAD i jak wbudowany import; `width = 0,5` → pół metra |
| pomijaj | `width` ignorowane, liczy się tylko `linewidth` |

Jeśli w Twoim rysunku szerokie polilinie *naprawdę* oznaczają szerokość w terenie (np. jezdnia narysowana jedną grubą polilinią), przełącz na tryb środkowy.

### Miniatury w legendzie

Kolor każdej encji CAD pochodzi z **właściwości definiowanej danymi** na kolumnie `color`. QGIS rysuje w legendzie *statyczny* kolor symbolu, a nie wynik wyrażenia — dlatego przy setkach warstw wszystkie mają identyczny niebieski kwadracik, mimo że na mapie każda jest inna. Przy 90 warstwach poligonowych to realnie utrudnia pracę.

Wtyczka próbkuje kilkadziesiąt obiektów warstwy, ustala kolor dominujący i podstawia go jako kolor statyczny symbolu. Miniatura zaczyna odpowiadać temu, co widać na ekranie, a wyrażenie nadal wygrywa przy rysowaniu mapy — więc encje o własnych kolorach dalej rysują się poprawnie.

Próbkujemy garstkę obiektów zamiast całej tabeli: przy 400 warstwach pełny przebieg byłby zabójczy, a do kwadracika w legendzie więcej nie potrzeba. Warstwy tekstowe zostają bez miniatury, bo rysują się jako etykiety, nie jako symbol.

### Poprawa bez ponownego importu

*Wektor → WFG DWG Layers+ → Popraw wygląd wczytanych warstw…* nakłada style na warstwy, które już są w projekcie. Rozpoznaje je po `layername=` w źródle, po tabeli `dwgplus_layer_map` i po sufiksie nazwy — więc działa i w trybie filtrów, i po materializacji. Przy wielkim rysunku to sekundy zamiast ponownego czytania DXF-a.

## Atrybuty bloków — dane, których QGIS w ogóle nie widzi

Kota wysokościowa, numer drzewa, opis studzienki — w CAD-zie to zwykle **atrybut bloku** (ATTRIB), a nie tekst. Takich wartości w GeoPackage nie ma i nie będzie, bo biblioteka `libdxfrw`, której QGIS używa i do DWG, i do DXF, **nie zna atrybutów**. W jej enumie typów encji `ATTDEF` i `ATTRIB` są dosłownie zakomentowane, a `DRW_Interface` nie ma żadnego `addAttrib`. W czytniku DXF atrybuty wpadają do zbiorczego `else`, który przewija plik do następnej encji; w czytniku DWG lądują w `default:`. Wartość nie przekracza granicy między biblioteką a QGIS-em.

*Wektor → WFG DWG Layers+ → Wczytaj atrybuty bloków z rysunku…* omija ten problem:

1. czyta rysunek **sterownikiem DXF w GDAL** (wbudowany zawsze, zero zależności) z `DXF_INLINE_BLOCKS=FALSE` — tylko w tym trybie GDAL wystawia pole `BlockAttributes`,
2. zapisuje wynik do tabeli `dwgplus_block_attributes` w tym samym GeoPackage: jeden wiersz na wstawienie, jedna kolumna `att_<ZNACZNIK>` na znacznik (kolumny czysto liczbowe dostają typ REAL, więc od razu nadają się do klasyfikacji),
3. podpina to **nieniszczącym złączeniem** do wszystkich warstw `*_insert` i `blk__anchor` w projekcie.

Kluczem jest uchwyt encji: QGIS zapisuje w `inserts` kolumnę `handle` (dziesiętnie), GDAL zwraca `EntityHandle` (szesnastkowo) — `int(handle, 16)` daje bezpośrednie dopasowanie.

Po zastosowaniu rzędna jest zwykłym polem: można nią etykietować, filtrować, klasyfikować. Złączenia zdejmuje przycisk *Zdejmij złączenia* albo właściwości warstwy.

### Kodowanie tekstu

DXF deklarujący wersję R2018 powinien być w UTF-8, ale wiele CAD-ów zapisuje bajty w stronie kodowej systemu i nie poprawia nagłówka. Sterownik DXF w GDAL nie transkoduje wtedy łańcuchów — wiązania Pythona oddają surowe `bytes`, a znacznik `KOTA_WYKOŃCZENIE` zamienia się w literał repr-a i cała kolumna jest do wyrzucenia.

Wtyczka dekoduje takie łańcuchy jawnie; pole *Kodowanie tekstu* domyślnie stoi na `cp1250`. Poprawny UTF-8 przechodzi nietknięty — przekodowanie włącza się tylko wtedy, gdy GDAL faktycznie oddał bajty. Po skanie w podsumowaniu pojawia się informacja, czy plik tego wymagał.

Dla DWG potrzebny jest konwerter (ODA File Converter lub `dwg2dxf`) — wtyczka wykryje go sama. Jeśli masz DXF, nic dodatkowego nie jest potrzebne.

### Diagnostyka

W paczce jest `diagnostyka.py`. Wklejony do konsoli Pythona QGIS wypisuje dla każdej warstwy renderer, warstwy symbolu, jednostki, aktywne właściwości definiowane danymi oraz min/max kolumn `linewidth`, `width` i przykłady `color`. Raport ląduje w pliku tekstowym obok projektu — zawiera tylko metadane stylów, bez geometrii.

## Napraw kodowanie

*Wektor → WFG DWG Layers+ → Napraw kodowanie…*

DXF od wersji R2007 ma treść w UTF-8 i nagłówkowa strona kodowa `$DWGCODEPAGE` powinna być wtedy ignorowana. Wiele CAD-ów zostawia tam starą wartość, a biblioteka czytająca stosuje ją posłusznie — czyta bajty UTF-8 tak, jakby były w cp1250:

```
ę  →  bajty C4 99  →  odczytane jako cp1250  →  Ä™
ś  →  bajty C5 9B  →                         →  Ĺ›
ł  →  bajty C5 82  →                         →  Ĺ‚
```

To jest **odwracalne bez straty** — wystarczy konwersja w drugą stronę. Narzędzie skanuje wszystkie kolumny tekstowe GeoPackage, pokazuje podgląd (co, gdzie, ile, przed → po), robi kopię zapasową i poprawia trzy rzeczy naraz:

1. dane w GeoPackage — nazwy warstw CAD, nazwy bloków, treść tekstów,
2. filtry warstw w projekcie — odwołują się do wartości kolumny `layer`, więc muszą zmienić się razem z danymi,
3. nazwy warstw i grup w legendzie.

Poprawne napisy i liczby (`0,0,0,255`, `102,9`, `rzędne kanałów wodnych`) zostają nietknięte: naprawa wymaga obecności znaków charakterystycznych dla uszkodzenia i sprawdza, czy wynik zawiera polskie litery.

### Dwie pułapki, których nie widać z zewnątrz

**Wyzwalacze indeksu przestrzennego.** GeoPackage zakłada na tabelach z geometrią wyzwalacze RTree zadeklarowane jako `AFTER UPDATE ON <tabela>`, a nie `AFTER UPDATE OF geom`. SQLite kompiluje ich treść przy **każdym** `UPDATE` i rozwiązuje nazwy funkcji (`ST_IsEmpty`, `ST_MinX`…) już na etapie przygotowania zapytania — mimo że warunek `WHEN OLD.fid != NEW.fid` sprawia, że ciało nigdy się nie wykona. Zwykłe połączenie `sqlite3` tych funkcji nie zna, więc zapytanie nie daje się nawet skompilować. Wtyczka rejestruje atrapy; są bezpieczne, bo nie ruszamy ani geometrii, ani `fid`.

**Blokada pliku.** QGIS trzyma ten sam GeoPackage otwarty do odczytu. Przed zapisem wtyczka przeładowuje warstwy, co unieważnia pulę połączeń dostawcy OGR i zwalnia plik. Warstwy w trybie edycji blokują naprawę — ich bufor zapisałby stare wartości z powrotem.

## Odzyskaj warstwy z rysunku

*Wektor → WFG DWG Layers+ → Odzyskaj warstwy z rysunku…*

Objaw jest charakterystyczny: `inserts` i `texts` mają dziesiątki poprawnych nazw warstw CAD, a `lines`, `polylines` i `hatches` mają jedną — `0`. Wygląda to na rysunek bez warstw, ale nim nie jest. W jednym pliku z zasobu geodezyjnego było tak:

| gdzie | warstw |
|---|---|
| DXF, sekcja ENTITIES, encje POLYLINE | **72** |
| GeoPackage po imporcie, tabela `polylines` | **1** (`0`) |

Wbudowany import gubi przypisanie dla części encji — najczęściej dla „ciężkiej" `POLYLINE`, tej z osobnymi encjami `VERTEX`, którą wypuszczają eksporty z systemów geodezyjnych. Lekka `LWPOLYLINE` przechodzi bez szwanku, `INSERT` i `TEXT` też, więc łatwo uwierzyć, że to rysunek jest ubogi.

### Skąd to się bierze

Ciężka polilinia nie jest w DXF jedną encją, tylko ciągiem: `POLYLINE`, potem po jednym `VERTEX` na wierzchołek, na końcu `SEQEND`. Import czyta ten ciąg po kolei i **na `SEQEND` nadpisuje wspólne atrybuty encji atrybutami zamknięcia** — a `SEQEND` leży na warstwie `0`. W GeoPackage ląduje więc nie tylko cudza warstwa, ale i cudzy uchwyt:

```
DXF:   POLYLINE 19F3DB (warstwa "312-budynek")
         VERTEX 19F3DC
         VERTEX 19F3DD
         SEQEND 19F3DE (warstwa "0")
GPKG:  handle = 1700830 (19F3DE), layer = "0"
```

Dlatego naprawa nie może po prostu szukać uchwytu polilinii — w bazie go nie ma. Wtyczka wiąże uchwyt zamknięcia z warstwą polilinii, którą ono zamyka. To samo dotyczy `INSERT`-ów z atrybutami, tam jednak warstwa i tak przychodzi poprawna.

Naprawa nie wymaga ponownego importu. Uchwyt encji (kod grupy 5) jest w rysunku unikalny i **przeżywa import** — QGIS zapisuje go w kolumnie `handle`, tyle że dziesiętnie, podczas gdy DXF trzyma go szesnastkowo. Wtyczka przechodzi plik DXF raz, strumieniowo (para linii: kod, wartość — rysunek o wadze kilkuset megabajtów też przejdzie), buduje odwzorowanie `uchwyt → warstwa` i przepisuje je do GeoPackage. Geometrii nikt nie dotyka.

Okno pokazuje podgląd: ile obiektów w każdej tabeli, ile z nich udało się dopasować po uchwycie, ile zmieni warstwę i ile warstw będzie przed naprawą, a ile po. Ścieżkę rysunku źródłowego wtyczka znajduje sama — import zapisuje ją w tabeli `drawing` wewnątrz GeoPackage; gdy plik się przeprowadził, szuka też rysunku obok bazy.

Po naprawie wcześniej wczytane warstwy mają filtr na starą wartość i pokażą mniej obiektów. Wystarczy uruchomić import wtyczki jeszcze raz na tym samym GeoPackage — tym razem zobaczy wszystkie warstwy CAD.

### Czego ta naprawa nie zrobi

Encje powstałe z **rozbicia bloków** dzielą uchwyt z definicją bloku: jeden uchwyt, wiele kopii na mapie. Dostałyby więc warstwę z wnętrza bloku — zwykle `0` — a nie tę, którą niesie wstawienie. Domyślnie są pomijane, a właściwą drogą dla treści blokowej jest tryb bloków złożonych w oknie importu, który bierze warstwę ze wstawienia.

Bardzo stare DXF-y bez uchwytów encji są poza zasięgiem tej metody; okno powie to wprost, zamiast dopasowywać cokolwiek na chybił trafił. Źródłem musi być DXF tekstowy — DWG i binarny DXF nie przejdą.

## Podziel warstwę wg koloru

*Wektor → WFG DWG Layers+ → Podziel warstwę wg koloru…*

To narzędzie jest dla przypadku, w którym poprzednie nie ma czego odzyskać: rysunek naprawdę trzyma całą kreskę na warstwie `0`, a treść rozróżnia wyłącznie wygląd. Zanim się po nie sięgnie, warto sprawdzić właśnie „Odzyskaj warstwy z rysunku" — objaw jest identyczny, a przyczyna zupełnie inna.

Dzielić można po trzech niezależnych wymiarach: **kolorze**, **grubości pisaka** i **typie encji** (łuk / okrąg / odcinek / polilinia / splajn). Każdy wymiar to osobny przełącznik, bo z góry nie wiadomo, które sito jest właściwe. Skan pokazuje wszystkie kombinacje z liczbą obiektów i próbką koloru; nazwy warstw są edytowalne i — na życzenie — zapamiętywane, więc przy następnym pliku z tej samej pracowni wracają same.

Warstwy powstają jako filtry na wspólnej tabeli, więc podział jest natychmiastowy i nic nie waży. Trafiają do tych samych czterech grup geometrycznych co import, a nierozdzieloną warstwę źródłową można od razu usunąć z projektu, żeby ta sama geometria nie rysowała się dwa razy.

## Wydajność

Rysunek z 200 warstwami × 6 tabel to do 1200 potencjalnych warstw QGIS. Wbudowany dialog tworzy każdą i pyta o `featureCount()`. Tutaj robimy **jedno zapytanie `GROUP BY` na tabelę** — sześć zapytań zamiast 1200 — i dodajemy warstwy jedną paczką przez `addMapLayers()`.

## Struktura kodu

```
core/gpkg_schema.py     kontrakt: nazwy tabel, kolumn, sentinele, reguła widoczności
core/gpkg_reader.py     inwentaryzacja (czysty sqlite3, bez QGIS)
core/affine.py          macierze 2.5D, MINSERT (czysty Python, testowalne)
core/naming.py          nazwy warstw i sanityzacja tabel (czysty Python)
core/tree_builder.py    cztery grupy, tryb filtrów
core/materializer.py    tryb osobnych tabel
core/styler.py          renderery i etykiety odtworzone z wbudowanego importu
core/blocks.py          rekurencyjne składanie bloków w złożone geometrie
core/block_attributes.py atrybuty bloków (ATTRIB) czytane przez GDAL
core/encoding_fix.py    naprawa podwójnego kodowania
core/layer_fix.py       odzyskanie przypisania warstw z DXF-a po uchwycie
core/color_split.py     podział po kolorze / grubości / typie encji
core/producer_builtin.py odpalenie wbudowanego dialogu i wykrycie jego GPKG
core/producer_ogr.py    własny import DXF/DWG przez GDAL
core/runner.py          spięcie całości
gui/import_dialog.py    okno
```

Moduły `affine`, `naming`, `gpkg_schema` i `gpkg_reader` nie importują QGIS-a — da się je testować zwykłym Pythonem:

```
python -m unittest wfg_dwg_layers_plus.test.test_core -v
```

## Dlaczego tak, a nie przez API importera

`QgsDwgImporter` nie ma powiązań SIP. Klasa żyje w `src/app/dwg/`, kompiluje się do `qgis_app` i nie jest wystawiona ani w `qgis.core`, ani w `qgis.gui`; `QgisInterface` nie ma slotu `dwgImport()`. Z Pythona nie da się jej wywołać z parametrami — sprawdzone na `master` i `release-3_34`.

Dlatego kontraktem wtyczki jest **schemat GeoPackage**, który ten importer produkuje. Schemat jest identyczny od QGIS 3.34 do `master`, więc jest bezpiecznie się na nim oprzeć.

## Licencja

**Mozilla Public License 2.0** (`wfg_dwg_layers_plus/LICENSE`, nagłówki `SPDX-License-Identifier: MPL-2.0`)
— od wersji 1.6.0. © 2026 Piotr Mędrzycki. Wersje do 1.5.2 wydane na GPL-2.0-or-later i te kopie zostają na GPL.

- MPL-2.0 bez oznaczenia „Incompatible With Secondary Licenses” jest zgodna z GPL-2.0-or-later, więc wtyczka
  może działać w QGIS i trafić do repozytorium wtyczek QGIS.
- Copyleft na poziomie pliku: zmiany w plikach tej wtyczki udostępnia się na MPL-2.0, ale kod można łączyć
  z własnym, także zamkniętym, np. moduły rdzenia bez importu QGIS (`core/affine.py`, `core/naming.py`,
  `core/gpkg_schema.py`, `core/gpkg_reader.py`, `core/layer_fix.py`).
- Licencja na innych warunkach (np. do produktu komercyjnego bez warunków MPL): na podstawie osobnej umowy
  z autorem; kontakt przez zgłoszenie w repozytorium. Do czasu umowy współtwórcy zmiany wnosi wyłącznie autor.
