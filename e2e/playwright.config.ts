import { defineConfig, devices } from "@playwright/test";

/**
 * AutoCommerce E2E — Playwright configuration
 * Run: npx playwright test
 * Run with UI: npx playwright test --ui
 */
const localBaseURL = "http://localhost:3000";
const resolvedBaseURL = process.env.E2E_BASE_URL || localBaseURL;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,         // séquentiel pour éviter les conflits de DB
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 8_000 },

  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["json", { outputFile: "playwright-report/results.json" }],
  ],

  use: {
    baseURL: resolvedBaseURL,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    trace: "retain-on-failure",
    headless: true,
    locale: "fr-FR",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Tests mobiles (WhatsApp est souvent mobile)
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 7"] },
      testMatch: "**/mobile-*.spec.ts",
    },
  ],

  /* Démarrer le serveur de dev automatiquement si pas déjà lancé */
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "sh -c 'PORT=3000 npm run dev -- --host 127.0.0.1'",
        url: localBaseURL,
        cwd: "../autocommerce-app",
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
