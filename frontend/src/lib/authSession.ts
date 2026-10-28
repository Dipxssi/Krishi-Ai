import { notifyAuthChanged } from "@/lib/authEvents";

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  farmer_id: string;
};

const TOKEN_KEY = "krishi-ai-access-token";
const USER_KEY = "krishi-ai-auth-user";
const FARMER_STORAGE_KEY = "krishi-ai-farmer-profile";

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

export function persistAuthSession(accessToken: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  // Bust useSyncExternalStore cache in this tab.
  notifyAuthChanged();

  try {
    const raw = localStorage.getItem(FARMER_STORAGE_KEY);
    if (!raw) {
      localStorage.setItem(
        FARMER_STORAGE_KEY,
        JSON.stringify({
          farmer_id: user.farmer_id,
          location: "",
          farm_area_acres: 0,
          crop: "",
          preferred_language: "en",
        }),
      );
      return;
    }
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (parsed.farmer_id && parsed.farmer_id !== user.farmer_id) {
      localStorage.setItem(
        FARMER_STORAGE_KEY,
        JSON.stringify({
          farmer_id: user.farmer_id,
          location: "",
          farm_area_acres: 0,
          crop: "",
          preferred_language: "en",
        }),
      );
      return;
    }
    localStorage.setItem(
      FARMER_STORAGE_KEY,
      JSON.stringify({ ...parsed, farmer_id: user.farmer_id }),
    );
  } catch {
    localStorage.setItem(
      FARMER_STORAGE_KEY,
      JSON.stringify({
        farmer_id: user.farmer_id,
        location: "",
        farm_area_acres: 0,
        crop: "",
        preferred_language: "en",
      }),
    );
  }
}

export function clearAuthSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem("krishi-ai-demo-user");
  notifyAuthChanged();
}

export function isAuthenticated(): boolean {
  return Boolean(getAccessToken() && getAuthUser());
}
