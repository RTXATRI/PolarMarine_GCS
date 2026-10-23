import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  workers: process.env.CI ? 2 : 4,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    launchOptions: {
      args: ['--disable-logging', '--log-file=NUL']
    },
    trace: 'retain-on-failure'
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]
})
