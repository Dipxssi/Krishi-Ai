import { notifyAuthChanged } from "@/lib/authEvents";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  farmer_id: string;
};

const TOKEN_KEY = "krishi-ai-access-token";
const USER_KEY = "krishi-ai-auth-user";
const LAST_USER_KEY = "krishi-ai-last-user";
const OFFLINE_MODE_KEY = "krishi-ai-offline-session";
const LEGACY_FARMER_STORAGE_KEY = "krishi-ai-farmer-profile";

function clearLegacyFarmProfileStorage(): void {
  try {
    localStorage.removeItem(LEGACY_FARMER_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function ensureEmptyScopedFarmProfile(farmerId: string): void {
  if (!farmerId) return;
  const key = `${LEGACY_FARMER_STORAGE_KEY}:${farmerId}`;
  try {
    if (localStorage.getItem(key)) return;
    localStorage.setItem(
      key,
      JSON.stringify({
        farmer_id: farmerId,
        location: "",
        farm_area_acres: 0,
        crop: "",
        soil_type: "",
        budget: null,
        preferred_language: "en",
      }),
    );
  } catch {
    /* ignore */
  }
}

function cacheLastUser(user: AuthUser): void {
  try {
    localStorage.setItem(LAST_USER_KEY, JSON.stringify(user));
  } catch {
    /* ignore */
  }
}

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getAuthUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/** Last successfully signed-in user (survives logout/token clear for offline Continue as). */
export function getLastCachedUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(LAST_USER_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function isOfflineSession(): boolean {
  try {
    return localStorage.getItem(OFFLINE_MODE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setOfflineSession(enabled: boolean): void {
  try {
    if (enabled) localStorage.setItem(OFFLINE_MODE_KEY, "1");
    else localStorage.removeItem(OFFLINE_MODE_KEY);
  } catch {
    /* ignore */
  }
  notifyAuthChanged();
}

/**
 * Persist auth for the signed-in account.
 * Never copies another account's farm fields onto this farmer_id.
 */
export function persistAuthSession(accessToken: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  cacheLastUser(user);
  setOfflineSession(false);

  // Shared farm profile key is unsafe across accounts; conversations migrate on first load.
  clearLegacyFarmProfileStorage();
  ensureEmptyScopedFarmProfile(user.farmer_id);

  notifyAuthChanged();
}

/** Drop the JWT but keep the user row for offline Continue as / offline session. */
export function clearAccessTokenOnly(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
  notifyAuthChanged();
}

/**
 * Enter chat without a live JWT using the last cached profile (Phase 1).
 * Signup / first-time users without a cache cannot use this.
 */
export function continueOfflineAs(user?: AuthUser | null): AuthUser | null {
  const cached = user ?? getLastCachedUser() ?? getAuthUser();
  if (!cached?.farmer_id) return null;
  try {
    localStorage.setItem(USER_KEY, JSON.stringify(cached));
    cacheLastUser(cached);
    localStorage.setItem(OFFLINE_MODE_KEY, "1");
  } catch {
    return null;
  }
  ensureEmptyScopedFarmProfile(cached.farmer_id);
  notifyAuthChanged();
  return cached;
}

export function clearAuthSession(): void {
  // Keep LAST_USER_KEY so offline Continue as still works after explicit logout.
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(OFFLINE_MODE_KEY);
  localStorage.removeItem("krishi-ai-demo-user");
  clearLegacyFarmProfileStorage();
  notifyAuthChanged();
}

/** Online JWT session OR intentional offline Continue-as session. */
export function isAuthenticated(): boolean {
  const user = getAuthUser();
  if (!user) return false;
  if (getAccessToken()) return true;
  return isOfflineSession();
}
