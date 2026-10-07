#!/usr/bin/env bash
# E2E (OpenAI thật): readyz → POST /v1/jobs (Basic) → đọc SSE tới message.completed.
set -euo pipefail
GW="${GATEWAY_URL:-http://localhost:8080}"
USER_EMAIL="marketer@lumi.test"
USER_PW="${DEMO_MEMBER_PASSWORD:-marketer-demo-2026}"
"$(dirname "$0")/wait-ready.sh"

job=$(curl -fsS -u "$USER_EMAIL:$USER_PW" -H "Idempotency-Key: smoke-$(date +%s%N)" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":null,"input":{"text":"Giá Vitamin C Serum?","mode":"qa"}}' "$GW/v1/jobs")
job_id=$(echo "$job" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')
echo "job: $job_id"

events=$(curl -fsSN --max-time 120 -u "$USER_EMAIL:$USER_PW" "$GW/v1/jobs/$job_id/events")
echo "$events" | grep -q "event: message.completed" || { echo "$events"; echo "FAIL: không có message.completed" >&2; exit 1; }
echo "$events" | grep "event: message.completed" -A1 | grep -q '"chunk_id"' || { echo "FAIL: câu trả lời không có citation" >&2; exit 1; }
curl -fsS -u "$USER_EMAIL:$USER_PW" "$GW/v1/conversations" | grep -q '"id"' || { echo "FAIL: /v1/conversations rỗng" >&2; exit 1; }
echo "smoke OK"
