<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';

	let battingStats: any[] = $state([]);
	let pitchingStats: any[] = $state([]);
	let positionStats: any[] = $state([]);
	let activeTab = $state('batting');
	let viewMode = $state('percent'); // 'percent' or 'count'
	let loading = $state(true);
	let teamId = $state('');

	let sortField = $state('name');
	let sortDirection = $state('asc'); // 'asc' or 'desc'

	let { data } = $props();

	onMount(async () => {
		try {
			const activeId = sessionStorage.getItem('activeTeamId');
			if (!activeId) {
				console.warn('No active team ID found, waiting...');
				loading = false;
				return;
			}
			teamId = activeId;

			const [battingRes, pitchingRes, positionRes] = await Promise.all([
				apiFetch(`/teams/${teamId}/stats/batting`),
				apiFetch(`/teams/${teamId}/stats/pitching`),
				apiFetch(`/teams/${teamId}/stats/position`)
			]);

			if (battingRes.ok) battingStats = await battingRes.json();
			if (pitchingRes.ok) pitchingStats = await pitchingRes.json();
			if (positionRes.ok) positionStats = await positionRes.json();
		} catch (error) {
			console.error('Error fetching stats:', error);
		} finally {
			loading = false;
		}
	});

	function formatPositionStat(stat: any, pos: string) {
		const count = stat.positions[pos] || 0;
		if (viewMode === 'count') {
			return count > 0 ? count : '-';
		} else {
			if (stat.total_innings === 0) return '-';
			const pct = (count / stat.total_innings) * 100;
			return pct > 0 ? pct.toFixed(0) + '%' : '-';
		}
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
			let valA = a[sortField];
			let valB = b[sortField];

			if (sortField === 'k') {
				valA = (a.kd || 0) + (a.ke || 0);
				valB = (b.kd || 0) + (b.ke || 0);
			}

			if (valA === undefined || valA === null) valA = 0;
			if (valB === undefined || valB === null) valB = 0;

			if (sortField === 'name') {
				return sortDirection === 'asc'
					? valA.localeCompare(valB)
					: valB.localeCompare(valA);
			}

			return sortDirection === 'asc' ? valA - valB : valB - valA;
		})
	);

	let sortedPitching = $derived(
		[...pitchingStats].sort((a, b) => {
			let valA = a[sortField];
			let valB = b[sortField];

			if (sortField === 'ip') {
				valA = a.ip_outs || 0;
				valB = b.ip_outs || 0;
			}

			if (valA === undefined || valA === null) valA = 0;
			if (valB === undefined || valB === null) valB = 0;

			if (sortField === 'name') {
				return sortDirection === 'asc'
					? valA.localeCompare(valB)
					: valB.localeCompare(valA);
			}

			return sortDirection === 'asc' ? valA - valB : valB - valA;
		})
	);

	let sortedPositions = $derived(
		[...positionStats].sort((a, b) => {
			let valA = a[sortField];
			let valB = b[sortField];

			if (sortField === 'field_pct') {
				valA = a.total_innings > 0 ? (a.total_innings - (a.positions['0'] || 0)) / a.total_innings : 0;
				valB = b.total_innings > 0 ? (b.total_innings - (b.positions['0'] || 0)) / b.total_innings : 0;
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
				return sortDirection === 'asc'
					? valA.localeCompare(valB)
					: valB.localeCompare(valA);
			}

			return sortDirection === 'asc' ? valA - valB : valB - valA;
		})
	);
</script>

<div class="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
	<div class="sm:flex sm:items-center mb-6">
		<div class="sm:flex-auto">
			<h1 class="text-3xl font-extrabold text-base-content">Team Stats</h1>
			<p class="mt-2 text-sm text-base-content/70">
				View season batting, pitching, and defensive statistics.
			</p>
		</div>
	</div>

	<div class="tabs tabs-boxed mb-6 max-w-md bg-base-100 border border-base-300 shadow-sm p-1">
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'batting' ? 'tab-active font-bold text-primary' : 'text-base-content/60'}"
			onclick={() => selectTab('batting')}
		>
			Batting
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'pitching' ? 'tab-active font-bold text-primary' : 'text-base-content/60'}"
			onclick={() => selectTab('pitching')}
		>
			Pitching
		</button>
		<button
			class="tab tab-sm sm:tab-md {activeTab === 'position' ? 'tab-active font-bold text-primary' : 'text-base-content/60'}"
			onclick={() => selectTab('position')}
		>
			Positions
		</button>
	</div>

	{#if loading}
		<div class="card bg-base-100 shadow-xl border border-base-300 p-16 text-center">
			<span class="loading loading-spinner loading-lg text-primary"></span>
			<p class="mt-2 text-sm text-base-content/60">Loading stats...</p>
		</div>
	{:else}
		<div class="card bg-base-100 shadow-xl border border-base-300 overflow-hidden">
			{#if activeTab === 'batting'}
				<div class="overflow-x-auto">
					<table class="table table-zebra table-sm w-full">
						<thead>
							<tr>
								<th class="bg-base-200 text-base-content font-bold cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('jersey')}># {sortField === 'jersey' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('name')}>Name {sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pa')}>PA {sortField === 'pa' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('avg')}>AVG {sortField === 'avg' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('obp')}>OBP {sortField === 'obp' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('slg')}>SLG {sortField === 'slg' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('ops')}>OPS {sortField === 'ops' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('ab')}>AB {sortField === 'ab' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('h')}>H {sortField === 'h' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('singles')}>1B {sortField === 'singles' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('doubles')}>2B {sortField === 'doubles' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('triples')}>3B {sortField === 'triples' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('hr')}>HR {sortField === 'hr' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('bb')}>BB {sortField === 'bb' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('k')}>K {sortField === 'k' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
							</tr>
						</thead>
						<tbody>
							{#each sortedBatting as stat}
								<tr class="hover:bg-base-200/50 transition-colors">
									<td><span class="badge badge-sm badge-neutral">#{stat.jersey}</span></td>
									<td class="font-medium">{stat.name}</td>
									<td class="text-center">{stat.pa}</td>
									<td class="text-center font-mono font-semibold">{stat.avg.toFixed(3).replace(/^0/, '')}</td>
									<td class="text-center font-mono font-semibold">{stat.obp.toFixed(3).replace(/^0/, '')}</td>
									<td class="text-center font-mono font-semibold">{stat.slg.toFixed(3).replace(/^0/, '')}</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">{stat.ops.toFixed(3).replace(/^0/, '')}</td>
									<td class="text-center">{stat.ab}</td>
									<td class="text-center font-semibold">{stat.h}</td>
									<td class="text-center">{stat.singles}</td>
									<td class="text-center">{stat.doubles}</td>
									<td class="text-center">{stat.triples}</td>
									<td class="text-center">{stat.hr}</td>
									<td class="text-center">{stat.bb}</td>
									<td class="text-center text-error">{stat.kd + stat.ke}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			{#if activeTab === 'pitching'}
				<div class="overflow-x-auto">
					<table class="table table-zebra table-sm w-full">
						<thead>
							<tr>
								<th class="bg-base-200 text-base-content font-bold cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('jersey')}># {sortField === 'jersey' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('name')}>Name {sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('ip')}>IP {sortField === 'ip' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-info font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('k_9')}>K/9 {sortField === 'k_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-info font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('bb_9')}>BB/9 {sortField === 'bb_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-info font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('hbp_9')}>HBP/9 {sortField === 'hbp_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-info font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('r_9')}>R/9 {sortField === 'r_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('appearances')}>App {sortField === 'appearances' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('runs_allowed')}>R {sortField === 'runs_allowed' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('k')}>K {sortField === 'k' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('bb')}>BB {sortField === 'bb' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('hbp')}>HBP {sortField === 'hbp' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
							</tr>
						</thead>
						<tbody>
							{#each sortedPitching as stat}
								<tr class="hover:bg-base-200/50 transition-colors">
									<td><span class="badge badge-sm badge-neutral">#{stat.jersey}</span></td>
									<td class="font-medium">{stat.name}</td>
									<td class="text-center font-semibold">{stat.ip_display}</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">{stat.k_9.toFixed(1)}</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">{stat.bb_9.toFixed(1)}</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">{stat.hbp_9.toFixed(1)}</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">{stat.r_9.toFixed(1)}</td>
									<td class="text-center">{stat.appearances}</td>
									<td class="text-center text-error">{stat.runs_allowed}</td>
									<td class="text-center text-secondary">{stat.k}</td>
									<td class="text-center">{stat.bb}</td>
									<td class="text-center">{stat.hbp}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}

			{#if activeTab === 'position'}
				<div class="p-4 bg-base-100 border-b border-base-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
					<div>
						<h2 class="text-lg font-bold text-base-content">Position Distribution</h2>
						<p class="text-xs text-base-content/60">Shows where each player played throughout the season</p>
					</div>
					<div class="join border border-base-300 self-start sm:self-center bg-base-200 shadow-inner">
						<button
							class="join-item btn btn-xs {viewMode === 'percent' ? 'btn-primary font-bold' : 'btn-ghost'}"
							onclick={() => (viewMode = 'percent')}
						>
							% Split
						</button>
						<button
							class="join-item btn btn-xs {viewMode === 'count' ? 'btn-primary font-bold' : 'btn-ghost'}"
							onclick={() => (viewMode = 'count')}
						>
							Inning Count
						</button>
					</div>
				</div>

				<div class="overflow-x-auto">
					<table class="table table-zebra table-sm w-full">
						<thead>
							<tr>
								<th class="bg-base-200 text-base-content font-bold sticky left-0 z-20 cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('jersey')}># {sortField === 'jersey' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold sticky left-12 z-20 border-r border-base-200 cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('name')}>Name {sortField === 'name' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-info font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('field_pct')}>Infield % {sortField === 'field_pct' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-info font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('bench_pct')}>Bench % {sortField === 'bench_pct' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('total_innings')}>Total Innings {sortField === 'total_innings' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_0')}>Bench (X) {sortField === 'pos_0' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_1')}>P (1) {sortField === 'pos_1' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_2')}>C (2) {sortField === 'pos_2' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_3')}>1B (3) {sortField === 'pos_3' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_4')}>2B (4) {sortField === 'pos_4' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_5')}>3B (5) {sortField === 'pos_5' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_6')}>SS (6) {sortField === 'pos_6' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_7')}>LF (7) {sortField === 'pos_7' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_8')}>CF (8) {sortField === 'pos_8' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
								<th class="bg-base-200 text-base-content font-bold text-center cursor-pointer hover:bg-base-300 select-none transition-colors" onclick={() => handleSort('pos_9')}>RF (9) {sortField === 'pos_9' ? (sortDirection === 'asc' ? '▲' : '▼') : ''}</th>
							</tr>
						</thead>
						<tbody>
							{#each sortedPositions as stat}
								<tr class="hover:bg-base-200/50 transition-colors">
									<td class="sticky left-0 bg-base-100 z-10"><span class="badge badge-sm badge-neutral">#{stat.jersey}</span></td>
									<td class="font-medium sticky left-12 bg-base-100 z-10 border-r border-base-200">{stat.name}</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">
										{stat.total_innings > 0 ? (((stat.total_innings - (stat.positions['0'] || 0)) / stat.total_innings) * 100).toFixed(1) + '%' : '-'}
									</td>
									<td class="text-center font-mono font-bold text-info bg-info/10">{stat.bench_pct.toFixed(1)}%</td>
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
		</div>
	{/if}

	<!-- Legend -->
	{#if !loading}
		<div class="mt-6 card bg-base-100 border border-base-300 shadow-sm p-5">
			<h3 class="text-sm font-bold text-base-content mb-3 uppercase tracking-wide opacity-70">Legend</h3>
			{#if activeTab === 'batting'}
				<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-8 gap-y-1 text-xs text-base-content/70">
					<span><strong class="text-base-content">PA</strong> — Plate Appearances</span>
					<span><strong class="text-base-content">AB</strong> — At Bats</span>
					<span><strong class="text-base-content">H</strong> — Hits</span>
					<span><strong class="text-base-content">AVG</strong> — Batting Average (H/AB)</span>
					<span><strong class="text-base-content">OBP</strong> — On-Base Percentage</span>
					<span><strong class="text-base-content">SLG</strong> — Slugging Percentage</span>
					<span><strong class="text-base-content">OPS</strong> — On-Base + Slugging</span>
					<span><strong class="text-base-content">1B</strong> — Singles</span>
					<span><strong class="text-base-content">2B</strong> — Doubles</span>
					<span><strong class="text-base-content">3B</strong> — Triples</span>
					<span><strong class="text-base-content">HR</strong> — Home Runs</span>
					<span><strong class="text-base-content">BB</strong> — Base on Balls (Walk)</span>
					<span><strong class="text-base-content">K</strong> — Strikeouts (KL + KS)</span>
				</div>
			{/if}
			{#if activeTab === 'pitching'}
				<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-8 gap-y-1 text-xs text-base-content/70">
					<span><strong class="text-base-content">IP</strong> — Innings Pitched</span>
					<span><strong class="text-base-content">App</strong> — Appearances</span>
					<span><strong class="text-base-content">K</strong> — Strikeouts</span>
					<span><strong class="text-base-content">BB</strong> — Walks (Base on Balls)</span>
					<span><strong class="text-base-content">HBP</strong> — Hit By Pitch</span>
					<span><strong class="text-base-content">R</strong> — Runs Allowed</span>
					<span><strong class="text-base-content text-info">K/9</strong> — Strikeouts per 9 innings</span>
					<span><strong class="text-base-content text-info">BB/9</strong> — Walks per 9 innings</span>
					<span><strong class="text-base-content text-info">HBP/9</strong> — Hit By Pitch per 9 innings</span>
					<span><strong class="text-base-content text-info">R/9</strong> — Runs Allowed per 9 innings</span>
				</div>
			{/if}
			{#if activeTab === 'position'}
				<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-8 gap-y-1 text-xs text-base-content/70">
					<span><strong class="text-base-content text-info">Infield %</strong> — % of innings played in the field</span>
					<span><strong class="text-base-content text-info">Bench %</strong> — % of innings on the bench</span>
					<span><strong class="text-base-content">P (1)</strong> — Pitcher</span>
					<span><strong class="text-base-content">C (2)</strong> — Catcher</span>
					<span><strong class="text-base-content">1B (3)</strong> — First Base</span>
					<span><strong class="text-base-content">2B (4)</strong> — Second Base</span>
					<span><strong class="text-base-content">3B (5)</strong> — Third Base</span>
					<span><strong class="text-base-content">SS (6)</strong> — Shortstop</span>
					<span><strong class="text-base-content">LF (7)</strong> — Left Field</span>
					<span><strong class="text-base-content">CF (8)</strong> — Center Field</span>
					<span><strong class="text-base-content">RF (9)</strong> — Right Field</span>
					<span><strong class="text-base-content">X</strong> — Bench (not fielding)</span>
				</div>
			{/if}
		</div>
	{/if}
</div>
