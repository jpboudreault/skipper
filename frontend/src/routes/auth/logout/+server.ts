import { redirect, type RequestHandler } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ cookies }) => {
	// Clear the session cookie
	cookies.delete('session', { path: '/' });
	
	// Redirect to login page
	throw redirect(303, '/login');
};
