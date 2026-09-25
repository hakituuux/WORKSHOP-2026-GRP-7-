#!/bin/bash
cd "$(dirname "$0")"
pkill -f "$(pwd)/app.py" 2>/dev/null || true
sleep 1
source venv/bin/activate
export HTTP_HOST=0.0.0.0
export HTTP_PORT=5001
nohup python app.py >> /tmp/biorbite-flask.log 2>&1 &
echo $! > /tmp/biorbite-flask.pid
sleep 2
if curl -sf -o /dev/null http://127.0.0.1:5001/; then
  echo "OK http://127.0.0.1:5001 (pid $(cat /tmp/biorbite-flask.pid))"
else
  echo "ECHEC — voir /tmp/biorbite-flask.log"
  tail -20 /tmp/biorbite-flask.log
  exit 1
fi
