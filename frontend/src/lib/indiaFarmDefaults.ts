/** Curated statewide defaults for farm onboarding (not district-level surveys). */

export type IndianStateId =
  | "Andhra Pradesh"
  | "Arunachal Pradesh"
  | "Assam"
  | "Bihar"
  | "Chhattisgarh"
  | "Goa"
  | "Gujarat"
  | "Haryana"
  | "Himachal Pradesh"
  | "Jharkhand"
  | "Karnataka"
  | "Kerala"
  | "Madhya Pradesh"
  | "Maharashtra"
  | "Manipur"
  | "Meghalaya"
  | "Mizoram"
  | "Nagaland"
  | "Odisha"
  | "Punjab"
  | "Rajasthan"
  | "Sikkim"
  | "Tamil Nadu"
  | "Telangana"
  | "Tripura"
  | "Uttar Pradesh"
  | "Uttarakhand"
  | "West Bengal"
  | "Andaman and Nicobar Islands"
  | "Chandigarh"
  | "Dadra and Nagar Haveli and Daman and Diu"
  | "Delhi"
  | "Jammu and Kashmir"
  | "Ladakh"
  | "Lakshadweep"
  | "Puducherry";

export type StateFarmDefaults = {
  id: IndianStateId;
  /** Dominant / most common soil family in the state (simplified). */
  soil: string;
  /** Commonly grown crops (primary season staples + cash crops). */
  crops: string[];
};

/** Aliases returned by reverse-geocoders → canonical state id. */
const STATE_ALIASES: Record<string, IndianStateId> = {
  "nct of delhi": "Delhi",
  "national capital territory of delhi": "Delhi",
  "delhi": "Delhi",
  "jammu & kashmir": "Jammu and Kashmir",
  "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
  "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
  "pondicherry": "Puducherry",
  "orissa": "Odisha",
};

export const INDIA_STATE_DEFAULTS: StateFarmDefaults[] = [
  { id: "Andhra Pradesh", soil: "Red loamy / black cotton (regur)", crops: ["Rice", "Groundnut", "Cotton", "Chilli", "Sugarcane", "Maize"] },
  { id: "Arunachal Pradesh", soil: "Acidic red / forest loam", crops: ["Rice", "Maize", "Millet", "Potato", "Mustard"] },
  { id: "Assam", soil: "Alluvial / lateritic", crops: ["Rice", "Tea", "Jute", "Mustard", "Potato"] },
  { id: "Bihar", soil: "Gangetic alluvial", crops: ["Rice", "Wheat", "Maize", "Pulses", "Sugarcane"] },
  { id: "Chhattisgarh", soil: "Red / yellow / lateritic", crops: ["Rice", "Maize", "Pulses", "Oilseeds", "Sugarcane"] },
  { id: "Goa", soil: "Lateritic / coastal sandy", crops: ["Rice", "Cashew", "Coconut", "Arecanut", "Vegetables"] },
  { id: "Gujarat", soil: "Black cotton / alluvial / sandy", crops: ["Cotton", "Groundnut", "Wheat", "Bajra", "Castor"] },
  { id: "Haryana", soil: "Alluvial (sandy loam to clay loam)", crops: ["Wheat", "Rice", "Mustard", "Cotton", "Sugarcane"] },
  { id: "Himachal Pradesh", soil: "Hill / forest loam", crops: ["Apple", "Wheat", "Maize", "Potato", "Barley"] },
  { id: "Jharkhand", soil: "Red lateritic / sandy loam", crops: ["Rice", "Maize", "Pulses", "Oilseeds", "Vegetables"] },
  { id: "Karnataka", soil: "Red loamy / black cotton", crops: ["Ragi", "Rice", "Maize", "Sugarcane", "Coffee", "Cotton"] },
  { id: "Kerala", soil: "Lateritic / coastal alluvial", crops: ["Coconut", "Rubber", "Rice", "Pepper", "Banana", "Tea"] },
  { id: "Madhya Pradesh", soil: "Black cotton (regur) / red", crops: ["Soybean", "Wheat", "Gram", "Rice", "Maize", "Cotton"] },
  { id: "Maharashtra", soil: "Black cotton (regur)", crops: ["Cotton", "Soybean", "Jowar", "Sugarcane", "Onion", "Rice"] },
  { id: "Manipur", soil: "Red / lateritic hill soil", crops: ["Rice", "Maize", "Potato", "Pulses", "Vegetables"] },
  { id: "Meghalaya", soil: "Lateritic / acidic red", crops: ["Rice", "Maize", "Potato", "Turmeric", "Ginger"] },
  { id: "Mizoram", soil: "Acidic red / forest loam", crops: ["Rice", "Maize", "Ginger", "Turmeric", "Vegetables"] },
  { id: "Nagaland", soil: "Acidic red / forest loam", crops: ["Rice", "Maize", "Millet", "Potato", "Pulses"] },
  { id: "Odisha", soil: "Red / lateritic / coastal alluvial", crops: ["Rice", "Pulses", "Oilseeds", "Sugarcane", "Cotton"] },
  { id: "Punjab", soil: "Alluvial (sandy loam to loam)", crops: ["Wheat", "Rice", "Cotton", "Maize", "Sugarcane"] },
  { id: "Rajasthan", soil: "Desert sandy / arid / black in south", crops: ["Bajra", "Wheat", "Mustard", "Gram", "Cotton", "Guar"] },
  { id: "Sikkim", soil: "Hill / forest loam", crops: ["Maize", "Rice", "Cardamom", "Potato", "Ginger"] },
  { id: "Tamil Nadu", soil: "Red loamy / black / alluvial", crops: ["Rice", "Sugarcane", "Groundnut", "Cotton", "Banana", "Coconut"] },
  { id: "Telangana", soil: "Red sandy loam / black cotton", crops: ["Rice", "Cotton", "Maize", "Red gram", "Chilli"] },
  { id: "Tripura", soil: "Lateritic / alluvial", crops: ["Rice", "Rubber", "Potato", "Jute", "Vegetables"] },
  { id: "Uttar Pradesh", soil: "Gangetic alluvial", crops: ["Wheat", "Rice", "Sugarcane", "Potato", "Mustard", "Pulses"] },
  { id: "Uttarakhand", soil: "Hill / forest loam / alluvial in plains", crops: ["Rice", "Wheat", "Mandua", "Potato", "Sugarcane"] },
  { id: "West Bengal", soil: "Gangetic alluvial / lateritic", crops: ["Rice", "Jute", "Potato", "Mustard", "Tea", "Wheat"] },
  { id: "Andaman and Nicobar Islands", soil: "Coastal sandy / lateritic", crops: ["Coconut", "Rice", "Arecanut", "Banana", "Vegetables"] },
  { id: "Chandigarh", soil: "Alluvial loam", crops: ["Wheat", "Rice", "Maize", "Vegetables"] },
  { id: "Dadra and Nagar Haveli and Daman and Diu", soil: "Coastal alluvial / lateritic", crops: ["Rice", "Nagli", "Pulses", "Vegetables"] },
  { id: "Delhi", soil: "Yamuna alluvial", crops: ["Wheat", "Mustard", "Vegetables", "Fodder"] },
  { id: "Jammu and Kashmir", soil: "Alluvial / mountain loam", crops: ["Rice", "Maize", "Wheat", "Apple", "Saffron"] },
  { id: "Ladakh", soil: "Cold desert sandy / skeletal", crops: ["Barley", "Wheat", "Apricot", "Vegetables"] },
  { id: "Lakshadweep", soil: "Coral sandy", crops: ["Coconut", "Banana", "Vegetables"] },
  { id: "Puducherry", soil: "Coastal alluvial / red loam", crops: ["Rice", "Sugarcane", "Groundnut", "Coconut", "Cotton"] },
];

const BY_ID = new Map(INDIA_STATE_DEFAULTS.map((row) => [row.id, row]));

export function listIndianStates(): IndianStateId[] {
  return INDIA_STATE_DEFAULTS.map((row) => row.id);
}

export function getStateDefaults(state: string | null | undefined): StateFarmDefaults | null {
  const id = normalizeIndianState(state);
  return id ? BY_ID.get(id) ?? null : null;
}

export function normalizeIndianState(raw: string | null | undefined): IndianStateId | null {
  if (!raw?.trim()) return null;
  const trimmed = raw.trim();
  const direct = BY_ID.get(trimmed as IndianStateId);
  if (direct) return direct.id;
  const key = trimmed.toLowerCase().replace(/\s+/g, " ");
  if (STATE_ALIASES[key]) return STATE_ALIASES[key];
  for (const row of INDIA_STATE_DEFAULTS) {
    if (row.id.toLowerCase() === key) return row.id;
  }
  return null;
}

/** Parse saved location like "Hubli, Karnataka" or "Karnataka". */
export function parseLocationParts(location: string): { place: string; state: IndianStateId | null } {
  const text = location.trim();
  if (!text) return { place: "", state: null };

  const asState = normalizeIndianState(text);
  if (asState) return { place: "", state: asState };

  const comma = text.lastIndexOf(",");
  if (comma >= 0) {
    const place = text.slice(0, comma).trim();
    const state = normalizeIndianState(text.slice(comma + 1));
    if (state) return { place, state };
  }

  // "Village Karnataka" trailing state token
  for (const row of INDIA_STATE_DEFAULTS) {
    const suffix = new RegExp(`(?:^|[\\s,])${row.id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`, "i");
    if (suffix.test(text)) {
      return {
        place: text.replace(suffix, "").replace(/[,\s]+$/, "").trim(),
        state: row.id,
      };
    }
  }

  return { place: text, state: null };
}

export function buildLocation(place: string, state: IndianStateId | null): string {
  const p = place.trim();
  if (state && p) return `${p}, ${state}`;
  if (state) return state;
  return p;
}

type ReverseGeoJson = {
  principalSubdivision?: string;
  countryCode?: string;
  locality?: string;
  city?: string;
  localityInfo?: {
    administrative?: Array<{ name?: string; adminLevel?: number; description?: string }>;
  };
};

/**
 * Browser-friendly reverse geocode (no API key).
 * Returns Indian state when possible.
 */
export async function reverseGeocodeIndianState(
  lat: number,
  lon: number,
): Promise<{ state: IndianStateId | null; place: string }> {
  const url =
    `https://api.bigdatacloud.net/data/reverse-geocode-client` +
    `?latitude=${encodeURIComponent(String(lat))}` +
    `&longitude=${encodeURIComponent(String(lon))}` +
    `&localityLanguage=en`;

  const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
  if (!res.ok) {
    throw new Error(`Geocode failed (${res.status})`);
  }
  const data = (await res.json()) as ReverseGeoJson;
  if (data.countryCode && data.countryCode.toUpperCase() !== "IN") {
    throw new Error("Location is outside India");
  }

  let state =
    normalizeIndianState(data.principalSubdivision) ??
    normalizeIndianState(
      data.localityInfo?.administrative?.find((a) => a.adminLevel === 4)?.name,
    ) ??
    normalizeIndianState(
      data.localityInfo?.administrative?.find((a) => a.adminLevel === 5)?.name,
    );

  if (!state && data.localityInfo?.administrative) {
    for (const admin of data.localityInfo.administrative) {
      const hit = normalizeIndianState(admin.name);
      if (hit) {
        state = hit;
        break;
      }
    }
  }

  const place = (data.locality || data.city || "").trim();
  return { state, place };
}
