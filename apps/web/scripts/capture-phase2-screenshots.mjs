import { chromium } from '@playwright/test';
import fs from 'node:fs';

const baseURL = process.env.BASE_URL || 'http://localhost:3000';
const out = new URL('../public/screenshots/', import.meta.url);
const routes = [
  ['01-landing', '/', { width: 1440, height: 1100 }],
  ['02-live-call-console', '/dashboard/live', { width: 1440, height: 1100 }],
  ['03-supervisor-console', '/dashboard/supervisor', { width: 1440, height: 1100 }],
  ['04-quality-center', '/dashboard/quality', { width: 1440, height: 1100 }],
  ['05-queue-operations', '/dashboard/queues', { width: 1440, height: 1100 }],
  ['06-routing-rules', '/dashboard/routing', { width: 1440, height: 1100 }],
  ['07-agent-version-comparison', '/dashboard/agents/versions', { width: 1440, height: 1100 }],
  ['08-reporting-center', '/dashboard/reports', { width: 1440, height: 1100 }],
  ['09-provider-operations', '/dashboard/providers', { width: 1440, height: 1100 }],
  ['10-security-center', '/dashboard/security', { width: 1440, height: 1100 }],
  ['11-calls-inbox', '/dashboard/calls', { width: 1440, height: 1100 }],
  ['12-call-review-quality', '/dashboard/review', { width: 1440, height: 1100 }],
  ['13-leads-crm', '/dashboard/leads', { width: 1440, height: 1100 }],
  ['14-scheduling-operations', '/dashboard/calendar', { width: 1440, height: 1100 }],
  ['15-agent-builder', '/dashboard/agents', { width: 1440, height: 1100 }],
  ['16-analytics', '/dashboard/analytics', { width: 1440, height: 1100 }],
  ['17-compliance-center', '/dashboard/governance', { width: 1440, height: 1100 }],
  ['18-global-search', '/dashboard/search', { width: 1440, height: 1100 }],
  ['19-command-palette', '/dashboard', { width: 1440, height: 1100, palette: true }],
  ['20-mobile-supervisor', '/dashboard/supervisor', { width: 412, height: 915 }],
];
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined, args: ['--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server', '--proxy-bypass-list=<-loopback>'] });
for (const [name, route, view] of routes) {
  const page = await browser.newPage({ viewport: { width: view.width, height: view.height }, deviceScaleFactor: 1 });
  await page.goto(`${baseURL}${route}`, { waitUntil: 'networkidle', timeout: 120000 });
  if (view.palette) {
    await page.keyboard.press(process.platform === 'darwin' ? 'Meta+K' : 'Control+K');
    await page.waitForTimeout(250);
  }
  await page.screenshot({ path: new URL(`${name}.png`, out), fullPage: true });
  await page.close();
  console.log(`captured ${name}`);
}
await browser.close();
