@echo off
setlocal
cd /d "%~dp0"

if not exist "dist\QRYVANTA\QRYVANTA.exe" (
  echo ERROR: dist\QRYVANTA\QRYVANTA.exe was not found.
  echo Run build_windows.bat successfully before compiling the installer.
  exit /b 1
)

set "ISCC="
if not "%~1"=="" set "ISCC=%~1"
if "%ISCC%"=="" if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if "%ISCC%"=="" (
  echo ERROR: Inno Setup 6 compiler ISCC.exe was not found.
  echo Install Inno Setup 6, or pass the full compiler path as an argument.
  echo Example: compile_installer.bat "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
  exit /b 1
)

if not exist "installer-output" mkdir "installer-output"
"%ISCC%" "QRYVANTA-Setup.iss"
if errorlevel 1 (
  echo ERROR: Inno Setup compilation failed.
  exit /b 1
)
echo.
echo Installer created under installer-output\QRYVANTA-Setup-1.1.0-Offline-x64.exe
endlocal
