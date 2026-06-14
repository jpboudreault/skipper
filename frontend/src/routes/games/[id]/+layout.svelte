<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';

	let { children } = $props();
	let game: any = $state(null);

	$effect(() => {
		const id = $page.params.id;
		if (id) {
			apiFetch(`/games/${id}`)
				.then((r) => r.json())
				.then((data) => (game = data))
				.catch(console.error);
		}
	});

	const tabs = [
		{ name: 'Overview', path: '' },
		{ name: 'Availability', path: '/availability' },
		{ name: 'Lineup', path: '/lineup' },
		{ name: 'Batting Scorecard', path: '/batting' },
		{ name: 'Pitching Scorecard', path: '/pitching' }
	];
</script>

<div class="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 print:p-0 print:max-w-none print:m-0">
	<div class="mb-6 print:hidden">
		<a href="/games" class="btn btn-ghost btn-xs text-base-content/60 mb-2">← Back to Games</a>
		{#if game}
			<h1 class="text-xl sm:text-3xl font-extrabold text-base-content flex flex-wrap items-center gap-x-2 gap-y-1">
				{#if game.game_number}
					<span class="text-primary whitespace-nowrap">Game #{game.game_number}</span>
					<span class="text-base-content/30 hidden sm:inline">|</span>
				{/if}
				<span class="whitespace-nowrap">{game.date}</span>
				<span class="text-base-content/50 text-base sm:text-xl font-normal whitespace-nowrap">{game.home_away === 'A' ? 'at' : 'vs'}</span>
				<span class="text-base-content">{game.opponent || 'TBD'}</span>
				<span class="badge badge-sm sm:badge-md {game.result_runs_for != null ? 'badge-success' : 'badge-ghost'}">
					{game.result_runs_for != null ? 'Complete' : 'Scheduled'}
				</span>
			</h1>
		{/if}
	</div>

	<!-- Tabs -->
	<div class="tabs tabs-bordered mb-6 print:hidden">
		{#each tabs as tab}
			{@const href = `/games/${$page.params.id}${tab.path}`}
			{@const isActive = $page.url.pathname === href}
			<a
				{href}
				class="tab tab-bordered {isActive ? 'tab-active font-bold text-primary' : 'text-base-content/60'}"
			>
				{tab.name}
			</a>
		{/each}
	</div>

	{@render children()}
</div>
