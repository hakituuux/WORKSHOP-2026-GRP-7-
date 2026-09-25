#!/bin/bash
# Garde le dashboard BiOrbite vivant (redémarre si crash)
cd "$(dirname "$0")"
source venv/bin/activate
export HTTP_HOST=0.0.0.0
export HTTP_PORT=5001
exec python app.py
