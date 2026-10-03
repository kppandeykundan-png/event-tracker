#!/usr/bin/env bash
# Runs the whole pipeline on your own server (replaces GitHub Actions).
# Setup: copy env.example to .env and fill it in; make executable: chmod +x run_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source migration/.env; set +a
python3 scraper_v2.py
MINUTES="${MINUTES:-4}" python3 ais_collector.py
# publish static files to the web server folder
rsync -a index.html events.json data "${WEB_ROOT:?set WEB_ROOT in migration/.env}/"
