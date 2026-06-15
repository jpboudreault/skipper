<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { beforeNavigate } from '$app/navigation';
	import { t, translate } from '$lib/i18n';

	let players: any[] = $state([]);
	let appearances: any[] = $state([]);
	let loading = $state(true);
	let saving = $state(false);
let isDirty = $state(false);

	async function fetchData() {
		try {
			const [playersRes, pitchRes, availRes] = await Promise.all([
				apiFetch('/players/'),
				apiFetch(`/games/${$page.params.id}/pitching`),
				apiFetch(`/games/${$page.params.id}/availability`)
			]);

			if (pitchRes.ok) appearances = await pitchRes.json();

			let loadedPlayers: any[] = [];
			if (playersRes.ok) {
				loadedPlayers = await playersRes.json();
			}

			let absentIds = new Set();
			if (availRes.ok) {
				const avails = await availRes.json();
				for (const a of avails) {
					if (a.status === 'absent' || a.status === 'injured') {
						absentIds.add(a.player_id);
					}
				}
			}

			const activePitcherIds = new Set(appearances.map(a => a.player_id));

			players = loadedPlayers.filter(
				(p: any) => !p.is_coach && !p.is_substitute && (!absentIds.has(p.id) || activePitcherIds.has(p.id))
			);

			if (appearances.length === 0) addRow(false);
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(fetchData);

beforeNavigate((event) => {
    if (isDirty && !confirm(translate('common_confirm_unsaved'))) {
        event.cancel();
    }
});

	function inningToOuts(inningVal: number | string): number {
		const val = parseFloat(inningVal as string);
		if (isNaN(val)) return 0;
		const integerPart = Math.floor(val);
		const decimalPart = Math.round((val - integerPart) * 10);
		
		let extraOuts = 0;
		if (decimalPart === 1) {
			extraOuts = 1;
		} else if (decimalPart === 2) {
			extraOuts = 2;
		}
		
		return (integerPart - 1) * 3 + extraOuts;
	}

	function calculateOuts(entered: number | string, exited: number | string): number {
		const outsEntered = inningToOuts(entered);
		const outsExited = inningToOuts(exited);
		return Math.max(0, outsExited - outsEntered);
	}

	function addRow(markDirty = true) {
		appearances = [...appearances, {
			player_id: players[0]?.id || 0,
			inning_entered: 1,
			inning_exited: 2,
			ip_outs: 3,
			runs_allowed: 0,
			k: 0,
			bb: 0,
			hbp: 0,
			pitch_count: null
		}];
		if (markDirty) isDirty = true;
	}

	function removeRow(index: number) {
		appearances = appearances.filter((_, i) => i !== index);
		isDirty = true;
	}

	async function saveAll() {
		saving = true;
		try {
			const res = await apiFetch(`/games/${$page.params.id}/pitching`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(appearances.map(a => ({
					player_id: a.player_id,
					inning_entered: a.inning_entered,
					inning_exited: a.inning_exited,
					ip_outs: a.ip_outs,
					runs_allowed: a.runs_allowed,
					k: a.k,
					bb: a.bb,
					hbp: a.hbp,
					pitch_count: a.pitch_count || null
				})))
			});
			if (res.ok) setTimeout(() => { saving = false; isDirty = false; }, 500);
			else { saving = false; alert(translate('pitching_failed_save')); }
		} catch (e) {
			saving = false;
			console.error(e);
		}
	}
</script>

<div class="card bg-base-100 border border-base-300 shadow-xl overflow-hidden">
	<div class="px-6 py-4 border-b border-base-200 flex items-center justify-between bg-base-200/40">
		<div>
			<h2 class="text-xl font-bold text-base-content">{$t('pitching_title')}</h2>
			<p class="text-sm text-base-content/70 mt-1">{$t('pitching_description')}</p>
		</div>
		<div class="flex gap-2">
			<button onclick={() => addRow()} class="btn btn-neutral btn-sm">{$t('pitching_add_row')}</button>
			<button onclick={saveAll} disabled={saving} class="btn btn-success btn-sm shadow-md">
				{#if saving}
					<span class="loading loading-spinner loading-xs"></span>
					{$t('common_saving')}
				{:else}
					{$t('batting_save_all')}
				{/if}
			</button>
		</div>
	</div>

	{#if loading}
		<div class="p-16 text-center">
			<span class="loading loading-spinner loading-lg text-primary"></span>
			<p class="mt-2 text-sm text-base-content/60">{$t('pitching_loading')}</p>
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="table w-full">
				<thead class="bg-base-200">
					<tr>
						<th class="text-base-content font-bold w-40">{$t('pitching_pitcher')}</th>
						<th class="text-base-content font-bold text-center w-16">{$t('pitching_from_inning')}</th>
						<th class="text-base-content font-bold text-center w-16">{$t('pitching_to_inning')}</th>
						<th class="text-base-content font-bold text-center w-16">{$t('pitching_ip_outs')}</th>
						<th class="text-base-content font-bold text-center w-14">R</th>
						<th class="text-base-content font-bold text-center w-14">K</th>
						<th class="text-base-content font-bold text-center w-14">BB</th>
						<th class="text-base-content font-bold text-center w-14">HBP</th>
						<th class="text-base-content font-bold text-center w-16">{$t('pitching_pitches')}</th>
						<th class="text-base-content font-bold text-center w-12"></th>
					</tr>
				</thead>
				<tbody>
					{#each appearances as app, i}
						<tr class="hover:bg-base-200/50 transition-colors">
							<td>
								<select bind:value={app.player_id} class="select select-bordered select-sm w-full font-medium">
									{#each players as p}
										<option value={p.id}>#{p.jersey} {p.first_name} {p.last_name}</option>
									{/each}
								</select>
							</td>
							<td class="text-center"><input type="number" min="1" step="any" value={app.inning_entered === 0 ? '' : app.inning_entered} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.inning_entered = parseInt(v) || 0; app.ip_outs = calculateOuts(app.inning_entered, app.inning_exited); isDirty = true; }} class="input input-bordered input-sm text-center w-16" /></td>
							<td class="text-center"><input type="number" min="1" step="any" value={app.inning_exited === 0 ? '' : app.inning_exited} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.inning_exited = parseInt(v) || 0; app.ip_outs = calculateOuts(app.inning_entered, app.inning_exited); isDirty = true; }} class="input input-bordered input-sm text-center w-16" /></td>
							<td class="text-center"><input type="number" min="0" value={app.ip_outs === 0 ? '' : app.ip_outs} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.ip_outs = parseInt(v) || 0; isDirty = true; }} class="input input-bordered input-sm text-center w-16" /></td>
							<td class="text-center"><input type="number" min="0" value={app.runs_allowed === 0 ? '' : app.runs_allowed} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.runs_allowed = parseInt(v) || 0; isDirty = true; }} class="input input-bordered input-sm text-center w-14" /></td>
							<td class="text-center"><input type="number" min="0" value={app.k === 0 ? '' : app.k} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.k = parseInt(v) || 0; isDirty = true; }} class="input input-bordered input-sm text-center w-14" /></td>
							<td class="text-center"><input type="number" min="0" value={app.bb === 0 ? '' : app.bb} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.bb = parseInt(v) || 0; isDirty = true; }} class="input input-bordered input-sm text-center w-14" /></td>
							<td class="text-center"><input type="number" min="0" value={app.hbp === 0 ? '' : app.hbp} oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.hbp = parseInt(v) || 0; isDirty = true; }} class="input input-bordered input-sm text-center w-14" /></td>
							<td class="text-center"><input type="number" min="0" value={app.pitch_count === 0 ? '' : app.pitch_count} placeholder="—" oninput={(e) => { const v = (e.currentTarget as HTMLInputElement).value; app.pitch_count = parseInt(v) || 0; isDirty = true; }} class="input input-bordered input-sm text-center w-16" /></td>
							<td class="text-center">
								<button onclick={() => removeRow(i)} class="btn btn-ghost btn-error btn-xs">✕</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
