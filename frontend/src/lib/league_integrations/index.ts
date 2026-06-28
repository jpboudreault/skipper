import type { Component } from 'svelte';
import LfbqSpordleOpponentIntel from './lfbq_spordle/OpponentIntelPanel.svelte';

export type OpponentIntelProps = {
	gameId: number;
};

export const opponentIntelComponents: Record<string, Component<OpponentIntelProps>> = {
	lfbq_spordle: LfbqSpordleOpponentIntel
};

export function getOpponentIntelComponent(
	version?: string | null
): Component<OpponentIntelProps> | null {
	if (!version) return null;
	return opponentIntelComponents[version] ?? null;
}
