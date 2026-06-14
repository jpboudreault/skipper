<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { apiFetch } from '$lib/api';
	
	let { children } = $props();
	
	let teams = $state<any[]>([]);
	let activeTeamId = $state<string>('');
	let teamName = $state('Loading...');
	let mobileMenuOpen = $state(false);
	
	onMount(async () => {
		if ($page.url.pathname === '/login') return;

		try {
			const res = await apiFetch('/teams/');
			if (res.ok) {
				teams = await res.json();
				if (teams.length > 0) {
					const cachedId = sessionStorage.getItem('activeTeamId');
					const exists = cachedId ? teams.some(t => t.id.toString() === cachedId) : false;
					
					let currentTeam;
					if (cachedId && exists) {
						activeTeamId = cachedId;
						currentTeam = teams.find(t => t.id.toString() === cachedId);
					} else {
						activeTeamId = teams[0].id.toString();
						sessionStorage.setItem('activeTeamId', activeTeamId);
						currentTeam = teams[0];
					}
					
					teamName = currentTeam.name;
					sessionStorage.setItem('teamName', teamName);
				} else {
					teamName = 'No Team';
				}
			} else if (res.status === 401) {
				window.location.href = '/login';
			}
		} catch (e) {
			console.error("Failed to fetch teams", e);
			teamName = 'Error Loading Team';
		}
	});

	function handleTeamChange(e: Event) {
		const select = e.currentTarget as HTMLSelectElement;
		const teamId = select.value;
		sessionStorage.setItem('activeTeamId', teamId);
		const team = teams.find(t => t.id.toString() === teamId);
		if (team) {
			sessionStorage.setItem('teamName', team.name);
		}
		window.location.reload();
	}

	function closeMobileMenu() {
		mobileMenuOpen = false;
	}

	const navLinks = [
		{ href: '/', label: 'Dashboard', match: (p: string) => p === '/' },
		{ href: '/roster', label: 'Roster', match: (p: string) => p.startsWith('/roster') },
		{ href: '/matrix', label: 'Position Ratings', match: (p: string) => p.startsWith('/matrix') },
		{ href: '/games', label: 'Games', match: (p: string) => p.startsWith('/games') },
		{ href: '/stats', label: 'Stats', match: (p: string) => p.startsWith('/stats') },
	];
</script>

{#if $page.url.pathname !== '/login'}
	<div class="navbar bg-base-100 border-b border-base-300 px-4 sm:px-8 shadow-sm print:hidden">
		<div class="flex-1">
			<span class="text-xl font-extrabold text-primary tracking-wider uppercase flex items-center gap-1 sm:gap-2">
				⚾ Skipper 
				<span class="opacity-30 font-normal">|</span> 
				{#if teams.length > 1}
					<select 
						class="select select-ghost select-xs text-base font-bold bg-base-200/50 hover:bg-base-200 border-none rounded-lg px-2 py-1 h-auto min-h-0 focus:outline-none lowercase first-letter:uppercase" 
						value={activeTeamId} 
						onchange={handleTeamChange}
					>
						{#each teams as team}
							<option value={team.id.toString()} class="text-sm font-semibold">{team.name} ({team.season})</option>
						{/each}
					</select>
				{:else}
					<span class="text-base-content/85 text-base font-bold normal-case tracking-normal">{teamName}</span>
				{/if}
			</span>
		</div>

		<!-- Desktop nav links (hidden on mobile) -->
		<div class="flex-none gap-1 sm:gap-2 hidden md:flex">
			{#each navLinks as link}
				<a href={link.href} class="btn btn-ghost btn-sm {link.match($page.url.pathname) ? 'btn-active' : ''}">{link.label}</a>
			{/each}
			<a href="/auth/logout" class="btn btn-outline btn-error btn-sm ml-2">Logout</a>
		</div>

		<!-- Mobile hamburger button (shown on mobile only) -->
		<div class="flex-none md:hidden">
			<button
				class="btn btn-ghost btn-square btn-sm"
				onclick={() => mobileMenuOpen = !mobileMenuOpen}
				aria-label="Toggle menu"
			>
				{#if mobileMenuOpen}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				{:else}
					<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
						<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
					</svg>
				{/if}
			</button>
		</div>
	</div>

	<!-- Mobile dropdown menu -->
	{#if mobileMenuOpen}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-40 bg-black/20 md:hidden" onclick={closeMobileMenu}></div>
		<div class="fixed top-[64px] left-0 right-0 z-50 bg-base-100 border-b border-base-300 shadow-lg md:hidden animate-in">
			<div class="flex flex-col p-2 gap-1">
				{#each navLinks as link}
					<a
						href={link.href}
						class="btn btn-ghost btn-sm justify-start {link.match($page.url.pathname) ? 'btn-active' : ''}"
						onclick={closeMobileMenu}
					>
						{link.label}
					</a>
				{/each}
				<div class="divider my-1"></div>
				<a href="/auth/logout" class="btn btn-outline btn-error btn-sm justify-start" onclick={closeMobileMenu}>Logout</a>
			</div>
		</div>
	{/if}
{/if}

<main class="min-h-screen bg-base-200 text-base-content p-4 sm:p-8 print:bg-white print:p-0 print:min-h-0">
	{@render children()}
</main>

<style>
	.animate-in {
		animation: slideDown 0.15s ease-out;
	}
	@keyframes slideDown {
		from { opacity: 0; transform: translateY(-8px); }
		to { opacity: 1; transform: translateY(0); }
	}
</style>
