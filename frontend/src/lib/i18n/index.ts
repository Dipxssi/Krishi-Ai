import { loadFarmProfile, saveFarmProfileLocal } from "@/lib/farmProfile";
import { dictionaries, type MessageKey } from "./messages";
import { DEFAULT_LOCALE, LOCALES, type Locale } from "./types";

export type { Locale, MessageKey };
export { LOCALES, DEFAULT_LOCALE };

const LOCALE_KEY = "krishi-ai-ui-locale";
const CHOSEN_KEY = "krishi-ai-ui-locale-chosen";

type Listener = () => void;
const listeners = new Set<Listener>();

function isLocale(value: string | null): value is Locale {
  return value === "en" || value === "hi" || value === "kn";
}

export function getLocale(): Locale {
  try {
    const stored = localStorage.getItem(LOCALE_KEY);
    if (isLocale(stored)) return stored;
  } catch {
    /* ignore */
  }
  return DEFAULT_LOCALE;
}

export function hasChosenLocale(): boolean {
  try {
    return localStorage.getItem(CHOSEN_KEY) === "1";
  } catch {
    return false;
  }
}

export function setLocale(locale: Locale, { markChosen = true }: { markChosen?: boolean } = {}): void {
  try {
    localStorage.setItem(LOCALE_KEY, locale);
    if (markChosen) localStorage.setItem(CHOSEN_KEY, "1");
  } catch {
    /* ignore */
  }

  if (typeof document !== "undefined") {
    document.documentElement.lang = locale === "en" ? "en" : locale;
  }

  // Keep farm advice language aligned with UI choice when a profile exists.
  try {
    const profile = loadFarmProfile();
    if (profile.farmer_id) {
      saveFarmProfileLocal({ ...profile, preferred_language: locale });
    }
  } catch {
    /* ignore */
  }

  listeners.forEach((listener) => listener());
}

export function subscribeLocale(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function t(
  key: MessageKey,
  vars?: Record<string, string | number>,
  locale: Locale = getLocale(),
): string {
  const table = dictionaries[locale] ?? dictionaries.en;
  let text = table[key] ?? dictionaries.en[key] ?? String(key);
  if (vars) {
    for (const [name, value] of Object.entries(vars)) {
      text = text.replaceAll(`{${name}}`, String(value));
    }
  }
  return text;
}
