@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "BACKEND_DIR=%SCRIPT_DIR%\backend"
set "FRONTEND_DIR=%SCRIPT_DIR%\frontend"

echo.
echo   +-----------------------------------+
echo   ^|     Learn Coding  -  Setup        ^|
echo   +-----------------------------------+
echo.

:: ---- Step 1: Python --------------------------------------------------
echo   [1/4] Python runtime
set "PYTHON="

for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYTHON (
    cmd /c "%%p --version >nul 2>&1"
    if not errorlevel 1 set "PYTHON=%%p"
)

if not defined PYTHON (
    for /f "delims=" %%d in ('conda info --base 2^>nul') do if not defined PYTHON (
        if exist "%%d\python.exe" (
            cmd /c ""%%d\python.exe" --version >nul 2>&1"
            if not errorlevel 1 set "PYTHON=%%d\python.exe"
        )
    )
)

if defined PYTHON (
    for /f "tokens=1,2 delims= " %%v in ('!PYTHON! --version 2^>^&1') do echo         %%v %%w
    echo         [OK]
) else (
    echo         [FAIL] Python ^>= 3.10 required
    echo         https://python.org
    pause
    exit /b 1
)

:: ---- Step 2: Node.js -------------------------------------------------
echo.
echo   [2/4] Node.js runtime
where node >nul 2>&1
if errorlevel 1 (
    echo         [FAIL] Node.js not found
    echo         https://nodejs.org
    pause
    exit /b 1
)
for /f "delims=" %%v in ('node --version 2^>^&1') do echo         %%v
echo         [OK]

:: ---- Step 3: Python package ------------------------------------------
echo.
echo   [3/4] Python package (pip install)
echo.
!PYTHON! -m pip install -e "%BACKEND_DIR%"
if errorlevel 1 (
    echo.
    echo         [FAIL] pip install failed
    pause
    exit /b 1
)
echo.
echo         [OK]

:: ---- Step 4: Frontend build + DB seed --------------------------------
echo.
echo   [4/4] Frontend build ^& database
echo.
cd /d "%FRONTEND_DIR%"

call npm install
if errorlevel 1 (
    echo         [FAIL] npm install failed
    pause
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo         [FAIL] npm build failed
    pause
    exit /b 1
)

cd /d "%SCRIPT_DIR%"
!PYTHON! "%BACKEND_DIR%\seed.py"
if errorlevel 1 (
    echo         [FAIL] database seed failed
    pause
    exit /b 1
)
echo.
echo         [OK]

:: ---- Done ------------------------------------------------------------
echo.
echo   +-----------------------------------+
echo   ^|  All done.                        ^|
echo   ^|                                   ^|
echo   ^|  Start  : learn-code              ^|
echo   ^|  URL    : http://localhost:8000   ^|
echo   +-----------------------------------+
echo.
pause
