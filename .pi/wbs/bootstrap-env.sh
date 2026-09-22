#!/usr/bin/env bash
# Read-only env probe for Trinity Mock API WBS. Idempotent, <30s, always exits 0.
set +e
cd "$(cd "$(dirname "$0")/../.." && pwd)" 2>/dev/null || exit 0
UV=$(command -v uv >/dev/null 2>&1 && uv --version 2>/dev/null | awk '{print $2}')
[ -z "$UV" ] && UV="absent"
PY=.venv/bin/python
[ -x "$PY" ] || PY=$(command -v python3 2>/dev/null)
FA=""
if [ -n "$PY" ]; then FA=$("$PY" -c 'import fastapi,uvicorn;print(fastapi.__version__)' 2>/dev/null); fi
[ -z "$FA" ] && FA="absent"
UP=0
CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:1337/api/v1/config/status" 2>/dev/null)
[ "$CODE" = "200" ] && UP=1
AG=""
if [ "$UP" = "1" ]; then
  AG=$(curl -s --max-time 2 "http://127.0.0.1:1337/api/v1/agents" 2>/dev/null | "$PY" -c 'import sys,json;print(len(json.load(sys.stdin)))' 2>/dev/null)
fi
[ -z "$AG" ] && AG=0
echo "uv: ${UV}"
echo "fastapi: ${FA}"
echo "server_1337: up=${UP}"
echo "agents_seeded: ${AG}"
echo "STATE: uv=${UV} fastapi=${FA} server=${UP} agents=${AG}"
exit 0
