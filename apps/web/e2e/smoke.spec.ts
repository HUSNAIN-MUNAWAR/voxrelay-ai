import { test, expect } from '@playwright/test';
test('landing page exposes demo workspace', async ({ page }) => {
  await page.goto('http://127.0.0.1:3000');
  await expect(page.getByText('Every inbound call,')).toBeVisible();
  await expect(page.getByRole('link', { name: /Enter demo workspace/i })).toBeVisible();
});
