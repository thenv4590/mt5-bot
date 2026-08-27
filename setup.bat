@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===============================================
echo   MT5 TradingView Webhook Bot - Setup
echo ===============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo       Cai Python 3.10+ tu https://www.python.org/downloads/
    echo       Nho tick "Add Python to PATH" khi cai, roi chay lai file nay.
    pause
    exit /b 1
)

echo [1/5] Kiem tra Python...
python --version
echo.

echo [2/5] Tao virtual environment (venv)...
if not exist venv (
    python -m venv venv
    if errorlevel 1 (
        echo [LOI] Tao venv that bai.
        pause
        exit /b 1
    )
    echo     Da tao venv.
) else (
    echo     venv da ton tai, bo qua.
)
echo.

echo [3/5] Cai thu vien tu requirements.txt (co the mat vai phut)...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [LOI] Cai thu vien that bai. Kiem tra ket noi mang, hoac xem loi phia tren.
    pause
    exit /b 1
)
echo     Cai thu vien xong.
echo.

echo [4/5] Tao file cau hinh (neu chua co)...
if not exist config.json (
    copy config.example.json config.json >nul
    echo     Da tao config.json tu config.example.json.
    echo     -^> MO config.json va sua: price, magic, mt5.login, mt5.server, telegram... cho dung cua ban.
) else (
    echo     config.json da ton tai, khong ghi de.
)

if not exist .env (
    copy .env.example .env >nul
    echo     Da tao .env tu .env.example.
    echo     -^> MO .env va dien: MT5_PASSWORD_^<STRATEGY^>...
) else (
    echo     .env da ton tai, khong ghi de.
)
echo.

echo [5/5] Tao thu muc logs...
if not exist logs mkdir logs
echo.

echo ===============================================
echo   SETUP HOAN TAT!
echo.
echo   Buoc tiep theo:
echo    1. Mo config.json va .env, sua dung thong tin tai khoan MT5/Exness cua ban.
echo       (Xem chi tiet trong file HUONG_DAN_SU_DUNG.md)
echo    2. Chay file run.bat de khoi dong server.
echo ===============================================
pause
