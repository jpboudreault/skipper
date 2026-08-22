import { test, expect } from '@playwright/test';

test('French nav labels when locale is fr', async ({ page }) => {
	await page
		.context()
		.addCookies([{ name: 'session', value: 'test-token', domain: 'localhost', path: '/' }]);
	await page.addInitScript(() => {
		localStorage.setItem('skipper-locale', 'fr');
	});
	await page.route('**/api/teams/', async (route) => {
		await route.fulfill({ json: [{ id: 1, name: 'Test Team', season: '2026' }] });
	});
	await page.goto('/');
	await expect(page.getByRole('link', { name: 'Tableau de bord' })).toBeVisible();
	await expect(page.getByRole('link', { name: 'Matchs' })).toBeVisible();
});

test('English fallback for missing French key', async ({ page }) => {
	await page.addInitScript(() => {
		localStorage.setItem('skipper-locale', 'fr');
	});
	await page.goto('/login');
	await expect(page.locator('h2')).toContainText('Skipper');
});
