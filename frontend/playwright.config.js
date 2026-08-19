import { defineConfig, devices } from '@playwright/test'

/* E2E del funnel contra el bundle compilado. Usa el Chrome del sistema
   (channel: 'chrome') para no descargar navegadores propios.
   Requiere `npm run build` antes: lo encadena el script `test:e2e`. */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'line' : [['list']],
  use: {
    baseURL: `http://localhost:${process.env.E2E_PORT || 4173}`,
    trace: 'retain-on-failure',
    channel: 'chrome',
  },
  projects: [
    { name: 'escritorio', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
    { name: 'movil', use: { ...devices['Pixel 7'], channel: 'chrome' } },
  ],
  webServer: {
    command: 'node tests/e2e/server.mjs',
    url: `http://localhost:${process.env.E2E_PORT || 4173}/?stage=landing`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
})
