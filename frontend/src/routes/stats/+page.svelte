<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t, formatLocaleDate } from '$lib/i18n';
	import { waitForActiveTeamId } from '$lib/teamContext';
	import type { BattingStat, PitchingStat, PositionStat, DevelopmentTrends } from '$lib/types';

	let battingStats: BattingStat[] = $state([]);
	let pitchingStats: PitchingStat[] = $state([]);
	let positionStats: PositionStat[] = $state([]);
	let trends = $state<DevelopmentTrends | null>(null);
	let activeTab = $state('batting');
	let viewMode = $state('percent'); // 'percent' or 'count'
	let loading = $state(true);
	let teamId = $state('');

	let sortField = $state('name');
	let sortDirection = $state('asc'); // 'asc' or 'desc'

	const dateFormatOptions: Intl.DateTimeFormatOptions = {
		month: 'short',
		day: 'numeric'
	};

	let maxOps = $derived(
		(trends?.cumulative_batting ?? []).reduce((m, p) => Math.max(m, p.ops), 0.001)
	);

	onMount(async () => {
		try {
			const activeId = await waitForActiveTeamId();
			if (!activeId) {
				loading = false;
				return;
			}
			teamId = activeId;

			const [battingRes, pitchingRes, positionRes, trendsRes] = await Promise.all([
				apiFetch(`/teams/${teamId}/stats/batting`),
				apiFetch(`/teams/${teamId}/stats/pitching`),
				apiFetch(`/teams/${teamId}/stats/position`),
				apiFetch(`/teams/${teamId}/stats/trends`)
			]);

			if (battingRes.ok) battingStats = await battingRes.json();
			if (pitchingRes.ok) pitchingStats = await pitchingRes.json();
			if (positionRes.ok) positionStats = await positionRes.json();
			if (trendsRes.ok) trends = await trendsRes.json();
		} catch (error) {
			console.error('Error fetching stats:', error);
		} finally {
			loading = false;
		}
	});

	function fieldInnings(stat: any): number {
		return stat.total_innings - (stat.positions['0'] || 0);
	}

	function formatPositionStat(stat: any, pos: string) {
		const count = stat.positions[pos] || 0;
		if (viewMode === 'count') {
			return count > 0 ? count : '-';
		}
		if (stat.total_innings === 0) return '-';
		// Bench % is share of all innings; field position % is share of innings on the field only.
		const denominator = pos === '0' ? stat.total_innings : fieldInnings(stat);
		if (denominator === 0) return '-';
		const pct = (count / denominator) * 100;
		return pct > 0 ? pct.toFixed(0) + '%' : '-';
	}

	function handleSort(field: string) {
		if (sortField === field) {
			sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
		} else {
			sortField = field;
			sortDirection = 'asc';
		}
	}

	function selectTab(tab: string) {
		activeTab = tab;
		sortField = 'name';
		sortDirection = 'asc';
	}

	let sortedBatting = $derived(
		[...battingStats].sort((a, b) => {
			let valA: any = (a as any)[sortField];
			let valB: any = (b as any)[sortField];

			if (sortField === 'k') {
				valA = (a.kd || 0) + (a.ke || 0);
				valB = (b.kd || 0) + (b.ke || 0);
			}

			if (valA === undefined || valA === null) valA = 0;
			if (valB === undefined || valB === null) valB = 0;

			if (sortField === 'name') {
				return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
			}

			return sortDirection === 'asc' ? valA - valB : valB - valA;
		})
	);

	let sortedPitching = $derived(
		[...pitchingStats].sort((a, b) => {
			let valA: any = (a as any)[sortField];
			let valB: any = (b as any)[sortField];

			if (sortField === 'ip') {
				valA = a.ip_outs || 0;
				valB = b.ip_outs || 0;
			}

			if (valA === undefined || valA === null) valA = 0;
			if (valB === undefined || valB === null) valB = 0;

			if (sortField === 'name') {
				return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
			}

			return sortDirection === 'asc' ? valA - valB : valB - valA;
		})
	);

	let sortedPositions = $derived(
		[...positionStats].sort((a, b) => {
			let valA: any = (a as any)[sortField];
			let valB: any = (b as any)[sortField];

			if (sortField === 'field_pct') {
				valA =
					a.total_innings > 0 ? (a.total_innings - (a.positions['0'] || 0)) / a.total_innings : 0;
				valB =
					b.total_innings > 0 ? (b.total_innings - (b.positions['0'] || 0)) / b.total_innings : 0;
			} else if (sortField === 'bench_pct') {
				valA = a.bench_pct || 0;
				valB = b.bench_pct || 0;
			} else if (sortField.startsWith('pos_')) {
				const pos = sortField.split('_')[1];
				valA = a.positions[pos] || 0;
				valB = b.positions[pos] || 0;
			}

			if (valA === undefined || valA === null) valA = 0;
			if (valB === undefined || valB === null) valB = 0;

			if (sortField === 'name') {
				return sortDirection === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
			}

			return sortDirection === 'asc' ? valA - valB : valB - valA;
		})
	);
</script>

<div class="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
	<div class="mb-6 sm:flex sm:items-center">
		<div class="sm:flex-auto">
			<h1 class="text-base-content text-3xl font-extrabold">{$t('stats_title')}</h1>
			<p class="text-base-content/70 mt-2 text-sm">
				{$t('stats_description')}
			</p>
		</div>
	</div>

	<div class="tabs tabs-boxed bg-base-100 border-base-300 mb-6 max-w-md border p-1 shadow-sm">
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'batting'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => selectTab('batting')}
		>
			{$t('stats_batting')}
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'pitching'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => selectTab('pitching')}
		>
			{$t('stats_pitching')}
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'position'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => selectTab('position')}
		>
			{$t('stats_positions')}
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'trends'
				? 'tab-active text-primary font-bold'
				: 'text-base-content/60'}"
			onclick={() => selectTab('trends')}
		>
			{$t('stats_trends')}
		</button>
	</div>

	{#if loading}
		<div class="card bg-base-100 border-base-300 border p-16 text-center shadow-xl">
			<span class="loading loading-spinner loading-lg text-primary"></span>
			<p class="text-base-content/60 mt-2 text-sm">{$t('stats_loading')}</p>
		</div>
	{:else}
		<div class="card bg-base-100 border-base-300 overflow-hidden border shadow-xl">
			{#if activeTab === 'batting'}
				<div class="overflow-x-auto">
					<table class="table-zebra table-sm table w-full">
						<thead>
							<tr>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer font-bold transition-colors select-none"
									onclick={() => handleSort('jersey')}
									># {sortField === 'jersey' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer font-bold transition-colors select-none"
									onclick={() => handleSort('name')}
									>{$t('stats_name')}
									{sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pa')}
									>PA {sortField === 'pa' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('avg')}
									>AVG {sortField === 'avg' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('obp')}
									>OBP {sortField === 'obp' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('slg')}
									>SLG {sortField === 'slg' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('ops')}
									>OPS {sortField === 'ops' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('ab')}
									>AB {sortField === 'ab' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('h')}
									>H {sortField === 'h' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('singles')}
									>1B {sortField === 'singles' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('doubles')}
									>2B {sortField === 'doubles' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('triples')}
									>3B {sortField === 'triples' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('hr')}
									>HR {sortField === 'hr' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('bb')}
									>BB {sortField === 'bb' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('k')}
									>K {sortField === 'k' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each sortedBatting as stat}
								<tr class="hover:bg-base-200/50 transition-colors">
									<td><span class="badge badge-sm badge-neutral">#{stat.jersey}</span></td>
									<td class="font-medium">{stat.name}</td>
									<td class="text-center">{stat.pa}</td>
									<td class="text-center font-mono font-semibold"
										>{stat.avg.toFixed(3).replace(/^0/, '')}</td
									>
									<td class="text-center font-mono font-semibold"
										>{stat.obp.toFixed(3).replace(/^0/, '')}</td
									>
									<td class="text-center font-mono font-semibold"
										>{stat.slg.toFixed(3).replace(/^0/, '')}</td
									>
									<td class="text-info bg-info/10 text-center font-mono font-bold"
										>{stat.ops.toFixed(3).replace(/^0/, '')}</td
									>
									<td class="text-center">{stat.ab}</td>
									<td class="text-center font-semibold">{stat.h}</td>
									<td class="text-center">{stat.singles}</td>
									<td class="text-center">{stat.doubles}</td>
									<td class="text-center">{stat.triples}</td>
									<td class="text-center">{stat.hr}</td>
									<td class="text-center">{stat.bb}</td>
									<td class="text-error text-center">{stat.kd + stat.ke}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			{#if activeTab === 'pitching'}
				<div class="overflow-x-auto">
					<table class="table-zebra table-sm table w-full">
						<thead>
							<tr>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer font-bold transition-colors select-none"
									onclick={() => handleSort('jersey')}
									># {sortField === 'jersey' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer font-bold transition-colors select-none"
									onclick={() => handleSort('name')}
									>{$t('stats_name')}
									{sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('ip')}
									>IP {sortField === 'ip' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-info hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('k_9')}
									>K/9 {sortField === 'k_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-info hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('bb_9')}
									>BB/9 {sortField === 'bb_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-info hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('hbp_9')}
									>HBP/9 {sortField === 'hbp_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-info hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('r_9')}
									>R/9 {sortField === 'r_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('appearances')}
									>App {sortField === 'appearances'
										? sortDirection === 'asc'
											? '▲'
											: '▼'
										: ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('runs_allowed')}
									>R {sortField === 'runs_allowed' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('k')}
									>K {sortField === 'k' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('bb')}
									>BB {sortField === 'bb' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('hbp')}
									>HBP {sortField === 'hbp' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each sortedPitching as stat}
								<tr class="hover:bg-base-200/50 transition-colors">
									<td><span class="badge badge-sm badge-neutral">#{stat.jersey}</span></td>
									<td class="font-medium">{stat.name}</td>
									<td class="text-center font-semibold">{stat.ip_display}</td>
									<td class="text-info bg-info/10 text-center font-mono font-bold"
										>{stat.k_9.toFixed(1)}</td
									>
									<td class="text-info bg-info/10 text-center font-mono font-bold"
										>{stat.bb_9.toFixed(1)}</td
									>
									<td class="text-info bg-info/10 text-center font-mono font-bold"
										>{stat.hbp_9.toFixed(1)}</td
									>
									<td class="text-info bg-info/10 text-center font-mono font-bold"
										>{stat.r_9.toFixed(1)}</td
									>
									<td class="text-center">{stat.appearances}</td>
									<td class="text-error text-center">{stat.runs_allowed}</td>
									<td class="text-secondary text-center">{stat.k}</td>
									<td class="text-center">{stat.bb}</td>
									<td class="text-center">{stat.hbp}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			{#if activeTab === 'position'}
				<div
					class="bg-base-100 border-base-200 flex flex-col gap-2 border-b p-4 sm:flex-row sm:items-center sm:justify-between"
				>
					<div>
						<h2 class="text-base-content text-lg font-bold">{$t('stats_position_distribution')}</h2>
						<p class="text-base-content/60 text-xs">{$t('stats_position_distribution_desc')}</p>
					</div>
					<div
						class="join border-base-300 bg-base-200 self-start border shadow-inner sm:self-center"
					>
						<button
							class="join-item btn btn-xs {viewMode === 'percent'
								? 'btn-primary font-bold'
								: 'btn-ghost'}"
							onclick={() => (viewMode = 'percent')}
						>
							{$t('stats_percent_split')}
						</button>
						<button
							class="join-item btn btn-xs {viewMode === 'count'
								? 'btn-primary font-bold'
								: 'btn-ghost'}"
							onclick={() => (viewMode = 'count')}
						>
							{$t('stats_inning_count')}
						</button>
					</div>
				</div>

				<div class="overflow-x-auto">
					<table class="table-zebra table-sm table w-full">
						<thead>
							<tr>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 sticky left-0 z-20 cursor-pointer font-bold transition-colors select-none"
									onclick={() => handleSort('jersey')}
									># {sortField === 'jersey' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content border-base-200 hover:bg-base-300 sticky left-12 z-20 cursor-pointer border-r font-bold transition-colors select-none"
									onclick={() => handleSort('name')}
									>{$t('stats_name')}
									{sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-info hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('field_pct')}
									>{$t('stats_infield_pct')}
									{sortField === 'field_pct' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-info hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('bench_pct')}
									>{$t('stats_bench_pct')}
									{sortField === 'bench_pct' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('total_innings')}
									>{$t('stats_total_innings')}
									{sortField === 'total_innings' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_0')}
									>Bench (X) {sortField === 'pos_0'
										? sortDirection === 'asc'
											? '▲'
											: '▼'
										: ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_1')}
									>P (1) {sortField === 'pos_1' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_2')}
									>C (2) {sortField === 'pos_2' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_3')}
									>1B (3) {sortField === 'pos_3' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_4')}
									>2B (4) {sortField === 'pos_4' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_5')}
									>3B (5) {sortField === 'pos_5' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_6')}
									>SS (6) {sortField === 'pos_6' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_7')}
									>LF (7) {sortField === 'pos_7' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_8')}
									>CF (8) {sortField === 'pos_8' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
								<th
									class="bg-base-200 text-base-content hover:bg-base-300 cursor-pointer text-center font-bold transition-colors select-none"
									onclick={() => handleSort('pos_9')}
									>RF (9) {sortField === 'pos_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th
								>
							</tr>
						</thead>
						<tbody>
							{#each sortedPositions as stat}
								<tr class="hover:bg-base-200/50 transition-colors">
									<td class="bg-base-100 sticky left-0 z-10"
										><span class="badge badge-sm badge-neutral">#{stat.jersey}</span></td
									>
									<td class="bg-base-100 border-base-200 sticky left-12 z-10 border-r font-medium"
										>{stat.name}</td
									>
									<td class="text-info bg-info/10 text-center font-mono font-bold">
										{stat.total_innings > 0
											? (
													((stat.total_innings - (stat.positions['0'] || 0)) / stat.total_innings) *
													100
												).toFixed(1) + '%'
											: '-'}
									</td>
									<td class="text-info bg-info/10 text-center font-mono font-bold"
										>{stat.bench_pct.toFixed(1)}%</td
									>
									<td class="text-center font-semibold">{stat.total_innings}</td>
									{#each Array(10) as _, i}
										<td class="text-center font-mono">{formatPositionStat(stat, i.toString())}</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
			{#if activeTab === 'trends'}
				<div class="space-y-8 p-5">
					{#if !trends || trends.cumulative_batting.length === 0}
						<p class="text-base-content/60 py-8 text-center text-sm">
							{$t('stats_trends_no_games')}
						</p>
					{:else}
						<div>
							<h3 class="text-base-content text-sm font-bold tracking-wide uppercase opacity-70">
								{$t('stats_trends_batting_title')}
							</h3>
							<p class="text-base-content/60 mb-3 text-xs">{$t('stats_trends_batting_desc')}</p>
							<div class="space-y-1.5">
								{#each trends.cumulative_batting as point}
									<div class="flex items-center gap-3 text-xs">
										<span class="text-base-content/70 w-28 shrink-0 truncate"
											>{formatLocaleDate(point.date, dateFormatOptions)}</span
										>
										<div class="bg-base-200 h-4 flex-1 overflow-hidden rounded">
											<div
												class="bg-info h-4 rounded"
												style="width: {Math.min(100, (point.ops / maxOps) * 100)}%"
											></div>
										</div>
										<span class="w-28 shrink-0 text-right font-mono">
											{point.avg.toFixed(3).replace(/^0/, '')} /
											<span class="text-info font-bold"
												>{point.ops.toFixed(3).replace(/^0/, '')}</span
											>
										</span>
									</div>
								{/each}
							</div>
						</div>

						<div>
							<h3 class="text-base-content text-sm font-bold tracking-wide uppercase opacity-70">
								{$t('stats_trends_variety_title')}
							</h3>
							<p class="text-base-content/60 mb-3 text-xs">{$t('stats_trends_variety_desc')}</p>
							<div class="space-y-1.5">
								{#each trends.position_variety as row}
									<div class="flex items-center gap-3 text-xs">
										<span class="w-8 shrink-0"
											><span class="badge badge-sm badge-neutral">#{row.jersey}</span></span
										>
										<span class="w-40 shrink-0 truncate font-medium">{row.name}</span>
										<div class="bg-base-200 h-4 flex-1 overflow-hidden rounded">
											<div
												class="bg-success h-4 rounded"
												style="width: {(row.distinct_positions / 9) * 100}%"
											></div>
										</div>
										<span class="text-base-content/70 w-32 shrink-0 text-right"
											>{row.distinct_positions} {$t('stats_trends_distinct_positions')}</span
										>
									</div>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Legend -->
	{#if !loading}
		<div class="card bg-base-100 border-base-300 mt-6 border p-5 shadow-sm">
			<h3 class="text-base-content mb-3 text-sm font-bold tracking-wide uppercase opacity-70">
				{$t('stats_legend')}
			</h3>
			{#if activeTab === 'batting'}
				<div
					class="text-base-content/70 grid grid-cols-2 gap-x-8 gap-y-1 text-xs sm:grid-cols-3 lg:grid-cols-4"
				>
					<span><strong class="text-base-content">PA</strong> — {$t('stats_legend_pa')}</span>
					<span><strong class="text-base-content">AB</strong> — {$t('stats_legend_ab')}</span>
					<span><strong class="text-base-content">H</strong> — {$t('stats_legend_h')}</span>
					<span><strong class="text-base-content">AVG</strong> — {$t('stats_legend_avg')}</span>
					<span><strong class="text-base-content">OBP</strong> — {$t('stats_legend_obp')}</span>
					<span><strong class="text-base-content">SLG</strong> — {$t('stats_legend_slg')}</span>
					<span><strong class="text-base-content">OPS</strong> — {$t('stats_legend_ops')}</span>
					<span><strong class="text-base-content">1B</strong> — {$t('stats_legend_1b')}</span>
					<span><strong class="text-base-content">2B</strong> — {$t('stats_legend_2b')}</span>
					<span><strong class="text-base-content">3B</strong> — {$t('stats_legend_3b')}</span>
					<span><strong class="text-base-content">HR</strong> — {$t('stats_legend_hr')}</span>
					<span><strong class="text-base-content">BB</strong> — {$t('stats_legend_bb')}</span>
					<span><strong class="text-base-content">K</strong> — {$t('stats_legend_k')}</span>
				</div>
			{/if}
			{#if activeTab === 'pitching'}
				<div
					class="text-base-content/70 grid grid-cols-2 gap-x-8 gap-y-1 text-xs sm:grid-cols-3 lg:grid-cols-4"
				>
					<span><strong class="text-base-content">IP</strong> — {$t('stats_legend_ip')}</span>
					<span><strong class="text-base-content">App</strong> — {$t('stats_legend_app')}</span>
					<span><strong class="text-base-content">K</strong> — {$t('stats_legend_k_pitching')}</span
					>
					<span
						><strong class="text-base-content">BB</strong> — {$t('stats_legend_bb_pitching')}</span
					>
					<span><strong class="text-base-content">HBP</strong> — {$t('stats_legend_hbp')}</span>
					<span><strong class="text-base-content">R</strong> — {$t('stats_legend_r')}</span>
					<span
						><strong class="text-base-content text-info">K/9</strong> — {$t(
							'stats_legend_k9'
						)}</span
					>
					<span
						><strong class="text-base-content text-info">BB/9</strong> — {$t(
							'stats_legend_bb9'
						)}</span
					>
					<span
						><strong class="text-base-content text-info">HBP/9</strong> — {$t(
							'stats_legend_hbp9'
						)}</span
					>
					<span
						><strong class="text-base-content text-info">R/9</strong> — {$t(
							'stats_legend_r9'
						)}</span
					>
				</div>
			{/if}
			{#if activeTab === 'position'}
				<div
					class="text-base-content/70 grid grid-cols-2 gap-x-8 gap-y-1 text-xs sm:grid-cols-3 lg:grid-cols-4"
				>
					<span
						><strong class="text-base-content text-info">{$t('stats_infield_pct')}</strong> — {$t(
							'stats_legend_infield_pct'
						)}</span
					>
					<span
						><strong class="text-base-content text-info">{$t('stats_bench_pct')}</strong> — {$t(
							'stats_legend_bench_pct'
						)}</span
					>
					<span><strong class="text-base-content">P (1)</strong> — {$t('stats_legend_p')}</span>
					<span><strong class="text-base-content">C (2)</strong> — {$t('stats_legend_c')}</span>
					<span
						><strong class="text-base-content">1B (3)</strong> — {$t('stats_legend_1b_pos')}</span
					>
					<span
						><strong class="text-base-content">2B (4)</strong> — {$t('stats_legend_2b_pos')}</span
					>
					<span
						><strong class="text-base-content">3B (5)</strong> — {$t('stats_legend_3b_pos')}</span
					>
					<span><strong class="text-base-content">SS (6)</strong> — {$t('stats_legend_ss')}</span>
					<span><strong class="text-base-content">LF (7)</strong> — {$t('stats_legend_lf')}</span>
					<span><strong class="text-base-content">CF (8)</strong> — {$t('stats_legend_cf')}</span>
					<span><strong class="text-base-content">RF (9)</strong> — {$t('stats_legend_rf')}</span>
					<span><strong class="text-base-content">X</strong> — {$t('stats_legend_x')}</span>
				</div>
			{/if}
		</div>
	{/if}
</div>
