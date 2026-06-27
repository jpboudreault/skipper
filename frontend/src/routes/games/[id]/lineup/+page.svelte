<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { getLineupPrintComponent } from '$lib/league_formats';
	import DefensivePositionsPrint from '$lib/league_formats/lineup/defensive_positions.svelte';
	import { t, translate, statusLabel } from '$lib/i18n';

	let players: any[] = $state([]);
	let game: any = $state(null);
	let team: any = $state(null);
	let lineup: any[] = $state([]);
	let availability: any[] = $state([]);
	let battingLines: any[] = $state([]);
	let positionScores: any[] = $state([]);
	let loading = $state(true);
	let solving = $state(false);
	let solveStatus = $state('');
	let solveIsError = $state(false);
	let savingOrder = $state(false);
	let autoSaving = $state(false);
	let injuryMode = $state(false);
	let changingInnings = $state(false);
	let printTarget: 'lineup' | 'defense' | null = $state(null);

	const MIN_INNINGS = 1;
	const MAX_INNINGS = 12;

	// Batting order: ordered list of player IDs
	let battingOrder: number[] = $state([]);

	// Drag state
	let dragIndex: number | null = $state(null);
	let dragOverIndex: number | null = $state(null);

	const POSITIONS: Record<number, string> = {
		0: 'X', 1: '1', 2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8', 9: '9'
	};

	let numInnings = $derived(game?.innings_played || team?.innings_per_game || 5);
	let LineupPrintCard = $derived(getLineupPrintComponent(team?.lineup_print_version));

	async function fetchData() {
		try {
			const [pRes, gRes, tRes, lRes, aRes, bRes, psRes] = await Promise.all([
				apiFetch('/players/'),
				apiFetch(`/games/${$page.params.id}`),
				apiFetch('/teams/'),
				apiFetch(`/games/${$page.params.id}/lineup`),
				apiFetch(`/games/${$page.params.id}/availability`),
				apiFetch(`/games/${$page.params.id}/batting`),
				apiFetch('/position-scores/'),
			]);
			if (pRes.ok) players = await pRes.json();
			if (gRes.ok) game = await gRes.json();
			if (tRes.ok && game) { 
				const teams = await tRes.json(); 
				team = teams.find((t: any) => t.id === game.team_id) || teams[0]; 
			}
			if (lRes.ok) lineup = await lRes.json();
			if (aRes.ok) availability = await aRes.json();
			if (bRes.ok) battingLines = await bRes.json();
			if (psRes.ok) positionScores = await psRes.json();

			// Build batting order from saved batting_order field, fallback to jersey order
			initBattingOrder();
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchData();
		const resetPrintTarget = () => { printTarget = null; };
		window.addEventListener('afterprint', resetPrintTarget);
		return () => window.removeEventListener('afterprint', resetPrintTarget);
	});

	function triggerPrint(target: 'lineup' | 'defense') {
		printTarget = target;
		requestAnimationFrame(() => window.print());
	}

	function getAvailablePlayers(): any[] {
		const absentIds = new Set(
			availability.filter(a => a.status === 'absent' || a.status === 'injured').map(a => a.player_id)
		);
		return players.filter(p => !absentIds.has(p.id) && !p.is_coach);
	}

	let availablePlayerIds = $derived(new Set(getAvailablePlayers().map(p => p.id)));
	let hasUnlockedValues = $derived(lineup.some(cell => !cell.locked));

	function clearUnlocked() {
		lineup = lineup.filter(cell => cell.locked);
		saveLineup();
	}

	function initBattingOrder() {
		const available = getAvailablePlayers();
		// Sort by saved batting_order if it exists, else jersey number
		const withOrder = available.map(p => {
			const bl = battingLines.find((b: any) => b.player_id === p.id);
			return { ...p, batting_order: bl?.batting_order ?? null };
		});
		withOrder.sort((a, b) => {
			if (a.batting_order !== null && b.batting_order !== null) return a.batting_order - b.batting_order;
			if (a.batting_order !== null) return -1;
			if (b.batting_order !== null) return 1;
			return a.jersey - b.jersey;
		});
		battingOrder = withOrder.map(p => p.id);
	}

	function getPlayer(id: number) {
		return players.find(p => p.id === id);
	}

	// --- Drag and Drop ---
	function onDragStart(e: DragEvent, index: number) {
		dragIndex = index;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', String(index));
		}
	}

	function onDragOver(e: DragEvent, index: number) {
		e.preventDefault();
		if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
		if (dragOverIndex !== index) dragOverIndex = index;
	}

	function onDragLeave() {
		dragOverIndex = null;
	}

	function onDrop(e: DragEvent, index: number) {
		e.preventDefault();
		if (dragIndex === null || dragIndex === index) {
			dragIndex = null;
			dragOverIndex = null;
			return;
		}
		const newOrder = [...battingOrder];
		const [moved] = newOrder.splice(dragIndex, 1);
		newOrder.splice(index, 0, moved);
		battingOrder = newOrder;
		dragIndex = null;
		dragOverIndex = null;
		saveBattingOrder();
	}

	function onDragEnd() {
		dragIndex = null;
		dragOverIndex = null;
	}

	async function saveBattingOrder() {
		savingOrder = true;
		try {
			// Build payload: one BattingLine update per player with their batting_order position
			const lines = battingOrder.map((playerId, idx) => {
				const existing = battingLines.find((b: any) => b.player_id === playerId) || {};
				return {
					player_id: playerId,
					batting_order: idx + 1,
					singles: existing.singles ?? 0,
					doubles: existing.doubles ?? 0,
					triples: existing.triples ?? 0,
					hr: existing.hr ?? 0,
					bb: existing.bb ?? 0,
					bbi: existing.bbi ?? 0,
					hbp: existing.hbp ?? 0,
					sac: existing.sac ?? 0,
					intf: existing.intf ?? 0,
					kd: existing.kd ?? 0,
					ke: existing.ke ?? 0,
					outs_not_k: existing.outs_not_k ?? 0,
					fc: existing.fc ?? 0,
					roe: existing.roe ?? 0,
					rbi: existing.rbi ?? 0,
					r: existing.r ?? 0,
					sb: existing.sb ?? 0,
				};
			});
			const res = await apiFetch(`/games/${$page.params.id}/batting`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(lines)
			});
			if (res.ok) {
				battingLines = await apiFetch(`/games/${$page.params.id}/batting`).then(r => r.json());
			}
		} catch (e) {
			console.error(e);
			alert(translate('lineup_failed_save_batting_order'));
		} finally {
			savingOrder = false;
		}
	}

	// --- Lineup Grid ---
	function getCell(playerId: number, inning: number): any | null {
		return lineup.find(l => l.player_id === playerId && l.inning === inning) || null;
	}

	function getCellPosition(playerId: number, inning: number): number | null {
		const cell = getCell(playerId, inning);
		return cell ? cell.position : null;
	}

	function isInjured(playerId: number, inning: number): boolean {
		const avail = availability.find(a => a.player_id === playerId);
		return avail && avail.injury_inning !== null && inning >= avail.injury_inning;
	}

	async function toggleInjury(playerId: number, inning: number) {
		const avail = availability.find(a => a.player_id === playerId);
		const isAlreadyInjuredHere = avail && avail.injury_inning === inning;
		const newInning = isAlreadyInjuredHere ? null : inning;
		
		try {
			await apiFetch(`/games/${$page.params.id}/injury`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ player_id: playerId, injury_inning: newInning })
			});
			
			const idx = availability.findIndex(a => a.player_id === playerId);
			if (idx >= 0) {
				availability[idx].injury_inning = newInning;
			} else {
				availability.push({ player_id: playerId, injury_inning: newInning });
			}
			availability = [...availability];
		} catch(e) {
			console.error(e);
			alert(translate('lineup_failed_update_injury'));
		}
	}

	function isLocked(playerId: number, inning: number): boolean {
		const cell = getCell(playerId, inning);
		return cell?.locked || false;
	}

	function setCell(playerId: number, inning: number, position: number) {
		const existing = lineup.findIndex(l => l.player_id === playerId && l.inning === inning);
		
		if (isNaN(position)) {
			// Clear the assignment if the user selects "—"
			if (existing >= 0) {
				lineup.splice(existing, 1);
			}
		} else {
			if (existing >= 0) {
				lineup[existing].position = position;
				lineup[existing].locked = true; // Auto-lock when manually set
			} else {
				lineup.push({ game_id: parseInt($page.params.id || '0'), inning, player_id: playerId, position, locked: true });
			}
		}
		
		lineup = [...lineup];
		saveLineup();
	}

	function toggleInningLock(inning: number) {
		const isLocked = isInningLocked(inning);
		lineup.forEach(cell => {
			if (cell.inning === inning) {
				if (!isLocked) {
					// Lock all assigned values (0-9)
					if (cell.position !== null && cell.position !== undefined && !isNaN(cell.position)) {
						cell.locked = true;
					} else {
						cell.locked = false;
					}
				} else {
					// Unlock all values in the inning
					cell.locked = false;
				}
			}
		});
		lineup = [...lineup];
		saveLineup();
	}

	function isInningLocked(inning: number) {
		return lineup.some(l => l.inning === inning && l.locked);
	}

	async function saveLineup() {
		autoSaving = true;
		try {
			const cells = lineup.map(l => ({
				inning: l.inning,
				player_id: l.player_id,
				position: l.position,
				locked: l.locked || false
			}));
			await apiFetch(`/games/${$page.params.id}/lineup`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(cells)
			});
		} catch (e) {
			console.error(e);
		} finally {
			setTimeout(() => { autoSaving = false; }, 800);
		}
	}

	async function saveAll() {
		await saveBattingOrder();
		await saveLineup();
	}

	async function fillGaps() {
		solving = true;
		solveStatus = '';
		solveIsError = false;
		await saveLineup();
		try {
			const res = await apiFetch(`/games/${$page.params.id}/solve`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			});
			if (res.ok) {
				const result = await res.json();
				solveStatus = translate('lineup_solved', { status: result.status });
				const lRes = await apiFetch(`/games/${$page.params.id}/lineup`);
				if (lRes.ok) lineup = await lRes.json();
			} else {
				const err = await res.json();
				solveIsError = true;
				solveStatus = translate('lineup_error_prefix', { message: err.detail });
			}
		} catch (e: any) {
			solveIsError = true;
			solveStatus = translate('lineup_error_prefix', { message: e.message });
		} finally {
			solving = false;
		}
	}

	function getPositionCount(inning: number, position: number): number {
		return lineup.filter(l => l.inning === inning && l.position === position && availablePlayerIds.has(l.player_id)).length;
	}

	function getInningPoints(inning: number): number {
		const cells = lineup.filter(l => l.inning === inning && l.position > 0 && availablePlayerIds.has(l.player_id));
		let total = 0;
		for (const cell of cells) {
			const ps = positionScores.find(s => s.player_id === cell.player_id && s.position === cell.position);
			if (ps) {
				total += ps.score;
			}
		}
		return total;
	}

	async function changeInnings(delta: number) {
		if (!game || changingInnings) return;
		const newCount = numInnings + delta;
		if (newCount < MIN_INNINGS || newCount > MAX_INNINGS) return;

		changingInnings = true;
		try {
			const res = await apiFetch(`/games/${$page.params.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ date: game.date, innings_played: newCount })
			});
			if (!res.ok) {
				const err = await res.json();
				alert(translate('lineup_error_prefix', { message: err.detail }));
				return;
			}

			game = await res.json();
			lineup = lineup.filter(l => l.inning <= newCount);
			availability = availability.map(a =>
				a.injury_inning !== null && a.injury_inning > newCount
					? { ...a, injury_inning: null }
					: a
			);

			const lRes = await apiFetch(`/games/${$page.params.id}/lineup`);
			if (lRes.ok) lineup = await lRes.json();
		} catch (e) {
			console.error(e);
			alert(translate('lineup_failed_change_innings'));
		} finally {
			changingInnings = false;
		}
	}

</script>

<div class="space-y-6 print:hidden">

	<!-- ── Lineup Grid & Batting Order ── -->
	<div class="space-y-4">
		<div class="flex items-center justify-between flex-wrap gap-4">
			<div>
				<h2 class="text-xl font-bold text-base-content">{$t('lineup_title')}</h2>
				<p class="text-sm text-base-content/70">{$t('lineup_description')}</p>
				<div class="flex items-center gap-2 mt-2">
					<span class="text-sm font-semibold text-base-content/80">{$t('lineup_innings_label')}:</span>
					<div class="join border border-base-300">
						<button
							class="btn btn-xs join-item"
							onclick={() => changeInnings(-1)}
							disabled={changingInnings || numInnings <= MIN_INNINGS}
							aria-label={$t('lineup_remove_inning')}
							title={$t('lineup_remove_inning')}
						>−</button>
						<span class="btn btn-xs join-item btn-ghost no-animation pointer-events-none min-w-16">
							{#if changingInnings}
								<span class="loading loading-spinner loading-xs"></span>
							{:else}
								{$t('lineup_innings_count', { count: numInnings })}
							{/if}
						</span>
						<button
							class="btn btn-xs join-item"
							onclick={() => changeInnings(1)}
							disabled={changingInnings || numInnings >= MAX_INNINGS}
							aria-label={$t('lineup_add_inning')}
							title={$t('lineup_add_inning')}
						>+</button>
					</div>
				</div>
			</div>
			<div class="flex gap-2 items-center flex-wrap">
				{#if autoSaving}
					<span class="loading loading-spinner loading-xs text-primary mr-2"></span>
					<span class="text-xs text-base-content/60 mr-2">{$t('lineup_saving')}</span>
				{:else}
					<span class="badge badge-success badge-outline gap-1 mr-2">
						✓ {$t('lineup_saved')}
					</span>
				{/if}

				<button onclick={() => injuryMode = !injuryMode} class="btn btn-sm shadow-md gap-1 {injuryMode ? 'btn-error text-error-content' : 'btn-outline border-base-300'}">
					🩹 {injuryMode ? $t('lineup_exit_injury_mode') : $t('lineup_injury_mode')}
				</button>
				<button onclick={() => triggerPrint('lineup')} class="btn btn-neutral btn-sm shadow-md gap-1">
					🖨️ {$t('lineup_print_lineup')}
				</button>
				<button onclick={() => triggerPrint('defense')} class="btn btn-neutral btn-sm shadow-md gap-1">
					🛡️ {$t('lineup_print_defense')}
				</button>
				{#if hasUnlockedValues}
					<button onclick={clearUnlocked} class="btn btn-warning btn-sm shadow-md gap-1">
						🧹 {$t('lineup_clear_unlocked')}
					</button>
				{/if}
				<button onclick={fillGaps} disabled={solving} class="btn btn-primary btn-sm shadow-md gap-1">
					{#if solving}
						<span class="loading loading-spinner loading-xs"></span> {$t('lineup_solving')}
					{:else}
						⚡ {$t('lineup_fill_gaps')}
					{/if}
				</button>
			</div>
		</div>

		{#if solveStatus}
			<div class="alert {solveIsError ? 'alert-error' : 'alert-success'} py-3 shadow-sm rounded-lg flex items-center justify-between">
				<div class="flex items-center gap-2">
					<span>{solveStatus}</span>
				</div>
			</div>
		{/if}

		{#if game}
			<div class="alert bg-base-100 border border-base-300 py-3 shadow-sm rounded-lg flex items-center justify-between">
				<div class="flex items-center gap-2">
					<span class="badge badge-md {game.mode === 'compete' ? 'badge-info' : 'badge-success'}">
						{game.mode === 'compete' ? $t('lineup_compete_mode') : $t('lineup_develop_mode')}
					</span>
					<span class="text-sm text-base-content/70">
						{game.mode === 'compete' ? $t('lineup_compete_desc') : $t('lineup_develop_desc')}
					</span>
				</div>
			</div>
		{/if}

		{#if !loading}
			<div class="card bg-base-100 border border-base-300 shadow-xl overflow-hidden">
				<div class="overflow-x-auto">
					<table class="table table-sm table-pin-rows table-pin-cols w-full">
						<thead class="bg-base-200">
							<tr>
								<th class="bg-base-300 text-base-content font-bold w-64 sticky left-0 z-20">
									{$t('lineup_order_player')}
								</th>
								{#each Array(numInnings) as _, inn}
									<th class="bg-base-200 text-base-content font-bold text-center w-24">
										<div class="flex flex-col items-center justify-center gap-1 py-1">
											<span>{$t('lineup_inning', { number: inn + 1 })}</span>
											<button
												onclick={() => toggleInningLock(inn + 1)}
												class="btn btn-xs min-h-0 h-6 px-2 bg-base-100/50 border border-base-300 hover:bg-base-300 transition-colors {isInningLocked(inn + 1) ? 'text-warning border-warning/30' : 'text-base-content/50'}"
												title={isInningLocked(inn + 1) ? $t('lineup_unlock_inning') : $t('lineup_lock_inning')}
											>
												{isInningLocked(inn + 1) ? '🔓' : '🔒'}
											</button>
										</div>
									</th>
								{/each}
								<th class="bg-base-200 text-base-content font-bold text-center w-16">{$t('lineup_bench')}</th>
							</tr>
						</thead>
						<tbody>
							{#each battingOrder as playerId, idx}
								{@const player = getPlayer(playerId)}
								{@const avail = availability.find(a => a.player_id === playerId)}
								{#if player}
									{@const benchCount = Array.from({length: numInnings}, (_, i) => getCellPosition(player.id, i + 1)).filter(p => p === 0).length}
									<tr 
										draggable={true}
										ondragstart={(e) => onDragStart(e, idx)}
										ondragover={(e) => onDragOver(e, idx)}
										ondragleave={onDragLeave}
										ondrop={(e) => onDrop(e, idx)}
										ondragend={onDragEnd}
										class="hover:bg-base-200/50 transition-colors group
											{dragOverIndex === idx && dragIndex !== idx ? 'bg-primary/10 border-t-2 border-primary' : ''}
											{dragIndex === idx ? 'opacity-40' : ''}"
									>
										<td class="bg-base-100 font-medium text-base-content border-r border-base-300 sticky left-0 z-10">
											<div class="flex items-center gap-2 select-none">
												<!-- Drag handle -->
												<span class="text-base-content/40 text-lg flex-shrink-0 cursor-grab active:cursor-grabbing" aria-hidden="true">⠿</span>
												<!-- Player info -->
												<span class="text-base-content/50 text-xs flex-shrink-0 w-6 text-right">#{player.jersey}</span>
												<span class="truncate md:hidden">{player.first_name} {player.last_name.charAt(0)}.</span>
												<span class="truncate hidden md:inline">{player.first_name} {player.last_name}</span>
												{#if player.is_substitute}
													<span class="badge badge-xs badge-neutral text-[9px] ml-1 uppercase">{$t('lineup_sub')}</span>
												{/if}
												
												{#if avail && avail.status !== 'available'}
													<span class="badge badge-xs {avail.status === 'late' ? 'badge-warning' : 'badge-error'} ml-auto uppercase text-[9px]">
														{statusLabel(avail.status)}
													</span>
												{/if}
												{#if avail && avail.injury_inning}
													<span class="badge badge-xs badge-error ml-auto uppercase text-[9px]" title="Injured in Inning {avail.injury_inning}">🏥 INN {avail.injury_inning}</span>
												{/if}
											</div>
										</td>
										{#each Array(numInnings) as _, inn}
											{@const pos = getCellPosition(player.id, inn + 1)}
											{@const locked = isLocked(player.id, inn + 1)}
											<td class="text-center border-r border-base-200 last:border-r-0 {locked ? 'locked-cell' : ''} {isInjured(player.id, inn + 1) ? 'bg-error/10' : ''}">
												{#if injuryMode}
													<button class="w-full h-full min-h-[30px] flex items-center justify-center hover:bg-error/20 transition-colors" onclick={() => toggleInjury(player.id, inn + 1)}>
														{#if isInjured(player.id, inn + 1)}
															<span class="text-error" title="Injured">🏥</span>
														{:else}
															<span class="opacity-20 hover:opacity-100">🩹</span>
														{/if}
													</button>
												{:else}
													{#if isInjured(player.id, inn + 1)}
														<div class="text-center text-error text-xs font-bold w-16 mx-auto cursor-not-allowed">🏥 {$t('lineup_injured_bench')}</div>
													{:else}
														<div class="flex flex-col items-center gap-0.5">
															<select
																value={pos?.toString() ?? ''}
																onchange={(e) => setCell(player.id, inn + 1, parseInt(e.currentTarget.value))}
																class="select select-bordered select-xs w-16 {locked ? 'select-warning locked-position-select font-bold' : ''}"
															>
																<option value="">—</option>
																{#each Object.entries(POSITIONS) as [val, label]}
																	<option value={val} disabled={val === '1' && player.is_substitute}>{label}</option>
																{/each}
															</select>
														</div>
													{/if}
												{/if}
											</td>
										{/each}
										<td class="text-center font-bold {benchCount > 1 ? 'text-warning' : 'text-base-content/60'}">
											{benchCount}
										</td>
									</tr>
								{/if}
							{/each}
						</tbody>
						<tfoot class="bg-base-300 font-bold">
							<tr>
								<td class="py-3 sticky left-0 bg-base-300 text-base-content font-bold border-r border-base-300 text-right pr-4">
									{$t('lineup_total_points')}
								</td>
								{#each Array(numInnings) as _, inn}
									<td class="text-center text-primary font-bold border-r border-base-200 last:border-r-0">
										{getInningPoints(inn + 1)}
									</td>
								{/each}
								<td></td>
							</tr>
						</tfoot>
					</table>
				</div>
			</div>

			<!-- Validation summary -->
			<div class="card bg-base-100 border border-base-300 shadow-xl p-5">
				<h3 class="text-md font-bold text-base-content mb-3 border-b border-base-200 pb-1">{$t('lineup_validation_title')}</h3>
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
					{#each Array(numInnings) as _, inn}
						{@const assigned = lineup.filter(l => l.inning === inn + 1 && l.position > 0 && availablePlayerIds.has(l.player_id)).length}
						{@const benched = lineup.filter(l => l.inning === inn + 1 && l.position === 0 && availablePlayerIds.has(l.player_id)).length}
						<div class="flex items-center gap-2 flex-wrap">
							<span class="font-semibold text-base-content/80">{$t('lineup_inning', { number: inn + 1 })}:</span>
							<span class="badge {assigned === 9 ? 'badge-success text-success-content' : 'badge-warning'} badge-sm font-bold">
								{$t('lineup_fielders', { count: assigned })}
							</span>
							<span class="badge badge-ghost badge-sm">{$t('lineup_benched', { count: benched })}</span>
							{#each [1,2,3,4,5,6,7,8,9] as pos}
								{@const count = getPositionCount(inn + 1, pos)}
								{#if count > 1}
									<span class="badge badge-error badge-sm font-bold">⚠ {POSITIONS[pos]} ×{count}</span>
								{/if}
							{/each}
						</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
</div>

<div class="hidden {printTarget === 'lineup' ? 'print:block' : 'print:hidden'}">
	<LineupPrintCard 
		{game}
		{team}
		{players}
		{battingOrder}
		{lineup}
		{availability}
	/>
</div>

<div class="hidden {printTarget === 'defense' ? 'print:block' : 'print:hidden'}">
	<DefensivePositionsPrint
		{game}
		{team}
		{players}
		{battingOrder}
		{lineup}
		{availability}
		numInnings={numInnings}
	/>
</div>

<style>
	:global(td.locked-cell) {
		background-color: color-mix(in oklab, var(--color-warning) 5%, var(--color-base-100));
	}

	:global(select.locked-position-select),
	:global(select.locked-position-select option) {
		background-color: color-mix(in oklab, var(--color-warning) 12%, var(--color-base-100));
	}
</style>
