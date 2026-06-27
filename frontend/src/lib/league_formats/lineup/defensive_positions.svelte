<script lang="ts">
	import { t } from '$lib/i18n';

	let { game, team, players, battingOrder, lineup, availability = [], numInnings } = $props();

	const POSITIONS: Record<number, string> = {
		0: 'X', 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9'
	};

	let dateStr = $derived(
		game?.date
			? new Date(game.date).toLocaleDateString('en-GB', {
					day: '2-digit',
					month: '2-digit',
					year: 'numeric',
					timeZone: 'UTC'
				})
			: ''
	);

	function getPlayer(id: number) {
		return players.find((p: any) => p.id === id);
	}

	function getCellPosition(playerId: number, inning: number): number | null {
		const cell = lineup.find((l: any) => l.player_id === playerId && l.inning === inning);
		return cell ? cell.position : null;
	}

	function formatPosition(pos: number | null): string {
		if (pos === null || pos === undefined) return '—';
		return POSITIONS[pos] ?? '—';
	}

	function isInjured(playerId: number, inning: number): boolean {
		const avail = availability.find((a: any) => a.player_id === playerId);
		return avail && avail.injury_inning !== null && inning >= avail.injury_inning;
	}
</script>

<div class="font-sans text-black bg-white p-2">
	<h1 class="text-center font-bold text-lg mb-2 uppercase tracking-wide">{$t('lineup_defense_title')}</h1>

	<div class="text-xs mb-2 grid grid-cols-2 gap-x-4 gap-y-0.5">
		<div><span class="font-semibold">{$t('lineup_defense_team')}:</span> {team?.name || ''}</div>
		<div><span class="font-semibold">{$t('lineup_defense_opponent')}:</span> {game?.opponent || ''}</div>
		<div><span class="font-semibold">{$t('lineup_defense_date')}:</span> {dateStr}</div>
		<div><span class="font-semibold">{$t('lineup_defense_game_number')}:</span> {game?.game_number || ''}</div>
	</div>

	<table class="w-full border-collapse border border-black text-xs">
		<thead>
			<tr class="bg-gray-100">
				<th class="border border-black p-1 text-left font-bold w-48">{$t('lineup_order_player')}</th>
				{#each Array(numInnings) as _, inn}
					<th class="border border-black p-1 text-center font-bold w-10">{$t('lineup_inning', { number: inn + 1 })}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each battingOrder as playerId}
				{@const player = getPlayer(playerId)}
				{#if player}
					<tr>
						<td class="border border-black p-1 font-medium">
							<span class="text-gray-600 mr-1">#{player.jersey}</span>
							{player.first_name} {player.last_name}
							{#if player.is_substitute}
								<span class="text-[9px] uppercase ml-1">({$t('lineup_sub')})</span>
							{/if}
						</td>
						{#each Array(numInnings) as _, inn}
							{@const pos = getCellPosition(player.id, inn + 1)}
							<td class="border border-black p-1 text-center font-bold {isInjured(player.id, inn + 1) ? 'text-red-700' : ''}">
								{isInjured(player.id, inn + 1) ? '🏥' : formatPosition(pos)}
							</td>
						{/each}
					</tr>
				{/if}
			{/each}
		</tbody>
	</table>
</div>

<style>
	@media print {
		@page {
			margin: 0.5cm;
			size: portrait;
		}
	}
</style>
