from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class FarmContextBase(BaseModel):
    location: str
    farm_area_acres: float
    crop: str | None = None
    growth_stage: str | None = None
    soil_type: str | None = None
    soil_npk: dict[str, float] | None = None
    irrigation_available: bool | None = None
    budget: float | None = None
    preferred_language: str = "English"
    season: str | None = None


class FarmContextCreate(FarmContextBase):
    farmer_id: str


class FarmContextUpdate(BaseModel):
    location: str | None = None
    farm_area_acres: float | None = None
    crop: str | None = None
    growth_stage: str | None = None
    soil_type: str | None = None
    soil_npk: dict[str, float] | None = None
    irrigation_available: bool | None = None
    budget: float | None = None
    preferred_language: str | None = None
    season: str | None = None


class FarmContext(FarmContextBase):
    farmer_id: str

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    query: str
    farmer_id: str
    image_url: str | None = None
    image_base64: str | None = None
    selected_crop: str | None = None
    vision_model: str | None = None  # "mobilenetv3" | "heuristic"
    language: str | None = None


class RouteRequest(BaseModel):
    query: str
    farmer_id: str | None = None
    image_url: str | None = None


class RouteResponse(BaseModel):
    request_id: str
    selected_agents: list[str]
    agent_scores: dict[str, float]
    missing_information: list[str]
    risk_level: str
    routing_mode: str


class MobileNetV3PredictionItem(BaseModel):
    class_idx: int
    display_name: str
    crop: str
    disease: str
    is_healthy: bool
    confidence: float
    confidence_is_calibrated: bool = False


class ImageDiagnosisRequest(BaseModel):
    image_base64: str
    crop_hint: str | None = None


class ImageDiagnosisResult(BaseModel):
    status: str  # "accepted" | "rejected" | "ok"
    rejection_reason: str | None = None
    plant_name: str | None = None
    predicted_disease: str | None = None
    is_healthy: bool = False
    confidence: float | None = None
    confidence_is_calibrated: bool = False
    model_version: str | None = None
    top_3: list[MobileNetV3PredictionItem] = Field(default_factory=list)
    image_quality_score: float | None = None
    crop_id: str | None = None
    crop_confidence: float | None = None
    disease: str | None = None
    disease_confidence: float | None = None
    severity: str | None = None
    requires_expert: bool = False
    expert_id: str | None = None
    treatment_hints: list[str] = Field(default_factory=list)
    latency_ms: float | None = None
    disclaimer: str | None = (
        "Model confidence is uncalibrated softmax probability. This prediction is from an "
        "experimental MobileNetV3 model not verified for field production. Physical expert confirmation required."
    )


class ElasticNetPredictionItem(BaseModel):
    class_idx: int
    display_name: str
    crop: str
    disease: str
    is_healthy: bool
    confidence: float
    confidence_is_calibrated: bool = False


class ElasticNetDiagnosisRequest(BaseModel):
    image_base64: str
    crop_hint: str | None = None
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


class ElasticNetDiagnosisResponse(BaseModel):
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None
    predicted_class: str | None = None
    crop_id: str | None = None
    disease: str | None = None
    confidence: float | None = None
    confidence_is_calibrated: bool = False
    top_3: list[ElasticNetPredictionItem] = Field(default_factory=list)
    requires_expert: bool = False
    treatment_hints: list[str] = Field(default_factory=list)
    image_quality_score: float | None = None
    inference_time_ms: float
    model_version: str = "elasticnet_plantdisease_best"
    disclaimer: str = (
        "Model confidence is uncalibrated. This test endpoint is strictly for offline "
        "and experimental evaluation and is not verified for field production."
    )


class MobileNetV3DiagnosisRequest(BaseModel):
    image_base64: str
    crop_hint: str | None = None
    confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


class MobileNetV3DiagnosisResponse(BaseModel):
    status: str  # "accepted" | "rejected"
    rejection_reason: str | None = None
    plant_name: str | None = None
    predicted_disease: str | None = None
    is_healthy: bool = False
    predicted_class: str | None = None
    crop_id: str | None = None
    disease: str | None = None
    confidence: float | None = None
    confidence_is_calibrated: bool = False
    top_3: list[MobileNetV3PredictionItem] = Field(default_factory=list)
    requires_expert: bool = False
    treatment_hints: list[str] = Field(default_factory=list)
    image_quality_score: float | None = None
    inference_time_ms: float
    model_version: str = "mobilenetv3_plantdisease_best"
    disclaimer: str = (
        "Model confidence is uncalibrated softmax probability. This test endpoint is strictly for offline "
        "and experimental evaluation and is not verified for field production."
    )


class StructuredRecommendation(BaseModel):
    action_summary: str
    reasons: list[str] = Field(default_factory=list)
    financial_summary: dict[str, Any] | None = None
    sources: list[str] = Field(default_factory=list)
    human_review_required: bool = False
    risk_level: str = "medium"
    conflicts_resolved: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    request_id: str
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    expert_verdict: str | None = None  # correct | incorrect | unsafe


class VoiceTranscribeRequest(BaseModel):
    audio_base64: str = Field(min_length=1)
    language_hint: str | None = Field(default=None, max_length=20)
    filename: str = Field(default="recording.webm", max_length=255)
    content_type: str = Field(default="audio/webm", max_length=128)


class VoiceTranscribeResponse(BaseModel):
    text: str
    normalized_crop: str | None = None
    note: str | None = None


class VoiceSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    # Groq Orpheus English voices: austin, troy, daniel, autumn, diana, hannah
    voice: str = Field(default="austin", min_length=1, max_length=40)


class EvidenceItem(BaseModel):
    source: str
    value: Any
    unit: str | None = None
    agent: str | None = None


class ToolTrace(BaseModel):
    agent: str
    tool: str
    arguments: dict[str, Any]
    status: str
    output: Any = None
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z"))


class DecisionScore(BaseModel):
    agronomic_suitability: float
    expected_profit: float
    water_risk: float
    disease_risk: float | None = None
    input_cost: float
    agronomic_score: float
    economic_score: float
    final_score: float
    agronomic_weight: float
    economic_weight: float


class AgentResult(BaseModel):
    agent: str
    recommendation: str
    confidence: float = 0.5
    tool_evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class EscalationDetailsSchema(BaseModel):
    requires_escalation: bool = False
    urgency: str = "low"  # "high" | "medium" | "low"
    reason: str = ""
    safe_next_step: str = ""
    sample_instructions: str = ""
    action_label: str = ""


class QueryResponse(BaseModel):
    request_id: str
    query: str
    farmer_id: str
    selected_crop: str | None = None
    farm_profile_crop: str | None = None
    final_recommendation: str
    response_language: str = "en"
    disclaimer: str = (
        "KrishiAI provides AI-generated guidance that may not always be accurate. "
        "Verify important crop diagnoses and treatment decisions with a qualified agricultural expert."
    )
    escalation: EscalationDetailsSchema | None = None
    structured_recommendation: StructuredRecommendation | None = None
    image_diagnosis: ImageDiagnosisResult | None = None
    decision_score: DecisionScore | None = None
    agents_used: list[str]
    confidence: float
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    revision_count: int = 0
    agent_results: list[AgentResult] = Field(default_factory=list)
