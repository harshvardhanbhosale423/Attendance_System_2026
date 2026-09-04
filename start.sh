#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d venv ]; then
    echo "Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

source venv/bin/activate

echo "================================================================"
echo "  Starting College Attendance System..."
echo "  Once you see 'Running on http://...', open your browser to:"
echo "      http://localhost:5000"
echo "  Other PCs on the same WiFi/LAN can use your PC's IP address"
echo "  instead of 'localhost' (see README section 5)."
echo "  Press CTRL+C to stop the server."
echo "================================================================"
echo

( sleep 2 && (xdg-open http://localhost:5000 2>/dev/null || open http://localhost:5000 2>/dev/null) ) &
python3 app.py
