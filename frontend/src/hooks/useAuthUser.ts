import { useSyncExternalStore } from "react";
import type { AuthUser } from "@/api";
import { subscribeAuth } from "@/lib/authEvents";

const USER_KEY = "krishi-ai-auth-user";

let cachedRaw: string | null | undefined = undefined;
let cachedUser: AuthUser | null = null;

function readAuthUserCached(): AuthUser | null {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(USER_KEY);
  } catch {
    raw = null;
  }

  // Must return a stable reference when data is unchanged (React useSyncExternalStore).
  if (raw === cachedRaw) {
    return cachedUser;
  }

  cachedRaw = raw;
  if (!raw) {
    cachedUser = null;
    return cachedUser;
  }

  try {
    cachedUser = JSON.parse(raw) as AuthUser;
  } catch {
    cachedUser = null;
  }
  return cachedUser;
}

function invalidateAndNotify(onStoreChange: () => void) {
  cachedRaw = undefined;
  onStoreChange();
}

function subscribe(onStoreChange: () => void) {
  const unsubscribe = subscribeAuth(() => invalidateAndNotify(onStoreChange));
  const onStorage = (event: StorageEvent) => {
    if (
      event.key === USER_KEY ||
      event.key === "krishi-ai-access-token" ||
      event.key === "krishi-ai-offline-session" ||
      event.key === "krishi-ai-last-user" ||
      event.key === null
    ) {
      invalidateAndNotify(onStoreChange);
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    unsubscribe();
    window.removeEventListener("storage", onStorage);
  };
}

export function useAuthUser(): AuthUser | null {
  return useSyncExternalStore(subscribe, readAuthUserCached, () => null);
}

export function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}
