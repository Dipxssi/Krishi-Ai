import { getFarmer, type FarmContext } from "@/api";
import { getAuthUser } from "@/lib/authSession";

/** @deprecated Shared key — never read across accounts; removed on auth boundaries. */
export const FARMER_STORAGE_KEY = "krishi-ai-farmer-profile";

export function farmProfileStorageKey(farmerId: string): string {
  return `krishi-ai-farmer-profile:${farmerId}`;
}

function onboardingKey(farmerId: string) {
  return `krishi-ai-onboarding-complete:${farmerId}`;
}

export function emptyFarmProfile(farmerId = ""): FarmContext {
  return {
    farmer_id: farmerId,
    location: "",
    farm_area_acres: 0,
    crop: "",
    soil_type: "",
    budget: null,
    preferred_language: "en",
  };
}

function normalizeProfile(parsed: FarmContext, farmerId: string): FarmContext {
  return {
    ...emptyFarmProfile(farmerId),
    ...parsed,
    farmer_id: farmerId,
    farm_area_acres: Number(parsed.farm_area_acres) || 0,
    budget:
      parsed.budget == null || Number.isNaN(Number(parsed.budget))
        ? null
        : Number(parsed.budget) || null,
  };
}

/** Drop the unscoped profile key so it cannot leak between accounts. */
export function clearLegacyFarmProfileStorage(): void {
  try {
    localStorage.removeItem(FARMER_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Migrate legacy shared profile only when it already belongs to this farmer.
 * Otherwise delete it so the next account never inherits it.
 */
function readScopedOrMigrate(farmerId: string): FarmContext | null {
  const scopedRaw = localStorage.getItem(farmProfileStorageKey(farmerId));
  if (scopedRaw) {
    return normalizeProfile(JSON.parse(scopedRaw) as FarmContext, farmerId);
  }

  const legacyRaw = localStorage.getItem(FARMER_STORAGE_KEY);
  if (!legacyRaw) return null;

  try {
    const parsed = JSON.parse(legacyRaw) as FarmContext;
    if (parsed.farmer_id && parsed.farmer_id === farmerId) {
      const normalized = normalizeProfile(parsed, farmerId);
      localStorage.setItem(farmProfileStorageKey(farmerId), JSON.stringify(normalized));
      clearLegacyFarmProfileStorage();
      return normalized;
    }
  } catch {
    /* malformed */
  }

  clearLegacyFarmProfileStorage();
  return null;
}

export function loadFarmProfile(): FarmContext {
  const user = getAuthUser();
  const farmerId = user?.farmer_id ?? "";
  if (!farmerId) return emptyFarmProfile("");

  try {
    return readScopedOrMigrate(farmerId) ?? emptyFarmProfile(farmerId);
  } catch {
    return emptyFarmProfile(farmerId);
  }
}

export function saveFarmProfileLocal(profile: FarmContext): void {
  const farmerId = profile.farmer_id || getAuthUser()?.farmer_id;
  if (!farmerId) return;
  const normalized = normalizeProfile(profile, farmerId);
  localStorage.setItem(farmProfileStorageKey(farmerId), JSON.stringify(normalized));
  clearLegacyFarmProfileStorage();
}

export function ensureEmptyLocalFarmProfile(farmerId: string): void {
  if (!farmerId) return;
  if (localStorage.getItem(farmProfileStorageKey(farmerId))) return;
  saveFarmProfileLocal(emptyFarmProfile(farmerId));
}

/** Pull the signed-in farmer's Neon profile into user-scoped local cache. */
export async function hydrateFarmProfileFromServer(): Promise<FarmContext | null> {
  const user = getAuthUser();
  if (!user?.farmer_id) return null;
  try {
    const remote = await getFarmer(user.farmer_id);
    const local = loadFarmProfile();
    // Signup hydrates in the background. If the person already saved a real
    // farm profile, a slower response that still has the empty stub must not
    // overwrite it.
    if (hasRequiredFarmFields(local) && !hasRequiredFarmFields(remote)) {
      return local;
    }
    saveFarmProfileLocal(remote);
    syncOnboardingFlagFromProfile(remote);
    return remote;
  } catch {
    ensureEmptyLocalFarmProfile(user.farmer_id);
    const local = loadFarmProfile();
    syncOnboardingFlagFromProfile(local);
    return local;
  }
}

export function markOnboardingComplete(farmerId: string): void {
  localStorage.setItem(onboardingKey(farmerId), "1");
}

export function clearOnboardingComplete(farmerId?: string): void {
  if (farmerId) {
    localStorage.removeItem(onboardingKey(farmerId));
    return;
  }
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const key = localStorage.key(i);
    if (key?.startsWith("krishi-ai-onboarding-complete:")) keys.push(key);
  }
  keys.forEach((key) => localStorage.removeItem(key));
}

/** True when required farm fields are filled (ignores local onboarding flag). */
export function hasRequiredFarmFields(profile?: FarmContext): boolean {
  const user = getAuthUser();
  if (!user) return false;
  const p = profile ?? loadFarmProfile();
  if (p.farmer_id !== user.farmer_id) return false;
  return Boolean(
    p.location.trim() &&
      (p.crop ?? "").trim() &&
      Number(p.farm_area_acres) > 0,
  );
}

export function isFarmProfileComplete(profile?: FarmContext): boolean {
  const user = getAuthUser();
  if (!user) return false;
  const p = profile ?? loadFarmProfile();
  if (!hasRequiredFarmFields(p)) return false;
  return localStorage.getItem(onboardingKey(user.farmer_id)) === "1";
}

/**
 * After a returning user hydrates a complete Neon profile, treat onboarding as done
 * so they are not forced through the signup farm form again.
 */
export function syncOnboardingFlagFromProfile(profile?: FarmContext): void {
  const user = getAuthUser();
  if (!user?.farmer_id) return;
  const p = profile ?? loadFarmProfile();
  if (hasRequiredFarmFields(p)) {
    markOnboardingComplete(user.farmer_id);
  }
}
