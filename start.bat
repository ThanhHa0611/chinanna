@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

echo ========================================
echo   Phong Van - Khoi dong he thong
echo ========================================
echo.

set "BACKEND=%~dp0backend"
set "FRONTEND=%~dp0frontend"
set "FRONTEND_ADMIN=%~dp0frontend-admin"
set "FRONTEND_SUPERADMIN=%~dp0frontend-superadmin"
set "PYTHON=%BACKEND%\venv\Scripts\python.exe"
set "PIP=%BACKEND%\venv\Scripts\pip.exe"

if not exist "%PYTHON%" (
    echo [Backend] Tao virtual environment...
    python -m venv "%BACKEND%\venv"
    if errorlevel 1 (
        echo [Loi] Khong tao duoc venv. Kiem tra Python da cai chua.
        pause
        exit /b 1
    )
)

echo [Backend] Cai dependencies...
"%PIP%" install -r "%BACKEND%\requirements.txt" -q
if errorlevel 1 (
    echo [Loi] Cai pip that bai.
    pause
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [Loi] Chua cai Node.js/npm. Tai tai: https://nodejs.org/
    pause
    exit /b 1
)

echo [Frontend] Cai dependencies (1 lenh cho ca 3 app)...
cd /d "%~dp0"
call npm install
if errorlevel 1 (
    echo [Loi] npm install that bai.
    pause
    exit /b 1
)

echo.
echo [Backend]  http://127.0.0.1:8000
echo [Mentee]   http://localhost:5173  ^(珍珠群 - do^)
echo [Mentor]   http://localhost:5174/login  ^(Mentor Du hoc Trung Quoc - hong pastel^)
echo [Super]    http://localhost:5175/login  ^(Super Admin^)
echo.
echo Dang dong server cu tren cong 8000, 5173, 5174, 5175...

for /f "tokens=5" %%p in ('netstat -ano ^| findstr "127.0.0.1:8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5174" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5175" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [Backend] Tao admin mac dinh (neu chua co)...
cd /d "%BACKEND%"
"%PYTHON%" seed_admin.py

if not exist "%BACKEND%\service-account.json" (
    echo.
    echo [Canh bao] Chua co service-account.json - form ke khai Google Docs chua chay duoc.
    echo            Chay: backend\setup_google.bat
)

echo.
echo Dang mo 4 cua so server...
echo  - Mentor Du hoc Trung Quoc PHAI mo cua so "Phong Van - Mentor"
echo  - Super Admin PHAI mo cua so "Phong Van - Super Admin"
echo  - Mentee PHAI mo cua so "Phong Van - Mentee"
echo.

start "Phong Van - Backend" cmd /k "cd /d "%BACKEND%" && "%PYTHON%" app.py"
timeout /t 2 /nobreak >nul
start "Phong Van - Mentor" cmd /k "cd /d "%FRONTEND_ADMIN%" && npm run dev"
timeout /t 2 /nobreak >nul
start "Phong Van - Super Admin" cmd /k "cd /d "%FRONTEND_SUPERADMIN%" && npm run dev"
timeout /t 2 /nobreak >nul
start "Phong Van - Mentee" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo Da khoi dong xong.
echo Mentee: http://localhost:5173
echo Mentor: http://localhost:5174/login
echo Super Admin: http://localhost:5175/login
echo.
echo Dang cho server san sang, roi mo 3 trang...
timeout /t 6 /nobreak >nul
start "" "http://localhost:5173"
start "" "http://localhost:5174/login"
start "" "http://localhost:5175/login"
pause


