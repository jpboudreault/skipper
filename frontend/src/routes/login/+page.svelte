<script lang="ts">
	import { onMount } from 'svelte';
	import type { IPublicClientApplication } from '@azure/msal-browser';
	import { completeMicrosoftSession, initMsal, startMicrosoftLogin } from '$lib/msal';
	import { t, translate } from '$lib/i18n';
	import { API_URL } from '$lib/api';

	let status: 'idle' | 'loading' | 'success' | 'error' = $state('idle');
	let errorMessage = $state('');
	let googleClientId = $state('');
	let microsoftClientId = $state('');
	let configLoaded = $state(false);
	let microsoftReady = $state(false);
	let msalInstance: IPublicClientApplication | null = null;

	const authConfigured = $derived(Boolean(googleClientId || microsoftClientId));

	onMount(async () => {
		try {
			const res = await fetch(`${API_URL}/api/config`);
			if (res.ok) {
				const data = await res.json();
				googleClientId = data.google_client_id || '';
				microsoftClientId = data.microsoft_client_id || '';
			}
			configLoaded = true;
		} catch (e) {
			console.error('Failed to load config', e);
			configLoaded = true;
		}

		if (googleClientId) {
			if (!document.getElementById('google-jssdk')) {
				const script = document.createElement('script');
				script.id = 'google-jssdk';
				script.src = 'https://accounts.google.com/gsi/client';
				script.async = true;
				script.defer = true;
				script.onload = initializeGoogleSignIn;
				document.head.appendChild(script);
			} else {
				initializeGoogleSignIn();
			}
		}

		if (microsoftClientId) {
			await initializeMicrosoftSignIn();
		}
	});

	function initializeGoogleSignIn() {
		if (typeof window !== 'undefined' && (window as any).google) {
			const google = (window as any).google;

			google.accounts.id.initialize({
				client_id: googleClientId,
				callback: handleGoogleCredentialResponse,
				auto_select: false,
				cancel_on_tap_outside: true
			});

			const btnContainer = document.getElementById('google-signin-btn');
			if (btnContainer) {
				google.accounts.id.renderButton(btnContainer, {
					type: 'standard',
					theme: 'filled_blue',
					size: 'large',
					text: 'signin_with',
					shape: 'rectangular',
					logo_alignment: 'left',
					width: btnContainer.clientWidth || 320
				});
			}

			google.accounts.id.prompt();
		}
	}

	async function initializeMicrosoftSignIn() {
		const { msal, redirectResult } = await initMsal(microsoftClientId);
		msalInstance = msal;

		if (redirectResult?.idToken) {
			status = 'loading';
			try {
				await completeMicrosoftSession(redirectResult.idToken);
				await handleAuthSuccess();
			} catch (e) {
				await handleAuthError(e);
			}
		}

		microsoftReady = true;
	}

	async function handleAuthSuccess() {
		status = 'success';
		setTimeout(() => {
			window.location.href = '/';
		}, 1500);
	}

	async function handleAuthError(e: unknown) {
		console.error('Login verification error:', e);
		status = 'error';
		errorMessage = e instanceof Error ? e.message : String(e);
	}

	async function handleGoogleCredentialResponse(response: { credential: string }) {
		status = 'loading';
		try {
			const res = await fetch('/auth/callback/google', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ credential: response.credential })
			});

			if (res.ok) {
				await handleAuthSuccess();
			} else {
				const errData = await res.json();
				throw new Error(errData.detail || translate('common_failed_to_load'));
			}
		} catch (e) {
			await handleAuthError(e);
		}
	}

	async function handleMicrosoftLogin() {
		if (!msalInstance || !microsoftReady) return;
		status = 'loading';
		try {
			await startMicrosoftLogin(msalInstance);
		} catch (e) {
			await handleAuthError(e);
		}
	}
</script>

<div class="bg-base-200 flex min-h-screen items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
	<div class="card bg-base-100 border-base-300 w-full max-w-md space-y-6 border p-8 shadow-xl">
		<div class="text-center">
			<h2
				class="text-primary flex items-center justify-center gap-2 text-4xl font-black tracking-wider uppercase"
			>
				⚾ Skipper
			</h2>
			<p class="text-base-content/60 mt-2 text-sm">{$t('login_subtitle')}</p>
		</div>

		<div class="divider">{$t('login_authentication')}</div>

		<div class="space-y-4">
			{#if status === 'loading'}
				<div class="flex flex-col items-center justify-center space-y-2 py-6">
					<span class="loading loading-spinner loading-lg text-primary"></span>
					<p class="text-base-content/70 text-sm font-medium">{$t('login_verifying')}</p>
				</div>
			{:else if status === 'success'}
				<div class="flex flex-col items-center justify-center space-y-2 py-6 text-center">
					<span class="animate-bounce text-5xl">🎉</span>
					<p class="text-md text-success mt-2 font-bold">{$t('login_login_successful')}</p>
					<p class="text-base-content/60 text-xs">{$t('login_redirecting')}</p>
				</div>
			{:else}
				{#if status === 'error'}
					<div class="alert alert-error rounded-lg py-3 text-sm shadow-sm">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							class="h-6 w-6 shrink-0 stroke-current"
							fill="none"
							viewBox="0 0 24 24"
							><path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
							/></svg
						>
						<span>{errorMessage}</span>
					</div>
				{/if}

				{#if configLoaded && !authConfigured}
					<div
						class="alert alert-warning flex flex-col items-start gap-2 rounded-lg py-3 text-sm shadow-sm"
					>
						<div class="text-warning-content flex items-center gap-2 font-bold">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								class="h-6 w-6 shrink-0 stroke-current"
								fill="none"
								viewBox="0 0 24 24"
								><path
									stroke-linecap="round"
									stroke-linejoin="round"
									stroke-width="2"
									d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
								/></svg
							>
							<span>{$t('login_config_missing')}</span>
						</div>
						<p class="text-xs leading-relaxed opacity-90">
							{$t('login_config_missing_detail')}
						</p>
					</div>
				{:else}
					<div class="flex flex-col items-center gap-4 py-4">
						{#if googleClientId}
							<div id="google-signin-btn" class="flex w-full max-w-xs justify-center"></div>
						{/if}
						{#if microsoftClientId}
							<button
								type="button"
								class="btn btn-neutral w-full max-w-xs gap-2"
								disabled={!microsoftReady}
								onclick={handleMicrosoftLogin}
							>
								<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 23 23">
									<path fill="#f35325" d="M1 1h10v10H1z" />
									<path fill="#81bc06" d="M12 1h10v10H12z" />
									<path fill="#05a6f0" d="M1 12h10v10H1z" />
									<path fill="#ffba08" d="M12 12h10v10H12z" />
								</svg>
								{$t('login_continue_with_microsoft')}
							</button>
						{/if}
					</div>
				{/if}
			{/if}
		</div>
	</div>
</div>
