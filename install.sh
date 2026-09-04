#!/bin/bash
echo "================================================================"
echo "  College Attendance System - First Time Setup"
echo "================================================================"
echo

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Install it first (e.g. 'sudo apt install python3 python3-venv' on Linux,"
    echo "or from python.org on Mac)."
    exit 1
fi

echo "[1/4] Creating virtual environment..."
python3 -m venv venv

echo "[2/4] Activating virtual environment..."
source venv/bin/activate

echo "[3/4] Installing required packages (this may take a few minutes)..."
pip install -r requirements.txt

echo "[4/4] Setting up configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file with default settings (SQLite, works immediately)."
else
    echo ".env already exists, leaving it as-is."
fi

echo
echo "================================================================"
echo "  Setup complete!"
echo "  Run ./start.sh any time to start the system."
echo "================================================================"
