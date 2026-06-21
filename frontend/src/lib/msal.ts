import { PublicClientApplication, type AuthenticationResult, type IPublicClientApplication } from '@azure/msal-browser';

export const MICROSOFT_CALLBACK_PATH = '/auth/callback/microsoft';
export const MICROSOFT_SCOPES = ['openid', 'profile', 'email'];

export function getMicrosoftRedirectUri(): string {
	return `${window.location.origin}${MICROSOFT_CALLBACK_PATH}`;
}

export async function createMsalInstance(clientId: string): Promise<IPublicClientApplication> {
	const msal = new PublicClientApplication({
		auth: {
			clientId,
			authority: 'https://login.microsoftonline.com/common',
			redirectUri: getMicrosoftRedirectUri()
		},
		cache: {
			cacheLocation: 'sessionStorage'
		}
	});
	await msal.initialize();
	return msal;
}

/** Initialize MSAL and resolve any in-flight redirect before starting a new login. */
export async function initMsal(clientId: string): Promise<{
	msal: IPublicClientApplication;
	redirectResult: AuthenticationResult | null;
}> {
	const msal = await createMsalInstance(clientId);
	const redirectResult = await msal.handleRedirectPromise();
	return { msal, redirectResult };
}

export async function completeMicrosoftSession(idToken: string): Promise<void> {
	const authRes = await fetch('/auth/callback/microsoft', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ id_token: idToken })
	});

	if (!authRes.ok) {
		const err = await authRes.json();
		throw new Error(err.detail || 'Authentication failed');
	}
}

export async function startMicrosoftLogin(msal: IPublicClientApplication): Promise<void> {
	await msal.loginRedirect({
		scopes: MICROSOFT_SCOPES
	});
}
