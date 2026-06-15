<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t, translate } from '$lib/i18n';

	let { data } = $props();
	const token = $derived(data.user?.token);

	let players: any[] = $state([]);
	let team: any = $state(null);
	let loading = $state(true);
	let newPlayer = $state({ first_name: '', last_name: '', jersey: null as number | null, active: true, role: 'player' });

	let rosterRegular = $derived(players.filter(p => !p.is_coach && !p.is_substitute));
	let rosterCoaches = $derived(players.filter(p => p.is_coach).sort((a, b) => a.coach_type === 'head' ? -1 : 1));
	let rosterSubs = $derived(players.filter(p => p.is_substitute));
	let hasHeadCoach = $derived(players.some(p => p.is_coach && p.coach_type === 'head'));

	async function fetchTeam() {
		try {
			const res = await apiFetch('/teams/');
			if (res.ok) {
				const teams = await res.json();
				const activeId = sessionStorage.getItem('activeTeamId');
				if (teams.length > 0) {
					team = teams.find((t: any) => t.id.toString() === activeId) || teams[0];
				}
			}
		} catch (e) {
			console.error("Failed to fetch team", e);
		}
	}

	async function fetchPlayers() {
		try {
			const res = await apiFetch('/players/');
			if (res.ok) {
				players = await res.json();
			} else {
				const errText = await res.text();
				console.error("Failed to load players, server says:", errText);
				alert(translate('roster_failed_load_players', { error: errText }));
			}
		} catch (e: any) {
			console.error("Fetch error:", e);
			alert(translate('roster_fetch_error', { error: e.message || String(e) }));
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchTeam();
		fetchPlayers();
	});

	async function updatePlayer(player: any, field: string, value: any) {
		const originalValue = player[field];
		if (originalValue === value) return;
		
		player[field] = value;
		players = [...players]; // Trigger reactivity

		try {
			const res = await apiFetch(`/players/${player.id}`, {
				method: 'PUT',
				headers: { 
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ [field]: value })
			});
			if (!res.ok) {
				if (res.status === 401) {
					alert(translate('common_session_expired'));
					window.location.href = '/login';
				}
				throw new Error("Update failed");
			}
		} catch (e) {
			// Revert on error
			player[field] = originalValue;
			players = [...players];
			console.error(e);
			alert(translate('roster_failed_save_change'));
		}
	}

	async function updateRole(player: any, newRole: string) {
		let is_substitute = newRole === 'substitute';
		let is_coach = newRole === 'head_coach' || newRole === 'assistant_coach';
		let coach_type = newRole === 'head_coach' ? 'head' : (newRole === 'assistant_coach' ? 'assistant' : null);

		if (player.is_substitute === is_substitute && player.is_coach === is_coach && player.coach_type === coach_type) return;

		player.is_substitute = is_substitute;
		player.is_coach = is_coach;
		player.coach_type = coach_type;
		players = [...players];

		try {
			const res = await apiFetch(`/players/${player.id}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ is_substitute, is_coach, coach_type })
			});
			if (!res.ok) throw new Error("Update failed");
		} catch (e) {
			console.error(e);
			alert(translate('roster_failed_save_role'));
			fetchPlayers();
		}
	}

	async function addPlayer() {
		if (!newPlayer.first_name || !newPlayer.last_name || newPlayer.jersey === null) return;
		
		const payload = {
			...newPlayer,
			is_substitute: newPlayer.role === 'substitute',
			is_coach: newPlayer.role === 'head_coach' || newPlayer.role === 'assistant_coach',
			coach_type: newPlayer.role === 'head_coach' ? 'head' : (newPlayer.role === 'assistant_coach' ? 'assistant' : null)
		};
		// @ts-ignore
		delete payload.role;

		try {
			const res = await apiFetch('/players/', {
				method: 'POST',
				headers: { 
					'Content-Type': 'application/json'
				},
				body: JSON.stringify(payload)
			});
			if (res.ok) {
				const created = await res.json();
				players = [...players, created];
				newPlayer = { first_name: '', last_name: '', jersey: null, active: true, role: 'player' };
			}
		} catch (e) {
			console.error(e);
			alert(translate('roster_failed_add_player'));
		}
	}
	
	async function deletePlayer(id: number) {
		if (!confirm(translate('roster_confirm_remove'))) return;
		try {
			const res = await apiFetch(`/players/${id}`, {
				method: 'DELETE'
			});
			if (res.ok) {
				players = players.filter(p => p.id !== id);
			}
		} catch (e) {
			console.error(e);
		}
	}
</script>

<div class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
	<div class="sm:flex sm:items-center mb-6">
		<div class="sm:flex-auto">
			<h1 class="text-3xl font-bold text-base-content">
				{team ? `${team.name} ${team.season}` : $t('roster_team_roster')}
			</h1>
			<p class="mt-2 text-sm text-base-content/70">
				{team
					? $t('roster_managing_season', { season: team.season })
					: $t('roster_managing_default')}
			</p>
		</div>
	</div>

	<div class="card bg-base-100 shadow-xl border border-base-300 overflow-hidden">
		<div class="overflow-x-auto">
			<table class="table w-full">
				<thead class="bg-base-200">
					<tr>
						<th class="text-base-content font-bold w-24">{$t('roster_jersey')}</th>
						<th class="text-base-content font-bold">{$t('roster_first_name')}</th>
						<th class="text-base-content font-bold">{$t('roster_last_name')}</th>
						<th class="text-base-content font-bold w-40">{$t('roster_role')}</th>
						<th class="text-base-content font-bold w-32">{$t('roster_active')}</th>
						<th class="text-base-content font-bold w-24 text-right">{$t('common_actions')}</th>
					</tr>
				</thead>
				<tbody>
					{#if loading}
						<tr>
							<td colspan="5" class="text-center py-8">
								<span class="loading loading-spinner loading-md text-primary"></span>
								<p class="mt-2 text-sm text-base-content/60">{$t('roster_loading_players')}</p>
							</td>
						</tr>
					{:else if players.length === 0}
						<tr>
							<td colspan="5" class="text-center py-8 text-base-content/60">{$t('roster_no_players')}</td>
						</tr>
					{/if}
					
					{#snippet playerRow(player: any)}
						<tr class="hover:bg-base-200/50 transition-colors">
							<td>
								<input 
									type="number" 
									value={player.jersey} 
									onblur={(e) => updatePlayer(player, 'jersey', parseInt(e.currentTarget.value))}
									class="input input-bordered input-sm w-20"
								/>
							</td>
							<td>
								<div class="flex items-center gap-2">
									<input 
										type="text" 
										value={player.first_name} 
										onblur={(e) => updatePlayer(player, 'first_name', e.currentTarget.value)}
										class="input input-bordered input-sm w-full"
									/>
								</div>
							</td>
							<td>
								<input 
									type="text" 
									value={player.last_name} 
									onblur={(e) => updatePlayer(player, 'last_name', e.currentTarget.value)}
									class="input input-bordered input-sm w-full"
								/>
							</td>
							<td>
								<select
									value={player.is_coach ? (player.coach_type === 'head' ? 'head_coach' : 'assistant_coach') : (player.is_substitute ? 'substitute' : 'player')}
									onchange={(e) => updateRole(player, e.currentTarget.value)}
									class="select select-bordered select-sm w-full"
								>
									<option value="player">{$t('roster_role_player')}</option>
									<option value="substitute">{$t('roster_role_substitute')}</option>
									<option value="head_coach" disabled={hasHeadCoach && player.coach_type !== 'head'}>{$t('roster_role_head_coach')}</option>
									<option value="assistant_coach">{$t('roster_role_assistant_coach')}</option>
								</select>
							</td>
							<td>
								<select 
									value={player.active.toString()} 
									onchange={(e) => updatePlayer(player, 'active', e.currentTarget.value === 'true')}
									class="select select-bordered select-sm w-full"
								>
									<option value="true">{$t('common_yes')}</option>
									<option value="false">{$t('common_no')}</option>
								</select>
							</td>
							<td class="text-right">
								<button onclick={() => deletePlayer(player.id)} class="btn btn-ghost btn-error btn-xs">
									{$t('common_delete')}
								</button>
							</td>
						</tr>
					{/snippet}

					{#if rosterRegular.length > 0}
						<tr class="bg-base-300/50"><td colspan="6" class="font-bold text-sm uppercase text-base-content/70 py-2 px-4">{$t('roster_section_players')}</td></tr>
						{#each rosterRegular as player}
							{@render playerRow(player)}
						{/each}
					{/if}

					{#if rosterCoaches.length > 0}
						<tr class="bg-base-300/50"><td colspan="6" class="font-bold text-sm uppercase text-base-content/70 py-2 px-4">{$t('roster_section_coaches')}</td></tr>
						{#each rosterCoaches as player}
							{@render playerRow(player)}
						{/each}
					{/if}

					{#if rosterSubs.length > 0}
						<tr class="bg-base-300/50"><td colspan="6" class="font-bold text-sm uppercase text-base-content/70 py-2 px-4">{$t('roster_section_substitutes')}</td></tr>
						{#each rosterSubs as player}
							{@render playerRow(player)}
						{/each}
					{/if}

					<!-- Add new player row -->
					<tr class="bg-base-200/40">
						<td>
							<input 
								type="number" 
								bind:value={newPlayer.jersey} 
								placeholder="#"
								class="input input-bordered input-sm w-20"
							/>
						</td>
						<td>
							<input 
								type="text" 
								bind:value={newPlayer.first_name} 
								placeholder={$t('roster_first_name')}
								class="input input-bordered input-sm w-full"
							/>
						</td>
						<td>
							<input 
								type="text" 
								bind:value={newPlayer.last_name} 
								placeholder={$t('roster_last_name')}
								class="input input-bordered input-sm w-full"
							/>
						</td>
						<td>
							<select bind:value={newPlayer.role} class="select select-bordered select-sm w-full">
								<option value="player">{$t('roster_role_player')}</option>
								<option value="substitute">{$t('roster_role_substitute')}</option>
								<option value="head_coach" disabled={hasHeadCoach}>{$t('roster_role_head_coach')}</option>
								<option value="assistant_coach">{$t('roster_role_assistant_coach')}</option>
							</select>
						</td>
						<td>
							<span class="badge badge-success ml-2 py-3 px-4 font-bold">{$t('common_yes')}</span>
						</td>
						<td class="text-right">
							<button onclick={addPlayer} class="btn btn-primary btn-sm">
								{$t('roster_add_player')}
							</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</div>
