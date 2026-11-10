import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests run against a running TrustShield stack (docker compose up, or local dev servers).
 * Set E2E_BASE_URL to point elsewhere, e.g. E2E_BASE_URL=http://localhost:3100.
 */
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }], ["json", { outputFile: "../reports/e2e-results.json" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
