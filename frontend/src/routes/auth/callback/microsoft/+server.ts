import { json, type RequestHandler } from '@sveltejs/kit';

export const POST: RequestHandler = async ({ request, cookies }) => {
	try {
		const { id_token } = await request.json();

		if (!id_token) {
			return json({ detail: 'No id_token provided' }, { status: 400 });
		}

		const res = await fetch('http://127.0.0.1:8000/api/auth/microsoft', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'Accept-Language': request.headers.get('accept-language') || 'en'
			},
			body: JSON.stringify({ id_token })
		});

		if (!res.ok) {
			const errData = await res.json();
			return json({ detail: errData.detail || 'Authentication failed' }, { status: res.status });
		}

		const data = await res.json();

		cookies.set('session', data.access_token, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			secure: process.env.NODE_ENV === 'production',
			maxAge: 60 * 60 * 24 * 30
		});

		return json({ ok: true });
	} catch (e: any) {
		console.error('Microsoft Auth server callback error:', e);
		return json({ detail: e.message || 'Internal Server Error' }, { status: 500 });
	}
};
