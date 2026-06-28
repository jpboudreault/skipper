import { writable, derived, get } from 'svelte/store';
import { apiFetch } from '$lib/api';
import type { Team } from '$lib/types';

/**
 * Central source of truth for the user's teams and the currently active team.
 *
 * Pages should call {@link loadTeams} once (usually in the root layout) and then
 * read the `teams` / `activeTeamId` / `activeTeam` stores, or await
 * {@link waitForActiveTeamId} when they need the id before their own fetch.
 */

export const teams = writable<Team[]>([]);
export const activeTeamId = writable<string | null>(null);
export const activeTeam = derived(
	[teams, activeTeamId],
	([$teams, $id]) => $teams.find((t) => t.id.toString() === $id) ?? null
);

let ready = false;
let waiters: Array<(teamId: string | null) => void> = [];

function readCachedTeamId(): string | null {
	return typeof sessionStorage !== 'undefined' ? sessionStorage.getItem('activeTeamId') : null;
}

function resolveWaiters(id: string | null): void {
	ready = true;
	for (const resolve of waiters) {
		resolve(id);
	}
	waiters = [];
}

/** Backwards-compatible signal that the active team has been resolved. */
export function notifyTeamsReady(teamId: string | null): void {
	activeTeamId.set(teamId);
	resolveWaiters(teamId);
}

/** Resolves with the active team id, waiting for {@link loadTeams} if needed. */
export function waitForActiveTeamId(): Promise<string | null> {
	if (ready) {
		return Promise.resolve(get(activeTeamId) ?? readCachedTeamId());
	}
	return new Promise((resolve) => {
		waiters.push(resolve);
	});
}

/** Set the active team, persisting it and unblocking any waiters. */
export function setActiveTeamId(id: string): void {
	activeTeamId.set(id);
	if (typeof sessionStorage !== 'undefined') {
		sessionStorage.setItem('activeTeamId', id);
		const team = get(teams).find((t) => t.id.toString() === id);
		if (team) {
			sessionStorage.setItem('teamName', team.name);
		}
	}
	resolveWaiters(id);
}

/**
 * Fetch the user's teams and resolve the active team (cached selection if still
 * valid, otherwise the first team). Updates the stores and sessionStorage.
 */
export async function loadTeams(): Promise<{ teams: Team[]; activeTeamId: string | null }> {
	let res: Response;
	try {
		res = await apiFetch('/teams/');
	} catch (e) {
		resolveWaiters(null);
		throw e;
	}

	if (!res.ok) {
		resolveWaiters(null);
		return { teams: [], activeTeamId: null };
	}

	const list: Team[] = await res.json();
	teams.set(list);

	if (list.length === 0) {
		activeTeamId.set(null);
		resolveWaiters(null);
		return { teams: list, activeTeamId: null };
	}

	const cachedId = readCachedTeamId();
	const exists = cachedId ? list.some((t) => t.id.toString() === cachedId) : false;
	const resolvedId = exists ? (cachedId as string) : list[0].id.toString();
	setActiveTeamId(resolvedId);
	return { teams: list, activeTeamId: resolvedId };
}
