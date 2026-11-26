#!/bin/sh
# Buduje wfg_dwg_layers_plus-v<wersja>.zip do instalacji w QGIS (Wtyczki -> Zainstaluj z ZIP).
set -e
cd "$(dirname "$0")"
VER=$(sed -n 's/^version=//p' wfg_dwg_layers_plus/metadata.txt)
OUT="wfg_dwg_layers_plus-v${VER}.zip"
rm -f "$OUT"
# plugins.qgis.org wants a README inside the package: the repository README goes in at build time
cp README.md wfg_dwg_layers_plus/README.md
zip -r -q "$OUT" wfg_dwg_layers_plus -x '*/__pycache__/*' '*.pyc' '*/.pytest_cache/*'
rm -f wfg_dwg_layers_plus/README.md
echo "$OUT"
