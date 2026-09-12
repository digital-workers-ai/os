import { defineConfig, devices } from '@playwright/test'

const ignored = ['node_modules/**', 'results/**', 'report/**']

export default defineConfig({
  testDir: '.',
  outputDir: 'results',
  testIgnore: ignored,
  snapshotPathTemplate: '{testDir}/__screenshots__/{testFilePath}/{arg}{ext}',
  fullyParallel: true,
  timeout: 60_000,
  workers: 2,
  retries: 0,
  reporter: [['list'], ['html', { outputFolder: 'report', open: 'never' }]],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.BASE_URL ?? 'http://localhost:3092',
    viewport: { width: 1280, height: 800 },
    contextOptions: { reducedMotion: 'reduce' },
    colorScheme: 'light',
    locale: 'en-US',
    timezoneId: 'UTC',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  expect: {
    toHaveScreenshot: { animations: 'disabled', caret: 'hide', maxDiffPixels: 0 },
  },
  projects: [
    { name: 'chromium', testIgnore: [...ignored, 'dashboard/**'] },
    { name: 'dashboard', testMatch: 'dashboard/**', use: { baseURL: process.env.DASHBOARD_URL ?? 'http://localhost:3093' } },
  ],
})
