<script lang="ts">
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';

	let players: any[] = $state([]);
	let scores: any[] = $state([]);
	let loading = $state(true);

	const POSITIONS = [
		{ id: 1, name: 'P' },
		{ id: 2, name: 'C' },
		{ id: 3, name: '1B' },
		{ id: 4, name: '2B' },
		{ id: 5, name: '3B' },
		{ id: 6, name: 'SS' },
		{ id: 7, name: 'LF' },
		{ id: 8, name: 'CF' },
		{ id: 9, name: 'RF' }
	];

	let { data } = $props();
	const token = $derived(data.user?.token);

	async function fetchData() {
		try {
			const [playersRes, scoresRes] = await Promise.all([
				apiFetch('/players/'),
				apiFetch('/position-scores/')
			]);

			if (playersRes.ok && scoresRes.ok) {
				const allPlayers = await playersRes.json();
				players = allPlayers.filter((p: any) => !p.is_coach);
				scores = await scoresRes.json();
			}
		} catch (e) {
			console.error('Failed to fetch matrix data', e);
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		fetchData();
	});

	function getScoreObj(playerId: number, positionId: number) {
		const s = scores.find((s) => s.player_id === playerId && s.position === positionId);
		return s || { score: 0, is_forbidden: false };
	}

	async function updateScore(
		playerId: number,
		positionId: number,
		score: number,
		isForbidden: boolean
	) {
		// Optimistic update locally
		const existingIndex = scores.findIndex(
			(s) => s.player_id === playerId && s.position === positionId
		);
		const newScoreObj = {
			player_id: playerId,
			position: positionId,
			score,
			is_forbidden: isForbidden
		};

		if (existingIndex >= 0) {
			scores[existingIndex] = newScoreObj;
		} else {
			scores.push(newScoreObj);
		}

		try {
			const res = await apiFetch(`/position-scores/${playerId}/${positionId}`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({ score, is_forbidden: isForbidden })
			});
			if (!res.ok) {
				if (res.status === 401) {
					alert('Session expired. Please log in again.');
					window.location.href = '/login';
				}
				throw new Error('Failed to save');
			}
		} catch (e) {
			console.error(e);
			alert('Failed to save score');
		}
	}
</script>

<div class="mx-auto max-w-[1400px] px-4 py-8 sm:px-6 lg:px-8">
	<div class="sm:flex sm:items-center mb-6">
		<div class="sm:flex-auto">
			<h1 class="text-3xl font-bold text-base-content">Position Ratings</h1>
			<p class="mt-2 text-sm text-base-content/70">
				Rate players from 0-10 at each position. Check the box to mark a position as forbidden.
			</p>
		</div>
	</div>

	<div class="card bg-base-100 shadow-xl border border-base-300 overflow-hidden">
		{#if loading}
			<div class="p-16 text-center">
				<span class="loading loading-spinner loading-lg text-primary"></span>
				<p class="mt-2 text-sm text-base-content/60">Loading matrix...</p>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="table table-sm table-pin-rows table-pin-cols w-full">
					<thead>
						<tr>
							<th class="bg-base-300 text-base-content font-bold w-48 sticky left-0 z-20">
								Player
							</th>
							{#each POSITIONS as pos}
								<th class="bg-base-200 text-base-content font-bold text-center w-24">
									{pos.name}
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each players as player}
							<tr class="hover:bg-base-200/50 transition-colors">
								<td class="bg-base-100 font-medium text-base-content border-r border-base-300 sticky left-0 z-10">
									{player.first_name} {player.last_name}
									<span class="badge badge-sm badge-neutral ml-1">#{player.jersey}</span>
								</td>

								{#each POSITIONS as pos}
									{@const currentScore = getScoreObj(player.id, pos.id)}
									<td class="text-center border-r border-base-200 last:border-r-0 {currentScore.is_forbidden ? 'bg-error/10' : ''}">
										<div class="flex items-center justify-center space-x-1">
											<input
												type="number"
												min="0"
												max="10"
												value={currentScore.score}
												disabled={currentScore.is_forbidden}
												onblur={(e) =>
													updateScore(
														player.id,
														pos.id,
														parseInt(e.currentTarget.value) || 0,
														currentScore.is_forbidden
													)}
												class="input input-bordered input-xs text-center w-12"
											/>
											<input
												type="checkbox"
												checked={currentScore.is_forbidden}
												onchange={(e) =>
													updateScore(
														player.id,
														pos.id,
														currentScore.score,
														e.currentTarget.checked
													)}
												class="checkbox checkbox-error checkbox-xs"
												title="Forbidden"
											/>
										</div>
									</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>
