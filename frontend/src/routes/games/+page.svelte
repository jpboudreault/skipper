<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { apiFetch } from '$lib/api';
	import { t, translate } from '$lib/i18n';

	let { data } = $props();
	const token = $derived(data.user?.token);

	let games: any[] = $state([]);
	let loading = $state(true);
	let showCreate = $state(false);
	let teams: any[] = $state([]);
	let activeTab = $state('schedule');
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
		develop: 'games_mode_develop'
	};

	async function fetchData() {
		try {
			const [gamesRes, teamsRes] = await Promise.all([apiFetch('/games/'), apiFetch('/teams/')]);
			if (gamesRes.ok) games = await gamesRes.json();
			if (teamsRes.ok) {
				teams = await teamsRes.json();
				const activeId = sessionStorage.getItem('activeTeamId');
				if (teams.length > 0) {
					const activeTeam = teams.find((t: any) => t.id.toString() === activeId) || teams[0];
					newGame.league = activeTeam.default_league || '';
				}
			}
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchData();
		if ($page.url.searchParams.get('tab') === 'pitching-plan') {
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

	async function deleteGame(id: number) {
		if (!confirm(translate('games_delete_game_confirm'))) return;
		try {
			await apiFetch(`/games/${id}`, {
				method: 'DELETE'
			});
			games = games.filter((g) => g.id !== id);
		} catch (e) {
			console.error(e);
		}
	}

	async function fetchPitchingPlan() {
		activeTab = 'pitching-plan';
		if (pitchingPlanData) return;

		loadingPitching = true;
		try {
			const activeId = sessionStorage.getItem('activeTeamId');
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

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
	<div class="mb-6 sm:flex sm:items-center sm:justify-between">
		<div>
			<h1 class="text-base-content text-3xl font-bold">{$t('games_title')}</h1>
			<p class="text-base-content/70 mt-2 text-sm">
				{$t('games_description')}
			</p>
		</div>
		<button
			onclick={() => (showCreate = !showCreate)}
			class="btn {showCreate ? 'btn-neutral' : 'btn-primary'} mt-4 shadow-md sm:mt-0"
		>
			{showCreate ? $t('games_cancel') : $t('games_new_game')}
		</button>
	</div>

	<div class="tabs tabs-boxed bg-base-100 border-base-300 mb-6 max-w-md border p-1 shadow-sm">
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'schedule'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => (activeTab = 'schedule')}
		>
			{$t('games_schedule')}
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

	{#if activeTab === 'schedule'}
		{#if showCreate}
			<div class="card bg-base-100 border-base-300 mb-8 border p-6 shadow-xl">
				<h3 class="text-base-content mb-4 text-lg font-bold">{$t('games_create_new_game')}</h3>
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
					<div class="form-control">
						<label for="date" class="label"><span class="label-text">{$t('common_date')}</span></label>
						<input
							id="date"
							type="date"
							bind:value={newGame.date}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="game_number" class="label"><span class="label-text">{$t('games_game_number')}</span></label>
						<input
							id="game_number"
							type="text"
							bind:value={newGame.game_number}
							placeholder={$t('games_placeholder_game_number')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="opponent" class="label"><span class="label-text">{$t('games_opponent')}</span></label>
						<input
							id="opponent"
							type="text"
							bind:value={newGame.opponent}
							placeholder={$t('games_placeholder_opponent')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="venue" class="label"><span class="label-text">{$t('games_venue')}</span></label>
						<input
							id="venue"
							type="text"
							bind:value={newGame.venue}
							placeholder={$t('games_placeholder_venue')}
							class="input input-bordered input-sm w-full"
						/>
					</div>
					<div class="form-control">
						<label for="home_away" class="label"><span class="label-text">{$t('games_home_away')}</span></label>
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
						<label for="mode" class="label"><span class="label-text">{$t('games_optimizer_mode')}</span></label>
						<select
							id="mode"
							bind:value={newGame.mode}
							class="select select-bordered select-sm w-full"
						>
							<option value="compete">{$t('games_mode_compete_full')}</option>
							<option value="develop">{$t('games_mode_develop_full')}</option>
						</select>
					</div>
					<div class="form-control">
						<label for="game_type" class="label"><span class="label-text">{$t('games_game_type')}</span></label>
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
						<label for="league" class="label"><span class="label-text">{$t('games_league')}</span></label>
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
					<button onclick={createGame} class="btn btn-success btn-sm">{$t('games_create_game')}</button>
				</div>
			</div>
		{/if}

		<div class="card bg-base-100 border-base-300 overflow-hidden border shadow-xl">
			{#if loading}
				<div class="p-16 text-center">
					<span class="loading loading-spinner loading-lg text-primary"></span>
					<p class="text-base-content/60 mt-2 text-sm">{$t('games_loading_games')}</p>
				</div>
			{:else if games.length === 0}
				<div class="text-base-content/60 py-16 text-center">
					<p class="text-lg">{$t('games_no_games')}</p>
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
								<th class="text-base-content w-24 text-right font-bold">{$t('common_actions')}</th>
							</tr>
						</thead>
						<tbody>
							{#each games as game}
								<tr
									class="hover:bg-base-200/50 cursor-pointer transition"
									onclick={() => goto(`/games/${game.id}`)}
								>
									<td class="text-base-content font-medium">{game.date}</td>
									<td class="text-base-content text-center">{game.game_number || '—'}</td>
									<td class="text-base-content">{game.opponent || '—'}</td>
									<td class="text-base-content">{game.home_away || '—'}</td>
									<td>
										<span
											class="badge badge-sm {game.mode === 'compete'
												? 'badge-info'
												: 'badge-success'} mr-1"
										>
											{$t(modeKeys[game.mode] ?? game.mode)}
										</span>
										<span class="badge badge-sm badge-neutral">
											{$t(gameTypeKeys[game.game_type] ?? game.game_type)}
										</span>
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
									<td class="text-right">
										<button
											onclick={(e) => {
												e.stopPropagation();
												deleteGame(game.id);
											}}
											class="btn btn-ghost btn-error btn-xs">{$t('common_delete')}</button
										>
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
										<div class="mx-auto max-w-[100px] truncate" title={game.opponent}>
											{game.opponent || $t('dashboard_tbd')}
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
