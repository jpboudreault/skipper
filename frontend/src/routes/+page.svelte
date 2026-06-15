<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t, translate, formatLocaleDate } from '$lib/i18n';

	let dashboardData: any = $state(null);
	let loading = $state(true);
	let error = $state('');

	const dateFormatOptions: Intl.DateTimeFormatOptions = {
		weekday: 'short',
		month: 'short',
		day: 'numeric'
	};

	onMount(async () => {
		// Wait a tiny bit for layout to set activeTeamId if needed
		setTimeout(async () => {
			const teamId = sessionStorage.getItem('activeTeamId');
			if (!teamId) {
				loading = false;
				return;
			}

			try {
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
		}, 100);
	});
</script>

<div class="max-w-7xl mx-auto space-y-6">
	<div class="flex items-center justify-between">
		<h1 class="text-3xl font-extrabold text-base-content">{$t('dashboard_title')}</h1>
		<a href="/stats" class="btn btn-primary btn-sm shadow-md">{$t('dashboard_full_season_stats')}</a>
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
		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">

			<!-- Left Column: Games -->
			<div class="lg:col-span-1 space-y-6">
				<!-- Last Game -->
				<div class="card bg-base-100 shadow-xl border border-base-300">
					<div class="card-body p-6">
						<h2 class="card-title text-lg border-b border-base-200 pb-2">{$t('dashboard_last_game_result')}</h2>
						{#if dashboardData.last_game}
							<div class="mt-2 text-center">
								<div class="text-sm text-base-content/60 font-semibold uppercase tracking-wider mb-2">
									{formatLocaleDate(dashboardData.last_game.date, dateFormatOptions)}
								</div>
								<div class="flex justify-center items-center gap-4 text-2xl font-black">
									<div class="flex flex-col items-center">
										<span class="text-base-content/80 text-sm mb-1">{dashboardData.last_game.home_away === 'H' ? dashboardData.team_name : dashboardData.last_game.opponent}</span>
										<span class={dashboardData.last_game.home_away === 'H' ?
											(dashboardData.last_game.result_runs_for > dashboardData.last_game.result_runs_against ? 'text-success' : '') :
											(dashboardData.last_game.result_runs_against > dashboardData.last_game.result_runs_for ? 'text-success' : '')}>
											{dashboardData.last_game.home_away === 'H' ? dashboardData.last_game.result_runs_for : dashboardData.last_game.result_runs_against}
										</span>
									</div>
									<span class="text-base-content/30">-</span>
									<div class="flex flex-col items-center">
										<span class="text-base-content/80 text-sm mb-1">{dashboardData.last_game.home_away === 'A' ? dashboardData.team_name : dashboardData.last_game.opponent}</span>
										<span class={dashboardData.last_game.home_away === 'A' ?
											(dashboardData.last_game.result_runs_for > dashboardData.last_game.result_runs_against ? 'text-success' : '') :
											(dashboardData.last_game.result_runs_against > dashboardData.last_game.result_runs_for ? 'text-success' : '')}>
											{dashboardData.last_game.home_away === 'A' ? dashboardData.last_game.result_runs_for : dashboardData.last_game.result_runs_against}
										</span>
									</div>
								</div>
								<div class="mt-4">
									<a href="/games/{dashboardData.last_game.id}/batting" class="btn btn-outline btn-xs">{$t('dashboard_box_score')}</a>
								</div>
							</div>
						{:else}
							<p class="text-base-content/50 italic py-4">{$t('dashboard_no_completed_games')}</p>
						{/if}
					</div>
				</div>

				<!-- Upcoming Games -->
				<div class="card bg-base-100 shadow-xl border border-base-300">
					<div class="card-body p-6">
						<div class="flex items-center justify-between border-b border-base-200 pb-2 mb-4">
							<h2 class="card-title text-lg">{$t('dashboard_upcoming_games')}</h2>
							<a href="/games?tab=pitching-plan" class="btn btn-ghost btn-xs text-primary">{$t('dashboard_pitching_plan')}</a>
						</div>

						{#if dashboardData.upcoming_games && dashboardData.upcoming_games.length > 0}
							<div class="space-y-4">
								{#each dashboardData.upcoming_games as game}
									<div class="bg-base-200/50 p-3 rounded-lg border border-base-200">
										<div class="flex justify-between items-center mb-2">
											<span class="font-bold">{formatLocaleDate(game.date, dateFormatOptions)}</span>
											<span class="badge badge-sm {game.home_away === 'H' ? 'badge-neutral' : 'badge-outline'}">{game.home_away === 'H' ? $t('common_home') : $t('common_away')}</span>
										</div>
										<div class="text-lg font-bold mb-3">{$t('dashboard_vs')} {game.opponent || $t('dashboard_tbd')}</div>
										<div class="flex gap-2">
											<a href="/games/{game.id}/lineup" class="btn btn-primary btn-sm flex-1">{$t('dashboard_lineup')}</a>
											<a href="/games/{game.id}/availability" class="btn btn-outline btn-sm flex-1">{$t('dashboard_availabilities')}</a>
										</div>
									</div>
								{/each}
							</div>
							<div class="mt-4 text-center">
								<a href="/games" class="text-primary text-sm font-semibold hover:underline">{$t('dashboard_view_all_games')}</a>
							</div>
						{:else}
							<p class="text-base-content/50 italic">{$t('dashboard_no_upcoming')}</p>
						{/if}
					</div>
				</div>
			</div>

			<!-- Right Column: Recent Stats -->
			<div class="lg:col-span-2 space-y-6">
				<div class="card bg-base-100 shadow-xl border border-base-300 h-full">
					<div class="card-body p-6">
						<div class="flex items-center justify-between mb-4 border-b border-base-200 pb-2">
							<div>
								<h2 class="card-title text-xl">{$t('dashboard_individual_stats')}</h2>
								<p class="text-sm text-base-content/60">{$t('dashboard_top_performers')}</p>
							</div>
							<a href="/stats" class="btn btn-ghost btn-sm text-primary">{$t('dashboard_full_season')}</a>
						</div>

						<div class="grid grid-cols-1 md:grid-cols-2 gap-8 mt-4">
							<!-- Batting Leaders -->
							<div>
								<h3 class="font-bold text-lg mb-3 flex items-center gap-2">
									<span class="text-2xl">⚾</span> {$t('dashboard_top_hitters')}
								</h3>
								{#if dashboardData.recent_batting && dashboardData.recent_batting.length > 0}
									<div class="overflow-x-auto">
										<table class="table table-sm">
											<thead class="bg-base-200 text-base-content">
												<tr>
													<th>{$t('common_player')}</th>
													<th class="text-center">AVG</th>
													<th class="text-center">OBP</th>
													<th class="text-center font-bold text-primary">OPS</th>
												</tr>
											</thead>
											<tbody>
												{#each dashboardData.recent_batting as stat}
													<tr>
														<td class="font-semibold">{stat.name}</td>
														<td class="text-center">{(stat.avg).toFixed(3).replace(/^0/, '')}</td>
														<td class="text-center">{(stat.obp).toFixed(3).replace(/^0/, '')}</td>
														<td class="text-center font-bold text-primary">{(stat.ops).toFixed(3).replace(/^0/, '')}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{:else}
									<p class="text-base-content/50 italic text-sm">{$t('dashboard_no_batting_stats')}</p>
								{/if}
							</div>

							<!-- Pitching Leaders -->
							<div>
								<h3 class="font-bold text-lg mb-3 flex items-center gap-2">
									<span class="text-2xl">🔥</span> {$t('dashboard_top_pitchers')}
								</h3>
								{#if dashboardData.recent_pitching && dashboardData.recent_pitching.length > 0}
									<div class="overflow-x-auto">
										<table class="table table-sm">
											<thead class="bg-base-200 text-base-content">
												<tr>
													<th>{$t('common_player')}</th>
													<th class="text-center">K/9</th>
													<th class="text-center">RA/9</th>
													<th class="text-center font-bold text-primary">IP</th>
												</tr>
											</thead>
											<tbody>
												{#each dashboardData.recent_pitching as stat}
													<tr>
														<td class="font-semibold">{stat.name}</td>
														<td class="text-center">{(stat.k_9).toFixed(1)}</td>
														<td class="text-center">{(stat.r_9).toFixed(2)}</td>
														<td class="text-center font-bold text-primary">{stat.ip_display}</td>
													</tr>
												{/each}
											</tbody>
										</table>
									</div>
								{:else}
									<p class="text-base-content/50 italic text-sm">{$t('dashboard_no_pitching_stats')}</p>
								{/if}
							</div>
						</div>
					</div>
				</div>
			</div>

		</div>
	{/if}
</div>
