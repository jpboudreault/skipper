<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
import { beforeNavigate } from '$app/navigation';

	let players: any[] = $state([]);
	let battingData: Record<number, any> = $state({});
	let loading = $state(true);
	let saving = $state(false);
let isDirty = $state(false);
	let photoIngestionEnabled = $state(false);

	// Photo ingestion state
	let ingesting = $state(false);
	let ingestError = $state('');
	let ingestSuccess = $state(false);
	let dragOver = $state(false);

	// Players sorted by batting order (set in Lineup tab)
	let sortedPlayers = $derived(() => {
		const mapped = players
			.filter((p) => !p.is_coach)
			.map((p) => ({
				...p,
				batting_order: battingData[p.id]?.batting_order ?? null
			}));

		const hasAnyOrder = mapped.some((p) => p.batting_order !== null);

		if (hasAnyOrder) {
			// Only show players who are in the lineup (have a batting_order set)
			const inLineup = mapped.filter((p) => p.batting_order !== null);
			inLineup.sort((a, b) => (a.batting_order as number) - (b.batting_order as number));
			return inLineup;
		} else {
			// Fallback: show all available players sorted by jersey
			const fallback = [...mapped];
			fallback.sort((a, b) => a.jersey - b.jersey);
			return fallback;
		}
	});

	// Standard English baseball abbreviations
	const statColumns = [
		{ key: 'singles', label: '1B' },
		{ key: 'doubles', label: '2B' },
		{ key: 'triples', label: '3B' },
		{ key: 'hr', label: 'HR' },
		{ key: 'bb', label: 'BB' },
		{ key: 'bbi', label: 'IBB' }, // Intentional Base on Balls
		{ key: 'hbp', label: 'HBP' }, // Hit By Pitch
		{ key: 'sac', label: 'SAC' },
		{ key: 'intf', label: 'INT' },
		{ key: 'kd', label: 'KL' }, // Strikeout Looking
		{ key: 'ke', label: 'KS' }, // Strikeout Swinging
		{ key: 'outs_not_k', label: 'OUT' },
		{ key: 'fc', label: 'FC' }, // Fielder's Choice
		{ key: 'roe', label: 'ROE' }, // Reached on Error
		{ key: 'rbi', label: 'RBI' },
		{ key: 'r', label: 'R' },
		{ key: 'sb', label: 'SB' } // Stolen Base
	];

	async function fetchData() {
		try {
			const [playersRes, battingRes, availRes, configRes] = await Promise.all([
				apiFetch('/players/'),
				apiFetch(`/games/${$page.params.id}/batting`),
				apiFetch(`/games/${$page.params.id}/availability`),
				apiFetch('/config')
			]);

			if (configRes.ok) {
				const conf = await configRes.json();
				photoIngestionEnabled = conf.photo_ingestion_enabled;
			}

			if (battingRes.ok) {
				const lines = await battingRes.json();
				for (const line of lines) {
					battingData[line.player_id] = line;
				}
			}

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

			players = loadedPlayers.filter((p: any) => {
				if (!absentIds.has(p.id)) return true;
				// If absent, only include if they have actual non-zero stats
				const data = battingData[p.id];
				if (!data) return false;
				return statColumns.some((col) => data[col.key] > 0);
			});
		} catch (e) {
			console.error(e);
		} finally {
			loading = false;
		}
	}

	onMount(fetchData);

beforeNavigate((event) => {
    if (isDirty && !confirm('You have unsaved changes. Leave without saving?')) {
        event.cancel();
    }
});

	function getVal(playerId: number, key: string): number {
		return battingData[playerId]?.[key] ?? 0;
	}

	function setVal(playerId: number, key: string, value: number) {
		if (!battingData[playerId]) {
			battingData[playerId] = { player_id: playerId };
			for (const col of statColumns) {
				battingData[playerId][col.key] = 0;
			}
		}
		battingData[playerId][key] = value;
    isDirty = true;
	}

	async function saveAll() {
		saving = true;
		try {
			const lines = Object.values(battingData).map((d: any) => ({
				player_id: d.player_id,
				...Object.fromEntries(statColumns.map((c) => [c.key, d[c.key] ?? 0]))
			}));
			const res = await apiFetch(`/games/${$page.params.id}/batting`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(lines)
			});
			if (res.ok) {
				// Brief success flash
				setTimeout(() => { saving = false; isDirty = false; }, 500);
			} else {
				saving = false;
				alert('Failed to save');
			}
		} catch (e) {
			saving = false;
			console.error(e);
			alert('Error saving batting data');
		}
	}

	// --- Photo Ingestion ---

	async function ingestScoresheet(file: File) {
		ingesting = true;
		ingestError = '';
		ingestSuccess = false;

		try {
			const formData = new FormData();
			formData.append('file', file);

			const res = await apiFetch(`/games/${$page.params.id}/batting/ingest`, {
				method: 'POST',
				body: formData
				// Do NOT set Content-Type — browser sets it with multipart boundary
			});

			if (!res.ok) {
				const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
				throw new Error(err.detail || `Server error (${res.status})`);
			}

			const data = await res.json();
			const parsed: any[] = data.parsed || [];

			// Merge parsed results into battingData
			let matched = 0;
			for (const entry of parsed) {
				if (entry.player_id && entry.matched) {
					if (!battingData[entry.player_id]) {
						battingData[entry.player_id] = { player_id: entry.player_id };
					}
					for (const col of statColumns) {
						battingData[entry.player_id][col.key] = entry[col.key] ?? 0;
					}
					matched++;
				}
			}

			// Trigger reactivity
			battingData = { ...battingData };
			ingestSuccess = true;

			// Auto-dismiss success after 6 seconds
			setTimeout(() => (ingestSuccess = false), 6000);
		} catch (e: any) {
			ingestError = e.message || 'Failed to parse scoresheet';
			console.error('Ingest error:', e);
		} finally {
			ingesting = false;
		}
	}

	function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		if (input.files && input.files.length > 0) {
			ingestScoresheet(input.files[0]);
		}
	}

	function handleDrop(event: DragEvent) {
		event.preventDefault();
		dragOver = false;
		if (event.dataTransfer?.files && event.dataTransfer.files.length > 0) {
			ingestScoresheet(event.dataTransfer.files[0]);
		}
	}

	function handleDragOver(event: DragEvent) {
		event.preventDefault();
		dragOver = true;
	}

	function handleDragLeave() {
		dragOver = false;
	}
</script>

<div class="card bg-base-100 border-base-300 overflow-hidden border shadow-xl">
	<div class="border-base-200 bg-base-200/40 flex items-center justify-between border-b px-6 py-4">
		<div>
			<h2 class="text-base-content text-xl font-bold">Batting Stats</h2>
			<p class="text-base-content/70 mt-1 text-sm">
				Enter game batting stats for each player. Click Save when done.
			</p>
		</div>
		<button onclick={saveAll} disabled={saving} class="btn btn-success btn-sm shadow-md">
			{#if saving}
				<span class="loading loading-spinner loading-xs"></span>
				Saving...
			{:else}
				Save All
			{/if}
		</button>
	</div>

	{#if photoIngestionEnabled}
		<!-- Photo Upload Zone -->
		<div class="border-base-200 bg-base-100 border-b px-6 py-4">
		{#if ingesting}
			<!-- Ingesting state -->
			<div
				class="from-primary/5 to-secondary/5 border-primary/20 flex items-center justify-center gap-3 rounded-xl border-2 bg-gradient-to-r py-6"
			>
				<span class="loading loading-spinner loading-md text-primary"></span>
				<div>
					<p class="text-base-content font-semibold">Parsing scoresheet with AI...</p>
					<p class="text-base-content/60 text-sm">This can take up to 1 minute.</p>
				</div>
			</div>
		{:else}
			<!-- Dropzone -->
			<div
				role="button"
				tabindex="0"
				class="relative flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed py-6 transition-all
					{dragOver
					? 'border-primary bg-primary/10 scale-[1.01]'
					: 'border-base-300 hover:border-primary/50 hover:bg-base-200/30'}"
				ondrop={handleDrop}
				ondragover={handleDragOver}
				ondragleave={handleDragLeave}
				onclick={() => document.getElementById('scoresheet-upload')?.click()}
				onkeydown={(e) => {
					if (e.key === 'Enter' || e.key === ' ')
						document.getElementById('scoresheet-upload')?.click();
				}}
			>
				<input
					id="scoresheet-upload"
					type="file"
					accept="image/*,.heic,.heif"
					class="hidden"
					onchange={handleFileSelect}
				/>
				<svg
					class="text-primary/60 mb-2 h-10 w-10"
					fill="none"
					stroke="currentColor"
					viewBox="0 0 24 24"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
					></path>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="1.5"
						d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
					></path>
				</svg>
				<p class="text-base-content font-semibold">Upload Scoresheet Photo</p>
				<p class="text-base-content/50 mt-1 text-xs">
					Drag & drop or click to browse · JPEG, PNG, WebP
				</p>
			</div>
		{/if}

		<!-- Success alert -->
		{#if ingestSuccess}
			<div class="alert alert-success mt-3 shadow-sm">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-5 w-5 shrink-0 stroke-current"
					fill="none"
					viewBox="0 0 24 24"
					><path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
					/></svg
				>
				<span
					>Scoresheet parsed! Review the values below and click <strong>Save All</strong> when ready.</span
				>
			</div>
		{/if}

		<!-- Error alert -->
		{#if ingestError}
			<div class="alert alert-error mt-3 shadow-sm">
				<svg
					xmlns="http://www.w3.org/2000/svg"
					class="h-5 w-5 shrink-0 stroke-current"
					fill="none"
					viewBox="0 0 24 24"
					><path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
					/></svg
				>
				<span>{ingestError}</span>
				<button class="btn btn-ghost btn-xs" onclick={() => (ingestError = '')}>✕</button>
			</div>
		{/if}
	</div>
	{/if}

	{#if loading}
		<div class="p-16 text-center">
			<span class="loading loading-spinner loading-lg text-primary"></span>
			<p class="text-base-content/60 mt-2 text-sm">Loading batting scorecard...</p>
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="table-sm table-pin-rows table w-full">
				<thead class="bg-base-200">
					<tr>
						<th class="bg-base-300 text-base-content sticky left-0 z-20 w-12 font-bold">#</th>
						<th class="bg-base-300 text-base-content sticky left-12 z-20 min-w-[140px] font-bold"
							>Player</th
						>
						{#each statColumns as col}
							<th class="bg-base-200 text-base-content w-12 text-center font-bold">{col.label}</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each sortedPlayers() as player}
						<tr class="hover:bg-base-200/50 transition-colors">
							<td
								class="bg-base-100 text-base-content/70 border-base-300 sticky left-0 z-10 border-r font-bold"
								>{player.jersey}</td
							>
							<td
								class="bg-base-100 text-base-content border-base-300 sticky left-12 z-10 min-w-[140px] border-r font-medium"
								>{player.first_name} {player.last_name}</td
							>
							{#each statColumns as col}
								<td class="text-center">
									<input
										type="number"
										min="0"
										value={getVal(player.id, col.key) === 0 ? '' : getVal(player.id, col.key)}
										onblur={(e) => setVal(player.id, col.key, parseInt(e.currentTarget.value) || 0)}
										class="input input-bordered input-xs w-10 p-0 text-center"
									/>
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
