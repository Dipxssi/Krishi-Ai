const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export type FarmContext = {
  farmer_id: string;
  location: string;
  farm_area_acres: number;
  crop?: string | null;
  growth_stage?: string | null;
  soil_type?: string | null;
  soil_npk?: Record<string, number> | null;
  irrigation_available?: boolean | null;
  budget?: number | null;
  preferred_language?: string;
  season?: string | null;
};

export type QueryResponse = {
  query: string;
  farmer_id: string;
  final_recommendation: string;
  decision_score: {
    agronomic_score: number;
    economic_score: number;
    final_score: number;
    expected_profit: number;
    water_risk: number;
    disease_risk: number;
  } | null;
  agents_used: string[];
  confidence: number;
  evidence: { source: string; value: unknown; unit?: string | null }[];
  tool_traces: { agent: string; tool: string; status: string }[];
  warnings: string[];
  missing_context: string[];
  revision_count: number;
};

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    return JSON.stringify(data.detail ?? data);
  } catch {
    return res.statusText;
  }
}

export async function createFarmer(payload: FarmContext): Promise<FarmContext> {
  const res = await fetch(`${API_BASE}/farmers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.status === 409) {
    return getFarmer(payload.farmer_id);
  }
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getFarmer(farmerId: string): Promise<FarmContext> {
  const res = await fetch(`${API_BASE}/farmers/${encodeURIComponent(farmerId)}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function askAdvice(farmerId: string, query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ farmer_id: farmerId, query }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
