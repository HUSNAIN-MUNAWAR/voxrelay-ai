import { chromium } from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const routes = [
  ['01-landing-page.png', '/'],
  ['02-executive-dashboard.png', '/dashboard'],
  ['03-live-call-console.png', '/dashboard/live'],
  ['04-supervisor-console.png', '/dashboard/supervisor'],
  ['05-calls-inbox.png', '/dashboard/calls'],
  ['06-quality-review.png', '/dashboard/review'],
  ['07-leads-crm-pipeline.png', '/dashboard/leads'],
  ['08-scheduling-operations.png', '/dashboard/calendar'],
  ['09-agent-builder.png', '/dashboard/agents'],
  ['10-agent-version-diff.png', '/dashboard/agents/versions'],
  ['11-routing-policy-studio.png', '/dashboard/routing'],
  ['12-queue-operations.png', '/dashboard/queues'],
  ['13-provider-operations.png', '/dashboard/providers'],
  ['14-security-center.png', '/dashboard/security'],
  ['15-reporting-center.png', '/dashboard/reports'],
  ['16-global-search-command.png', '/dashboard/search'],
];

const base = process.env.VOXRELAY_WEB_URL || 'http://localhost:3000';
const outDir = fileURLToPath(new URL('../../../assets/screenshots/', import.meta.url));
await fs.mkdir(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
for (const [name, route] of routes) {
  await page.goto(`${base}${route}`, { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(outDir, name), fullPage: true });
}
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(`${base}/dashboard/supervisor`, { waitUntil: 'networkidle' });
await page.screenshot({ path: path.join(outDir, '17-mobile-supervisor.png'), fullPage: true });
await browser.close();
console.log(`Captured ${routes.length + 1} screenshots in assets/screenshots`);
