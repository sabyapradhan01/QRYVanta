@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo QRYVANTA GitHub publish helper
echo Repository: https://github.com/sabyapradhan01/QRYVanta.git
echo.
where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git was not found. Install Git for Windows, then retry.
  exit /b 1
)

for /f "delims=" %%R in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%R"
if not defined ORIGIN_URL (
  git remote add origin https://github.com/sabyapradhan01/QRYVanta.git
  if errorlevel 1 exit /b 1
) else (
  git remote set-url origin https://github.com/sabyapradhan01/QRYVanta.git
  if errorlevel 1 exit /b 1
)

echo Staging non-ignored changes, including any optional media you added to assets\...
git add -A
if errorlevel 1 exit /b 1

echo.
echo Files currently staged for a possible new commit:
git status --short

git diff --cached --quiet
if errorlevel 1 (
  echo.
  set /p "CONFIRM=Review the list above. Commit these staged changes and push? (Y/N): "
  if /I not "!CONFIRM!"=="Y" (
    git restore --staged .
    echo Nothing was committed. Staged changes were unstaged; your working files remain.
    exit /b 1
  )
  git commit -m "Update QRYVANTA source and offline assets"
  if errorlevel 1 exit /b 1
)

echo.
echo Pushing branch main. Git may open the standard GitHub authentication flow.
git push -u origin main
if errorlevel 1 (
  echo.
  echo Push failed. Check GitHub authentication and confirm the remote repo is empty,
  echo or fetch/integrate any existing remote commits before retrying. Do not force-push.
  exit /b 1
)
echo.
echo Push completed successfully.
endlocal
