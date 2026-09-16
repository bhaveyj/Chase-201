import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "../..");
const frontendPort = Number(process.env.PLAYWRIGHT_PORT || 3000);
const frontendUrl = `http://localhost:${frontendPort}`;
const python =
  process.env.API_PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
export default defineConfig({
  testDir: "./e2e",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR || "test-results",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: frontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: [
    {
      command: `"${python}" tests/e2e_server.py`,
      cwd: path.join(root, "apps/api"),
      url: "http://localhost:8001/health",
      reuseExistingServer: false,
      timeout: 60_000,
      env: {
        FRONTEND_URL: frontendUrl,
        CORS_ORIGINS: JSON.stringify([frontendUrl]),
      },
    },
    {
      command: `npm run dev -- --port ${frontendPort}`,
      cwd: path.join(root, "apps/web"),
      url: frontendUrl,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_URL: "http://localhost:8001",
        NEXT_TELEMETRY_DISABLED: "1",
        NEXT_OUTPUT_DIR: process.env.PLAYWRIGHT_NEXT_OUTPUT_DIR || ".next-e2e",
      },
    },
  ],
});
