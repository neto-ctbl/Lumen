import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests_e2e",
  use: {
    baseURL: "http://127.0.0.1:5175",
    headless: true,
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1",
    reuseExistingServer: true,
    url: "http://127.0.0.1:5175",
  },
});
