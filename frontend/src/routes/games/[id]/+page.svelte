<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t, translate } from '$lib/i18n';
	import { getOpponentIntelComponent } from '$lib/league_integrations';

	let game: any = $state(null);
	let activeTeam: any = $state(null);
	let editing = $state(false);

	let OpponentIntel = $derived(getOpponentIntelComponent(activeTeam?.integration_version));

	async function fetchGame() {
		const res = await apiFetch(`/games/${$page.params.id}`);
		if (res.ok) game = await res.json();
	}

	async function fetchActiveTeam() {
		const res = await apiFetch('/teams/');
		if (!res.ok) return;
		const teams = await res.json();
		const cachedId = sessionStorage.getItem('activeTeamId');
		activeTeam = teams.find((team: any) => team.id.toString() === cachedId) ?? teams[0] ?? null;
	}

	onMount(async () => {
		await Promise.all([fetchGame(), fetchActiveTeam()]);
	});

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

	async function deleteGame() {
		if (!game || !confirm(translate('games_delete_game_confirm'))) return;
		try {
			const res = await apiFetch(`/games/${game.id}`, { method: 'DELETE' });
			if (res.ok) {
				goto('/games?tab=past');
			}
		} catch (e) {
			console.error(e);
		}
	}
</script>

{#if game}
	<div class="card bg-base-100 border border-base-300 shadow-xl p-6 space-y-4">
		<h2 class="text-xl font-bold text-base-content border-b border-base-200 pb-2">{$t('game_overview_game_details')}</h2>
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
			<div class="form-control">
				<label for="edit_date" class="label"><span class="label-text font-semibold">{$t('common_date')}</span></label>
				{#if editing}
					<input id="edit_date" type="date" bind:value={game.date} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.date}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_game_number" class="label"><span class="label-text font-semibold">{$t('games_game_number')}</span></label>
				{#if editing}
					<input id="edit_game_number" type="text" bind:value={game.game_number} placeholder={$t('games_placeholder_game_number')} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.game_number || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_opponent" class="label"><span class="label-text font-semibold">{$t('games_opponent')}</span></label>
				{#if editing}
					<input id="edit_opponent" type="text" bind:value={game.opponent} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.opponent || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_venue" class="label"><span class="label-text font-semibold">{$t('games_venue')}</span></label>
				{#if editing}
					<input id="edit_venue" type="text" bind:value={game.venue} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.venue || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_home_away" class="label"><span class="label-text font-semibold">{$t('games_home_away')}</span></label>
				{#if editing}
					<select id="edit_home_away" bind:value={game.home_away} class="select select-bordered select-sm w-full">
						<option value="H">{$t('common_home')}</option>
						<option value="A">{$t('common_away')}</option>
					</select>
				{:else}
					<p class="text-base-content font-medium ml-1">{game.home_away === 'H' ? $t('common_home') : $t('common_away')}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_mode" class="label"><span class="label-text font-semibold">{$t('games_optimizer_mode')}</span></label>
				{#if editing}
					<select id="edit_mode" bind:value={game.mode} class="select select-bordered select-sm w-full">
						<option value="compete">{$t('games_mode_compete')}</option>
						<option value="develop">{$t('games_mode_develop')}</option>
					</select>
				{:else}
					<div class="ml-1">
						<span class="badge {game.mode === 'compete' ? 'badge-info' : 'badge-success'}">
							{game.mode === 'compete' ? $t('games_mode_compete') : $t('games_mode_develop')}
						</span>
					</div>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_league" class="label"><span class="label-text font-semibold">{$t('games_league')}</span></label>
				{#if editing}
					<input id="edit_league" type="text" bind:value={game.league} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.league || '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_innings" class="label"><span class="label-text font-semibold">{$t('game_overview_innings_played')}</span></label>
				{#if editing}
					<input id="edit_innings" type="number" bind:value={game.innings_played} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.innings_played || $t('common_default')}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_runs_for" class="label"><span class="label-text font-semibold">{$t('game_overview_runs_for')}</span></label>
				{#if editing}
					<input id="edit_runs_for" type="number" bind:value={game.result_runs_for} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.result_runs_for ?? '—'}</p>
				{/if}
			</div>
			<div class="form-control">
				<label for="edit_runs_against" class="label"><span class="label-text font-semibold">{$t('game_overview_runs_against')}</span></label>
				{#if editing}
					<input id="edit_runs_against" type="number" bind:value={game.result_runs_against} class="input input-bordered input-sm w-full" />
				{:else}
					<p class="text-base-content font-medium ml-1">{game.result_runs_against ?? '—'}</p>
				{/if}
			</div>
			{#if activeTeam?.integration_version}
				<div class="form-control sm:col-span-2">
					<label for="edit_external_game_id" class="label">
						<span class="label-text font-semibold">{$t('games_external_game_id')}</span>
					</label>
					{#if editing}
						<input
							id="edit_external_game_id"
							type="text"
							bind:value={game.external_game_id}
							placeholder={$t('games_placeholder_external_game_id')}
							class="input input-bordered input-sm w-full"
						/>
					{:else}
						<p class="text-base-content font-medium ml-1">{game.external_game_id || '—'}</p>
					{/if}
				</div>
			{/if}
		</div>

		<div class="flex gap-2 pt-4 border-t border-base-200 justify-end">
			{#if editing}
				<button onclick={saveGame} class="btn btn-success btn-sm">{$t('common_save')}</button>
				<button onclick={() => { editing = false; fetchGame(); }} class="btn btn-neutral btn-sm">{$t('common_cancel')}</button>
			{:else}
				<button onclick={deleteGame} class="btn btn-ghost btn-error btn-sm">{$t('common_delete')}</button>
				<button onclick={() => editing = true} class="btn btn-primary btn-sm px-6">{$t('common_edit')}</button>
			{/if}
		</div>
	</div>

	{#if OpponentIntel}
		<div class="mt-6">
			<OpponentIntel gameId={game.id} />
		</div>
	{/if}
{/if}
