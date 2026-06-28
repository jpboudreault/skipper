<script lang="ts">
	let { game, team, players, battingOrder, lineup, availability = [] } = $props();

	// Derived states
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
	let isHome = $derived(game?.home_away === 'H');
	let isAway = $derived(game?.home_away === 'A');

	const POSITIONS: Record<number, string> = {
		0: 'X',
		1: '1',
		2: '2',
		3: '3',
		4: '4',
		5: '5',
		6: '6',
		7: '7',
		8: '8',
		9: '9'
	};

	function getStartingPos(playerId: number) {
		const cell = lineup.find((l: any) => l.player_id === playerId && l.inning === 1);
		return cell ? POSITIONS[cell.position] || '' : '';
	}

	let startingPlayers = $derived(
		battingOrder.map((id: number) => players.find((p: any) => p.id === id)).filter(Boolean)
	);
	let orderRows = $derived(Array.from({ length: 15 }, (_, i) => startingPlayers[i] || null));

	let startingIds = $derived(new Set(battingOrder));
	let absentIds = $derived(
		new Set(
			availability
				.filter((a: any) => a.status === 'absent' || a.status === 'injured')
				.map((a: any) => a.player_id)
		)
	);
	let subs = $derived(
		players.filter(
			(p: any) => p.active && !p.is_coach && !startingIds.has(p.id) && !absentIds.has(p.id)
		)
	);
	let subRows = $derived(Array.from({ length: 9 }, (_, i) => subs[i] || null));
	const subLetters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'];

	let coaches = $derived(
		players
			.filter((p: any) => p.is_coach && !absentIds.has(p.id))
			.sort((a: any, b: any) => {
				if (a.coach_type === 'head') return -1;
				if (b.coach_type === 'head') return 1;
				return 0;
			})
	);
	let coachRows = $derived(Array.from({ length: 4 }, (_, i) => coaches[i] || null));
</script>

<!-- Single batting-order card; rendered twice so the sheet can be cut in half -->
{#snippet lineupCard()}
	<div class="min-w-0 flex-1 border-2 border-blue-600 bg-blue-50/30 p-1 text-[11px] leading-tight">
		<h1 class="py-1 text-center text-lg font-bold tracking-wide text-blue-700 uppercase">
			Ordre des Frappeurs
		</h1>

		<!-- HEADER TABLE -->
		<table class="mb-1.5 w-full border-collapse border border-blue-600">
			<tbody>
				<tr class="border-b border-blue-600">
					<td class="w-1/4 border-r border-blue-600 p-0.5">
						<div class="text-[9px] font-semibold text-blue-600">N° PARTIE</div>
						<div class="h-3 font-bold">{game?.game_number || ''}</div>
					</td>
					<td class="w-1/4 border-r border-blue-600 p-0.5">
						<div class="text-[9px] font-semibold text-blue-600">DATE : JJ/MM/AAAA</div>
						<div class="h-3 font-bold">{dateStr}</div>
					</td>
					<td class="w-1/4 border-r border-blue-600 p-0.5 text-center">
						<div class="mr-2 inline-block text-[9px] font-semibold text-blue-600">RECEVEUR</div>
						<div
							class="inline-block h-3 w-3 border border-blue-600 text-center align-middle text-[10px] leading-[10px] font-bold"
						>
							{isHome ? 'X' : ''}
						</div>
					</td>
					<td class="w-1/4 p-0.5 text-center">
						<div class="mr-2 inline-block text-[9px] font-semibold text-blue-600">VISITEUR</div>
						<div
							class="inline-block h-3 w-3 border border-blue-600 text-center align-middle text-[10px] leading-[10px] font-bold"
						>
							{isAway ? 'X' : ''}
						</div>
					</td>
				</tr>
				<tr class="border-b border-blue-600">
					<td colspan="2" class="border-r border-blue-600 p-0.5">
						<span class="mr-2 text-[9px] font-semibold text-blue-600">DIVISION</span>
						<span class="font-bold">{team?.division || ''}</span>
					</td>
					<td colspan="2" class="p-0.5">
						<span class="mr-2 text-[9px] font-semibold text-blue-600">CLASSE</span>
						<span class="font-bold">{team?.classe || ''}</span>
					</td>
				</tr>
				<tr class="border-b border-blue-600">
					<td colspan="4" class="flex p-0.5">
						<span class="w-20 text-[9px] font-semibold text-blue-600">ÉQUIPE</span>
						<span class="font-bold whitespace-nowrap">{team?.name || ''}</span>
					</td>
				</tr>
				<tr class="border-b border-blue-600">
					<td colspan="4" class="flex p-0.5">
						<span class="w-20 text-[9px] font-semibold text-blue-600">OPPOSANT</span>
						<span class="font-bold whitespace-nowrap">{game?.opponent || ''}</span>
					</td>
				</tr>
				<tr>
					<td colspan="4" class="flex p-0.5">
						<span class="w-20 text-[9px] font-semibold text-blue-600">LIGUE</span>
						<span class="font-bold whitespace-nowrap"
							>{game?.league || team?.default_league || ''}</span
						>
					</td>
				</tr>
			</tbody>
		</table>

		<!-- BATTING ORDER TABLE -->
		<table class="mb-1.5 w-full border-collapse border border-blue-600">
			<thead>
				<tr class="border-b border-blue-600 bg-blue-500 text-white">
					<th class="w-6 border-r border-blue-600 p-0.5 text-center font-semibold">#</th>
					<th class="w-8 border-r border-blue-600 p-0.5 text-center font-semibold">No</th>
					<th class="border-r border-blue-600 p-0.5 text-left font-semibold">Nom</th>
					<th class="border-r border-blue-600 p-0.5 text-left font-semibold">Prénom</th>
					<th class="w-12 border-r border-blue-600 p-0.5 text-center font-semibold">POS</th>
					<th class="w-12 p-0.5 text-center font-semibold">Subs</th>
				</tr>
			</thead>
			<tbody>
				{#each orderRows as player, i}
					<tr
						class="border-b border-blue-300 last:border-blue-600 {i % 2 === 0
							? 'bg-blue-50/20'
							: 'bg-white'} h-[18px]"
					>
						<td
							class="w-6 border-r border-blue-600 bg-blue-100/50 p-0 text-center text-[10px] text-blue-600"
							>{i + 1}</td
						>
						<td class="border-r border-blue-600 p-0 text-center font-bold"
							>{player?.jersey || ''}</td
						>
						<td class="border-r border-blue-600 p-0 px-1 font-medium">{player?.last_name || ''}</td>
						<td class="border-r border-blue-600 p-0 px-1 font-medium">{player?.first_name || ''}</td
						>
						<td class="border-r border-blue-600 p-0 text-center font-bold"
							>{player ? getStartingPos(player.id) : ''}</td
						>
						<td class="p-0 text-center text-[10px] font-bold">{player?.is_substitute ? '✓' : ''}</td
						>
					</tr>
				{/each}
			</tbody>
		</table>

		<!-- SUBSTITUTES AND COACHES ROW -->
		<div class="grid grid-cols-2 gap-2">
			<!-- SUBS TABLE -->
			<table class="w-full border-collapse border border-blue-600">
				<thead>
					<tr class="border-b border-blue-600 bg-blue-500 text-white">
						<th class="w-6 border-r border-blue-600 p-0.5"></th>
						<th class="w-8 border-r border-blue-600 p-0.5 text-center">No</th>
						<th class="p-0.5 text-left">SUBSTITUT</th>
					</tr>
				</thead>
				<tbody>
					{#each subRows as sub, i}
						<tr
							class="border-b border-blue-300 last:border-b-0 {i % 2 === 0
								? 'bg-blue-50/20'
								: 'bg-white'} h-[16px]"
						>
							<td
								class="border-r border-blue-600 bg-blue-100/50 p-0 text-center text-[9px] text-blue-600"
								>{subLetters[i]}</td
							>
							<td class="border-r border-blue-600 p-0 text-center font-bold">{sub?.jersey || ''}</td
							>
							<td class="p-0 px-1 font-medium">{sub ? `${sub.last_name} ${sub.first_name}` : ''}</td
							>
						</tr>
					{/each}
				</tbody>
			</table>

			<!-- COACHES TABLE -->
			<div class="flex w-full border border-blue-600">
				<!-- Vertical Text -->
				<div class="flex w-5 items-center justify-center border-r border-blue-600 bg-blue-100/50">
					<span
						class="text-[9px] font-semibold tracking-widest text-blue-600"
						style="writing-mode: vertical-rl; transform: rotate(180deg);"
					>
						ENTRAÎNEURS
					</span>
				</div>
				<div class="flex-1 overflow-hidden">
					<table class="w-full table-fixed border-collapse text-[8.5px] leading-none">
						<thead>
							<tr class="border-b border-blue-600 bg-blue-500 text-white">
								<th class="w-[12%] border-r border-blue-600 p-0.5 text-center font-bold">No</th>
								<th class="w-[36%] border-r border-blue-600 p-0.5 text-left font-bold">NOM</th>
								<th class="w-[36%] border-r border-blue-600 p-0.5 text-left font-bold">PRÉNOM</th>
								<th class="w-[16%] p-0.5 text-center font-bold">CHEF/ADJ.</th>
							</tr>
						</thead>
						<tbody>
							{#each coachRows as coach, i}
								<tr
									class="border-b border-blue-300 last:border-b-0 {i % 2 === 0
										? 'bg-blue-50/20'
										: 'bg-white'} h-[18px]"
								>
									<td class="border-r border-blue-600 p-0.5 text-center font-bold"
										>{coach?.jersey || ''}</td
									>
									<td
										class="truncate border-r border-blue-600 p-0.5 px-1 font-medium"
										title={coach?.last_name || ''}>{coach?.last_name || ''}</td
									>
									<td
										class="truncate border-r border-blue-600 p-0.5 px-1 font-medium"
										title={coach?.first_name || ''}>{coach?.first_name || ''}</td
									>
									<td
										class="truncate p-0.5 text-center text-[7.5px] leading-tight font-semibold text-blue-600"
										title={coach?.coach_type || ''}>{coach?.coach_type || ''}</td
									>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		</div>
	</div>
{/snippet}

<!-- Printable batting-order card (visibility controlled by parent wrapper) -->
<div class="printable-lineup bg-white font-sans text-black">
	<div class="flex items-start gap-1 divide-x-2 divide-dashed divide-gray-400">
		{@render lineupCard()}
		{@render lineupCard()}
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
