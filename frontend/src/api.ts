import type { Conversation } from "@/data/mockChats";
import { clearAuthSession, getAccessToken, type AuthUser } from "@/lib/authSession";

/** In dev, use Vite proxy (relative URLs). Set VITE_API_URL for production. */
const API_BASE = import.meta.env.VITE_API_URL ?? "";

export type { AuthUser };

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

export type EscalationDetails = {
  requires_escalation: boolean;
  urgency: string;
  reason: string;
  safe_next_step: string;
  sample_instructions: string;
  action_label: string;
};

export type QueryResponse = {
  request_id: string;
  query: string;
  farmer_id: string;
  selected_crop?: string | null;
  farm_profile_crop?: string | null;
  final_recommendation: string;
  response_language?: string;
  disclaimer?: string;
  escalation?: EscalationDetails | null;
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

function handleUnauthorized(res: Response): void {
  if (res.status !== 401) return;
  clearAuthSession();
  // Let RequireAuth / AuthSessionBootstrap navigate — keep outbox enqueue able to finish first.
}

/** Reject HTML/SPA responses so a wrong VITE_API_URL fails loudly instead of "empty history". */
async function ensureApiJson(res: Response, path: string): Promise<void> {
  if (res.status === 204) return;
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (ct.includes("application/json")) return;
  const snippet = (await res.clone().text()).slice(0, 80).replace(/\s+/g, " ");
  throw new Error(
    `API ${path} returned non-JSON (${res.status}, ${ct || "unknown type"}). ` +
      `Set Vercel VITE_API_URL to your Render FastAPI URL (no trailing slash). Preview: ${snippet}`,
  );
}

/** Sign-in/sign-up wait long enough for one cold start, then fail clearly. */
const AUTH_REQUEST_TIMEOUT_MS = 60_000;

export class ApiTimeoutError extends Error {
  constructor() {
    super("Krishi AI took too long to respond.");
    this.name = "ApiTimeoutError";
  }
}

async function apiFetch(
  path: string,
  init: RequestInit = {},
  auth = false,
  timeoutMs?: number,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const controller = timeoutMs ? new AbortController() : null;
  const timer = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: controller ? controller.signal : init.signal,
    });
    if (auth) handleUnauthorized(res);
    return res;
  } catch (error) {
    if (controller?.signal.aborted) throw new ApiTimeoutError();
    throw error;
  } finally {
    if (timer != null) window.clearTimeout(timer);
  }
}

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export async function signup(
  name: string,
  email: string,
  password: string,
  location?: string,
): Promise<AuthResponse> {
  const res = await apiFetch("/auth/signup", {
    method: "POST",
    body: JSON.stringify({
      name,
      email,
      password,
      location: location || undefined,
    }),
  }, false, AUTH_REQUEST_TIMEOUT_MS);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await apiFetch("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  }, false, AUTH_REQUEST_TIMEOUT_MS);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchMe(accessToken?: string | null): Promise<AuthUser> {
  const token = accessToken ?? getAccessToken();
  const res = await apiFetch("/auth/me", {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }, false, AUTH_REQUEST_TIMEOUT_MS);
  if (res.status === 401) {
    clearAuthSession();
  }
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createFarmer(payload: FarmContext): Promise<FarmContext> {
  const res = await apiFetch("/farmers", {
    method: "POST",
    body: JSON.stringify(payload),
  }, true);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updateFarmer(farmerId: string, payload: FarmContextUpdate): Promise<FarmContext> {
  const res = await apiFetch(`/farmers/${encodeURIComponent(farmerId)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  }, true);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** Update an existing profile, or create one if missing (PUT then POST on 404). */
export async function saveFarmer(payload: FarmContext): Promise<"created" | "updated"> {
  const { farmer_id, ...rest } = payload;
  const putRes = await apiFetch(`/farmers/${encodeURIComponent(farmer_id)}`, {
    method: "PUT",
    body: JSON.stringify(rest),
  }, true);
  if (putRes.ok) return "updated";
  if (putRes.status !== 404) {
    throw new Error(await parseError(putRes));
  }

  const postRes = await apiFetch("/farmers", {
    method: "POST",
    body: JSON.stringify(payload),
  }, true);
  if (postRes.status === 201 || postRes.ok) return "created";
  throw new Error(await parseError(postRes));
}

export async function getFarmer(farmerId: string): Promise<FarmContext> {
  const res = await apiFetch(`/farmers/${encodeURIComponent(farmerId)}`, {}, true);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function fetchRemoteConversations(): Promise<Conversation[]> {
  const res = await apiFetch("/conversations", {}, true);
  await ensureApiJson(res, "GET /conversations");
  if (res.status === 404) {
    throw new Error(
      "404 /conversations — this API host is not the KrishiAi FastAPI backend. Redeploy backend/ from this repo on Render and set Vercel VITE_API_URL to that service URL.",
    );
  }
  if (!res.ok) throw new Error(await parseError(res));
  const body = (await res.json()) as { conversations?: Conversation[] };
  return Array.isArray(body.conversations) ? body.conversations : [];
}

export async function pushRemoteConversations(conversations: Conversation[]): Promise<Conversation[]> {
  const res = await apiFetch(
    "/conversations",
    {
      method: "PUT",
      body: JSON.stringify({ conversations }),
    },
    true,
  );
  await ensureApiJson(res, "PUT /conversations");
  if (!res.ok) throw new Error(await parseError(res));
  const body = (await res.json()) as { conversations?: Conversation[] };
  return Array.isArray(body.conversations) ? body.conversations : [];
}

export async function pushRemoteConversation(conversation: Conversation): Promise<Conversation> {
  const res = await apiFetch(
    `/conversations/${encodeURIComponent(conversation.id)}`,
    {
      method: "PUT",
      body: JSON.stringify(conversation),
    },
    true,
  );
  await ensureApiJson(res, `PUT /conversations/${conversation.id}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteRemoteConversation(conversationId: string): Promise<void> {
  const res = await apiFetch(`/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  }, true);
  if (!res.ok && res.status !== 404) throw new Error(await parseError(res));
}

export async function deleteAllRemoteConversations(): Promise<void> {
  const res = await apiFetch("/conversations", { method: "DELETE" }, true);
  if (!res.ok) throw new Error(await parseError(res));
}

export async function askAdvice(
  farmerId: string,
  query: string,
  imageBase64?: string | null,
  selectedCrop?: string | null,
  visionModel?: string | null,
  language?: string | null,
): Promise<QueryResponse> {
  const res = await apiFetch("/query", {
    method: "POST",
    body: JSON.stringify({
      farmer_id: farmerId,
      query,
      image_base64: imageBase64 || undefined,
      selected_crop: selectedCrop || undefined,
      vision_model: visionModel || undefined,
      language: language || undefined,
    }),
  }, true);
  if (!res.ok) {
    if (res.status === 401) throw new Error("401 Unauthorized — sign in again when you have a connection.");
    throw new Error(await parseError(res));
  }
  return res.json();
}

export async function transcribeAudio(
  audioBase64: string,
  contentType: string,
  filename: string,
  languageHint?: string | null,
) {
  const res = await apiFetch("/voice/transcribe", {
    method: "POST",
    body: JSON.stringify({
      audio_base64: audioBase64,
      content_type: contentType,
      filename,
      language_hint: languageHint || undefined,
    }),
  }, true);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json() as Promise<{ text: string; normalized_crop?: string | null; note?: string | null }>;
}

export async function synthesizeSpeech(text: string): Promise<Blob> {
  const res = await apiFetch("/voice/speech", {
    method: "POST",
    body: JSON.stringify({ text }),
  }, true);
  if (!res.ok) throw new Error(await parseError(res));
  return res.blob();
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
  const res = await apiFetch("/crop/mobilenetv3-diagnosis", {
    method: "POST",
    body: JSON.stringify({
      image_base64: imageBase64,
      crop_hint: cropHint || undefined,
      confidence_threshold: confidenceThreshold ?? 0.60,
    }),
  }, true);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function submitFeedback(
  requestId: string,
  rating: number,
  comment?: string,
): Promise<void> {
  const res = await apiFetch("/feedback", {
    method: "POST",
    body: JSON.stringify({
      request_id: requestId,
      rating,
      comment: comment || undefined,
    }),
  }, true);
  if (!res.ok) throw new Error(await parseError(res));
}

export type NearbyHelpItem = {
  id: string;
  name: string;
  state: string;
  district: string;
  pincode: string;
  address: string;
  host_institution: string;
  phone: string;
  helpline: string;
  email: string;
  website: string;
  latitude?: number | null;
  longitude?: number | null;
  distance_km?: number | null;
  verified?: boolean;
};

export type NearbyHelpResponse = {
  status: "ok" | "fallback";
  centers: NearbyHelpItem[];
  results: NearbyHelpItem[];
  total: number;
  total_found: number;
  has_verified_results: boolean;
  kisan_call_centre: string;
  official_portal: string;
  fallback_info?: {
    notice: string;
    kisan_call_centre_helpline: string;
    official_portal_url: string;
    prompt_for_district: string;
  } | null;
  fallback_notice?: string | null;
};

export async function fetchNearbyAgriculturalHelp(params: {
  lat?: number | null;
  lon?: number | null;
  district?: string | null;
  pincode?: string | null;
  query?: string | null;
  limit?: number;
}): Promise<NearbyHelpResponse> {
  const searchParams = new URLSearchParams();
  if (params.lat != null && params.lon != null) {
    searchParams.set("lat", String(params.lat));
    searchParams.set("lon", String(params.lon));
  }
  if (params.district) searchParams.set("district", params.district);
  if (params.pincode) searchParams.set("pincode", params.pincode);
  if (params.query) searchParams.set("query", params.query);
  if (params.limit) searchParams.set("limit", String(params.limit));

  const res = await fetch(`${API_BASE}/help/nearby?${searchParams.toString()}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

