let ready = false;
let activeTeamId: string | null = null;
let waiters: Array<(teamId: string | null) => void> = [];

export function notifyTeamsReady(teamId: string | null): void {
	ready = true;
	activeTeamId = teamId;
	for (const resolve of waiters) {
		resolve(teamId);
	}
	waiters = [];
}

export function waitForActiveTeamId(): Promise<string | null> {
	if (ready) {
		return Promise.resolve(activeTeamId ?? sessionStorage.getItem('activeTeamId'));
	}
	return new Promise((resolve) => {
		waiters.push(resolve);
	});
}
