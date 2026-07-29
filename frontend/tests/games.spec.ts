import { expect, test } from '@playwright/test';

test.use({ timezoneId: 'America/Toronto' });

test('uses local calendar date for game defaults and upcoming split', async ({ context, page }) => {
	await context.addCookies([
		{
			name: 'session',
			value: 'test-token',
			domain: 'localhost',
			path: '/'
		}
	]);

	await page.addInitScript(() => {
		const fixedNow = new Date('2026-06-29T01:30:00.000Z').valueOf();
		const RealDate = Date;
		class MockDate extends RealDate {
			constructor(...args: any[]) {
				if (args.length === 0) {
					super(fixedNow);
				} else {
					super(...(args as []));
				}
			}

			static now() {
				return fixedNow;
			}
		}
		Object.setPrototypeOf(MockDate, RealDate);
		globalThis.Date = MockDate as DateConstructor;
	});

	await page.route('**/api/teams/', async (route) => {
		await route.fulfill({ json: [{ id: 1, name: 'Test Team', season: '2026' }] });
	});
	await page.route('**/api/games/', async (route) => {
		await route.fulfill({
			json: [
				{
					id: 1,
					team_id: 1,
					date: '2026-06-28',
					opponent: 'Tonight Rivals',
					home_away: 'H',
					mode: 'compete',
					game_type: 'season',
					result_runs_for: null,
					result_runs_against: null
				}
			]
		});
	});
	await page.route('**/api/games/upcoming-intel', async (route) => {
		await route.fulfill({ json: [] });
	});

	await page.goto('/games');

	await expect(page.getByRole('link', { name: /Tonight Rivals/ })).toBeVisible();

	await page.getByRole('button', { name: 'New Game' }).click();
	await expect(page.locator('#date')).toHaveValue('2026-06-28');

	await page.getByRole('button', { name: /Past/ }).click();
	await expect(page.getByRole('link', { name: /Tonight Rivals/ })).toHaveCount(0);
});
