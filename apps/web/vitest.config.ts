import { defineConfig } from "vitest/config";

// Unit test thuần (không mạng). E2E Playwright nằm ở e2e/ — chạy riêng bằng `pnpm e2e`.
export default defineConfig({ test: { include: ["lib/**/*.test.ts"] } });
