import { defineConfig } from "@playwright/test";

// E2E cần stack đang chạy (gateway + worker + web) và OpenAI thật — không chạy trong `pnpm test`.
export default defineConfig({
  testDir: "e2e",
  timeout: 180_000,
  expect: { timeout: 120_000 },
  use: {
    baseURL: process.env.WEB_URL ?? "http://localhost:3000",
    channel: process.env.PW_CHANNEL ?? "chrome", // dùng Chrome đã cài trên máy, không cần tải Chromium
    headless: true,
    trace: "retain-on-failure",
  },
});
