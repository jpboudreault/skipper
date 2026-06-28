<script lang="ts">
	import { onMount } from 'svelte';
	import { completeMicrosoftSession, initMsal } from '$lib/msal';
	import { t } from '$lib/i18n';

	let status: 'loading' | 'error' = $state('loading');
	let errorMessage = $state('');

	onMount(async () => {
		try {
			const res = await fetch('/api/config');
			if (!res.ok) {
				throw new Error('Failed to load configuration');
			}
			const data = await res.json();
			const clientId = data.microsoft_client_id;
			if (!clientId) {
				throw new Error('Microsoft login is not configured');
			}

			const { redirectResult } = await initMsal(clientId);

			if (!redirectResult) {
				window.location.href = '/login';
				return;
			}

			if (!redirectResult.idToken) {
				throw new Error('No ID token received from Microsoft');
			}

			await completeMicrosoftSession(redirectResult.idToken);
			window.location.href = '/';
		} catch (e) {
			status = 'error';
			errorMessage = e instanceof Error ? e.message : String(e);
		}
	});
</script>

<div class="bg-base-200 flex min-h-screen items-center justify-center px-4 py-12">
	<div
		class="card bg-base-100 border-base-300 w-full max-w-md space-y-6 border p-8 text-center shadow-xl"
	>
		{#if status === 'loading'}
			<span class="loading loading-spinner loading-lg text-primary mx-auto"></span>
			<p class="text-base-content/70 text-sm font-medium">{$t('login_verifying')}</p>
		{:else}
			<div class="alert alert-error rounded-lg py-3 text-sm shadow-sm">
				<span>{errorMessage}</span>
			</div>
			<a href="/login" class="btn btn-primary">{$t('login_authentication')}</a>
		{/if}
	</div>
</div>
