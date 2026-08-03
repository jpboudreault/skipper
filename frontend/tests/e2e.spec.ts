import { test, expect, type Page } from '@playwright/test';

async function signIn(page: Page) {
	await page
		.context()
		.addCookies([{ name: 'session', value: 'test-token', domain: 'localhost', path: '/' }]);
}

test('Login page shows Skipper branding', async ({ page }) => {
	await page.goto('/login');
	await expect(page.locator('h2')).toContainText('Skipper');
});

test('Lineup page has print button and printable card', async ({ page }) => {
	await signIn(page);

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

test('Batting OCR ingest warns before leaving unsaved parsed stats', async ({ page }) => {
	await signIn(page);

	await page.route('**/api/teams/', async (route) => {
		await route.fulfill({ json: [{ id: 1, name: 'Test Team', season: '2026' }] });
	});
	await page.route('**/api/config', async (route) => {
		await route.fulfill({ json: { photo_ingestion_enabled: true } });
	});
	await page.route('**/api/games/1', async (route) => {
		await route.fulfill({
			json: { id: 1, team_id: 1, date: '2026-05-28', mode: 'compete', game_type: 'season' }
		});
	});
	await page.route('**/api/players/', async (route) => {
		await route.fulfill({
			json: [{ id: 1, first_name: 'Test', last_name: 'Player', jersey: 10, is_coach: false }]
		});
	});
	await page.route('**/api/games/1/batting', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/games/1/availability', async (route) => {
		await route.fulfill({ json: [] });
	});
	await page.route('**/api/games/1/batting/ingest', async (route) => {
		await route.fulfill({
			json: {
				parsed: [{ player_id: 1, matched: true, singles: 2, doubles: 0 }],
				player_count: 1
			}
		});
	});

	await page.goto('/games/1/batting');
	await page.locator('#scoresheet-upload').setInputFiles({
		name: 'scoresheet.png',
		mimeType: 'image/png',
		buffer: Buffer.from([0x89, 0x50, 0x4e, 0x47])
	});

	await expect(page.getByText(/Scoresheet parsed|Feuille de match analysée/)).toBeVisible();

	let dialogMessage = '';
	page.once('dialog', async (dialog) => {
		dialogMessage = dialog.message();
		await dialog.dismiss();
	});
	await page.locator('a[href="/games/1/lineup"]').click();
	expect(dialogMessage).toMatch(/unsaved changes|modifications non enregistrées/i);
	expect(page.url()).toMatch(/\/games\/1\/batting$/);
});
