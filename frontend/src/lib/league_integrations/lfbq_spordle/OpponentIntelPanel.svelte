<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t } from '$lib/i18n';
	import { formatOpponentMatchup, formatRecord, resultBadgeClass, type HomeAway } from '$lib/games';

	let { gameId }: { gameId: number } = $props();

	type Standing = {
		rank?: number;
		wins?: number;
		losses?: number;
		draws?: number;
		pct?: number;
		points?: number;
		avg_runs_for?: number;
		avg_runs_against?: number;
	};

	const resultLabelKeys: Record<string, string> = {
		win: 'common_win',
		loss: 'common_loss',
		tie: 'common_tie',
		draw: 'common_tie'
	};

	type RecentGame = {
		date?: string;
		opponent?: string;
		home_away?: HomeAway;
		score?: string;
		result?: string;
		spordle_url?: string;
	};

	type IntelPayload = {
		available: boolean;
		opponent_name?: string;
		standing?: Standing;
		recent_games?: RecentGame[];
		recent_games_limit?: number;
		spordle_game_url?: string;
		spordle_team_url?: string;
		fetched_at?: string;
	};

	let intel: IntelPayload | null = $state(null);
	let loading = $state(true);

	onMount(async () => {
		try {
			const res = await apiFetch(`/games/${gameId}/opponent-intel`);
			if (res.ok) {
				intel = await res.json();
			}
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	});
</script>

{#if loading}
	<!-- no skeleton: omit section until loaded -->
{:else if intel?.available}
	<div class="card bg-base-100 border-base-300 space-y-4 border p-6 shadow-xl">
		<div class="border-base-200 flex flex-wrap items-center justify-between gap-2 border-b pb-2">
			<h2 class="text-base-content text-xl font-bold">{$t('opponent_intel_title')}</h2>
			{#if intel.fetched_at}
				<span class="text-base-content/50 text-xs"
					>{$t('opponent_intel_updated', {
						time: intel.fetched_at.slice(0, 16).replace('T', ' ')
					})}</span
				>
			{/if}
		</div>

		{#if intel.standing}
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
				<div class="stat bg-base-200 rounded-box p-3">
					<div class="stat-title text-xs">{$t('opponent_intel_rank')}</div>
					<div class="stat-value text-primary text-2xl">#{intel.standing.rank ?? '—'}</div>
				</div>
				<div class="stat bg-base-200 rounded-box p-3">
					<div class="stat-title text-xs">{$t('opponent_intel_record')}</div>
					<div class="stat-value text-2xl">
						{formatRecord(
							intel.standing.wins ?? 0,
							intel.standing.losses ?? 0,
							intel.standing.draws ?? 0
						)}
					</div>
				</div>
				<div class="stat bg-base-200 rounded-box p-3">
					<div class="stat-title text-xs">{$t('opponent_intel_win_pct')}</div>
					<div class="stat-value text-2xl">
						{intel.standing.pct != null ? intel.standing.pct.toFixed(3) : '—'}
					</div>
				</div>
				<div class="stat bg-base-200 rounded-box p-3">
					<div class="stat-title text-xs">{$t('opponent_intel_points')}</div>
					<div class="stat-value text-2xl">{intel.standing.points ?? '—'}</div>
				</div>
				<div class="stat bg-base-200 rounded-box p-3">
					<div class="stat-title text-xs">{$t('opponent_intel_runs_per_game')}</div>
					<div class="stat-value text-2xl">{intel.standing.avg_runs_for ?? '—'}</div>
				</div>
				<div class="stat bg-base-200 rounded-box p-3">
					<div class="stat-title text-xs">{$t('opponent_intel_runs_allowed_per_game')}</div>
					<div class="stat-value text-2xl">{intel.standing.avg_runs_against ?? '—'}</div>
				</div>
			</div>
		{/if}

		{#if intel.recent_games && intel.recent_games.length > 0}
			<div>
				<div class="mb-2 flex flex-wrap items-baseline gap-2">
					<h3 class="text-base-content font-semibold">{$t('opponent_intel_recent_games')}</h3>
					<span class="text-base-content/50 text-xs">
						{$t('opponent_intel_recent_games_note', {
							count: intel.recent_games.length
						})}
					</span>
				</div>
				<ul class="space-y-2">
					{#each intel.recent_games as game}
						<li class="border-base-200 rounded-lg border px-3 py-2">
							{#if game.spordle_url}
								<a
									href={game.spordle_url}
									target="_blank"
									rel="noopener noreferrer"
									class="hover:text-primary flex flex-wrap items-center gap-2 text-sm"
								>
									<span class="text-base-content/60">{game.date}</span>
									<span class="font-medium"
										>{formatOpponentMatchup(game.home_away, game.opponent, {
											vsLabel: $t('dashboard_vs')
										})}</span
									>
									{#if game.score}
										<span class="font-mono">{game.score}</span>
									{/if}
									{#if game.result}
										<span class="badge badge-sm {resultBadgeClass(game.result)} uppercase">
											{$t(resultLabelKeys[game.result] ?? game.result)}
										</span>
									{/if}
								</a>
							{:else}
								<div class="flex flex-wrap items-center gap-2 text-sm">
									<span class="text-base-content/60">{game.date}</span>
									<span class="font-medium"
										>{formatOpponentMatchup(game.home_away, game.opponent, {
											vsLabel: $t('dashboard_vs')
										})}</span
									>
									{#if game.score}
										<span class="font-mono">{game.score}</span>
									{/if}
									{#if game.result}
										<span class="badge badge-sm {resultBadgeClass(game.result)} uppercase">
											{$t(resultLabelKeys[game.result] ?? game.result)}
										</span>
									{/if}
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if intel.spordle_game_url || intel.spordle_team_url}
			<div class="flex flex-wrap gap-2 pt-2">
				{#if intel.spordle_game_url}
					<a
						href={intel.spordle_game_url}
						target="_blank"
						rel="noopener noreferrer"
						class="btn btn-primary btn-sm"
					>
						{$t('opponent_intel_view_game_spordle')}
					</a>
				{/if}
				{#if intel.spordle_team_url}
					<a
						href={intel.spordle_team_url}
						target="_blank"
						rel="noopener noreferrer"
						class="btn btn-outline btn-sm"
					>
						{$t('opponent_intel_view_team_spordle')}
					</a>
				{/if}
			</div>
		{/if}
	</div>
{/if}
