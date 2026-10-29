import { useCallback, useSyncExternalStore } from "react";
import {
  getLocale,
  hasChosenLocale,
  setLocale,
  subscribeLocale,
  t,
  type Locale,
  type MessageKey,
} from "@/lib/i18n";

function subscribe(onStoreChange: () => void) {
  return subscribeLocale(onStoreChange);
}

export function useI18n() {
  const locale = useSyncExternalStore(subscribe, getLocale, () => "en" as Locale);
  const chosen = useSyncExternalStore(
    subscribe,
    hasChosenLocale,
    () => true,
  );

  const translate = useCallback(
    (key: MessageKey, vars?: Record<string, string | number>) => t(key, vars, locale),
    [locale],
  );

  return {
    locale,
    chosen,
    setLocale,
    t: translate,
  };
}
