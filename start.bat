@echo off
echo.
echo  MA Provider Network Assistant
echo  ================================
echo.

REM ══════════════════════════════════════════════════════════════
REM  EDIT THESE LINES — your configuration
REM ══════════════════════════════════════════════════════════════

REM Your OpenAI API key
set OPENAI_API_KEY= 'API Key'

REM Path to your parquet data folder
REM This folder must contain:
REM   hwai_specialty_mapping.parquet
REM   npi_scores.parquet
REM   specialties\  (your specialty parquet files)
set DATA_DIR=C:\Users\Aviral.Gupta\Downloads\ma_router_app\data

REM ══════════════════════════════════════════════════════════════
REM  Settings — no need to change these
REM ══════════════════════════════════════════════════════════════
set LLM_PROVIDER=openai
set OPENAI_MODEL=gpt-4o
set HOST=0.0.0.0
set PORT=8000

REM ── Validate API key ──────────────────────────────────────────
if "%OPENAI_API_KEY%"=="PASTE_YOUR_KEY_HERE" (
    echo  ERROR: Open start.bat in Notepad and replace PASTE_YOUR_KEY_HERE
    echo         with your actual OpenAI API key, then save and run again.
    echo.
    pause
    exit /b 1
)

REM ── Validate data folder ──────────────────────────────────────
if not exist "%DATA_DIR%" (
    echo  WARNING: DATA_DIR does not exist: %DATA_DIR%
    echo  The router will still work for Guide / Strategy / Out-of-scope queries.
    echo  NPI Search queries will fail until data is in place.
    echo.
)

REM ── Check required folders exist ─────────────────────────────
if not exist "router_standalone\core\router" (
    echo  ERROR: router_standalone\core\router\ not found.
    echo  Copy your router_standalone folder into this directory.
    echo.
    pause
    exit /b 1
)

if not exist "npi_search_agent\core" (
    echo  ERROR: npi_search_agent\core\ not found.
    echo  Copy your npi_search_agent folder into this directory.
    echo.
    pause
    exit /b 1
)

echo  Provider : %LLM_PROVIDER%
echo  Model    : %OPENAI_MODEL%
echo  Data dir : %DATA_DIR%
echo  Port     : %PORT%
echo.
echo  ── Share with your team ──────────────────────────────────
echo  1. Open a NEW terminal and run:  ipconfig
echo  2. Find your IPv4 Address (e.g. 192.168.1.42)
echo  3. Share:  http://192.168.1.42:%PORT%
echo  ──────────────────────────────────────────────────────────
echo.
echo  Starting server... (keep this window open, Ctrl+C to stop)
echo.

python server.py
pause
