<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { t, translate, statusLabel } from '$lib/i18n';

	let players: any[] = $state([]);
	let availability: any[] = $state([]);
	let loading = $state(true);

	let draggedPlayerId: number | null = $state(null);

	// Touch drag state
	let touchGhost: HTMLElement | null = $state(null);
	let touchCurrentStatus: string | null = $state(null);

	async function fetchData() {
		try {
			const [playersRes, availRes] = await Promise.all([
				apiFetch('/players/'),
				apiFetch(`/games/${$page.params.id}/availability`)
			]);
			if (playersRes.ok) players = await playersRes.json();
			if (availRes.ok) availability = await availRes.json();
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(fetchData);

	function getStatus(playerId: number): string {
		const a = availability.find((a) => a.player_id === playerId);
		return (a?.status || 'available').toLowerCase();
	}

	async function setStatus(playerId: number, newStatus: string) {
		console.log('[availability] sending status:', newStatus);

		// Optimistic update
		const existing = availability.find((a) => a.player_id === playerId);
		if (existing) {
			existing.status = newStatus;
		} else {
			availability.push({
				game_id: parseInt($page.params.id ?? ''),
				player_id: playerId,
				status: newStatus
			});
		}
		availability = [...availability];

		try {
			const res = await apiFetch(`/games/${$page.params.id}/availability`, {
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify([{ player_id: playerId, status: newStatus }])
			});
			console.log('[availability] response status:', res.status);
			if (!res.ok) {
				if (res.status === 401) {
					alert(translate('common_session_expired'));
					window.location.href = '/login';
				}
				throw new Error(`HTTP ${res.status}`);
			}
		} catch (e) {
			console.error('[availability] save failed:', e);
		}
	}

	// --- Desktop drag events ---
	function handleDragStart(e: DragEvent, playerId: number) {
		draggedPlayerId = playerId;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', playerId.toString());
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		if (e.dataTransfer) {
			e.dataTransfer.dropEffect = 'move';
		}
	}

	function handleDrop(e: DragEvent, newStatus: string) {
		e.preventDefault();
		if (draggedPlayerId !== null) {
			const playerId = draggedPlayerId;
			draggedPlayerId = null;
			if (getStatus(playerId) !== newStatus) {
				setStatus(playerId, newStatus);
			}
		}
	}

	// --- Touch drag events (mobile) ---
	function handleTouchStart(e: TouchEvent, playerId: number) {
		const touch = e.touches[0];
		draggedPlayerId = playerId;

		// Create a floating ghost element
		const target = e.currentTarget as HTMLElement;
		const ghost = target.cloneNode(true) as HTMLElement;
		ghost.style.position = 'fixed';
		ghost.style.zIndex = '9999';
		ghost.style.pointerEvents = 'none';
		ghost.style.opacity = '0.85';
		ghost.style.width = target.offsetWidth + 'px';
		ghost.style.transform = 'scale(1.05) rotate(2deg)';
		ghost.style.boxShadow = '0 8px 32px rgba(0,0,0,0.18)';
		ghost.style.left = touch.clientX - target.offsetWidth / 2 + 'px';
		ghost.style.top = touch.clientY - 30 + 'px';
		document.body.appendChild(ghost);
		touchGhost = ghost;

		// Dim the original
		target.style.opacity = '0.3';
	}

	function handleTouchMove(e: TouchEvent) {
		e.preventDefault(); // Prevent scrolling while dragging
		const touch = e.touches[0];

		if (touchGhost) {
			const target = e.currentTarget as HTMLElement;
			touchGhost.style.left = touch.clientX - target.offsetWidth / 2 + 'px';
			touchGhost.style.top = touch.clientY - 30 + 'px';
		}

		// Find which drop zone we're over
		const el = document.elementFromPoint(touch.clientX, touch.clientY);
		if (el) {
			const dropZone = el.closest('[data-drop-status]') as HTMLElement | null;
			touchCurrentStatus = dropZone?.dataset.dropStatus || null;

			// Highlight active zone
			document.querySelectorAll('[data-drop-status]').forEach((zone) => {
				(zone as HTMLElement).classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
			});
			if (dropZone) {
				dropZone.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
			}
		}
	}

	function handleTouchEnd(e: TouchEvent) {
		// Clean up ghost
		if (touchGhost) {
			touchGhost.remove();
			touchGhost = null;
		}

		// Restore original opacity
		const target = e.currentTarget as HTMLElement;
		target.style.opacity = '1';

		// Remove highlights
		document.querySelectorAll('[data-drop-status]').forEach((zone) => {
			(zone as HTMLElement).classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
		});

		// Perform the drop
		if (draggedPlayerId !== null && touchCurrentStatus) {
			const playerId = draggedPlayerId;
			const newStatus = touchCurrentStatus;
			draggedPlayerId = null;
			touchCurrentStatus = null;
			if (getStatus(playerId) !== newStatus) {
				setStatus(playerId, newStatus);
			}
		} else {
			draggedPlayerId = null;
			touchCurrentStatus = null;
		}
	}

	// --- Quick-action tap buttons for mobile ---
	function cycleStatus(playerId: number) {
		const current = getStatus(playerId);
		const order = ['available', 'absent', 'late'];
		const nextIdx = (order.indexOf(current) + 1) % order.length;
		setStatus(playerId, order[nextIdx]);
	}

	const columns = ['available', 'absent', 'late'];
</script>

{#if loading}
	<div class="p-16 text-center">
		<span class="loading loading-spinner loading-lg text-primary"></span>
		<p class="text-base-content/60 mt-2 text-sm">{$t('availability_loading')}</p>
	</div>
{:else}
	{#snippet availabilitySection(title: string, description: string, isCoach: boolean)}
		<div class="mb-6 {isCoach ? 'mt-12' : ''}">
			<h2 class="text-base-content text-xl font-bold">{title}</h2>
			<p class="text-base-content/60 text-sm">{description}</p>
		</div>
		<div class="flex flex-col items-stretch gap-6 md:flex-row">
			{#each columns as status}
				<div
					class="card bg-base-100 border-base-300 flex min-h-[250px] flex-1 flex-col border shadow-md transition-all duration-150"
					role="application"
					data-drop-status={status}
					ondragover={handleDragOver}
					ondrop={(e) => handleDrop(e, status)}
				>
					<div
						class="border-base-200 bg-base-200/40 flex items-center justify-between rounded-t-xl border-b p-4"
					>
						<h3
							class="text-sm font-bold tracking-wider uppercase
							{status === 'available' ? 'text-success' : ''}
							{status === 'absent' ? 'text-error' : ''}
							{status === 'late' ? 'text-warning' : ''}
						"
						>
							{statusLabel(status)}
						</h3>
						<span class="badge badge-neutral"
							>{players.filter((p) => !!p.is_coach === isCoach && getStatus(p.id) === status)
								.length}</span
						>
					</div>
					<div class="flex flex-grow flex-col gap-2 p-4">
						{#each players.filter((p) => !!p.is_coach === isCoach && getStatus(p.id) === status) as player}
							<div
								class="card bg-base-200/40 border-base-300 hover:bg-base-200/90 flex cursor-grab touch-none flex-row items-center gap-2 border p-3 transition-colors"
								role="button"
								tabindex="0"
								draggable="true"
								ondragstart={(e) => handleDragStart(e, player.id)}
								ontouchstart={(e) => handleTouchStart(e, player.id)}
								ontouchmove={(e) => handleTouchMove(e)}
								ontouchend={(e) => handleTouchEnd(e)}
							>
								<span class="badge badge-neutral badge-sm">#{player.jersey}</span>
								<span class="text-base-content text-sm font-medium"
									>{player.first_name} {player.last_name}</span
								>
								{#if player.is_coach}
									<span class="badge badge-xs badge-info ml-auto text-[9px] uppercase"
										>{player.coach_type === 'head' ? 'HC' : 'AC'}</span
									>
								{:else if player.is_substitute}
									<span class="badge badge-xs badge-neutral ml-auto text-[9px] uppercase"
										>{$t('lineup_sub')}</span
									>
								{/if}
								<!-- Mobile tap button: cycle through statuses -->
								<button
									class="btn btn-ghost btn-xs ml-auto md:hidden"
									onclick={(e) => {
										e.stopPropagation();
										cycleStatus(player.id);
									}}
									title={$t('availability_tap_change_status')}
								>
									{#if status === 'available'}
										<span class="text-error text-base">→</span>
									{:else if status === 'absent'}
										<span class="text-warning text-base">→</span>
									{:else}
										<span class="text-success text-base">→</span>
									{/if}
								</button>
							</div>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/snippet}

	{@render availabilitySection(
		$t('availability_player_availability'),
		$t('availability_player_availability_desc'),
		false
	)}
	{@render availabilitySection(
		$t('availability_coach_availability'),
		$t('availability_coach_availability_desc'),
		true
	)}
{/if}
