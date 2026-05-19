@echo off
setlocal enableextensions
title Compaatible Marketing Cockpit

REM Se placer dans le dossier cockpit/ (le code reel y vit, le .bat est a la racine du projet).
cd /d "%~dp0\cockpit"
if errorlevel 1 (
    echo [ERREUR] Dossier 'cockpit' introuvable a cote de ce .bat.
    echo   Place lancer-cockpit.bat a la racine du projet Compaatible Marketing.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Compaatible Marketing Cockpit
echo ============================================================
echo.

REM 1. Verifier Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERREUR] Python introuvable dans le PATH.
    echo   Installe Python 3.10 ou plus depuis python.org
    echo   et coche "Add Python to PATH" pendant l'install.
    pause
    exit /b 1
)
echo [1/3] Python detecte :
python --version
echo.

REM 2. Verifier que les deps sont importables
echo [2/3] Test des dependances...
python -c "import flask, anthropic, psycopg2, dotenv" >nul 2>nul
if errorlevel 1 (
    echo   Une ou plusieurs deps manquent. Installation...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERREUR] L'installation a echoue.
        echo   Verifie ta connexion internet.
        echo   Tu peux aussi essayer manuellement : pip install -r requirements.txt
        pause
        exit /b 1
    )
) else (
    echo   Toutes les deps disponibles : OK.
)
echo.

REM 3. Preparer fichiers .env et dossiers data
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo   .env cree depuis .env.example
    )
)
if not exist "data\uploads" mkdir "data\uploads" >nul 2>nul
if not exist "data\outputs" mkdir "data\outputs" >nul 2>nul
if not exist "data\cache" mkdir "data\cache" >nul 2>nul

REM 4. Smoke test
python -c "import sys; sys.path.insert(0, '.'); from app import create_app; create_app()" 2>app_import_error.tmp
if errorlevel 1 (
    echo.
    echo [ERREUR] L'app Flask ne peut pas demarrer. Stacktrace :
    type app_import_error.tmp
    del app_import_error.tmp >nul 2>nul
    pause
    exit /b 1
)
del app_import_error.tmp >nul 2>nul

echo [3/3] Smoke test OK.
echo.
echo ============================================================
echo   Lancement de Flask...
echo   URL : http://localhost:5000
echo   Pour arreter : Ctrl+C dans cette fenetre
echo ============================================================
echo.

REM Ouvrir le navigateur apres 2 secondes
start "" /b cmd /c "timeout /t 2 /nobreak >nul 2>nul && start http://localhost:5000"

REM Lancer Flask
python app.py

echo.
echo ============================================================
echo   Flask s'est arrete.
echo ============================================================
pause
exit /b 0
