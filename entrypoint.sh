#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

exec uvicorn all_in_all_llm.main:app --host "$HOST" --port "$PORT"
