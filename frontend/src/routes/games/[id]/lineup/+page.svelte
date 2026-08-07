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
	let solveOptions = $state<any[]>([]);
	let showSolveOptions = $state(false);
	let selectedSolveOptionIdx = $state(0);
	let solveTolerancePct = $state<number | null>(null);
	let applyingOption = $state(false);
	let savingOrder = $state(false);
	let autoSaving = $state(false);
	let injuryMode = $state(false);
	let changingInnings = $state(false);
	let printTarget: 'lineup' | 'defense' | null = $state(null);
	let snapshots: any[] = $state([]);
	let showHistory = $state(false);

	const MIN_INNINGS = 1;
	const MAX_INNINGS = 12;

	// Batting order: ordered list of player IDs
	let battingOrder: number[] = $state([]);

	// Drag state
	let dragIndex: number | null = $state(null);
	let dragOverIndex: number | null = $state(null);

	// Touch drag state (mobile)
	let touchGhost: HTMLElement | null = $state(null);
	let touchCurrentIndex: number | null = $state(null);

	const MODE_LABELS: Record<string, string> = {
		compete: 'lineup_compete_mode',
		develop: 'lineup_develop_mode',
		optimal: 'lineup_optimal_mode'
	};

	const MODE_DESCS: Record<string, string> = {
		compete: 'lineup_compete_desc',
		develop: 'lineup_develop_desc',
		optimal: 'lineup_optimal_desc'
	};

	function modeBadgeClass(mode: string): string {
		if (mode === 'optimal') return 'badge-warning';
		if (mode === 'compete') return 'badge-info';
		return 'badge-success';
	}

	function optionQualityForAssignments(assignments: any[]): number {
		if (!game || !positionScores.length) return 0;
		const lateStart = numInnings - Math.ceil(numInnings / 3);
		let total = 0;
		for (const cell of assignments) {
			if (cell.position === 0) continue;
			const ps = positionScores.find(
				(s) => s.player_id === cell.player_id && s.position === cell.position
			);
			if (!ps) continue;
			const weight = cell.inning - 1 >= lateStart ? (team?.late_inning_weight ?? 1.5) : 1;
			total += ps.score * weight;
		}
		return Math.round(total * 10) / 10;
	}

	function getOptionPosition(assignments: any[], playerId: number, inning: number): number | null {
		const cell = assignments.find((a) => a.player_id === playerId && a.inning === inning);
		return cell?.position ?? null;
	}

	function getOptionBenchCount(assignments: any[], playerId: number): number {
		return Array.from({ length: numInnings }, (_, i) =>
			getOptionPosition(assignments, playerId, i + 1)
		).filter((p) => p === 0).length;
	}

	function getOptionInningPoints(assignments: any[], inning: number): number {
		const lateStart = numInnings - Math.ceil(numInnings / 3);
		let total = 0;
		for (const cell of assignments) {
			if (cell.inning !== inning || cell.position <= 0) continue;
			if (!availablePlayerIds.has(cell.player_id)) continue;
			const ps = positionScores.find(
				(s) => s.player_id === cell.player_id && s.position === cell.position
			);
			if (!ps) continue;
			const weight = cell.inning - 1 >= lateStart ? (team?.late_inning_weight ?? 1.5) : 1;
			total += ps.score * weight;
		}
		return Math.round(total * 10) / 10;
	}

	function selectSolveOption(idx: number) {
		selectedSolveOptionIdx = idx;
	}

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
				apiFetch('/position-scores/')
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
			await loadSnapshots();
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	async function loadSnapshots() {
		try {
			const res = await apiFetch(`/games/${$page.params.id}/lineup/snapshots`);
			if (res.ok) snapshots = await res.json();
		} catch (e) {
			console.error(e);
		}
	}

	async function saveSnapshot() {
		const saved = await saveLineup();
		if (!saved) {
			alert(translate('lineup_failed_save_snapshot'));
			return;
		}
		try {
			const res = await apiFetch(`/games/${$page.params.id}/lineup/snapshots`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ label: 'manual' })
			});
			if (res.ok) await loadSnapshots();
		} catch (e) {
			console.error(e);
		}
	}

	async function restoreSnapshotById(id: number) {
		try {
			const res = await apiFetch(`/games/${$page.params.id}/lineup/snapshots/${id}/restore`, {
				method: 'POST'
			});
			if (res.ok) {
				const lRes = await apiFetch(`/games/${$page.params.id}/lineup`);
				if (lRes.ok) lineup = await lRes.json();
				showHistory = false;
			}
		} catch (e) {
			console.error(e);
		}
	}

	onMount(() => {
		fetchData();
		const resetPrintTarget = () => {
			printTarget = null;
		};
		window.addEventListener('afterprint', resetPrintTarget);
		return () => window.removeEventListener('afterprint', resetPrintTarget);
	});

	function triggerPrint(target: 'lineup' | 'defense') {
		printTarget = target;
		requestAnimationFrame(() => window.print());
	}

	function getAvailablePlayers(): any[] {
		const absentIds = new Set(
			availability
				.filter((a) => a.status === 'absent' || a.status === 'injured')
				.map((a) => a.player_id)
		);
		return players.filter((p) => !absentIds.has(p.id) && !p.is_coach);
	}

	let availablePlayerIds = $derived(new Set(getAvailablePlayers().map((p) => p.id)));
	let hasUnlockedValues = $derived(lineup.some((cell) => !cell.locked));

	function clearUnlocked() {
		lineup = lineup.filter((cell) => cell.locked);
		saveLineup();
	}

	function initBattingOrder() {
		const available = getAvailablePlayers();
		// Sort by saved batting_order if it exists, else jersey number
		const withOrder = available.map((p) => {
			const bl = battingLines.find((b: any) => b.player_id === p.id);
			return { ...p, batting_order: bl?.batting_order ?? null };
		});
		withOrder.sort((a, b) => {
			if (a.batting_order !== null && b.batting_order !== null)
				return a.batting_order - b.batting_order;
			if (a.batting_order !== null) return -1;
			if (b.batting_order !== null) return 1;
			return a.jersey - b.jersey;
		});
		battingOrder = withOrder.map((p) => p.id);
	}

	function getPlayer(id: number) {
		return players.find((p) => p.id === id);
	}

	// --- Drag and Drop ---
	function reorderBattingOrder(fromIndex: number, toIndex: number) {
		if (fromIndex === toIndex) return;
		const newOrder = [...battingOrder];
		const [moved] = newOrder.splice(fromIndex, 1);
		newOrder.splice(toIndex, 0, moved);
		battingOrder = newOrder;
		saveBattingOrder();
	}

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
		if (dragIndex === null) {
			dragIndex = null;
			dragOverIndex = null;
			return;
		}
		reorderBattingOrder(dragIndex, index);
		dragIndex = null;
		dragOverIndex = null;
	}

	function onDragEnd() {
		dragIndex = null;
		dragOverIndex = null;
	}

	// --- Touch drag events (mobile) ---
	function handleTouchStart(e: TouchEvent, index: number) {
		const touch = e.touches[0];
		dragIndex = index;

		const target = e.currentTarget as HTMLElement;
		const ghost = target.cloneNode(true) as HTMLElement;
		ghost.style.position = 'fixed';
		ghost.style.zIndex = '9999';
		ghost.style.pointerEvents = 'none';
		ghost.style.opacity = '0.85';
		ghost.style.width = target.offsetWidth + 'px';
		ghost.style.transform = 'scale(1.05) rotate(2deg)';
		ghost.style.boxShadow = '0 8px 32px rgba(0,0,0,0.18)';
		ghost.style.left = touch.clientX - target.offsetWidth / 2 + 'px';
		ghost.style.top = touch.clientY - 30 + 'px';
		document.body.appendChild(ghost);
		touchGhost = ghost;

		target.style.opacity = '0.3';
	}

	function handleTouchMove(e: TouchEvent) {
		e.preventDefault();
		const touch = e.touches[0];

		if (touchGhost) {
			const target = e.currentTarget as HTMLElement;
			touchGhost.style.left = touch.clientX - target.offsetWidth / 2 + 'px';
			touchGhost.style.top = touch.clientY - 30 + 'px';
		}

		const el = document.elementFromPoint(touch.clientX, touch.clientY);
		if (el) {
			const row = el.closest('[data-row-index]') as HTMLElement | null;
			const idx = row ? parseInt(row.dataset.rowIndex ?? '', 10) : NaN;
			touchCurrentIndex = Number.isNaN(idx) ? null : idx;
			dragOverIndex = touchCurrentIndex;
		}
	}

	function handleTouchEnd(e: TouchEvent) {
		if (touchGhost) {
			touchGhost.remove();
			touchGhost = null;
		}

		const target = e.currentTarget as HTMLElement;
		target.style.opacity = '1';

		if (dragIndex !== null && touchCurrentIndex !== null && dragIndex !== touchCurrentIndex) {
			reorderBattingOrder(dragIndex, touchCurrentIndex);
		}
		dragIndex = null;
		dragOverIndex = null;
		touchCurrentIndex = null;
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
					sb: existing.sb ?? 0
				};
			});
			const res = await apiFetch(`/games/${$page.params.id}/batting`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(lines)
			});
			if (res.ok) {
				battingLines = await apiFetch(`/games/${$page.params.id}/batting`).then((r) => r.json());
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
		return lineup.find((l) => l.player_id === playerId && l.inning === inning) || null;
	}

	function getCellPosition(playerId: number, inning: number): number | null {
		const cell = getCell(playerId, inning);
		return cell ? cell.position : null;
	}

	function isInjured(playerId: number, inning: number): boolean {
		const avail = availability.find((a) => a.player_id === playerId);
		return avail && avail.injury_inning !== null && inning >= avail.injury_inning;
	}

	async function toggleInjury(playerId: number, inning: number) {
		const avail = availability.find((a) => a.player_id === playerId);
		const isAlreadyInjuredHere = avail && avail.injury_inning === inning;
		const newInning = isAlreadyInjuredHere ? null : inning;

		try {
			await apiFetch(`/games/${$page.params.id}/injury`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ player_id: playerId, injury_inning: newInning })
			});

			const idx = availability.findIndex((a) => a.player_id === playerId);
			if (idx >= 0) {
				availability[idx].injury_inning = newInning;
			} else {
				availability.push({ player_id: playerId, injury_inning: newInning });
			}
			availability = [...availability];
		} catch (e) {
			console.error(e);
			alert(translate('lineup_failed_update_injury'));
		}
	}

	function isLocked(playerId: number, inning: number): boolean {
		const cell = getCell(playerId, inning);
		return cell?.locked || false;
	}

	function setCell(playerId: number, inning: number, position: number) {
		const existing = lineup.findIndex((l) => l.player_id === playerId && l.inning === inning);

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
				lineup.push({
					game_id: parseInt($page.params.id || '0'),
					inning,
					player_id: playerId,
					position,
					locked: true
				});
			}
		}

		lineup = [...lineup];
		saveLineup();
	}

	function toggleInningLock(inning: number) {
		const isLocked = isInningLocked(inning);
		lineup.forEach((cell) => {
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
		return lineup.some((l) => l.inning === inning && l.locked);
	}

	async function saveLineup(): Promise<boolean> {
		autoSaving = true;
		try {
			const cells = lineup.map((l) => ({
				inning: l.inning,
				player_id: l.player_id,
				position: l.position,
				locked: l.locked || false
			}));
			const res = await apiFetch(`/games/${$page.params.id}/lineup`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(cells)
			});
			return res.ok;
		} catch (e) {
			console.error(e);
			return false;
		} finally {
			setTimeout(() => {
				autoSaving = false;
			}, 800);
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
		showSolveOptions = false;
		solveOptions = [];
		await saveLineup();
		try {
			const res = await apiFetch(`/games/${$page.params.id}/solve`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' }
			});
			if (res.ok) {
				const result = await res.json();
				if (result.applied) {
					const status = result.options?.[0]?.status ?? result.status ?? 'feasible';
					solveStatus = translate('lineup_solved', { status });
					const lRes = await apiFetch(`/games/${$page.params.id}/lineup`);
					if (lRes.ok) lineup = await lRes.json();
					await loadSnapshots();
				} else {
					solveOptions = result.options ?? [];
					solveTolerancePct = result.tolerance_pct ?? null;
					selectedSolveOptionIdx = 0;
					showSolveOptions = true;
				}
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

	async function applySolveOption(option: any) {
		applyingOption = true;
		try {
			const res = await apiFetch(`/games/${$page.params.id}/solve/apply`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ assignments: option.assignments })
			});
			if (res.ok) {
				showSolveOptions = false;
				solveOptions = [];
				solveStatus = translate('lineup_solved', { status: option.status });
				solveIsError = false;
				const lRes = await apiFetch(`/games/${$page.params.id}/lineup`);
				if (lRes.ok) lineup = await lRes.json();
				await loadSnapshots();
			} else {
				const err = await res.json();
				solveIsError = true;
				solveStatus = translate('lineup_error_prefix', { message: err.detail });
			}
		} catch (e: any) {
			solveIsError = true;
			solveStatus = translate('lineup_error_prefix', { message: e.message });
		} finally {
			applyingOption = false;
		}
	}

	function closeSolveOptions() {
		showSolveOptions = false;
		solveOptions = [];
		selectedSolveOptionIdx = 0;
	}

	function getPositionCount(inning: number, position: number): number {
		return lineup.filter(
			(l) => l.inning === inning && l.position === position && availablePlayerIds.has(l.player_id)
		).length;
	}

	function getInningPoints(inning: number): number {
		const cells = lineup.filter(
			(l) => l.inning === inning && l.position > 0 && availablePlayerIds.has(l.player_id)
		);
		let total = 0;
		for (const cell of cells) {
			const ps = positionScores.find(
				(s) => s.player_id === cell.player_id && s.position === cell.position
			);
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
			lineup = lineup.filter((l) => l.inning <= newCount);
			availability = availability.map((a) =>
				a.injury_inning !== null && a.injury_inning > newCount ? { ...a, injury_inning: null } : a
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
		<div class="flex flex-wrap items-center justify-between gap-4">
			<div>
				<h2 class="text-base-content text-xl font-bold">{$t('lineup_title')}</h2>
				<p class="text-base-content/70 text-sm">{$t('lineup_description')}</p>
				<div class="mt-2 flex items-center gap-2">
					<span class="text-base-content/80 text-sm font-semibold"
						>{$t('lineup_innings_label')}:</span
					>
					<div class="join border-base-300 border">
						<button
							class="btn btn-xs join-item"
							onclick={() => changeInnings(-1)}
							disabled={changingInnings || numInnings <= MIN_INNINGS}
							aria-label={$t('lineup_remove_inning')}
							title={$t('lineup_remove_inning')}>−</button
						>
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
							title={$t('lineup_add_inning')}>+</button
						>
					</div>
				</div>
			</div>
			<div class="flex flex-wrap items-center gap-2">
				{#if autoSaving}
					<span class="loading loading-spinner loading-xs text-primary mr-2"></span>
					<span class="text-base-content/60 mr-2 text-xs">{$t('lineup_saving')}</span>
				{:else}
					<span class="badge badge-success badge-outline mr-2 gap-1">
						✓ {$t('lineup_saved')}
					</span>
				{/if}

				<button
					onclick={() => (injuryMode = !injuryMode)}
					class="btn btn-sm gap-1 shadow-md {injuryMode
						? 'btn-error text-error-content'
						: 'btn-outline border-base-300'}"
				>
					🩹 {injuryMode ? $t('lineup_exit_injury_mode') : $t('lineup_injury_mode')}
				</button>
				<button
					onclick={() => triggerPrint('lineup')}
					class="btn btn-neutral btn-sm gap-1 shadow-md"
				>
					🖨️ {$t('lineup_print_lineup')}
				</button>
				<button
					onclick={() => triggerPrint('defense')}
					class="btn btn-neutral btn-sm gap-1 shadow-md"
				>
					🛡️ {$t('lineup_print_defense')}
				</button>
				{#if hasUnlockedValues}
					<button onclick={clearUnlocked} class="btn btn-warning btn-sm gap-1 shadow-md">
						🧹 {$t('lineup_clear_unlocked')}
					</button>
				{/if}
				<div class="dropdown dropdown-end">
					<button
						type="button"
						onclick={() => {
							showHistory = !showHistory;
							if (showHistory) loadSnapshots();
						}}
						class="btn btn-outline border-base-300 btn-sm gap-1 shadow-md"
					>
						🕑 {$t('lineup_history')}
					</button>
					{#if showHistory}
						<div
							class="dropdown-content rounded-box bg-base-100 border-base-300 z-50 mt-2 w-72 border p-3 shadow-lg"
						>
							<button onclick={saveSnapshot} class="btn btn-primary btn-xs mb-2 w-full gap-1">
								💾 {$t('lineup_history_save')}
							</button>
							{#if snapshots.length === 0}
								<p class="text-base-content/60 py-2 text-center text-xs">
									{$t('lineup_history_empty')}
								</p>
							{:else}
								<ul class="menu menu-sm max-h-64 overflow-y-auto p-0">
									{#each snapshots as snap}
										<li>
											<button
												onclick={() => restoreSnapshotById(snap.id)}
												class="flex justify-between"
											>
												<span class="truncate">
													{snap.label === 'before_solve'
														? $t('lineup_history_before_solve')
														: $t('lineup_history_manual')}
												</span>
												<span class="text-base-content/50 text-[10px]">
													{snap.created_at ? new Date(snap.created_at).toLocaleString() : ''}
												</span>
											</button>
										</li>
									{/each}
								</ul>
							{/if}
						</div>
					{/if}
				</div>
				<button
					onclick={fillGaps}
					disabled={solving}
					class="btn btn-primary btn-sm gap-1 shadow-md"
				>
					{#if solving}
						<span class="loading loading-spinner loading-xs"></span> {$t('lineup_solving')}
					{:else}
						⚡ {$t('lineup_fill_gaps')}
					{/if}
				</button>
			</div>
		</div>

		{#if solveStatus}
			<div
				class="alert {solveIsError
					? 'alert-error'
					: 'alert-success'} flex items-center justify-between rounded-lg py-3 shadow-sm"
			>
				<div class="flex items-center gap-2">
					<span>{solveStatus}</span>
				</div>
			</div>
		{/if}

		{#if showSolveOptions && solveOptions.length > 0}
			{@const activeOption = solveOptions[selectedSolveOptionIdx]}
			<div class="modal modal-open">
				<div class="modal-box flex max-h-[90vh] max-w-6xl flex-col">
					<h3 class="text-lg font-bold">{$t('lineup_solve_options_title')}</h3>
					<p class="text-base-content/70 mt-1 text-sm">
						{$t('lineup_solve_options_count', { count: solveOptions.length })}
					</p>

					<div
						class="tabs tabs-boxed bg-base-200 border-base-300 mt-4 flex-wrap gap-1 border p-1 shadow-sm"
						role="tablist"
					>
						{#each solveOptions as option, idx}
							<button
								type="button"
								role="tab"
								aria-selected={selectedSolveOptionIdx === idx}
								class="tab tab-sm {selectedSolveOptionIdx === idx
									? 'tab-active text-primary font-bold'
									: 'text-base-content/60'}"
								onclick={() => selectSolveOption(idx)}
							>
								{$t('lineup_solve_option_tab', { number: option.option_id })}
								{#if game?.mode === 'develop'}
									<span class="text-base-content/60 ml-1 text-xs"
										>({Math.round(option.dev_score)})</span
									>
								{:else}
									<span class="text-base-content/60 ml-1 text-xs"
										>({option.quality_score ??
											optionQualityForAssignments(option.assignments)})</span
									>
								{/if}
							</button>
						{/each}
					</div>

					{#if activeOption}
						<div class="mt-3 flex flex-wrap items-center gap-2">
							{#if selectedSolveOptionIdx === 0 && game?.mode === 'compete'}
								<span class="badge badge-sm badge-primary">{$t('lineup_solve_option_best')}</span>
							{:else if selectedSolveOptionIdx > 0 && game?.mode === 'compete' && solveTolerancePct}
								<span class="badge badge-sm badge-ghost"
									>{$t('lineup_solve_option_within_tolerance', {
										pct: solveTolerancePct
									})}</span
								>
							{/if}
							{#if game?.mode === 'develop'}
								<span class="text-sm">
									{$t('lineup_solve_option_dev', {
										score: Math.round(activeOption.dev_score)
									})}
								</span>
							{:else}
								<span class="text-sm">
									{$t('lineup_solve_option_quality', {
										score:
											activeOption.quality_score ??
											optionQualityForAssignments(activeOption.assignments)
									})}
								</span>
							{/if}
							<span class="text-base-content/60 text-xs capitalize">{activeOption.status}</span>
						</div>

						<div class="border-base-300 mt-4 min-h-0 flex-1 overflow-auto rounded-lg border">
							<table class="table-sm table-pin-rows table-pin-cols table w-full">
								<thead class="bg-base-200">
									<tr>
										<th
											class="bg-base-300 text-base-content sticky left-0 z-20 w-48 font-bold"
										>
											{$t('lineup_order_player')}
										</th>
										{#each Array(numInnings) as _, inn}
											<th class="bg-base-200 text-base-content w-14 text-center font-bold">
												{$t('lineup_inning', { number: inn + 1 })}
											</th>
										{/each}
										<th class="bg-base-200 text-base-content w-12 text-center font-bold"
											>{$t('lineup_bench')}</th
										>
									</tr>
								</thead>
								<tbody>
									{#each battingOrder as playerId}
										{@const player = getPlayer(playerId)}
										{#if player}
											{@const benchCount = getOptionBenchCount(
												activeOption.assignments,
												player.id
											)}
											<tr class="hover:bg-base-200/50">
												<td
													class="bg-base-100 text-base-content border-base-300 sticky left-0 z-10 border-r font-medium"
												>
													<div class="flex items-center gap-2">
														<span class="text-base-content/50 w-6 text-right text-xs"
															>#{player.jersey}</span
														>
														<span class="truncate">{player.first_name} {player.last_name}</span>
													</div>
												</td>
												{#each Array(numInnings) as _, inn}
													{@const pos = getOptionPosition(
														activeOption.assignments,
														player.id,
														inn + 1
													)}
													<td
														class="border-base-200 border-r text-center last:border-r-0 {pos === 0
															? 'text-base-content/40'
															: pos === 1
																? 'text-warning font-bold'
																: 'font-semibold'}"
													>
														{pos !== null ? POSITIONS[pos] : '—'}
													</td>
												{/each}
												<td
													class="text-center font-bold {benchCount > 1
														? 'text-warning'
														: 'text-base-content/60'}"
												>
													{benchCount}
												</td>
											</tr>
										{/if}
									{/each}
								</tbody>
								<tfoot class="bg-base-300 font-bold">
									<tr>
										<td
											class="bg-base-300 text-base-content border-base-300 sticky left-0 border-r py-2 pr-4 text-right text-sm font-bold"
										>
											{$t('lineup_total_points')}
										</td>
										{#each Array(numInnings) as _, inn}
											<td
												class="text-primary border-base-200 border-r text-center text-sm font-bold last:border-r-0"
											>
												{getOptionInningPoints(activeOption.assignments, inn + 1)}
											</td>
										{/each}
										<td></td>
									</tr>
								</tfoot>
							</table>
						</div>
					{/if}

					<div class="modal-action mt-4 shrink-0">
						<button class="btn btn-ghost" onclick={closeSolveOptions} disabled={applyingOption}>
							{$t('lineup_solve_cancel')}
						</button>
						<button
							class="btn btn-primary"
							disabled={applyingOption || !activeOption}
							onclick={() => activeOption && applySolveOption(activeOption)}
						>
							{#if applyingOption}
								<span class="loading loading-spinner loading-xs"></span>
							{/if}
							{$t('lineup_solve_apply')}
						</button>
					</div>
				</div>
				<button
					class="modal-backdrop"
					aria-label={$t('lineup_solve_cancel')}
					onclick={closeSolveOptions}
				></button>
			</div>
		{/if}

		{#if game}
			<div
				class="alert bg-base-100 border-base-300 flex items-center justify-between rounded-lg border py-3 shadow-sm"
			>
				<div class="flex items-center gap-2">
					<span class="badge badge-md {modeBadgeClass(game.mode)}">
						{$t(MODE_LABELS[game.mode] ?? game.mode)}
					</span>
					<span class="text-base-content/70 text-sm">
						{$t(MODE_DESCS[game.mode] ?? game.mode)}
					</span>
				</div>
			</div>
		{/if}

		{#if !loading}
			<div class="card bg-base-100 border-base-300 overflow-hidden border shadow-xl">
				<div class="overflow-x-auto">
					<table class="table-sm table-pin-rows table-pin-cols table w-full">
						<thead class="bg-base-200">
							<tr>
								<th class="bg-base-300 text-base-content sticky left-0 z-20 w-64 font-bold">
									{$t('lineup_order_player')}
								</th>
								{#each Array(numInnings) as _, inn}
									<th class="bg-base-200 text-base-content w-24 text-center font-bold">
										<div class="flex flex-col items-center justify-center gap-1 py-1">
											<span>{$t('lineup_inning', { number: inn + 1 })}</span>
											<button
												onclick={() => toggleInningLock(inn + 1)}
												class="btn btn-xs bg-base-100/50 border-base-300 hover:bg-base-300 h-6 min-h-0 border px-2 transition-colors {isInningLocked(
													inn + 1
												)
													? 'text-warning border-warning/30'
													: 'text-base-content/50'}"
												title={isInningLocked(inn + 1)
													? $t('lineup_unlock_inning')
													: $t('lineup_lock_inning')}
											>
												{isInningLocked(inn + 1) ? '🔓' : '🔒'}
											</button>
										</div>
									</th>
								{/each}
								<th class="bg-base-200 text-base-content w-16 text-center font-bold"
									>{$t('lineup_bench')}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each battingOrder as playerId, idx}
								{@const player = getPlayer(playerId)}
								{@const avail = availability.find((a) => a.player_id === playerId)}
								{#if player}
									{@const benchCount = Array.from({ length: numInnings }, (_, i) =>
										getCellPosition(player.id, i + 1)
									).filter((p) => p === 0).length}
									<tr
										data-row-index={idx}
										draggable={true}
										ondragstart={(e) => onDragStart(e, idx)}
										ondragover={(e) => onDragOver(e, idx)}
										ondragleave={onDragLeave}
										ondrop={(e) => onDrop(e, idx)}
										ondragend={onDragEnd}
										class="hover:bg-base-200/50 group transition-colors
											{dragOverIndex === idx && dragIndex !== idx ? 'bg-primary/10 border-primary border-t-2' : ''}
											{dragIndex === idx ? 'opacity-40' : ''}"
									>
										<td
											class="bg-base-100 text-base-content border-base-300 sticky left-0 z-10 border-r font-medium"
										>
											<div
												class="flex cursor-grab touch-none items-center gap-2 select-none active:cursor-grabbing"
												role="button"
												tabindex="0"
												ontouchstart={(e) => handleTouchStart(e, idx)}
												ontouchmove={handleTouchMove}
												ontouchend={handleTouchEnd}
											>
												<!-- Drag handle -->
												<span
													class="text-base-content/40 flex-shrink-0 text-lg"
													aria-hidden="true">⠿</span
												>
												<!-- Player info -->
												<span class="text-base-content/50 w-6 flex-shrink-0 text-right text-xs"
													>#{player.jersey}</span
												>
												<span class="truncate md:hidden"
													>{player.first_name} {player.last_name.charAt(0)}.</span
												>
												<span class="hidden truncate md:inline"
													>{player.first_name} {player.last_name}</span
												>
												{#if player.is_substitute}
													<span class="badge badge-xs badge-neutral ml-1 text-[9px] uppercase"
														>{$t('lineup_sub')}</span
													>
												{/if}

												{#if avail && avail.status !== 'available'}
													<span
														class="badge badge-xs {avail.status === 'late'
															? 'badge-warning'
															: 'badge-error'} text-[9px] uppercase"
													>
														{statusLabel(avail.status)}
													</span>
												{/if}
												{#if avail && avail.injury_inning}
													<span
														class="badge badge-xs badge-error text-[9px] uppercase"
														title="Injured in Inning {avail.injury_inning}"
														>🏥 INN {avail.injury_inning}</span
													>
												{/if}

												<!-- Mobile tap buttons: move up/down in batting order -->
												<div class="ml-auto flex flex-col md:hidden">
													<button
														class="btn btn-ghost btn-xs h-5 min-h-0 px-1"
														disabled={idx === 0}
														onclick={(e) => {
															e.stopPropagation();
															reorderBattingOrder(idx, idx - 1);
														}}
														title={$t('lineup_tap_move_up')}
													>
														<span class="text-base">↑</span>
													</button>
													<button
														class="btn btn-ghost btn-xs h-5 min-h-0 px-1"
														disabled={idx === battingOrder.length - 1}
														onclick={(e) => {
															e.stopPropagation();
															reorderBattingOrder(idx, idx + 1);
														}}
														title={$t('lineup_tap_move_down')}
													>
														<span class="text-base">↓</span>
													</button>
												</div>
											</div>
										</td>
										{#each Array(numInnings) as _, inn}
											{@const pos = getCellPosition(player.id, inn + 1)}
											{@const locked = isLocked(player.id, inn + 1)}
											<td
												class="border-base-200 border-r text-center last:border-r-0 {locked
													? 'locked-cell'
													: ''} {isInjured(player.id, inn + 1) ? 'bg-error/10' : ''}"
											>
												{#if injuryMode}
													<button
														class="hover:bg-error/20 flex h-full min-h-[30px] w-full items-center justify-center transition-colors"
														onclick={() => toggleInjury(player.id, inn + 1)}
													>
														{#if isInjured(player.id, inn + 1)}
															<span class="text-error" title="Injured">🏥</span>
														{:else}
															<span class="opacity-20 hover:opacity-100">🩹</span>
														{/if}
													</button>
												{:else if isInjured(player.id, inn + 1)}
													<div
														class="text-error mx-auto w-16 cursor-not-allowed text-center text-xs font-bold"
													>
														🏥 {$t('lineup_injured_bench')}
													</div>
												{:else}
													<div class="flex flex-col items-center gap-0.5">
														<select
															value={pos?.toString() ?? ''}
															onchange={(e) =>
																setCell(player.id, inn + 1, parseInt(e.currentTarget.value))}
															class="select select-bordered select-xs w-16 {locked
																? 'select-warning locked-position-select font-bold'
																: ''}"
														>
															<option value="">—</option>
															{#each Object.entries(POSITIONS) as [val, label]}
																<option value={val} disabled={val === '1' && player.is_substitute}
																	>{label}</option
																>
															{/each}
														</select>
													</div>
												{/if}
											</td>
										{/each}
										<td
											class="text-center font-bold {benchCount > 1
												? 'text-warning'
												: 'text-base-content/60'}"
										>
											{benchCount}
										</td>
									</tr>
								{/if}
							{/each}
						</tbody>
						<tfoot class="bg-base-300 font-bold">
							<tr>
								<td
									class="bg-base-300 text-base-content border-base-300 sticky left-0 border-r py-3 pr-4 text-right font-bold"
								>
									{$t('lineup_total_points')}
								</td>
								{#each Array(numInnings) as _, inn}
									<td
										class="text-primary border-base-200 border-r text-center font-bold last:border-r-0"
									>
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
			<div class="card bg-base-100 border-base-300 border p-5 shadow-xl">
				<h3 class="text-md text-base-content border-base-200 mb-3 border-b pb-1 font-bold">
					{$t('lineup_validation_title')}
				</h3>
				<div class="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
					{#each Array(numInnings) as _, inn}
						{@const assigned = lineup.filter(
							(l) => l.inning === inn + 1 && l.position > 0 && availablePlayerIds.has(l.player_id)
						).length}
						{@const benched = lineup.filter(
							(l) => l.inning === inn + 1 && l.position === 0 && availablePlayerIds.has(l.player_id)
						).length}
						<div class="flex flex-wrap items-center gap-2">
							<span class="text-base-content/80 font-semibold"
								>{$t('lineup_inning', { number: inn + 1 })}:</span
							>
							<span
								class="badge {assigned === 9
									? 'badge-success text-success-content'
									: 'badge-warning'} badge-sm font-bold"
							>
								{$t('lineup_fielders', { count: assigned })}
							</span>
							<span class="badge badge-ghost badge-sm"
								>{$t('lineup_benched', { count: benched })}</span
							>
							{#each [1, 2, 3, 4, 5, 6, 7, 8, 9] as pos}
								{@const count = getPositionCount(inn + 1, pos)}
								{#if count > 1}
									<span class="badge badge-error badge-sm font-bold"
										>⚠ {POSITIONS[pos]} ×{count}</span
									>
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
	<LineupPrintCard {game} {team} {players} {battingOrder} {lineup} {availability} />
</div>

<div class="hidden {printTarget === 'defense' ? 'print:block' : 'print:hidden'}">
	<DefensivePositionsPrint
		{game}
		{team}
		{players}
		{battingOrder}
		{lineup}
		{availability}
		{numInnings}
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
