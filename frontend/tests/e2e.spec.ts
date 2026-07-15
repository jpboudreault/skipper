import { test, expect } from '@playwright/test';

test('Login page shows Skipper branding', async ({ page }) => {
	await page.goto('/login');
	await expect(page.locator('h2')).toContainText('Skipper');
});

test('Lineup page has print button and printable card', async ({ page }) => {
	await page
		.context()
		.addCookies([{ name: 'session', value: 'test-token', domain: 'localhost', path: '/' }]);

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

test('Pitching page preserves partial innings when saving', async ({ page }) => {
	let savedPayload: unknown = null;

	await page
		.context()
		.addCookies([{ name: 'session', value: 'test-token', domain: 'localhost', path: '/' }]);

	await page.route('**/api/games/1', async (route) => {
		const json = { id: 1, team_id: 1, date: '2026-05-28', mode: 'compete', game_type: 'season' };
		await route.fulfill({ json });
	});
	await page.route('**/api/teams/', async (route) => {
		const json = [{ id: 1, name: 'Test Team', season: '2026' }];
		await route.fulfill({ json });
	});
	await page.route('**/api/players/', async (route) => {
		const json = [{ id: 1, first_name: 'Test', last_name: 'Pitcher', jersey: 10, is_coach: false }];
		await route.fulfill({ json });
	});
	await page.route('**/api/games/1/availability', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/games/1/pitching', async (route) => {
		if (route.request().method() === 'PUT') {
			savedPayload = route.request().postDataJSON();
			await route.fulfill({ json: { ok: true } });
			return;
		}
		await route.fulfill({ json: [] });
	});

	await page.goto('/games/1/pitching');

	const row = page.locator('tbody tr').first();
	await expect(row).toBeVisible();
	await row.locator('input').nth(0).fill('1.1');
	await row.locator('input').nth(1).fill('2.2');
	await page.getByRole('button', { name: /Save All/i }).click();

	expect(savedPayload).toEqual([
		expect.objectContaining({
			player_id: 1,
			inning_entered: 1.1,
			inning_exited: 2.2,
			ip_outs: 4
		})
	]);
});
