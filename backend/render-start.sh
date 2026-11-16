#!/bin/sh
set -eu
exec python -m uvicorn app.hosted:app --host 0.0.0.0 --port "${PORT:?Render must provide PORT}" --workers 1
