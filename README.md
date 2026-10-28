# QRYVANTA — Query Intelligence Studio

QRYVANTA is a desktop SQL workspace with linting, query-performance analysis, database exploration, account management, offline learning resources, quiz practice, and report exports.

## Features

- Oracle, MySQL, and PostgreSQL adapter support.
- SQL console, command history, Database Explorer, lint findings, and performance recommendations.
- Offline LEARN, HELP, QUIZ, and competitive SQL practice sections.
- CSV table export, SQL history text export, and PDF/DOCX/TXT report export.
- Five themes with day/night mode.
- PyInstaller and Inno Setup configuration for a Windows installer.

## Requirements

- Python 3.11+ recommended for source development.
- Windows for the Windows `.exe` and Inno Setup workflow.
- A compatible database server for live database connections. Oracle SQL*Plus console functionality additionally requires a compatible local SQL*Plus installation.

## Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## Test and build

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py main.py database_view.py adapters analyzer core database linter feature_windows.py learning_content.py quiz_engine.py export_utils.py tools tests
```

On Windows, run `build_windows.bat` to test, compile, and create the PyInstaller onedir bundle. Then run `compile_installer.bat` to invoke Inno Setup 6 and create the offline installer under `installer-output/`.

## Optional media assets

The application has graceful fallbacks when optional media is not supplied. To enable the video and portraits, place your licensed media at these paths before building:

```text
assets/learn.mp4
assets/Dev1.jpg
assets/Dev2.jpg
assets/fac.jpg
```

These four files were not present in the source archive used to prepare this repository package. Add them from your own project folder before publishing if they should be part of the public repository and installer. If `learn.mp4` exceeds GitHub's normal file-size limit, use Git LFS or another distribution method.

## Included documentation

- `README.txt` — end-user setup and troubleshooting guide.
- `BUILD_INSTRUCTIONS.txt` — build steps.
- `docs/` — quiz and SQL learning study documents.
- `GITHUB_PUBLISHING.md` — repository publishing notes.

## License

No license is included yet. The project owner should select a license before granting others permission to reuse, modify, or redistribute the code.
