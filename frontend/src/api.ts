/** In dev, use Vite proxy (relative URLs). Set VITE_API_URL for production. */
const API_BASE = import.meta.env.VITE_API_URL ?? "";

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

export type FarmContextUpdate = Partial<Omit<FarmContext, "farmer_id">>;

export type ToolTrace = {
  agent: string;
  tool: string;
  arguments: Record<string, unknown>;
  status: string;
  output?: unknown;
  error?: string | null;
  timestamp?: string;
};

export type DecisionScore = {
  agronomic_suitability: number;
  expected_profit: number;
  water_risk: number;
  disease_risk?: number | null;
  input_cost: number;
  agronomic_score: number;
  economic_score: number;
  final_score: number;
  agronomic_weight: number;
  economic_weight: number;
};

export type QueryResponse = {
  request_id: string;
  query: string;
  farmer_id: string;
  selected_crop?: string | null;
  farm_profile_crop?: string | null;
  final_recommendation: string;
  structured_recommendation?: {
    action_summary: string;
    reasons: string[];
    financial_summary?: Record<string, number> | null;
    sources: string[];
    human_review_required: boolean;
    risk_level: string;
    conflicts_resolved: string[];
  } | null;
  image_diagnosis?: {
    status: string;
    rejection_reason?: string | null;
    plant_name?: string | null;
    predicted_disease?: string | null;
    is_healthy?: boolean;
    confidence?: number | null;
    confidence_is_calibrated?: boolean;
    model_version?: string | null;
    crop_id?: string | null;
    disease?: string | null;
    disease_confidence?: number | null;
    severity?: string | null;
    requires_expert: boolean;
    treatment_hints: string[];
    disclaimer?: string | null;
    top_3?: {
      display_name: string;
      confidence: number;
      class_idx?: number;
      crop?: string;
      disease?: string;
      is_healthy?: boolean;
    }[] | null;
  } | null;
  decision_score: DecisionScore | null;
  agents_used: string[];
  confidence: number;
  evidence: { source: string; value: unknown; unit?: string | null; agent?: string }[];
  tool_traces: ToolTrace[];
  warnings: string[];
  missing_context: string[];
  revision_count: number;
};

export type Loan = {
  id: string;
  name: string;
  category: string;
  interest_rate_percent: number;
  effective_rate_with_subvention_percent?: number | null;
  max_amount_inr?: number | null;
  repayment_period?: string;
  collateral?: string;
  eligibility: string;
  where_to_apply: string;
  documents?: string[];
};

export type Scheme = {
  id: string;
  name: string;
  category: string;
  benefit: string;
  eligibility: string;
  how_to_apply: string;
  link?: string;
  keywords?: string[];
};

export type CropArticle = {
  id: string;
  crop: string | null;
  title: string;
  text: string;
};

export type KnowledgeSummary = {
  scheme_count: number;
  crop_article_count: number;
  loan_count: number;
  scheme_categories: string[];
  crops_covered: string[];
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
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updateFarmer(farmerId: string, payload: FarmContextUpdate): Promise<FarmContext> {
  const res = await fetch(`${API_BASE}/farmers/${encodeURIComponent(farmerId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** Create a new profile or update an existing one (POST then PUT on 409). */
export async function saveFarmer(payload: FarmContext): Promise<"created" | "updated"> {
  const res = await fetch(`${API_BASE}/farmers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (res.status === 201) return "created";
  if (res.status === 409) {
    const { farmer_id, ...rest } = payload;
    await updateFarmer(farmer_id, rest);
    return "updated";
  }
  if (!res.ok) throw new Error(await parseError(res));
  return "created";
}

export async function getFarmer(farmerId: string): Promise<FarmContext> {
  const res = await fetch(`${API_BASE}/farmers/${encodeURIComponent(farmerId)}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function askAdvice(
  farmerId: string,
  query: string,
  imageBase64?: string | null,
  selectedCrop?: string | null,
  visionModel?: string | null,
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      farmer_id: farmerId,
      query,
      image_base64: imageBase64 || undefined,
      selected_crop: selectedCrop || undefined,
      vision_model: visionModel || undefined,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchKnowledgeSummary(): Promise<KnowledgeSummary> {
  const res = await fetch(`${API_BASE}/knowledge/summary`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchLoans(category?: string): Promise<{ items: Loan[]; total: number }> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/knowledge/loans${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchSchemes(category?: string, q?: string): Promise<{ items: Scheme[]; total: number }> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (q) params.set("q", q);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/knowledge/schemes${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchCropArticles(crop?: string, q?: string): Promise<{ items: CropArticle[]; total: number }> {
  const params = new URLSearchParams();
  if (crop) params.set("crop", crop);
  if (q) params.set("q", q);
  const qs = params.toString();
  const res = await fetch(`${API_BASE}/knowledge/crops${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export type MobileNetV3PredictionItem = {
  class_idx: number;
  display_name: string;
  crop: string;
  disease: string;
  is_healthy: boolean;
  confidence: number;
  confidence_is_calibrated: boolean;
};

export type MobileNetV3DiagnosisResponse = {
  status: "accepted" | "rejected";
  rejection_reason?: string | null;
  predicted_class?: string | null;
  crop_id?: string | null;
  disease?: string | null;
  confidence?: number | null;
  confidence_is_calibrated: boolean;
  top_3: MobileNetV3PredictionItem[];
  requires_expert: boolean;
  treatment_hints: string[];
  image_quality_score?: number | null;
  inference_time_ms: number;
  model_version: string;
  disclaimer: string;
};

export async function diagnoseMobileNetV3(
  imageBase64: string,
  cropHint?: string | null,
  confidenceThreshold?: number,
): Promise<MobileNetV3DiagnosisResponse> {
  const res = await fetch(`${API_BASE}/crop/mobilenetv3-diagnosis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      image_base64: imageBase64,
      crop_hint: cropHint || undefined,
      confidence_threshold: confidenceThreshold ?? 0.60,
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

