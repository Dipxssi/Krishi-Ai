import { useState } from "react";
import {
  diagnoseMobileNetV3,
  type MobileNetV3DiagnosisResponse,
} from "./api";

interface MobileNetV3TestPanelProps {
  imageBase64: string | null;
  selectedCrop?: string;
  disabled?: boolean;
}

export default function MobileNetV3TestPanel({
  imageBase64,
  selectedCrop,
  disabled = false,
}: MobileNetV3TestPanelProps) {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MobileNetV3DiagnosisResponse | null>(null);

  const handleRunDiagnosis = async () => {
    if (!imageBase64) return;
    setLoading(true);
    setError(null);

    try {
      const data = await diagnoseMobileNetV3(imageBase64, selectedCrop);
      setResult(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg || "Failed to execute MobileNetV3 diagnosis.");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setResult(null);
    setError(null);
  };

  return (
    <div className="mobilenet-test-container" role="region" aria-label="Experimental MobileNetV3 Test Mode">
      <div className="mobilenet-toggle-row">
        <label className="mobilenet-toggle-label">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => {
              setEnabled(e.target.checked);
              if (!e.target.checked) handleClear();
            }}
            disabled={disabled}
            className="mobilenet-checkbox"
          />
          <span className="mobilenet-toggle-text">
            <strong>Experimental MobileNetV3 Test Mode</strong>
            <span className="mobilenet-toggle-badge">Test Endpoint</span>
          </span>
        </label>
      </div>

      {enabled && (
        <div className="mobilenet-panel">
          <div className="mobilenet-notice-banner" role="alert">
            <span className="mobilenet-warning-icon">🧪</span>
            <div>
              <strong className="mobilenet-notice-title">
                Experimental Model — Not Verified for Field Diagnosis
              </strong>
              <p className="mobilenet-notice-desc">
                Sends the photo directly to <code>POST /crop/mobilenetv3-diagnosis</code> for model evaluation.
                This test mode is isolated from live recommendation routing and does NOT prescribe chemical treatments.
              </p>
            </div>
          </div>

          <div className="mobilenet-actions">
            <button
              type="button"
              onClick={handleRunDiagnosis}
              disabled={disabled || loading || !imageBase64}
              className="btn-mobilenet-test"
            >
              {loading ? "Analyzing with MobileNetV3 (MPS)…" : "Run MobileNetV3 Test Diagnosis"}
            </button>
            {result && (
              <button
                type="button"
                onClick={handleClear}
                disabled={loading}
                className="btn-mobilenet-clear"
              >
                Clear Results
              </button>
            )}
            {!imageBase64 && (
              <span className="mobilenet-hint-text">
                (Upload a leaf photo above to enable test diagnosis)
              </span>
            )}
          </div>

          {error && (
            <div className="mobilenet-error-banner" role="alert">
              <strong>Test Diagnosis Error:</strong> {error}
            </div>
          )}

          {result && (
            <div className="mobilenet-result-card">
              <div className="mobilenet-result-header">
                <div className="mobilenet-status-pill-group">
                  <span
                    className={`mobilenet-status-badge ${
                      result.status === "accepted" ? "status-accepted" : "status-rejected"
                    }`}
                  >
                    Status: {result.status.toUpperCase()}
                  </span>
                  {result.requires_expert && (
                    <span className="mobilenet-expert-badge">
                      ⚠️ Expert Review Required
                    </span>
                  )}
                </div>
                <span className="mobilenet-latency">
                  Latency: {result.inference_time_ms.toFixed(1)} ms
                </span>
              </div>

              {result.status === "rejected" ? (
                <div className="mobilenet-rejection-box">
                  <h4>Prediction Abstained / Rejected</h4>
                  <p className="mobilenet-rejection-reason">
                    <strong>Reason:</strong> {result.rejection_reason || "Unspecified rejection criterion."}
                  </p>
                </div>
              ) : (
                <div className="mobilenet-diagnosis-box">
                  <div className="mobilenet-prediction-main">
                    <span className="mobilenet-label">Predicted Diagnosis</span>
                    <h3 className="mobilenet-predicted-class">
                      {result.predicted_class || `${result.crop_id} — ${result.disease}`}
                    </h3>
                  </div>

                  {result.confidence != null && (
                    <div className="mobilenet-confidence-callout">
                      <div className="mobilenet-confidence-value">
                        Confidence: <strong>{(result.confidence * 100).toFixed(1)}%</strong>
                      </div>
                      <span className="mobilenet-uncalibrated-tag">
                        ⚠️ Uncalibrated Softmax Probability
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Expert Review Warning */}
              <div className="mobilenet-expert-warning-box">
                <span className="mobilenet-expert-icon">⚠️</span>
                <div>
                  <strong>Mandatory Agronomic Warning:</strong>
                  <p>
                    Automated deep learning predictions on field imagery can be confounded by soil clutter,
                    lighting glare, and multiple leaves. <em>Never apply chemical fungicides or pesticides</em> based
                    solely on this test diagnosis without in-person Krishi Vigyan Kendra (KVK) verification.
                  </p>
                </div>
              </div>

              {/* Top-3 Candidates */}
              {result.top_3 && result.top_3.length > 0 && (
                <div className="mobilenet-top3-section">
                  <h4 className="mobilenet-section-title">Top-3 Candidate Predictions</h4>
                  <div className="mobilenet-top3-list">
                    {result.top_3.map((cand, idx) => {
                      const pct = Math.round(cand.confidence * 100);
                      return (
                        <div key={cand.class_idx ?? idx} className="mobilenet-candidate-item">
                          <div className="mobilenet-candidate-header">
                            <span className="mobilenet-candidate-rank">#{idx + 1}</span>
                            <span className="mobilenet-candidate-name">{cand.display_name}</span>
                            <span className="mobilenet-candidate-pct">{pct}%</span>
                          </div>
                          <div className="mobilenet-progress-bar-bg">
                            <div
                              className="mobilenet-progress-bar-fill"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <div className="mobilenet-candidate-meta">
                            <span>Crop: {cand.crop}</span>
                            <span>{cand.is_healthy ? "Healthy Foliage" : "Diseased Foliage"}</span>
                            <span>Uncalibrated</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Treatment / Safe Next Steps Hints */}
              {result.treatment_hints && result.treatment_hints.length > 0 && (
                <div className="mobilenet-hints-section">
                  <h4 className="mobilenet-section-title">Safe Agronomic Next Steps</h4>
                  <ul className="mobilenet-hints-list">
                    {result.treatment_hints.map((hint, i) => (
                      <li key={i}>{hint}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Model & Disclaimer Footer */}
              <div className="mobilenet-footer-meta">
                <div className="mobilenet-footer-details">
                  <span>Model: <code>{result.model_version}</code></span>
                  {result.image_quality_score != null && (
                    <span>Quality Score: {result.image_quality_score.toFixed(1)}</span>
                  )}
                </div>
                <p className="mobilenet-disclaimer-text">{result.disclaimer}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
