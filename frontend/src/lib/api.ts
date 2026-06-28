import { page } from '$app/stores';
import { get } from 'svelte/store';
import { getAcceptLanguage } from '$lib/i18n';

export const API_URL =
	typeof window !== 'undefined' &&
	window.location.hostname !== 'localhost' &&
	window.location.hostname !== '127.0.0.1'
		? ''
		: 'http://localhost:8000';

export async function apiFetch(path: string, options: RequestInit = {}) {
	const pageData = get(page).data;
	const token = pageData.user?.token;

	const headers = new Headers(options.headers || {});
	headers.set('Accept-Language', getAcceptLanguage());

	if (token && !headers.has('Authorization')) {
		headers.set('Authorization', `Bearer ${token}`);
	}

	const activeTeamId = sessionStorage.getItem('activeTeamId');
	if (activeTeamId && !headers.has('X-Active-Team-ID')) {
		headers.set('X-Active-Team-ID', activeTeamId);
	}

	let apiPath = path;
	if (!path.startsWith('http') && !path.startsWith('/api/') && path !== '/api') {
		apiPath = `/api${path.startsWith('/') ? path : '/' + path}`;
	}

	const url = apiPath.startsWith('http') ? apiPath : `${API_URL}${apiPath}`;
	const res = await fetch(url, { ...options, headers });

	if (
		res.status === 401 &&
		typeof window !== 'undefined' &&
		!window.location.pathname.startsWith('/login')
	) {
		window.location.href = '/login';
	}

	return res;
}
