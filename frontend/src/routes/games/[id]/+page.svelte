<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';

	let game: any = $state(null);
	let editing = $state(false);

	async function fetchGame() {
		const res = await apiFetch(`/games/${$page.params.id}`);
		if (res.ok) game = await res.json();
	}

	onMount(fetchGame);

	async function saveGame() {
		if (!game) return;
		const { id: gameId, ...gameData } = game;
		const res = await apiFetch(`/games/${gameId}`, {
			method: 'PUT',
			headers: { 
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(gameData)
		});
		if (res.ok) {
			game = await res.json();
			editing = false;
		}
	}
</script>

{#if game}
	<div class="card bg-base-100 border border-base-300 shadow-xl p-6 space-y-4">
		<h2 class="text-xl font-bold text-base-content border-b border-base-200 pb-2">Game Details</h2>
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
			<div class="form-control">
				<label for="edit_date" class="label"><span class="label-text font-semibold">Date</span></label>
				{#if editing}
					<input id="edit_date" type="date" bind:value={game.date} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.date}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_game_number" class="label"><span class="label-text font-semibold">Game #</span></label>
				{#if editing}
					<input id="edit_game_number" type="text" bind:value={game.game_number} placeholder="Optional game #" class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.game_number || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_opponent" class="label"><span class="label-text font-semibold">Opponent</span></label>
				{#if editing}
					<input id="edit_opponent" type="text" bind:value={game.opponent} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.opponent || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_venue" class="label"><span class="label-text font-semibold">Venue</span></label>
				{#if editing}
					<input id="edit_venue" type="text" bind:value={game.venue} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.venue || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_home_away" class="label"><span class="label-text font-semibold">Home/Away</span></label>
				{#if editing}
					<select id="edit_home_away" bind:value={game.home_away} class="select select-bordered select-sm w-full">
						<option value="H">Home</option>
						<option value="A">Away</option>
					</select>
				{:else}
					<p class="text-base-content font-medium ml-1">{game.home_away === 'H' ? 'Home' : 'Away'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_mode" class="label"><span class="label-text font-semibold">Optimizer Mode</span></label>
				{#if editing}
					<select id="edit_mode" bind:value={game.mode} class="select select-bordered select-sm w-full">
						<option value="compete">Compete</option>
						<option value="develop">Develop</option>
					</select>
				{:else}
					<div class="ml-1">
						<span class="badge {game.mode === 'compete' ? 'badge-info' : 'badge-success'}">
							{game.mode}
						</span>
					</div>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_league" class="label"><span class="label-text font-semibold">League</span></label>
				{#if editing}
					<input id="edit_league" type="text" bind:value={game.league} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.league || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_innings" class="label"><span class="label-text font-semibold">Innings Played</span></label>
				{#if editing}
					<input id="edit_innings" type="number" bind:value={game.innings_played} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.innings_played || 'Default'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_runs_for" class="label"><span class="label-text font-semibold">Runs For</span></label>
				{#if editing}
					<input id="edit_runs_for" type="number" bind:value={game.result_runs_for} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.result_runs_for ?? '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_runs_against" class="label"><span class="label-text font-semibold">Runs Against</span></label>
				{#if editing}
					<input id="edit_runs_against" type="number" bind:value={game.result_runs_against} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.result_runs_against ?? '—'}</p>
				{/if}
			</div>
		</div>

		<div class="flex gap-2 pt-4 border-t border-base-200 justify-end">
			{#if editing}
				<button onclick={saveGame} class="btn btn-success btn-sm">Save</button>
				<button onclick={() => { editing = false; fetchGame(); }} class="btn btn-neutral btn-sm">Cancel</button>
			{:else}
				<button onclick={() => editing = true} class="btn btn-primary btn-sm px-6">Edit</button>
			{/if}
		</div>
	</div>
{/if}
