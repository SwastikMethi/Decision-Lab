import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./frontend/e2e",
  timeout: 60000,
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5183",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: ".venv/bin/decisionlab serve --port 8778",
      env: { DECISIONLAB_DATA_ROOT: "./test-results/data" },
      url: "http://127.0.0.1:8778/api/v1/health",
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: "npm run dev -- --port 5183 --strictPort",
      env: { DECISIONLAB_API_TARGET: "http://127.0.0.1:8778" },
      url: "http://127.0.0.1:5183",
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
