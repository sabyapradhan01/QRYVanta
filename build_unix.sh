#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m unittest discover -s tests -v
python -m compileall -q app.py main.py database_view.py adapters analyzer core database linter feature_windows.py learning_content.py quiz_engine.py export_utils.py tools tests
python -m PyInstaller --clean --noconfirm QRYVANTA.spec
printf 'Build bundle created under dist/QRYVANTA. The Inno Setup installer is Windows-only.\n'
