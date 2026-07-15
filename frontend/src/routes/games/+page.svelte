<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { apiFetch } from '$lib/api';
	import { t, translate, formatLocaleDate } from '$lib/i18n';
	import {
		formatOpponentMatchup,
		splitGames,
		gameResult,
		homeAwayBadgeClass,
		resultBadgeClass,
		scheduleStatusBadgeClass,
		scheduleStatusLabelKey
	} from '$lib/games';
	import { activeTeam } from '$lib/teamContext';

	let games: any[] = $state([]);
	let intelByGameId: Record<number, any> = $state({});
	let loading = $state(true);
	let syncing = $state(false);
	let syncMessage = $state('');
	let showCreate = $state(false);
	let activeTab = $state('upcoming');
	let pitchingPlanData: any = $state(null);
	let loadingPitching = $state(false);
	let newGame = $state({
		date: new Date().toISOString().split('T')[0],
		game_number: '',
		opponent: '',
		venue: '',
		home_away: 'H',
		innings_played: null as number | null,
		mode: 'compete',
		game_type: 'season',
		league: '',
		notes: ''
	});

	const gameTypeKeys: Record<string, string> = {
		season: 'games_type_season',
		postseason: 'games_type_postseason',
		tournament: 'games_type_tournament'
	};

	const modeKeys: Record<string, string> = {
		compete: 'games_mode_compete',
		develop: 'games_mode_develop',
		optimal: 'games_mode_optimal'
	};

	const dateFormatOptions: Intl.DateTimeFormatOptions = {
		weekday: 'short',
		month: 'short',
		day: 'numeric'
	};

	const resultLabelKeys: Record<string, string> = {
		win: 'common_win',
		loss: 'common_loss',
		tie: 'common_tie'
	};

	$effect(() => {
		if ($activeTeam && !newGame.league) {
			newGame.league = $activeTeam.default_league || '';
		}
	});

	let { upcoming, past } = $derived(splitGames(games));
	let nextGame = $derived(upcoming[0] ?? null);
	let laterUpcoming = $derived(upcoming.slice(1));

	function setActiveTab(tab: string) {
		activeTab = tab;
		const url = new URL($page.url);
		if (tab === 'upcoming') {
			url.searchParams.delete('tab');
		} else {
			url.searchParams.set('tab', tab);
		}
		goto(url.pathname + url.search, { replaceState: true, keepFocus: true, noScroll: true });
	}

	function intelForGame(gameId: number) {
		return intelByGameId[gameId] ?? null;
	}

	function gameTypeBadgeClass(gameType: string) {
		if (gameType === 'postseason') return 'badge-secondary';
		if (gameType === 'tournament') return 'badge-warning';
		return 'badge-neutral';
	}

	async function fetchUpcomingIntel() {
		try {
			const res = await apiFetch('/games/upcoming-intel');
			if (!res.ok) return;
			const upcomingWithIntel = await res.json();
			const map: Record<number, any> = {};
			for (const game of upcomingWithIntel) {
				if (game.id != null) map[game.id] = game.intel;
			}
			intelByGameId = map;
		} catch (e) {
			console.error(e);
		}
	}

	async function fetchData() {
		try {
			const gamesRes = await apiFetch('/games/');
			if (gamesRes.ok) games = await gamesRes.json();
			await fetchUpcomingIntel();
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		const tab = $page.url.searchParams.get('tab');
		if (tab === 'pitching-plan' || tab === 'past' || tab === 'upcoming') {
			activeTab = tab;
		}
		fetchData();
		if (tab === 'pitching-plan') {
			fetchPitchingPlan();
		}
	});

	async function createGame() {
		try {
			const body: any = { ...newGame };
			if (!body.innings_played) delete body.innings_played;
			if (!body.game_number) delete body.game_number;
			const res = await apiFetch('/games/', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(body)
			});
			if (res.ok) {
				const created = await res.json();
				goto(`/games/${created.id}`);
			}
		} catch (e) {
			console.error(e);
			alert(translate('games_failed_create'));
		}
	}

	async function syncSchedule() {
		syncing = true;
		syncMessage = '';
		try {
			const res = await apiFetch('/games/sync-schedule', { method: 'POST' });
			const payload = await res.json();
			if (res.ok) {
				syncMessage = translate('games_sync_success', payload);
				await fetchData();
			} else {
				syncMessage = payload.detail || translate('games_sync_failed');
			}
		} catch (e) {
			console.error(e);
			syncMessage = translate('games_sync_failed');
		} finally {
			syncing = false;
		}
	}

	async function fetchPitchingPlan() {
		setActiveTab('pitching-plan');
		if (pitchingPlanData) return;

		loadingPitching = true;
		try {
			const activeId = $activeTeam?.id;
			if (!activeId) return;
			const res = await apiFetch(`/teams/${activeId}/stats/pitching-plan`);
			if (res.ok) {
				pitchingPlanData = await res.json();
			}
		} catch (e) {
			console.error(e);
		} finally {
			loadingPitching = false;
		}
	}
</script>

{#snippet upcomingGameCard(game: any, hero = false)}
	{@const intel = intelForGame(game.id)}
	<div
		class="{hero
			? 'bg-primary/5 border-primary border-2 shadow-lg'
			: 'bg-base-200/50 border-base-200'} rounded-lg border p-4"
	>
		<div class="mb-2 flex flex-wrap items-center justify-between gap-2">
			<div class="flex flex-wrap items-center gap-2">
				{#if hero}
					<span class="badge badge-primary badge-sm uppercase">{$t('games_next_game')}</span>
				{/if}
				<span class="font-bold {hero ? 'text-lg' : ''}"
					>{formatLocaleDate(game.date, dateFormatOptions)}</span
				>
				{#if game.game_number}
					<span class="text-base-content/60 text-sm">#{game.game_number}</span>
				{/if}
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<span class="badge badge-sm {homeAwayBadgeClass(game.home_away)}"
					>{game.home_away === 'H' ? $t('common_home') : $t('common_away')}</span
				>
				<span class="badge badge-sm {gameTypeBadgeClass(game.game_type)}">
					{$t(gameTypeKeys[game.game_type] ?? game.game_type)}
				</span>
				{#if scheduleStatusLabelKey(game.schedule_status)}
					<span class="badge badge-sm {scheduleStatusBadgeClass(game.schedule_status)}">
						{$t(scheduleStatusLabelKey(game.schedule_status))}
					</span>
				{/if}
			</div>
		</div>
		<a
			href="/games/{game.id}"
			class="hover:text-primary mb-3 block font-bold transition-colors {hero
				? 'text-2xl'
				: 'text-lg'}"
		>
			{formatOpponentMatchup(game.home_away, game.opponent, {
				vsLabel: $t('dashboard_vs'),
				tbd: $t('dashboard_tbd')
			})}
			{#if intel?.available && intel.record}
				<span class="text-base-content/70 ml-1 font-semibold {hero ? 'text-xl' : ''}"
					>({intel.record})</span
				>
			{/if}
		</a>
		<div class="flex flex-wrap gap-2">
			<a
				href="/games/{game.id}"
				class="btn btn-primary btn-sm min-w-[5.5rem] flex-1 {hero ? 'btn-md' : ''}"
				>{$t('dashboard_overview')}</a
			>
			<a
				href="/games/{game.id}/lineup"
				class="btn btn-outline btn-sm min-w-[5.5rem] flex-1 {hero ? 'btn-md' : ''}"
				>{$t('dashboard_lineup')}</a
			>
			<a
				href="/games/{game.id}/availability"
				class="btn btn-outline btn-sm min-w-[5.5rem] flex-1 {hero ? 'btn-md' : ''}"
				>{$t('dashboard_availabilities')}</a
			>
		</div>
	</div>
{/snippet}

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
	<div class="mb-6 sm:flex sm:items-center sm:justify-between">
		<div>
			<h1 class="text-base-content text-3xl font-bold">{$t('games_title')}</h1>
			<p class="text-base-content/70 mt-2 text-sm">
				{$t('games_description')}
			</p>
		</div>
		<div class="mt-4 flex flex-wrap gap-2 sm:mt-0">
			<button
				onclick={() => (showCreate = !showCreate)}
				class="btn {showCreate ? 'btn-neutral' : 'btn-primary'} shadow-md"
			>
				{showCreate ? $t('games_cancel') : $t('games_new_game')}
			</button>
			{#if $activeTeam?.integration_version}
				<button
					onclick={syncSchedule}
					class="btn btn-outline btn-secondary shadow-md"
					disabled={syncing}
				>
					{syncing ? $t('games_syncing') : $t('games_sync_schedule')}
				</button>
			{/if}
		</div>
	</div>
	{#if syncMessage}
		<p class="text-base-content/70 mb-4 text-sm">{syncMessage}</p>
	{/if}

	<div class="tabs tabs-boxed bg-base-100 border-base-300 mb-6 max-w-lg border p-1 shadow-sm">
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'upcoming'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => setActiveTab('upcoming')}
		>
			{$t('games_upcoming')}
			{#if !loading && upcoming.length > 0}
				<span class="badge badge-xs badge-primary ml-1">{upcoming.length}</span>
			{/if}
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'past'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => setActiveTab('past')}
		>
			{$t('games_past')}
			{#if !loading && past.length > 0}
				<span class="badge badge-xs badge-neutral ml-1">{past.length}</span>
			{/if}
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'pitching-plan'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={fetchPitchingPlan}
		>
			{$t('games_pitching_plan')}
		</button>
	</div>

	{#if activeTab === 'upcoming'}
		{#if showCreate}
			<div class="card bg-base-100 border-base-300 mb-8 border p-6 shadow-xl">
				<h3 class="text-base-content mb-4 text-lg font-bold">{$t('games_create_new_game')}</h3>
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
					<div class="form-control">
						<label for="date" class="label"
							><span class="label-text">{$t('common_date')}</span></label
						>
						<input
							id="date"
							type="date"
							bind:value={newGame.date}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="game_number" class="label"
							><span class="label-text">{$t('games_game_number')}</span></label
						>
						<input
							id="game_number"
							type="text"
							bind:value={newGame.game_number}
							placeholder={$t('games_placeholder_game_number')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="opponent" class="label"
							><span class="label-text">{$t('games_opponent')}</span></label
						>
						<input
							id="opponent"
							type="text"
							bind:value={newGame.opponent}
							placeholder={$t('games_placeholder_opponent')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="venue" class="label"
							><span class="label-text">{$t('games_venue')}</span></label
						>
						<input
							id="venue"
							type="text"
							bind:value={newGame.venue}
							placeholder={$t('games_placeholder_venue')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="home_away" class="label"
							><span class="label-text">{$t('games_home_away')}</span></label
						>
						<select
							id="home_away"
							bind:value={newGame.home_away}
							class="select select-bordered select-sm w-full"
						>
							<option value="H">{$t('common_home')}</option>
							<option value="A">{$t('common_away')}</option>
						</select>
					</div>
					<div class="form-control">
						<label for="mode" class="label"
							><span class="label-text">{$t('games_optimizer_mode')}</span></label
						>
						<select
							id="mode"
							bind:value={newGame.mode}
							class="select select-bordered select-sm w-full"
						>
							<option value="compete">{$t('games_mode_compete_full')}</option>
							<option value="develop">{$t('games_mode_develop_full')}</option>
							<option value="optimal">{$t('games_mode_optimal_full')}</option>
						</select>
					</div>
					<div class="form-control">
						<label for="game_type" class="label"
							><span class="label-text">{$t('games_game_type')}</span></label
						>
						<select
							id="game_type"
							bind:value={newGame.game_type}
							class="select select-bordered select-sm w-full"
						>
							<option value="season">{$t('games_type_season')}</option>
							<option value="postseason">{$t('games_type_postseason')}</option>
							<option value="tournament">{$t('games_type_tournament')}</option>
						</select>
					</div>
					<div class="form-control">
						<label for="league" class="label"
							><span class="label-text">{$t('games_league')}</span></label
						>
						<input
							id="league"
							type="text"
							bind:value={newGame.league}
							placeholder={$t('games_placeholder_league')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
				</div>
				<div class="mt-6 flex justify-end">
					<button onclick={createGame} class="btn btn-success btn-sm"
						>{$t('games_create_game')}</button
					>
				</div>
			</div>
		{/if}

		<div class="card bg-base-100 border-base-300 border p-6 shadow-xl">
			{#if loading}
				<div class="py-16 text-center">
					<span class="loading loading-spinner loading-lg text-primary"></span>
					<p class="text-base-content/60 mt-2 text-sm">{$t('games_loading_games')}</p>
				</div>
			{:else if upcoming.length === 0}
				<div class="text-base-content/60 py-16 text-center">
					<p class="text-lg">{$t('games_no_upcoming')}</p>
				</div>
			{:else}
				<div class="space-y-4">
					{@render upcomingGameCard(nextGame, true)}
					{#each laterUpcoming as game}
						{@render upcomingGameCard(game)}
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'past'}
		<div class="card bg-base-100 border-base-300 overflow-hidden border shadow-xl">
			{#if loading}
				<div class="p-16 text-center">
					<span class="loading loading-spinner loading-lg text-primary"></span>
					<p class="text-base-content/60 mt-2 text-sm">{$t('games_loading_games')}</p>
				</div>
			{:else if past.length === 0}
				<div class="text-base-content/60 py-16 text-center">
					<p class="text-lg">{$t('games_no_past')}</p>
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="table w-full">
						<thead class="bg-base-200">
							<tr>
								<th class="text-base-content font-bold">{$t('common_date')}</th>
								<th class="text-base-content w-20 font-bold">{$t('games_game_number')}</th>
								<th class="text-base-content font-bold">{$t('games_opponent')}</th>
								<th class="text-base-content w-20 font-bold">{$t('games_home_away')}</th>
								<th class="text-base-content font-bold">{$t('games_details')}</th>
								<th class="text-base-content w-32 font-bold">{$t('games_score')}</th>
								<th class="text-base-content w-24 font-bold">{$t('games_result')}</th>
							</tr>
						</thead>
						<tbody>
							{#each past as game}
								{@const result = gameResult(game.result_runs_for, game.result_runs_against)}
								<tr
									class="hover:bg-base-200/50 cursor-pointer transition"
									onclick={() => goto(`/games/${game.id}`)}
								>
									<td class="text-base-content font-medium">{game.date}</td>
									<td class="text-base-content text-center">{game.game_number || '—'}</td>
									<td class="text-base-content"
										>{formatOpponentMatchup(game.home_away, game.opponent, {
											vsLabel: $t('dashboard_vs'),
											tbd: '—'
										})}</td
									>
									<td>
										{#if game.home_away === 'H' || game.home_away === 'A'}
											<span class="badge badge-sm {homeAwayBadgeClass(game.home_away)}">
												{game.home_away === 'H' ? $t('common_home') : $t('common_away')}
											</span>
										{:else}
											<span class="text-base-content/50">—</span>
										{/if}
									</td>
									<td>
										<span
											class="badge badge-sm {game.mode === 'optimal'
												? 'badge-warning'
												: game.mode === 'compete'
													? 'badge-info'
													: 'badge-success'} mr-1"
										>
											{$t(modeKeys[game.mode] ?? game.mode)}
										</span>
										<span class="badge badge-sm badge-neutral">
											{$t(gameTypeKeys[game.game_type] ?? game.game_type)}
										</span>
										{#if scheduleStatusLabelKey(game.schedule_status)}
											<span
												class="badge badge-sm {scheduleStatusBadgeClass(game.schedule_status)} ml-1"
											>
												{$t(scheduleStatusLabelKey(game.schedule_status))}
											</span>
										{/if}
									</td>
									<td>
										{#if game.result_runs_for !== null && game.result_runs_against !== null}
											<span class="badge badge-outline"
												>{game.result_runs_for} - {game.result_runs_against}</span
											>
										{:else}
											<span class="text-base-content/50">—</span>
										{/if}
									</td>
									<td>
										{#if result}
											<span class="badge badge-sm {resultBadgeClass(result)} uppercase"
												>{$t(resultLabelKeys[result])}</span
											>
										{:else}
											<span class="text-base-content/50">—</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{/if}

	{#if activeTab === 'pitching-plan'}
		<div class="card bg-base-100 border-base-300 overflow-hidden border shadow-xl">
			{#if loadingPitching}
				<div class="p-16 text-center">
					<span class="loading loading-spinner loading-lg text-primary"></span>
					<p class="text-base-content/60 mt-2 text-sm">{$t('games_loading_pitching_plan')}</p>
				</div>
			{:else if !pitchingPlanData || pitchingPlanData.games.length === 0}
				<div class="text-base-content/60 py-16 text-center">
					<p class="text-lg">{$t('games_no_games_timeframe')}</p>
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="table-sm table w-full">
						<thead class="bg-base-200">
							<tr>
								<th class="text-base-content bg-base-200 sticky left-0 z-20 w-48 font-bold"
									>{$t('common_player')}</th
								>
								{#each pitchingPlanData.games as game}
									<th class="text-base-content border-base-300 border-l text-center font-bold">
										<div class="text-xs font-normal opacity-70">
											{new Date(game.date).toLocaleDateString(undefined, {
												month: 'short',
												day: 'numeric',
												timeZone: 'UTC'
											})}
										</div>
										<div
											class="mx-auto max-w-[100px] truncate"
											title={formatOpponentMatchup(game.home_away, game.opponent, {
												vsLabel: $t('dashboard_vs'),
												tbd: $t('dashboard_tbd')
											})}
										>
											{formatOpponentMatchup(game.home_away, game.opponent, {
												vsLabel: $t('dashboard_vs'),
												tbd: $t('dashboard_tbd')
											})}
										</div>
									</th>
								{/each}
								<th class="text-base-content border-base-300 border-l text-center font-bold"
									>{$t('common_total')}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each pitchingPlanData.players as player}
								{@const totalInns = pitchingPlanData.games.reduce(
									(acc: number, g: any) =>
										acc + (pitchingPlanData.pitching_innings[player.id]?.[g.id] || 0),
									0
								)}
								<tr class="hover:bg-base-200/50 transition">
									<td
										class="text-base-content bg-base-100 border-base-200 sticky left-0 z-10 border-r font-medium"
									>
										<span class="badge badge-sm badge-neutral mr-2">#{player.jersey}</span>
										{player.first_name}
										{player.last_name}
									</td>
									{#each pitchingPlanData.games as game}
										{@const inns = pitchingPlanData.pitching_innings[player.id]?.[game.id] || 0}
										<td
											class="border-base-200 border-l text-center {inns > 0
												? 'bg-primary/10 text-primary font-bold'
												: 'text-base-content/30'}"
										>
											{inns > 0 ? inns : '-'}
										</td>
									{/each}
									<td class="border-base-200 bg-base-200/50 border-l text-center font-bold">
										{totalInns}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{/if}
</div>
