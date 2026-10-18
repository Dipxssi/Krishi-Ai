import type { QueryResponse, ToolTrace } from "./api";
import SafeRecommendationRenderer from "./SafeRecommendationRenderer";

const MISSING_FIELD_LABELS: Record<string, string> = {
  location: "Location (district / mandi)",
  farm_area_acres: "Farm area (acres)",
  crop: "Crop",
  budget: "Budget (INR)",
  soil_type_or_soil_npk: "Soil type or NPK values",
};

type Provenance = "live" | "mock" | "registry" | "rag" | "tool" | null;

export default function QueryResultPanel({ result }: { result: QueryResponse }) {
  return (
    <section className="panel result" aria-labelledby="result-title">
      <h2 id="result-title">Recommendation</h2>
      {(result.selected_crop || result.farm_profile_crop) && (
        <div className="crop-context-row" role="region" aria-label="Crop context summary">
          {result.selected_crop && (
            <span className="crop-badge selected-badge">
              Inquiry crop: <strong>{result.selected_crop}</strong>
            </span>
          )}
          {result.farm_profile_crop && (
            <span className="crop-badge profile-badge">
              Farm profile crop: <strong>{result.farm_profile_crop}</strong>
            </span>
          )}
        </div>
      )}
      <div className="recommendation">
        <SafeRecommendationRenderer text={result.final_recommendation} />
      </div>

      <div className="meta-row">
        <span title="Composite heuristic consensus of specialist agents (not a calibrated disease probability)">
          Pipeline confidence {(result.confidence * 100).toFixed(0)}% (Heuristic)
        </span>
        <span>Revisions {result.revision_count}</span>
        {result.decision_score && (
          <span title="Heuristic composite index combining agronomic suitability and economics">
            Decision index {(result.decision_score.final_score * 100).toFixed(0)} / 100
          </span>
        )}
      </div>

      {result.missing_context.length > 0 && (
        <div className="missing-context" role="status">
          <h3>Missing farm context</h3>
          <p>Add these to your farm profile for better advice:</p>
          <ul className="list">
            {result.missing_context.map((field) => (
              <li key={field}>{MISSING_FIELD_LABELS[field] ?? field.replace(/_/g, " ")}</li>
            ))}
          </ul>
        </div>
      )}

      {result.decision_score && (
        <>
          <div className="score-bars">
            <ScoreBar label="Agronomic suitability" value={result.decision_score.agronomic_score} tone="leaf" />
            <ScoreBar label="Economic viability" value={result.decision_score.economic_score} tone="gold" />
            <ScoreBar label="Overall decision index" value={result.decision_score.final_score} tone="soil" />
          </div>
          <div className="risk-metrics">
            <MetricCard
              label="Expected profit"
              value={`₹${formatInr(result.decision_score.expected_profit)}`}
              hint="From tools + crop registry"
            />
            <MetricCard
              label="Input cost"
              value={`₹${formatInr(result.decision_score.input_cost)}`}
              hint="Estimated season costs"
            />
            <MetricCard
              label="Water risk"
              value={`${(result.decision_score.water_risk * 100).toFixed(0)}%`}
              hint="Higher = more rainfall stress"
              tone="risk"
            />
            {result.decision_score.disease_risk !== null &&
            result.decision_score.disease_risk !== undefined ? (
              <MetricCard
                label="Disease risk"
                value={`${(result.decision_score.disease_risk * 100).toFixed(0)}%`}
                hint="Heuristic indicator (not calibrated probability)"
                tone="risk"
              />
            ) : (
              <MetricCard
                label="Disease risk"
                value="Suppressed"
                hint="Unconfirmed diagnosis — expert review needed"
                tone="risk"
              />
            )}
          </div>
        </>
      )}

      {result.image_diagnosis && (() => {
        const diag = result.image_diagnosis;
        const isAccepted = (diag.status === "ok" || diag.status === "accepted") && !diag.requires_expert;
        const isMobileNet = diag.model_version?.includes("mobilenetv3");
        const plantName = diag.plant_name || (diag.crop_id ? diag.crop_id.charAt(0).toUpperCase() + diag.crop_id.slice(1) : "Crop");
        const diseaseLabel = diag.predicted_disease || (diag.disease ? diag.disease.replace(/_/g, " ") : "Unknown");
        const confScore = diag.confidence ?? diag.disease_confidence;

        return (
          <div
            className={`image-diagnosis diagnosis-${
              isAccepted
                ? "accepted"
                : diag.requires_expert
                ? "expert-review"
                : "rejected"
            }`}
          >
            <div className="diagnosis-status-header">
              <h3>Image diagnosis</h3>
              {isAccepted && (
                <span className="diagnosis-badge badge-accepted">
                  {isMobileNet ? "MobileNetV3 Visual Prediction" : "Automated screening match"}
                </span>
              )}
              {diag.requires_expert && (
                <span className="diagnosis-badge badge-expert">Unconfirmed · Expert review recommended</span>
              )}
              {diag.status === "rejected" && !diag.requires_expert && (
                <span className="diagnosis-badge badge-rejected">Abstained · Image not diagnostic</span>
              )}
            </div>

            {isAccepted ? (
              <div className="diagnosis-body">
                <p className="diagnosis-summary">
                  <strong>Plant: {plantName}</strong> ·{" "}
                  {diag.is_healthy ? (
                    <span className="status-healthy" style={{ color: "#2e7d32", fontWeight: 600 }}>
                      No supported disease detected (Healthy leaf scan)
                    </span>
                  ) : (
                    <span>
                      Predicted condition: <strong>{diseaseLabel}</strong>
                      {diag.severity && ` (${diag.severity})`}
                    </span>
                  )}
                  {confScore !== null && confScore !== undefined && (
                    <span className="conf-tag">
                      {" "}· Confidence: {(confScore * 100).toFixed(1)}% <em style={{ fontSize: "0.85em", opacity: 0.8 }}>(Uncalibrated)</em>
                    </span>
                  )}
                </p>

                {isMobileNet ? (
                  <div className="diagnosis-disclaimer" style={{ background: "#fff8e1", borderLeft: "4px solid #ffa000", padding: "8px 12px", margin: "10px 0", borderRadius: "4px" }}>
                    <p style={{ margin: 0, fontSize: "0.88rem", color: "#5d4037" }}>
                      ⚠️ <strong>Experimental model — not verified for field diagnosis</strong> (PlantDoc evaluation: 20.85% in-scope accuracy; uncalibrated softmax probability).
                      Do not apply chemical pesticides or fungicides based solely on AI predictions.
                      Physical verification by local Krishi Vigyan Kendra (KVK) or extension officer is required before chemical spraying.
                    </p>
                  </div>
                ) : (
                  <p className="diagnosis-disclaimer">
                    Note: Automated preliminary screening only. Does not constitute certified expert diagnosis or
                    established field accuracy. Scout the field and verify physical leaf symptoms before taking action.
                  </p>
                )}

                {diag.treatment_hints && diag.treatment_hints.length > 0 && (
                  <ul className="diagnosis-hints">
                    {diag.treatment_hints.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                )}

                {diag.top_3 && diag.top_3.length > 0 && (
                  <div className="diagnosis-top3-box" style={{ marginTop: "14px", paddingTop: "12px", borderTop: "1px solid #dce8d6" }}>
                    <span style={{ fontSize: "0.82rem", fontWeight: 700, color: "#2e5b37", textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: "8px" }}>
                      Alternative Candidate Predictions (MobileNetV3 Output)
                    </span>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      {diag.top_3.map((cand, idx) => (
                        <div key={idx} style={{ background: "#f1f8ed", border: "1px solid #c8e0be", padding: "6px 10px", borderRadius: "6px", fontSize: "0.84rem", color: "#1b3e23" }}>
                          <strong>#{idx + 1} {cand.display_name}</strong>: {(cand.confidence * 100).toFixed(1)}%
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : diag.requires_expert ? (
              <div className="diagnosis-body">
                <div className="diagnosis-abstain-notice notice-expert">
                  <p>
                    <strong>Automated diagnosis is unconfirmed.</strong> Do not apply chemical pesticides or fungicides
                    based on unverified automated scans. Physical inspection by a local Krishi Vigyan Kendra (KVK) or
                    extension agronomist is recommended.
                  </p>
                </div>
                {diag.rejection_reason && (
                  <p className="status err">{diag.rejection_reason}</p>
                )}
                {diag.treatment_hints && diag.treatment_hints.length > 0 && (
                  <ul className="diagnosis-hints">
                    {diag.treatment_hints.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <div className="diagnosis-body">
                <div className="diagnosis-abstain-notice notice-rejected">
                  <p>
                    <strong>Automated diagnosis abstained.</strong> The uploaded photo could not be verified reliably.
                    Photograph a single fully visible leaf centered against a plain neutral background in bright
                    daylight, or consult a local agronomist.
                  </p>
                </div>
                {diag.rejection_reason && (
                  <p className="status err">{diag.rejection_reason}</p>
                )}
              </div>
            )}
          </div>
        );
      })()}

      {result.structured_recommendation && (
        <div className="structured-rec">
          <h3>Structured summary</h3>
          <p>
            Risk: {result.structured_recommendation.risk_level}
            {result.structured_recommendation.human_review_required && " · Human review recommended"}
          </p>
          {result.structured_recommendation.conflicts_resolved.length > 0 && (
            <ul className="list">
              {result.structured_recommendation.conflicts_resolved.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="request-id">Request ID: {result.request_id}</p>

      <h3>Agents used</h3>
      <ul className="chips">
        {result.agents_used.map((a) => (
          <li key={a}>{a.replace(/_/g, " ")}</li>
        ))}
      </ul>

      {result.warnings.length > 0 && (
        <>
          <h3>Warnings</h3>
          <ul className="list warn-list">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </>
      )}

      {result.tool_traces.length > 0 && (
        <>
          <h3>Tool traces</h3>
          <p className="section-hint">Which tools ran, their status, and whether data was live or mock.</p>
          <div className="trace-table-wrap">
            <table className="trace-table">
              <thead>
                <tr>
                  <th>Agent</th>
                  <th>Tool</th>
                  <th>Status</th>
                  <th>Data</th>
                </tr>
              </thead>
              <tbody>
                {result.tool_traces.map((trace, i) => (
                  <ToolTraceRow key={`${trace.agent}-${trace.tool}-${i}`} trace={trace} />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Evidence</h3>
      <div className="evidence-grid">
        {groupEvidence(result.evidence).map(([agent, items]) => (
          <div key={agent} className="evidence-group">
            <h4>{agent.replace(/_/g, " ")}</h4>
            <ul className="list evidence">
              {items.map((e, i) => (
                <li key={`${e.source}-${i}`}>
                  <span className="evidence-line">
                    <strong>{e.source}</strong>
                    {provenanceBadge(inferProvenance(e.source, result.tool_traces))}
                  </span>
                  : {formatValue(e.value)}
                  {e.unit ? ` (${e.unit})` : ""}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function ToolTraceRow({ trace }: { trace: ToolTrace }) {
  const dataKind = traceDataKind(trace);
  return (
    <tr>
      <td>{trace.agent.replace(/_/g, " ")}</td>
      <td>
        <code>{trace.tool}</code>
        {trace.arguments && Object.keys(trace.arguments).length > 0 && (
          <details className="trace-args">
            <summary>args</summary>
            <pre>{JSON.stringify(trace.arguments, null, 2)}</pre>
          </details>
        )}
      </td>
      <td>
        <span className={`trace-status ${statusClass(trace.status)}`}>{trace.status}</span>
        {trace.error && <span className="trace-error">{trace.error}</span>}
      </td>
      <td>{dataKind ? <ProvenanceBadge kind={dataKind} /> : "—"}</td>
    </tr>
  );
}

function ScoreBar({ label, value, tone }: { label: string; value: number; tone: string }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  return (
    <div className="score-bar">
      <div className="score-bar-head">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="score-track">
        <div className={`score-fill ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: "risk";
}) {
  return (
    <div className={`metric-card${tone === "risk" ? " metric-risk" : ""}`}>
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      <span className="metric-hint">{hint}</span>
    </div>
  );
}

function ProvenanceBadge({ kind }: { kind: Exclude<Provenance, null> }) {
  const labels: Record<Exclude<Provenance, null>, string> = {
    live: "Live",
    mock: "Mock",
    registry: "Registry",
    rag: "RAG",
    tool: "Tool",
  };
  return <span className={`badge badge-${kind}`}>{labels[kind]}</span>;
}

function provenanceBadge(kind: Provenance) {
  if (!kind) return null;
  return <ProvenanceBadge kind={kind} />;
}

function traceDataKind(trace: ToolTrace): Provenance | null {
  if (!trace.output || typeof trace.output !== "object") return trace.status.startsWith("success") ? "tool" : null;
  const out = trace.output as Record<string, unknown>;
  if (typeof out.is_mock === "boolean") {
    return out.is_mock ? "mock" : "live";
  }
  if (trace.tool === "calculate_profit" || trace.tool === "search_schemes" || trace.tool === "search_loans") {
    return "tool";
  }
  return null;
}

function inferProvenance(source: string, traces: ToolTrace[]): Provenance {
  if (source.startsWith("crop_registry")) return "registry";
  if (source.startsWith("rag:") || source.includes("crops.json")) return "rag";
  if (source.includes("mock_weather") || source.includes("mock_market")) return "mock";

  const weatherTrace = traces.find((t) => t.tool === "get_weather" && t.status.startsWith("success"));
  if (source.includes("weather") && weatherTrace) {
    return traceDataKind(weatherTrace) === "live" ? "live" : "mock";
  }
  const marketTrace = traces.find((t) => t.tool === "get_market_price" && t.status.startsWith("success"));
  if ((source.includes("market") || source.includes("agmarknet")) && marketTrace) {
    return traceDataKind(marketTrace) === "live" ? "live" : "mock";
  }
  if (source.startsWith("scheme:") || source.startsWith("loan:") || source === "profit_calculator") {
    return "tool";
  }
  return null;
}

function statusClass(status: string): string {
  if (status.startsWith("success")) return "ok";
  if (status.includes("fail") || status.includes("error")) return "err";
  return "neutral";
}

function formatInr(value: number): string {
  return Math.round(value).toLocaleString("en-IN");
}

function groupEvidence(evidence: QueryResponse["evidence"]): [string, typeof evidence][] {
  const map = new Map<string, typeof evidence>();
  for (const item of evidence) {
    const agent = item.agent ?? inferAgent(item.source);
    const list = map.get(agent) ?? [];
    list.push(item);
    map.set(agent, list);
  }
  return Array.from(map.entries());
}

function inferAgent(source: string): string {
  if (source.startsWith("scheme:") || source.startsWith("loan:") || source.startsWith("crop_registry")) {
    return "finance";
  }
  if (source.includes("weather") || source.includes("mock_weather")) return "weather";
  if (source.includes("market") || source.includes("agmarknet")) return "market";
  return "knowledge";
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
