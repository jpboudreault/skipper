import { derived, get, writable } from 'svelte/store';
import en from '../../messages/en.json';
import fr from '../../messages/fr.json';

export type Locale = 'en' | 'fr';

const STORAGE_KEY = 'skipper-locale';
const messages: Record<Locale, Record<string, string>> = { en, fr };

let lockedLocale: Locale | null = null;

export const locale = writable<Locale>('en');

export function getLockedLocale(): Locale | null {
	return lockedLocale;
}

export function isMultilingual(): boolean {
	return lockedLocale === null;
}

export function detectLocale(): Locale {
	if (typeof window === 'undefined') return 'en';
	const saved = localStorage.getItem(STORAGE_KEY);
	if (saved === 'en' || saved === 'fr') return saved;
	for (const lang of navigator.languages ?? [navigator.language]) {
		const base = lang.split('-')[0].toLowerCase();
		if (base === 'fr') return 'fr';
		if (base === 'en') return 'en';
	}
	return 'en';
}

export function initLocale(serverLocked?: string | null): void {
	if (serverLocked === 'en' || serverLocked === 'fr') {
		lockedLocale = serverLocked;
		locale.set(serverLocked);
		return;
	}
	lockedLocale = null;
	locale.set(detectLocale());
}

export function setLocale(newLocale: Locale): void {
	if (lockedLocale) return;
	localStorage.setItem(STORAGE_KEY, newLocale);
	locale.set(newLocale);
}

export function getAcceptLanguage(): string {
	return get(locale);
}

function formatMessage(
	loc: Locale,
	key: string,
	params?: Record<string, string | number>
): string {
	let text = messages[loc][key] ?? messages.en[key] ?? key;
	if (params) {
		for (const [name, value] of Object.entries(params)) {
			text = text.replaceAll(`{${name}}`, String(value));
		}
	}
	return text;
}

export function translate(
	key: string,
	params?: Record<string, string | number>
): string {
	return formatMessage(get(locale), key, params);
}

export const t = derived(locale, ($locale) => {
	return (key: string, params?: Record<string, string | number>) =>
		formatMessage($locale, key, params);
});

export function statusLabel(status: string): string {
	const key = `availability_status_${status}`;
	return translate(key) !== key ? translate(key) : status;
}

export function formatLocaleDate(
	dateStr: string,
	options?: Intl.DateTimeFormatOptions
): string {
	if (!dateStr) return '';
	const loc = get(locale) === 'fr' ? 'fr-CA' : 'en-CA';
	// Calendar dates from the API (YYYY-MM-DD) are timezone-agnostic; parse as UTC
	// so evening games in Quebec do not display as the previous day.
	return new Date(dateStr).toLocaleDateString(loc, { timeZone: 'UTC', ...options });
}
