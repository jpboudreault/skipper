<script lang="ts">
	let { game, team, players, battingOrder, lineup, availability = [] } = $props();

	// Derived states
	let dateStr = $derived(game?.date ? new Date(game.date).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '');
	let isHome = $derived(game?.home_away === 'H');
	let isAway = $derived(game?.home_away === 'A');

	const POSITIONS: Record<number, string> = {
		0: 'X', 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9'
	};

	function getStartingPos(playerId: number) {
		const cell = lineup.find((l: any) => l.player_id === playerId && l.inning === 1);
		return cell ? (POSITIONS[cell.position] || '') : '';
	}

	let startingPlayers = $derived(battingOrder.map((id: number) => players.find((p: any) => p.id === id)).filter(Boolean));
	let orderRows = $derived(Array.from({ length: 15 }, (_, i) => startingPlayers[i] || null));

	let startingIds = $derived(new Set(battingOrder));
	let absentIds = $derived(new Set(availability.filter((a: any) => a.status === 'absent' || a.status === 'injured').map((a: any) => a.player_id)));
	let subs = $derived(players.filter((p: any) => p.active && !p.is_coach && !startingIds.has(p.id) && !absentIds.has(p.id)));
	let subRows = $derived(Array.from({ length: 9 }, (_, i) => subs[i] || null));
	const subLetters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'];

	let coaches = $derived(players.filter((p: any) => p.is_coach).sort((a: any, b: any) => {
		if (a.coach_type === 'head') return -1;
		if (b.coach_type === 'head') return 1;
		return 0;
	}));
	let coachRows = $derived(Array.from({ length: 4 }, (_, i) => coaches[i] || null));
</script>

<!-- Only visible during printing -->
<div class="hidden print:block printable-lineup font-sans text-black bg-white">
	<!-- Outline container simulating the paper size - scaled down to fit 3/4 page -->
	<div class="border-2 border-blue-600 w-1/2 p-1 bg-blue-50/30 text-[11px] leading-tight">
		<h1 class="text-center font-bold text-blue-700 text-lg py-1 tracking-wide uppercase">Ordre des Frappeurs</h1>

		<!-- HEADER TABLE -->
		<table class="w-full border-collapse border border-blue-600 mb-1.5">
			<tbody>
				<tr class="border-b border-blue-600">
					<td class="border-r border-blue-600 p-0.5 w-1/4">
						<div class="text-[9px] text-blue-600 font-semibold">N° PARTIE</div>
						<div class="font-bold h-3">{game?.game_number || ''}</div>
					</td>
					<td class="border-r border-blue-600 p-0.5 w-1/4">
						<div class="text-[9px] text-blue-600 font-semibold">DATE : JJ/MM/AAAA</div>
						<div class="font-bold h-3">{dateStr}</div>
					</td>
					<td class="border-r border-blue-600 p-0.5 text-center w-1/4">
						<div class="text-blue-600 text-[9px] font-semibold inline-block mr-2">RECEVEUR</div>
						<div class="inline-block w-3 h-3 border border-blue-600 align-middle font-bold text-center leading-[10px] text-[10px]">{isHome ? 'X' : ''}</div>
					</td>
					<td class="p-0.5 text-center w-1/4">
						<div class="text-blue-600 text-[9px] font-semibold inline-block mr-2">VISITEUR</div>
						<div class="inline-block w-3 h-3 border border-blue-600 align-middle font-bold text-center leading-[10px] text-[10px]">{isAway ? 'X' : ''}</div>
					</td>
				</tr>
				<tr class="border-b border-blue-600">
					<td colspan="2" class="border-r border-blue-600 p-0.5">
						<span class="text-[9px] text-blue-600 font-semibold mr-2">DIVISION</span>
						<span class="font-bold">{team?.division || ''}</span>
					</td>
					<td colspan="2" class="p-0.5">
						<span class="text-[9px] text-blue-600 font-semibold mr-2">CLASSE</span>
						<span class="font-bold">{team?.classe || ''}</span>
					</td>
				</tr>
				<tr class="border-b border-blue-600">
					<td colspan="4" class="p-0.5 flex">
						<span class="text-[9px] text-blue-600 font-semibold w-20">ÉQUIPE</span>
						<span class="font-bold whitespace-nowrap">{team?.name || ''}</span>
					</td>
				</tr>
				<tr class="border-b border-blue-600">
					<td colspan="4" class="p-0.5 flex">
						<span class="text-[9px] text-blue-600 font-semibold w-20">OPPOSANT</span>
						<span class="font-bold whitespace-nowrap">{game?.opponent || ''}</span>
					</td>
				</tr>
				<tr>
					<td colspan="4" class="p-0.5 flex">
						<span class="text-[9px] text-blue-600 font-semibold w-20">LIGUE</span>
						<span class="font-bold whitespace-nowrap">{game?.league || team?.default_league || ''}</span>
					</td>
				</tr>
			</tbody>
		</table>

		<!-- BATTING ORDER TABLE -->
		<table class="w-full border-collapse border border-blue-600 mb-1.5">
			<thead>
				<tr class="bg-blue-500 text-white border-b border-blue-600">
					<th class="p-0.5 border-r border-blue-600 font-semibold w-6 text-center">#</th>
					<th class="p-0.5 border-r border-blue-600 font-semibold w-8 text-center">No</th>
					<th class="p-0.5 border-r border-blue-600 font-semibold text-left">Nom</th>
					<th class="p-0.5 border-r border-blue-600 font-semibold text-left">Prénom</th>
					<th class="p-0.5 border-r border-blue-600 font-semibold w-12 text-center">POS</th>
					<th class="p-0.5 font-semibold w-12 text-center">Subs</th>
				</tr>
			</thead>
			<tbody>
				{#each orderRows as player, i}
					<tr class="border-b border-blue-300 last:border-blue-600 {i % 2 === 0 ? 'bg-blue-50/20' : 'bg-white'} h-[18px]">
						<td class="p-0 border-r border-blue-600 text-center text-blue-600 text-[10px] w-6 bg-blue-100/50">{i + 1}</td>
						<td class="p-0 border-r border-blue-600 text-center font-bold">{player?.jersey || ''}</td>
						<td class="p-0 px-1 border-r border-blue-600 font-medium">{player?.last_name || ''}</td>
						<td class="p-0 px-1 border-r border-blue-600 font-medium">{player?.first_name || ''}</td>
						<td class="p-0 border-r border-blue-600 text-center font-bold">{player ? getStartingPos(player.id) : ''}</td>
						<td class="p-0 text-center text-[10px] font-bold">{player?.is_substitute ? '✓' : ''}</td>
					</tr>
				{/each}
			</tbody>
		</table>

		<!-- SUBSTITUTES AND COACHES ROW -->
		<div class="grid grid-cols-2 gap-2">
			<!-- SUBS TABLE -->
			<table class="w-full border-collapse border border-blue-600">
				<thead>
					<tr class="bg-blue-500 text-white border-b border-blue-600">
						<th class="p-0.5 border-r border-blue-600 w-6"></th>
						<th class="p-0.5 border-r border-blue-600 w-8 text-center">No</th>
						<th class="p-0.5 text-left">SUBSTITUT</th>
					</tr>
				</thead>
				<tbody>
					{#each subRows as sub, i}
						<tr class="border-b border-blue-300 last:border-b-0 {i % 2 === 0 ? 'bg-blue-50/20' : 'bg-white'} h-[16px]">
							<td class="p-0 border-r border-blue-600 text-center text-blue-600 text-[9px] bg-blue-100/50">{subLetters[i]}</td>
							<td class="p-0 border-r border-blue-600 text-center font-bold">{sub?.jersey || ''}</td>
							<td class="p-0 px-1 font-medium">{sub ? `${sub.last_name} ${sub.first_name}` : ''}</td>
						</tr>
					{/each}
				</tbody>
			</table>

			<!-- COACHES TABLE -->
			<div class="w-full flex border border-blue-600">
				<!-- Vertical Text -->
				<div class="w-5 bg-blue-100/50 border-r border-blue-600 flex items-center justify-center">
					<span class="text-[9px] text-blue-600 tracking-widest font-semibold" style="writing-mode: vertical-rl; transform: rotate(180deg);">
						ENTRAÎNEURS
					</span>
				</div>
				<div class="flex-1 overflow-hidden">
					<table class="w-full border-collapse table-fixed text-[8.5px] leading-none">
						<thead>
							<tr class="bg-blue-500 text-white border-b border-blue-600">
								<th class="p-0.5 border-r border-blue-600 w-[12%] text-center font-bold">No</th>
								<th class="p-0.5 border-r border-blue-600 w-[36%] text-left font-bold">NOM</th>
								<th class="p-0.5 border-r border-blue-600 w-[36%] text-left font-bold">PRÉNOM</th>
								<th class="p-0.5 w-[16%] text-center font-bold">CHEF/ADJ.</th>
							</tr>
						</thead>
						<tbody>
							{#each coachRows as coach, i}
								<tr class="border-b border-blue-300 last:border-b-0 {i % 2 === 0 ? 'bg-blue-50/20' : 'bg-white'} h-[18px]">
									<td class="p-0.5 border-r border-blue-600 text-center font-bold">{coach?.jersey || ''}</td>
									<td class="p-0.5 px-1 border-r border-blue-600 font-medium truncate" title={coach?.last_name || ''}>{coach?.last_name || ''}</td>
									<td class="p-0.5 px-1 border-r border-blue-600 font-medium truncate" title={coach?.first_name || ''}>{coach?.first_name || ''}</td>
									<td class="p-0.5 text-center text-[7.5px] text-blue-600 font-semibold leading-tight truncate" title={coach?.coach_type || ''}>{coach?.coach_type || ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	</div>
</div>

<style>
	@media print {
		@page {
			margin: 0.5cm;
			size: portrait;
		}
		
		/* Force background colors to print */
		* {
			-webkit-print-color-adjust: exact !important;
			print-color-adjust: exact !important;
		}
	}
</style>
