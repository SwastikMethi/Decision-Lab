import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./frontend/e2e",
  timeout: 60000,
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: ".venv/bin/decisionlab serve --port 8768",
      env: { DECISIONLAB_DATA_ROOT: "./test-results/data" },
      url: "http://127.0.0.1:8768/api/v1/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60000,
    },
  ],
});
