import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';
process.env.PLAYWRIGHT_BROWSERS_PATH = path.resolve('pipeline/.cache/browsers');
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  use: { baseURL: 'http://127.0.0.1:3100', reducedMotion: 'reduce', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1100 } } },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
  webServer: { command: 'npm start -- --port 3100', url: 'http://127.0.0.1:3100', reuseExistingServer: false, timeout: 30000 },
});
