import type { Component } from 'svelte';
import BaseballQuebecLineup from './lineup/baseball_quebec.svelte';

export const DEFAULT_LINEUP_PRINT_VERSION = 'baseball_quebec';

export type LineupPrintProps = {
	game: any;
	team: any;
	players: any[];
	battingOrder: number[];
	lineup: any[];
	availability?: any[];
};

export const lineupPrintComponents: Record<string, Component<LineupPrintProps>> = {
	baseball_quebec: BaseballQuebecLineup
};

export function getLineupPrintComponent(version?: string | null): Component<LineupPrintProps> {
	const resolved = version || DEFAULT_LINEUP_PRINT_VERSION;
	return lineupPrintComponents[resolved] ?? lineupPrintComponents[DEFAULT_LINEUP_PRINT_VERSION];
}
