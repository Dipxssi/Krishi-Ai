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
    image_url: str | None = None  # ignored in V1


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
    disease_risk: float
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


class QueryResponse(BaseModel):
    query: str
    farmer_id: str
    final_recommendation: str
    decision_score: DecisionScore | None = None
    agents_used: list[str]
    confidence: float
    evidence: list[EvidenceItem] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_context: list[str] = Field(default_factory=list)
    revision_count: int = 0
    agent_results: list[AgentResult] = Field(default_factory=list)
