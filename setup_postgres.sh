#!/bin/bash
# PostgreSQL Setup Script for Linux/macOS
# Requires: PostgreSQL installed and psql in PATH
# Usage: bash setup_postgres.sh

set -e

echo ""
echo "============================================"
echo "  ATM SENTINEL - PostgreSQL Setup"
echo "============================================"
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "[ERROR] PostgreSQL not found. Please install PostgreSQL."
    echo "  Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
    echo "  macOS: brew install postgresql"
    exit 1
fi

echo "[+] PostgreSQL found. Proceeding with setup..."
echo ""

# Get database parameters from environment or use defaults
DB_USER=${DB_USER:-postgres}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-atm_sentinel}

# Ask for password if not set
if [ -z "$DB_PASSWORD" ]; then
    read -sp "Enter PostgreSQL password for user '$DB_USER': " DB_PASSWORD
    echo ""
fi

echo ""
echo "[*] Creating database '$DB_NAME' on $DB_HOST:$DB_PORT..."
echo ""

# Create database if it doesn't exist
PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"
if [ $? -ne 0 ]; then
    echo "[+] Creating database..."
    PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -c "CREATE DATABASE $DB_NAME;"
    if [ $? -eq 0 ]; then
        echo "[+] Database created successfully."
    else
        echo "[ERROR] Failed to create database. Check PostgreSQL is running."
        exit 1
    fi
else
    echo "[+] Database already exists."
fi

echo ""
echo "[*] Creating tables via SQLAlchemy ORM..."
echo "[*] Tables will be auto-created when you start the backend."
echo ""

echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Create .env file in backend/ directory"
echo "  2. Copy from backend/.env.example"
echo "  3. Update DB_PASSWORD and other settings"
echo "  4. Run backend with: uvicorn backend.main:app --reload --port 8000"
echo ""
