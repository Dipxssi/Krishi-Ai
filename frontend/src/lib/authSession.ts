import { notifyAuthChanged } from "@/lib/authEvents";
import { clearLegacyConversationStorage } from "@/lib/conversationStorage";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  farmer_id: string;
};

const TOKEN_KEY = "krishi-ai-access-token";
const USER_KEY = "krishi-ai-auth-user";
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

/**
 * Persist auth for the signed-in account.
 * Never copies another account's farm fields onto this farmer_id.
 */
export function persistAuthSession(accessToken: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));

  // Shared (unscoped) keys are unsafe on multi-account browsers / Vercel demos.
  clearLegacyFarmProfileStorage();
  clearLegacyConversationStorage();
  ensureEmptyScopedFarmProfile(user.farmer_id);

  notifyAuthChanged();
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem("krishi-ai-demo-user");
  clearLegacyFarmProfileStorage();
  clearLegacyConversationStorage();
  notifyAuthChanged();
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken() && getAuthUser());
}
