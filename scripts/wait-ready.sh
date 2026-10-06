#!/usr/bin/env bash
# Chờ gateway /readyz trả 200 (tối đa 120s).
set -euo pipefail
URL="${GATEWAY_URL:-http://localhost:8080}/readyz"
for _ in $(seq 1 60); do
  curl -fsS "$URL" >/dev/null 2>&1 && { echo "ready"; exit 0; }
  sleep 2
done
echo "gateway không sẵn sàng: $URL" >&2; exit 1
