<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	const API_URL = typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1'
		? ''
		: 'http://localhost:8000';

	let status: 'idle' | 'loading' | 'success' | 'error' = $state('idle');
	let errorMessage = $state('');
	let googleClientId = $state('');
	let configLoaded = $state(false);

	onMount(async () => {
		try {
			// 1. Fetch config from backend to get client ID
			const res = await fetch(`${API_URL}/api/config`);
			if (res.ok) {
				const data = await res.json();
				googleClientId = data.google_client_id || '';
			}
			configLoaded = true;
		} catch (e) {
			console.error("Failed to load config", e);
			configLoaded = true;
		}

		if (googleClientId) {
			// 2. Load the Google script
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
	});

	function initializeGoogleSignIn() {
		if (typeof window !== 'undefined' && (window as any).google) {
			const google = (window as any).google;
			
			// Initialize Google Identity
			google.accounts.id.initialize({
				client_id: googleClientId,
				callback: handleCredentialResponse,
				auto_select: false,
				cancel_on_tap_outside: true
			});

			// Render the custom button
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

			// Prompt One Tap (optional, fallback to button)
			google.accounts.id.prompt();
		}
	}

	async function handleCredentialResponse(response: any) {
		status = 'loading';
		try {
			// Send the Google credential token to our SvelteKit callback route
			const res = await fetch('/auth/callback/google', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ credential: response.credential })
			});

			if (res.ok) {
				status = 'success';
				// Delay briefly to show a nice success state, then do a hard redirect 
				// to ensure SvelteKit's root layout server-loads the new session cookie.
				setTimeout(() => {
					window.location.href = '/';
				}, 1500);
			} else {
				const errData = await res.json();
				throw new Error(errData.detail || 'Failed to authenticate with Google');
			}
		} catch (e: any) {
			console.error("Login verification error:", e);
			status = 'error';
			errorMessage = e.message || String(e);
		}
	}
</script>

<div class="min-h-screen flex items-center justify-center bg-base-200 py-12 px-4 sm:px-6 lg:px-8">
	<div class="card w-full max-w-md bg-base-100 shadow-xl border border-base-300 p-8 space-y-6">
		<div class="text-center">
			<h2 class="text-4xl font-black text-primary tracking-wider uppercase flex items-center justify-center gap-2">
				⚾ Skipper
			</h2>
			<p class="mt-2 text-sm text-base-content/60">Sign in to manage your team schedule & roster</p>
		</div>

		<div class="divider">Authentication</div>

		<div class="space-y-4">
			{#if status === 'loading'}
				<div class="flex flex-col items-center justify-center py-6 space-y-2">
					<span class="loading loading-spinner loading-lg text-primary"></span>
					<p class="text-sm font-medium text-base-content/70">Verifying with Google...</p>
				</div>
			{:else if status === 'success'}
				<div class="flex flex-col items-center justify-center py-6 space-y-2 text-center">
					<span class="text-5xl animate-bounce">🎉</span>
					<p class="text-md font-bold text-success mt-2">Login Successful!</p>
					<p class="text-xs text-base-content/60">Redirecting to your dashboard...</p>
				</div>
			{:else}
				{#if status === 'error'}
					<div class="alert alert-error text-sm py-3 shadow-sm rounded-lg">
						<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
						<span>{errorMessage}</span>
					</div>
				{/if}

				{#if configLoaded && !googleClientId}
					<div class="alert alert-warning text-sm py-3 shadow-sm rounded-lg flex flex-col items-start gap-2">
						<div class="flex items-center gap-2 font-bold text-warning-content">
							<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
							<span>Configuration Missing</span>
						</div>
						<p class="text-xs opacity-90 leading-relaxed">
							Google Sign-In is not configured yet. Please configure the <strong>GOOGLE_CLIENT_ID</strong> environment variable on your server (Fly.io / local .env) to enable login.
						</p>
					</div>
				{:else}
					<div class="flex justify-center py-4">
						<div id="google-signin-btn" class="w-full max-w-xs flex justify-center"></div>
					</div>
				{/if}
			{/if}
		</div>
	</div>
</div>
