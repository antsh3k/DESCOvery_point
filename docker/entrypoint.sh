#!/usr/bin/env bash
# Wait for Postgres, apply migrations, seed funds, then serve the API.
set -euo pipefail

echo "Waiting for Postgres to accept connections…"
python - <<'PY'
import os, time
import psycopg

dsn = os.environ["DATABASE_URL"].replace("+psycopg", "")
for attempt in range(60):
    try:
        psycopg.connect(dsn).close()
        print("Postgres is ready.")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Postgres did not become ready in time")
PY

echo "Applying migrations…"
alembic upgrade head

echo "Seeding funds…"
seed || echo "seed step skipped/failed (continuing)"

echo "Starting API…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
