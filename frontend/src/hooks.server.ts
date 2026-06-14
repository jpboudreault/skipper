import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
	// If it's a backend API request (starts with /api/), proxy it directly to the local FastAPI server (127.0.0.1:8000)
	const isApiPath = event.url.pathname.startsWith('/api/') || event.url.pathname === '/api';
	
	if (isApiPath) {
		const targetUrl = `http://127.0.0.1:8000${event.url.pathname}${event.url.search}`;
		
		const headers = new Headers(event.request.headers);
		headers.delete('host'); // Avoid host conflicts on localhost forwarding
		
		try {
			const res = await fetch(targetUrl, {
				method: event.request.method,
				headers: headers,
				body: event.request.method !== 'GET' && event.request.method !== 'HEAD' 
					? await event.request.arrayBuffer() 
					: undefined,
				duplex: 'half' // Required for node-fetch with request bodies
			} as any);
			
			return res;
		} catch (err) {
			console.error('Error proxying to FastAPI:', err);
			return new Response('Backend server unavailable', { status: 502 });
		}
	}

	const session = event.cookies.get('session');

	if (session) {
		event.locals.user = { token: session };
	} else {
		event.locals.user = null;
	}

	// Route protection: anything other than /login and /auth/... needs a session
	if (!session && !event.url.pathname.startsWith('/login') && !event.url.pathname.startsWith('/auth/')) {
		return new Response('Redirect', { status: 303, headers: { Location: '/login' } });
	}

	return await resolve(event);
};
