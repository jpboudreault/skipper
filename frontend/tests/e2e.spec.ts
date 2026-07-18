import { test, expect } from '@playwright/test';

test('Login page shows Skipper branding', async ({ page }) => {
	await page.goto('/login');
	await expect(page.locator('h2')).toContainText('Skipper');
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

test('Lineup autosave serializes rapid full-replacement saves', async ({ page }) => {
	const putPayloads: unknown[][] = [];
	let releaseFirstPut: () => void = () => {};
	let firstPutStarted: () => void = () => {};
	let secondPutStarted: () => void = () => {};
	const firstPut = new Promise<void>((resolve) => {
		firstPutStarted = resolve;
	});
	const secondPut = new Promise<void>((resolve) => {
		secondPutStarted = resolve;
	});

	await page.route('**/api/games/1', async (route) => {
		const json = {
			id: 1,
			team_id: 1,
			date: '2026-05-28',
			mode: 'compete',
			game_type: 'season',
			innings_played: 1
		};
		await route.fulfill({ json });
	});
	await page.route('**/api/teams/', async (route) => {
		const json = [{ id: 1, name: 'Test Team', season: '2026', innings_per_game: 1 }];
		await route.fulfill({ json });
	});
	await page.route('**/api/players/', async (route) => {
		const json = [{ id: 1, first_name: 'Test', last_name: 'Player', jersey: 10, is_coach: false }];
		await route.fulfill({ json });
	});
	await page.route('**/api/games/1/lineup/snapshots', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/games/1/lineup', async (route) => {
		if (route.request().method() === 'PUT') {
			putPayloads.push(JSON.parse(route.request().postData() ?? '[]'));
			if (putPayloads.length === 1) {
				firstPutStarted();
				await new Promise<void>((resolve) => {
					releaseFirstPut = resolve;
				});
			} else {
				secondPutStarted();
			}
			await route.fulfill({ json: { ok: true } });
			return;
		}
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
	const positionSelect = page.locator('tbody select').first();
	await expect(positionSelect).toBeVisible();

	await positionSelect.selectOption('1');
	await firstPut;
	await positionSelect.selectOption('2');
	await page.waitForTimeout(100);
	expect(putPayloads).toHaveLength(1);

	releaseFirstPut();
	await secondPut;

	expect((putPayloads[0][0] as { position: number }).position).toBe(1);
	expect((putPayloads[1][0] as { position: number }).position).toBe(2);
});
