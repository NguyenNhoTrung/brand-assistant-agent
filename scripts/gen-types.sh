#!/usr/bin/env bash
# Pydantic contracts → JSON Schema → apps/web/lib/types.gen.ts
set -euo pipefail
cd "$(dirname "$0")/.."
tmp=$(mktemp -t contracts.XXXX).json
uv run --package shared python -m shared.contracts.export "$tmp"
npx -y json-schema-to-typescript@15 -i "$tmp" -o apps/web/lib/types.gen.ts \
  --bannerComment "// SINH TỰ ĐỘNG bởi scripts/gen-types.sh từ packages/shared/contracts — KHÔNG sửa tay." \
  --unreachableDefinitions
rm -f "$tmp"
echo "→ apps/web/lib/types.gen.ts"
