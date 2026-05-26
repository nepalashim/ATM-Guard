@echo off
REM PostgreSQL Setup Script for Windows
REM Requires: PostgreSQL installed and psql in PATH
REM Usage: setup_postgres.bat

echo.
echo ============================================
echo  ATM SENTINEL - PostgreSQL Setup
echo ============================================
echo.

REM Check if PostgreSQL is installed
where psql >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PostgreSQL not found. Please install PostgreSQL and add to PATH.
    echo Download: https://www.postgresql.org/download/windows/
    pause
    exit /b 1
)

echo [+] PostgreSQL found. Proceeding with setup...
echo.

REM Get database parameters from environment or user input
if "%DB_PASSWORD%"=="" (
    echo Enter PostgreSQL password for user 'postgres':
    set /p DB_PASSWORD=Password: 
)

if "%DB_USER%"=="" set DB_USER=postgres
if "%DB_HOST%"=="" set DB_HOST=localhost
if "%DB_PORT%"=="" set DB_PORT=5432
if "%DB_NAME%"=="" set DB_NAME=atm_sentinel

echo.
echo [*] Creating database '%DB_NAME%' on %DB_HOST%:%DB_PORT%...
echo.

REM Create database
psql -U %DB_USER% -h %DB_HOST% -p %DB_PORT% -tc "SELECT 1 FROM pg_database WHERE datname = '%DB_NAME%'" | findstr 1 >nul
if %ERRORLEVEL% NEQ 0 (
    echo [+] Creating database...
    psql -U %DB_USER% -h %DB_HOST% -p %DB_PORT% -c "CREATE DATABASE %DB_NAME%;" 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo [+] Database created successfully.
    ) else (
        echo [ERROR] Failed to create database. Check PostgreSQL is running.
        pause
        exit /b 1
    )
) else (
    echo [+] Database already exists.
)

echo.
echo [*] Creating tables via SQLAlchemy ORM...
echo [*] Tables will be auto-created when you start the backend.
echo.

echo ============================================
echo  Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Create .env file in backend/ directory
echo   2. Copy from backend/.env.example
echo   3. Update DB_PASSWORD and other settings
echo   4. Run backend with: uvicorn backend.main:app --reload --port 8000
echo.
pause
