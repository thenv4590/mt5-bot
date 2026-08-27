@echo off
cd /d "%~dp0"

if not exist venv (
    echo [LOI] Chua thay venv. Hay chay setup.bat truoc.
    pause
    exit /b 1
)

if not exist config.json (
    echo [LOI] Chua co config.json. Hay chay setup.bat truoc, hoac copy config.example.json thanh config.json roi sua lai.
    pause
    exit /b 1
)

if not exist .env (
    echo [CANH BAO] Chua co file .env - mat khau MT5 / webhook secret se bi thieu.
    echo            Chay setup.bat, hoac copy .env.example thanh .env roi dien thong tin.
    echo.
)

call venv\Scripts\activate.bat

set HOST=0.0.0.0
set PORT=8000

echo ===============================================
echo   Dang khoi dong MT5 TradingView Webhook Bot
echo   URL noi bo:  http://localhost:%PORT%
echo   Webhook URL: http://localhost:%PORT%/api/order
echo   Nhan CTRL+C de dung server.
echo ===============================================
echo.

uvicorn app.main:app --host %HOST% --port %PORT%

echo.
echo Server da dung.
pause
