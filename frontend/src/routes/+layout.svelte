<script lang="ts">
	import '../app.css';
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import {
		initLocale,
		isMultilingual,
		setLocale,
		locale,
		t,
		translate,
		type Locale
	} from '$lib/i18n';
	import { teams, activeTeamId, activeTeam, loadTeams, setActiveTeamId } from '$lib/teamContext';

	let { data, children } = $props();

	let loadStatus = $state<'loading' | 'loaded' | 'empty' | 'error'>('loading');
	let mobileMenuOpen = $state(false);

	let teamName = $derived(
		$activeTeam
			? $activeTeam.name
			: loadStatus === 'empty'
				? translate('nav_no_team')
				: loadStatus === 'error'
					? translate('nav_error_loading_team')
					: translate('nav_loading')
	);
	let isAuthRoute = $derived(
		$page.url.pathname === '/login' || $page.url.pathname.startsWith('/auth/')
	);

	onMount(async () => {
		initLocale(data.lockedLocale);

		if (isAuthRoute) return;

		try {
			const result = await loadTeams();
			loadStatus = result.teams.length > 0 ? 'loaded' : 'empty';
		} catch (e) {
			console.error('Failed to fetch teams', e);
			loadStatus = 'error';
		}
	});

	function handleTeamChange(e: Event) {
		const select = e.currentTarget as HTMLSelectElement;
		setActiveTeamId(select.value);
		window.location.reload();
	}

	function closeMobileMenu() {
		mobileMenuOpen = false;
	}

	function switchLocale(newLocale: Locale) {
		if ($locale === newLocale) return;
		setLocale(newLocale);
		window.location.reload();
	}

	const navLinks = $derived([
		{ href: '/', label: $t('nav_dashboard'), match: (p: string) => p === '/' },
		{ href: '/roster', label: $t('nav_roster'), match: (p: string) => p.startsWith('/roster') },
		{
			href: '/matrix',
			label: $t('nav_position_ratings'),
			match: (p: string) => p.startsWith('/matrix')
		},
		{ href: '/games', label: $t('nav_games'), match: (p: string) => p.startsWith('/games') },
		{ href: '/stats', label: $t('nav_stats'), match: (p: string) => p.startsWith('/stats') }
	]);
</script>

{#if !isAuthRoute}
	<div class="navbar bg-base-100 border-base-300 border-b px-4 shadow-sm sm:px-8 print:hidden">
		<div class="flex-1">
			<span
				class="text-primary flex items-center gap-1 text-xl font-extrabold tracking-wider uppercase sm:gap-2"
			>
				⚾ Skipper
				<span class="font-normal opacity-30">|</span>
				{#if $teams.length > 1}
					<select
						class="select select-ghost select-xs bg-base-200/50 hover:bg-base-200 h-auto min-h-0 rounded-lg border-none px-2 py-1 text-base font-bold lowercase first-letter:uppercase focus:outline-none"
						value={$activeTeamId}
						onchange={handleTeamChange}
					>
						{#each $teams as team}
							<option value={team.id.toString()} class="text-sm font-semibold"
								>{team.name} ({team.season})</option
							>
						{/each}
					</select>
				{:else}
					<span class="text-base-content/85 text-base font-bold tracking-normal normal-case"
						>{teamName}</span
					>
				{/if}
			</span>
		</div>

		<!-- Desktop nav links (hidden on mobile) -->
		<div class="hidden flex-none items-center gap-1 sm:gap-2 md:flex">
			{#if isMultilingual()}
				<div class="join border-base-300 mr-1 border">
					<button
						class="join-item btn btn-xs {$locale === 'en' ? 'btn-primary' : 'btn-ghost'}"
						onclick={() => switchLocale('en')}
						aria-label={$t('nav_language_en')}>EN</button
					>
					<button
						class="join-item btn btn-xs {$locale === 'fr' ? 'btn-primary' : 'btn-ghost'}"
						onclick={() => switchLocale('fr')}
						aria-label={$t('nav_language_fr')}>FR</button
					>
				</div>
			{/if}
			{#each navLinks as link}
				<a
					href={link.href}
					class="btn btn-ghost btn-sm {link.match($page.url.pathname) ? 'btn-active' : ''}"
					>{link.label}</a
				>
			{/each}
			<a href="/auth/logout" class="btn btn-outline btn-error btn-sm ml-2">{$t('nav_logout')}</a>
		</div>

		<!-- Mobile hamburger button (shown on mobile only) -->
		<div class="flex flex-none items-center gap-2 md:hidden">
			{#if isMultilingual()}
				<div class="join border-base-300 border">
					<button
						class="join-item btn btn-xs {$locale === 'en' ? 'btn-primary' : 'btn-ghost'}"
						onclick={() => switchLocale('en')}>EN</button
					>
					<button
						class="join-item btn btn-xs {$locale === 'fr' ? 'btn-primary' : 'btn-ghost'}"
						onclick={() => switchLocale('fr')}>FR</button
					>
				</div>
			{/if}
			<button
				class="btn btn-ghost btn-square btn-sm"
				onclick={() => (mobileMenuOpen = !mobileMenuOpen)}
				aria-label={$t('nav_toggle_menu')}
			>
				{#if mobileMenuOpen}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="h-6 w-6"
					>
						<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				{:else}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="2"
						stroke="currentColor"
						class="h-6 w-6"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
						/>
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
		<div
			class="bg-base-100 border-base-300 animate-in fixed top-[64px] right-0 left-0 z-50 border-b shadow-lg md:hidden"
		>
			<div class="flex flex-col gap-1 p-2">
				{#each navLinks as link}
					<a
						href={link.href}
						class="btn btn-ghost btn-sm justify-start {link.match($page.url.pathname)
							? 'btn-active'
							: ''}"
						onclick={closeMobileMenu}
					>
						{link.label}
					</a>
				{/each}
				<div class="divider my-1"></div>
				<a
					href="/auth/logout"
					class="btn btn-outline btn-error btn-sm justify-start"
					onclick={closeMobileMenu}>{$t('nav_logout')}</a
				>
			</div>
		</div>
	{/if}
{/if}

<main
	class="bg-base-200 text-base-content min-h-screen p-4 sm:p-8 print:min-h-0 print:bg-white print:p-0"
>
	{@render children()}
</main>

<style>
	.animate-in {
		animation: slideDown 0.15s ease-out;
	}
	@keyframes slideDown {
		from {
			opacity: 0;
			transform: translateY(-8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
