import type { FarmContext } from "@/api";
import { getAuthUser } from "@/lib/authSession";

export const FARMER_STORAGE_KEY = "krishi-ai-farmer-profile";

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

export function loadFarmProfile(): FarmContext {
  const user = getAuthUser();
  const fallbackId = user?.farmer_id ?? "";
  try {
    const raw = localStorage.getItem(FARMER_STORAGE_KEY);
    if (!raw) return emptyFarmProfile(fallbackId);
    const parsed = JSON.parse(raw) as FarmContext;
    return {
      ...emptyFarmProfile(fallbackId),
      ...parsed,
      farmer_id: user?.farmer_id || parsed.farmer_id || fallbackId,
      farm_area_acres: Number(parsed.farm_area_acres) || 0,
      budget:
        parsed.budget == null || Number.isNaN(Number(parsed.budget))
          ? null
          : Number(parsed.budget) || null,
    };
  } catch {
    return emptyFarmProfile(fallbackId);
  }
}

export function saveFarmProfileLocal(profile: FarmContext): void {
  localStorage.setItem(FARMER_STORAGE_KEY, JSON.stringify(profile));
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

export function isFarmProfileComplete(profile?: FarmContext): boolean {
  const user = getAuthUser();
  if (!user) return false;
  const p = profile ?? loadFarmProfile();
  if (p.farmer_id !== user.farmer_id) return false;
  if (localStorage.getItem(onboardingKey(user.farmer_id)) !== "1") return false;
  return Boolean(
    p.location.trim() &&
      (p.crop ?? "").trim() &&
      Number(p.farm_area_acres) > 0,
  );
}
