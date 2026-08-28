import { test, expect } from '@playwright/test';

test('Login page shows Skipper branding', async ({ page }) => {
	await page.goto('/login');
	await expect(page.locator('h2')).toContainText('Skipper');
});

test('Microsoft callback does not load teams before session exists', async ({ page }) => {
	let teamsRequested = false;

	await page.route('**/api/config', async (route) => {
		await route.fulfill({
			json: { google_client_id: '', microsoft_client_id: '' }
		});
	});
	await page.route('**/api/teams/', async (route) => {
		teamsRequested = true;
		await route.fulfill({ status: 401, json: { detail: 'Unauthorized' } });
	});

	await page.goto('/auth/callback/microsoft');

	await expect(page.getByText('Microsoft login is not configured')).toBeVisible();
	expect(teamsRequested).toBe(false);
	await expect(page).toHaveURL(/\/auth\/callback\/microsoft/);
});

test('Lineup page has print button and printable card', async ({ page }) => {
	await page.route('**/api/games/1', async (route) => {
		const json = { id: 1, team_id: 1, date: '2026-05-28', mode: 'compete', game_type: 'season' };
		await route.fulfill({ json });
	});
	await page.route('**/api/teams/', async (route) => {
		const json = [{ id: 1, name: 'Test Team', season: '2026' }];
		await route.fulfill({ json });
	});
	await page.route('**/api/players/', async (route) => {
		const json = [{ id: 1, first_name: 'Test', last_name: 'Player', jersey: 10, is_coach: false }];
		await route.fulfill({ json });
	});
	await page.route('**/api/games/1/lineup', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/games/1/availability', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/games/1/batting', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/position-scores/', async (route) => {
		await route.fulfill({ json: [] });
	});

	await page.goto('/games/1/lineup');

	await expect(page.getByRole('button', { name: /Print/i })).toBeVisible();

	const printTitle = page.getByText('ORDRE DES FRAPPEURS');
	await expect(printTitle).toBeAttached();
});
