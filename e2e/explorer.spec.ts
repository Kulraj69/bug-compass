import { expect, test } from '@playwright/test';

test('overview, histogram navigation, and downloads', async ({ page, request }, testInfo) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'A map before the journey.' })).toBeVisible();
  await expect(page.locator('.histogram-card')).toHaveCount(12);
  await expect(page.locator('.overall-row')).toContainText('56.3%');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({ path: `pipeline/.cache/overview-${testInfo.project.name}.png`, fullPage: true });
  await page.getByRole('link', { name: 'Browse astropy/astropy: 6 tasks' }).click();
  await expect(page.getByRole('combobox', { name: 'REPOSITORY', exact: true })).toHaveValue('astropy/astropy');
  await expect(page.getByRole('status')).toHaveText('6 / 300 TASKS FOUND');
  const json = await request.get('/atlas.json');
  expect(json.ok()).toBeTruthy();
  expect((await json.json()).instances).toHaveLength(300);
  const csv = await request.get('/atlas.csv');
  expect(csv.ok()).toBeTruthy();
  expect(await csv.text()).toContain('bfs_recall@10');
  expect(errors).toEqual([]);
});

test('search, radius filters, receipt route, keyboard close, and empty state', async ({ page }, testInfo) => {
  await page.goto('/tasks');
  await page.getByLabel('SEARCH THE ARCHIVE').fill('django__django-15851');
  await expect(page.getByRole('status')).toHaveText('1 / 300 TASKS FOUND');
  const opener = page.getByRole('button', { name: 'Open django__django-15851, 4 hops' });
  await opener.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.terminal-node')).toHaveCount(5);
  expect((await dialog.locator('blockquote').innerText()).length).toBeLessThanOrEqual(300);
  await page.screenshot({ path: `pipeline/.cache/receipt-${testInfo.project.name}.png`, fullPage: false });
  expect(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth)).toBeTruthy();
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(opener).toBeFocused();
  await page.getByRole('button', { name: 'Reset filters' }).click();
  await page.getByLabel('LOCALIZATION RADIUS').selectOption('no_mentions');
  await expect(page.getByRole('status')).toHaveText('55 / 300 TASKS FOUND');
  await page.getByLabel('SEARCH THE ARCHIVE').fill('no-such-record-xyz');
  await expect(page.getByRole('heading', { name: 'No tasks match these filters.' })).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters and start again' }).click();
  await expect(page.getByRole('status')).toHaveText('300 / 300 TASKS FOUND');
  await page.getByRole('button', { name: 'Next →' }).click();
  await expect(page.getByText('Page 2 of 20')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('method and reduced motion remain readable', async ({ page }) => {
  await page.goto('/method');
  await expect(page.getByRole('heading', { name: 'A compass, with its workings exposed.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Static maps have blind spots.' })).toBeVisible();
  expect(await page.locator('.terminal-cursor').evaluate(node => getComputedStyle(node).animationName)).toBe('none');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
