import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests_e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4176",
    headless: true,
  },
  webServer: {
    command:
      "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -ExecutionPolicy Bypass -File .\\scripts\\run_e2e_stack.ps1",
    reuseExistingServer: false,
    timeout: 120_000,
    url: "http://127.0.0.1:4176/login",
  },
});
