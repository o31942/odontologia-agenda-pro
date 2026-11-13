@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul
if errorlevel 1 (
  echo ERROR: Git no esta instalado. Descargalo desde https://git-scm.com/downloads
  pause
  exit /b 1
)
set "REPO=https://github.com/o31942/odontologia-agenda-pro.git"
echo ==============================================
echo   DentalFlow - Publicacion inicial en GitHub
 echo ==============================================
echo Repositorio: %REPO%
echo IMPORTANTE: Crea primero el repositorio VACIO y PRIVADO en tu GitHub.
echo.
choice /M "Deseas publicar los archivos de DentalFlow"
if errorlevel 2 exit /b 0
if not exist .git git init
if errorlevel 1 goto :error
git add .
if errorlevel 1 goto :error
git diff --cached --quiet
if not errorlevel 1 goto :nochanges
git commit -m "feat: initial DentalFlow dental scheduling application"
if errorlevel 1 goto :error
:nochanges
git branch -M main
if errorlevel 1 goto :error
git remote get-url origin >nul 2>nul
if errorlevel 1 git remote add origin "%REPO%"
if errorlevel 1 goto :error
git remote set-url origin "%REPO%"
if errorlevel 1 goto :error
git push -u origin main
if errorlevel 1 goto :error
echo.
echo Listo: revisa https://github.com/o31942/odontologia-agenda-pro
pause
exit /b 0
:error
echo.
echo No se pudo completar. Revisa Git, el acceso a GitHub y que el repositorio este vacio.
pause
exit /b 1
