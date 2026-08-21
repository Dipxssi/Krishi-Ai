import { useState } from "react";
import type { FormEvent } from "react";
import { askAdvice, createFarmer, type QueryResponse } from "./api";

const DEMO_QUERY =
  "Tomato market price is falling, limited budget, rain expected next week. Should I treat, continue, or sell early?";

export default function App() {
  const [farmerId, setFarmerId] = useState("farmer-001");
  const [location, setLocation] = useState("Nashik");
  const [crop, setCrop] = useState("tomato");
  const [area, setArea] = useState(2);
  const [budget, setBudget] = useState(20000);
  const [query, setQuery] = useState(DEMO_QUERY);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);

  async function onSaveFarm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      await createFarmer({
        farmer_id: farmerId,
        location,
        farm_area_acres: area,
        crop,
        growth_stage: "fruiting",
        soil_type: "loam",
        soil_npk: { n: 40, p: 30, k: 40 },
        irrigation_available: true,
        budget,
        preferred_language: "English",
        season: "kharif",
      });
      setStatus(`Farm profile ready for ${farmerId}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save farm");
    } finally {
      setBusy(false);
    }
  }

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const data = await askAdvice(farmerId, query);
      setResult(data);
      setStatus("Advice generated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="sky" aria-hidden />
      <header className="hero">
        <p className="brand">KrishiAi</p>
        <h1>Decide with field context, not chat guesses.</h1>
        <p className="lede">
          Save your farm profile, ask in plain language, and get a multi-agent recommendation grounded in tools and
          evidence.
        </p>
      </header>

      <main className="layout">
        <section className="panel farm" aria-labelledby="farm-title">
          <h2 id="farm-title">Farm context</h2>
          <form onSubmit={onSaveFarm} className="form-grid">
            <label>
              Farmer ID
              <input value={farmerId} onChange={(e) => setFarmerId(e.target.value)} required />
            </label>
            <label>
              Location
              <input value={location} onChange={(e) => setLocation(e.target.value)} required />
            </label>
            <label>
              Crop
              <input value={crop} onChange={(e) => setCrop(e.target.value)} required />
            </label>
            <label>
              Area (acres)
              <input
                type="number"
                min={0.1}
                step={0.1}
                value={area}
                onChange={(e) => setArea(Number(e.target.value))}
                required
              />
            </label>
            <label>
              Budget (INR)
              <input
                type="number"
                min={0}
                step={500}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </label>
            <button type="submit" disabled={busy}>
              Save farm profile
            </button>
          </form>
        </section>

        <section className="panel ask" aria-labelledby="ask-title">
          <h2 id="ask-title">Ask KrishiAi</h2>
          <form onSubmit={onAsk} className="ask-form">
            <label>
              Your question
              <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={5} required />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Thinking…" : "Get recommendation"}
            </button>
          </form>
          {status && <p className="status ok">{status}</p>}
          {error && <p className="status err">{error}</p>}
        </section>

        {result && (
          <section className="panel result" aria-labelledby="result-title">
            <h2 id="result-title">Recommendation</h2>
            <p className="recommendation">{result.final_recommendation}</p>

            <div className="meta-row">
              <span>Confidence {(result.confidence * 100).toFixed(0)}%</span>
              <span>Revisions {result.revision_count}</span>
              {result.decision_score && (
                <span>Decision score {(result.decision_score.final_score * 100).toFixed(0)}</span>
              )}
            </div>

            <h3>Agents used</h3>
            <ul className="chips">
              {result.agents_used.map((a) => (
                <li key={a}>{a}</li>
              ))}
            </ul>

            {result.warnings.length > 0 && (
              <>
                <h3>Warnings</h3>
                <ul className="list">
                  {result.warnings.map((w) => (
                    <li key={w}>{w}</li>
                  ))}
                </ul>
              </>
            )}

            <h3>Evidence</h3>
            <ul className="list evidence">
              {result.evidence.slice(0, 12).map((e, i) => (
                <li key={`${e.source}-${i}`}>
                  <strong>{e.source}</strong>: {formatValue(e.value)}
                  {e.unit ? ` (${e.unit})` : ""}
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
