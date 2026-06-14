import { json, type RequestHandler } from '@sveltejs/kit';

export const POST: RequestHandler = async ({ request, cookies }) => {
	try {
		const { credential } = await request.json();
		
		if (!credential) {
			return json({ detail: 'No credential provided' }, { status: 400 });
		}

		const res = await fetch('http://127.0.0.1:8000/api/auth/google', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ credential })
		});

		if (!res.ok) {
			const errData = await res.json();
			return json({ detail: errData.detail || 'Authentication failed' }, { status: res.status });
		}

		const data = await res.json();
		
		// Set the session cookie
		cookies.set('session', data.access_token, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			secure: process.env.NODE_ENV === 'production',
			maxAge: 60 * 60 * 24 * 30 // 30 days
		});

		return json({ ok: true });
	} catch (e: any) {
		console.error("Google Auth server callback error:", e);
		return json({ detail: e.message || 'Internal Server Error' }, { status: 500 });
	}
};
