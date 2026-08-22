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

	await expect(page.getByRole('button', { name: /Print Lineup/i })).toBeVisible();

	const printTitle = page.getByText('ORDRE DES FRAPPEURS').first();
	await expect(printTitle).toBeAttached();
});

test('Empty pitching scorecard saves without fabricating an appearance', async ({ page }) => {
	const corsHeaders = {
		'Access-Control-Allow-Origin': 'http://localhost:5173',
		'Access-Control-Allow-Headers':
			'content-type, accept-language, authorization, x-active-team-id',
		'Access-Control-Allow-Methods': 'GET, PUT, OPTIONS'
	};

	await page
		.context()
		.addCookies([{ name: 'session', value: 'test-token', domain: 'localhost', path: '/' }]);

	await page.route('**/api/teams/', async (route) => {
		await route.fulfill({ json: [{ id: 1, name: 'Test Team', season: '2026' }] });
	});
	await page.route('**/api/games/1', async (route) => {
		const json = { id: 1, team_id: 1, date: '2026-05-28', mode: 'compete', game_type: 'season' };
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
		if (route.request().method() === 'OPTIONS') {
			await route.fulfill({ status: 204, headers: corsHeaders });
			return;
		}

		if (route.request().method() === 'PUT') {
			await route.fulfill({ json: { ok: true }, headers: corsHeaders });
			return;
		}

		await route.fulfill({ json: [], headers: corsHeaders });
	});

	const initialPitchingLoad = page.waitForResponse(
		(response) =>
			response.request().method() === 'GET' && response.url().endsWith('/api/games/1/pitching')
	);
	await page.goto('/games/1/pitching');
	await initialPitchingLoad;
	await expect(page.getByRole('heading', { name: /Pitching/i })).toBeVisible();
	await expect(page.locator('tbody tr')).toHaveCount(0);

	const saveRequest = page.waitForRequest(
		(request) => request.method() === 'PUT' && request.url().endsWith('/api/games/1/pitching')
	);
	await page.getByRole('button', { name: /Save All/i }).click();
	expect((await saveRequest).postDataJSON()).toEqual([]);
});
