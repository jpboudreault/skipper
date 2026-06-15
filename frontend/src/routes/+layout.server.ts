import type { LayoutServerLoad } from './$types';

function parseLockedLocale(value: string | undefined): 'en' | 'fr' | null {
	const normalized = value?.trim().toLowerCase();
	if (normalized === 'en' || normalized === 'fr') return normalized;
	return null;
}

export const load: LayoutServerLoad = async ({ locals }) => {
	return {
		user: locals.user,
		lockedLocale: parseLockedLocale(process.env.SKIPPER_LOCALE)
	};
};
