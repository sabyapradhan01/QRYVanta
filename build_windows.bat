@echo off
setlocal
cd /d "%~dp0"
python -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
python -m compileall -q app.py main.py database_view.py adapters analyzer core database linter feature_windows.py learning_content.py quiz_engine.py export_utils.py tools tests
if errorlevel 1 exit /b 1
python -m PyInstaller --clean --noconfirm QRYVANTA.spec
if errorlevel 1 exit /b 1
echo Build bundle created under dist\QRYVANTA. Compile QRYVANTA-Setup.iss with Inno Setup to build the Windows installer.
endlocal
