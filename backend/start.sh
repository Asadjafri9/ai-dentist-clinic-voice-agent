#!/bin/sh
# Single-container start: durable-job worker + API server.
# Jobs are leased/retried in MongoDB, so work survives restarts.
# At scale, run `python -m app.workers.runner` as its own service.
set -e

python -m app.workers.runner &
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
