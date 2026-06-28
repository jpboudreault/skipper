<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t, translate, formatLocaleDate } from '$lib/i18n';
	import { waitForActiveTeamId } from '$lib/teamContext';
	import { formatOpponentMatchup, homeAwayBadgeClass } from '$lib/games';

	let dashboardData: any = $state(null);
	let loading = $state(true);
	let error = $state('');

	const dateFormatOptions: Intl.DateTimeFormatOptions = {
		weekday: 'short',
		month: 'short',
		day: 'numeric'
	};

	const WARMUP_THROTTLE_MS = 6 * 60 * 60 * 1000;

	function shouldWarmup(teamId: string): boolean {
		const raw = sessionStorage.getItem(`dashboardWarmup:${teamId}`);
		if (!raw) return true;
		const last = parseInt(raw, 10);
		return Number.isNaN(last) || Date.now() - last > WARMUP_THROTTLE_MS;
	}

	function markWarmedUp(teamId: string) {
		sessionStorage.setItem(`dashboardWarmup:${teamId}`, String(Date.now()));
	}

	onMount(async () => {
		const teamId = await waitForActiveTeamId();
		if (!teamId) {
			loading = false;
			return;
		}

		try {
			if (shouldWarmup(teamId)) {
				await apiFetch(`/teams/${teamId}/stats/dashboard/warmup`, { method: 'POST' });
				markWarmedUp(teamId);
			}

			const res = await apiFetch(`/teams/${teamId}/stats/dashboard`);
			if (res.ok) {
				dashboardData = await res.json();
			} else {
				error = translate('dashboard_failed_load');
			}
		} catch (e) {
			error = translate('dashboard_error_connecting');
			console.error(e);
		} finally {
			loading = false;
		}
	});
</script>

<div class="mx-auto max-w-7xl space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-base-content text-3xl font-extrabold">{$t('dashboard_title')}</h1>
		<a href="/stats" class="btn btn-primary btn-sm shadow-md">{$t('dashboard_full_season_stats')}</a
		>
	</div>

	{#if loading}
		<div class="flex justify-center p-12">
			<span class="loading loading-spinner loading-lg text-primary"></span>
		</div>
	{:else if error}
		<div class="alert alert-error shadow-sm">
			<span>{error}</span>
		</div>
	{:else if dashboardData}
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
			<!-- Left Column: Games -->
			<div class="space-y-6 lg:col-span-1">
				<!-- Last Game -->
				<div class="card bg-base-100 border-base-300 border shadow-xl">
					<div class="card-body p-6">
						<h2 class="card-title border-base-200 border-b pb-2 text-lg">
							{$t('dashboard_last_game_result')}
						</h2>
						{#if dashboardData.last_game}
							<div class="mt-2 text-center">
								<div
									class="text-base-content/60 mb-2 text-sm font-semibold tracking-wider uppercase"
								>
									{formatLocaleDate(dashboardData.last_game.date, dateFormatOptions)}
								</div>
								<div class="flex items-center justify-center gap-4 text-2xl font-black">
									<div class="flex flex-col items-center">
										<span class="text-base-content/80 mb-1 text-sm"
											>{dashboardData.last_game.home_away === 'H'
												? dashboardData.team_name
												: dashboardData.last_game.opponent}</span
										>
										<span
											class={dashboardData.last_game.home_away === 'H'
												? dashboardData.last_game.result_runs_for >
													dashboardData.last_game.result_runs_against
													? 'text-success'
													: ''
												: dashboardData.last_game.result_runs_against >
													  dashboardData.last_game.result_runs_for
													? 'text-success'
													: ''}
										>
											{dashboardData.last_game.home_away === 'H'
												? dashboardData.last_game.result_runs_for
												: dashboardData.last_game.result_runs_against}
										</span>
									</div>
									<span class="text-base-content/30">-</span>
									<div class="flex flex-col items-center">
										<span class="text-base-content/80 mb-1 text-sm"
											>{dashboardData.last_game.home_away === 'A'
												? dashboardData.team_name
												: dashboardData.last_game.opponent}</span
										>
										<span
											class={dashboardData.last_game.home_away === 'A'
												? dashboardData.last_game.result_runs_for >
													dashboardData.last_game.result_runs_against
													? 'text-success'
													: ''
												: dashboardData.last_game.result_runs_against >
													  dashboardData.last_game.result_runs_for
													? 'text-success'
													: ''}
										>
											{dashboardData.last_game.home_away === 'A'
												? dashboardData.last_game.result_runs_for
												: dashboardData.last_game.result_runs_against}
										</span>
									</div>
								</div>
								<div class="mt-4">
									<a
										href="/games/{dashboardData.last_game.id}/batting"
										class="btn btn-outline btn-xs">{$t('dashboard_box_score')}</a
									>
								</div>
							</div>
						{:else}
							<p class="text-base-content/50 py-4 italic">{$t('dashboard_no_completed_games')}</p>
						{/if}
					</div>
				</div>

				<!-- Upcoming Games -->
				<div class="card bg-base-100 border-base-300 border shadow-xl">
					<div class="card-body p-6">
						<div class="border-base-200 mb-4 flex items-center justify-between border-b pb-2">
							<h2 class="card-title text-lg">{$t('dashboard_upcoming_games')}</h2>
							<a href="/games?tab=pitching-plan" class="btn btn-ghost btn-xs text-primary"
								>{$t('dashboard_pitching_plan')}</a
							>
						</div>

						{#if dashboardData.upcoming_games && dashboardData.upcoming_games.length > 0}
							<div class="space-y-4">
								{#each dashboardData.upcoming_games as game}
									<div class="bg-base-200/50 border-base-200 rounded-lg border p-3">
										<div class="mb-2 flex items-center justify-between">
											<span class="font-bold">{formatLocaleDate(game.date, dateFormatOptions)}</span
											>
											<span class="badge badge-sm {homeAwayBadgeClass(game.home_away)}"
												>{game.home_away === 'H' ? $t('common_home') : $t('common_away')}</span
											>
										</div>
										<a
											href="/games/{game.id}"
											class="hover:text-primary mb-3 block text-lg font-bold transition-colors"
										>
											{formatOpponentMatchup(game.home_away, game.opponent, {
												vsLabel: $t('dashboard_vs'),
												tbd: $t('dashboard_tbd')
											})}
											{#if game.intel?.available && game.intel.record}
												<span class="text-base-content/70 ml-1 font-semibold"
													>({game.intel.record})</span
												>
											{/if}
										</a>
										<div class="flex flex-wrap gap-2">
											<a
												href="/games/{game.id}"
												class="btn btn-primary btn-sm min-w-[5.5rem] flex-1"
												>{$t('dashboard_overview')}</a
											>
											<a
												href="/games/{game.id}/lineup"
												class="btn btn-outline btn-sm min-w-[5.5rem] flex-1"
												>{$t('dashboard_lineup')}</a
											>
											<a
												href="/games/{game.id}/availability"
												class="btn btn-outline btn-sm min-w-[5.5rem] flex-1"
												>{$t('dashboard_availabilities')}</a
											>
										</div>
									</div>
								{/each}
							</div>
							<div class="mt-4 text-center">
								<a
									href="/games?tab=upcoming"
									class="text-primary text-sm font-semibold hover:underline"
									>{$t('dashboard_view_all_games')}</a
								>
							</div>
						{:else}
							<p class="text-base-content/50 italic">{$t('dashboard_no_upcoming')}</p>
						{/if}
					</div>
				</div>
			</div>

			<!-- Right Column: Recent Stats -->
			<div class="space-y-6 lg:col-span-2">
				<div class="card bg-base-100 border-base-300 h-full border shadow-xl">
					<div class="card-body p-6">
						<div class="border-base-200 mb-4 flex items-center justify-between border-b pb-2">
							<div>
								<h2 class="card-title text-xl">{$t('dashboard_individual_stats')}</h2>
								<p class="text-base-content/60 text-sm">{$t('dashboard_top_performers')}</p>
							</div>
							<a href="/stats" class="btn btn-ghost btn-sm text-primary"
								>{$t('dashboard_full_season')}</a
							>
						</div>

						<div class="mt-4 grid grid-cols-1 gap-8 md:grid-cols-2">
							<!-- Batting Leaders -->
							<div>
								<h3 class="mb-3 flex items-center gap-2 text-lg font-bold">
									<span class="text-2xl">⚾</span>
									{$t('dashboard_top_hitters')}
								</h3>
								{#if dashboardData.recent_batting && dashboardData.recent_batting.length > 0}
									<div class="overflow-x-auto">
										<table class="table-sm table">
											<thead class="bg-base-200 text-base-content">
												<tr>
													<th>{$t('common_player')}</th>
													<th class="text-center">AVG</th>
													<th class="text-center">OBP</th>
													<th class="text-primary text-center font-bold">OPS</th>
												</tr>
											</thead>
											<tbody>
												{#each dashboardData.recent_batting as stat}
													<tr>
														<td class="font-semibold">{stat.name}</td>
														<td class="text-center">{stat.avg.toFixed(3).replace(/^0/, '')}</td>
														<td class="text-center">{stat.obp.toFixed(3).replace(/^0/, '')}</td>
														<td class="text-primary text-center font-bold"
															>{stat.ops.toFixed(3).replace(/^0/, '')}</td
														>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{:else}
									<p class="text-base-content/50 text-sm italic">
										{$t('dashboard_no_batting_stats')}
									</p>
								{/if}
							</div>

							<!-- Pitching Leaders -->
							<div>
								<h3 class="mb-3 flex items-center gap-2 text-lg font-bold">
									<span class="text-2xl">🔥</span>
									{$t('dashboard_top_pitchers')}
								</h3>
								{#if dashboardData.recent_pitching && dashboardData.recent_pitching.length > 0}
									<div class="overflow-x-auto">
										<table class="table-sm table">
											<thead class="bg-base-200 text-base-content">
												<tr>
													<th>{$t('common_player')}</th>
													<th class="text-center">K/9</th>
													<th class="text-center">RA/9</th>
													<th class="text-primary text-center font-bold">IP</th>
												</tr>
											</thead>
											<tbody>
												{#each dashboardData.recent_pitching as stat}
													<tr>
														<td class="font-semibold">{stat.name}</td>
														<td class="text-center">{stat.k_9.toFixed(1)}</td>
														<td class="text-center">{stat.r_9.toFixed(2)}</td>
														<td class="text-primary text-center font-bold">{stat.ip_display}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{:else}
									<p class="text-base-content/50 text-sm italic">
										{$t('dashboard_no_pitching_stats')}
									</p>
								{/if}
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
