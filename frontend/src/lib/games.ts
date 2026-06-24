export type HomeAway = 'H' | 'A' | null | undefined;

export type GameResult = 'win' | 'loss' | 'tie';

export type GameLike = {
	date: string;
	result_runs_for?: number | null;
	result_runs_against?: number | null;
};

/** Sports notation: home vs opponent, away @ opponent. */
export function matchupPrefix(homeAway: HomeAway, vsLabel = 'vs'): string {
	return homeAway === 'A' ? '@' : vsLabel;
}

export function formatOpponentMatchup(
	homeAway: HomeAway,
	opponent: string | null | undefined,
	options: { vsLabel?: string; tbd?: string } = {}
): string {
	const { vsLabel = 'vs', tbd = 'TBD' } = options;
	const name = opponent?.trim() || tbd;
	return `${matchupPrefix(homeAway, vsLabel)} ${name}`;
}

export function todayIso(): string {
	return new Date().toISOString().slice(0, 10);
}

export function isUpcomingGame(game: GameLike, today = todayIso()): boolean {
	return game.date >= today && game.result_runs_for == null;
}

export function isPastGame(game: GameLike, today = todayIso()): boolean {
	return game.date < today || game.result_runs_for != null;
}

export function splitGames<T extends GameLike>(games: T[], today = todayIso()) {
	const upcoming = games.filter((g) => isUpcomingGame(g, today)).sort((a, b) => a.date.localeCompare(b.date));
	const past = games.filter((g) => isPastGame(g, today)).sort((a, b) => b.date.localeCompare(a.date));
	return { upcoming, past };
}

export function gameResult(
	runsFor: number | null | undefined,
	runsAgainst: number | null | undefined
): GameResult | null {
	if (runsFor == null || runsAgainst == null) return null;
	if (runsFor > runsAgainst) return 'win';
	if (runsFor < runsAgainst) return 'loss';
	return 'tie';
}

/** DaisyUI badge class for home/away pills. */
export function homeAwayBadgeClass(homeAway: HomeAway): string {
	if (homeAway === 'H') return 'badge-info';
	if (homeAway === 'A') return 'badge-secondary';
	return 'badge-ghost';
}

/** DaisyUI badge class for win/loss/tie pills (matches opponent intel styling). */
export function resultBadgeClass(result: GameResult | string | null | undefined): string {
	if (result === 'win') return 'badge-success';
	if (result === 'loss') return 'badge-error';
	if (result === 'tie' || result === 'draw') return 'badge-info';
	return 'badge-ghost';
}

export function formatRecord(wins: number, losses: number, draws = 0): string {
	return `${wins}-${losses}-${draws}`;
}
