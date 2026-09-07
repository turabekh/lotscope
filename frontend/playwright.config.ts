import { defineConfig, devices } from '@playwright/test'

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  timeout: 45_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
      testIgnore: /mobile\.spec\.ts$/,
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 5'] },
      testMatch: /mobile\.spec\.ts$/,
    },
  ],
  // A built bundle, not `pnpm dev`. The dev server transforms roughly 270 modules on
  // every page load and does it in one Node process, so the workers queue behind each
  // other rather than behind anything in the product: one browser reached the lot page
  // in 2.4s, four in 9.1s, eight in 17.1s, against a 10s expect timeout. `vite build`
  // costs about four seconds once and serves static files after that.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'pnpm exec vite build && pnpm exec vite preview --port 5173 --strictPort',
        url: BASE_URL,
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
      },
})
