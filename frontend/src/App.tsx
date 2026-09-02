import { useCallback, useState, type ChangeEvent, type FormEvent } from "react";
import { askAdvice, type QueryResponse } from "./api";
import FarmContextForm from "./FarmContextForm";
import KnowledgeHub from "./KnowledgeHub";
import QueryResultPanel from "./QueryResultPanel";

const DEMO_QUERY =
  "Tomato market price is falling, limited budget, rain expected next week. Should I treat, continue, or sell early?";

type Tab = "ask" | "hub";

export default function App() {
  const [tab, setTab] = useState<Tab>("ask");
  const [farmerId, setFarmerId] = useState("farmer-001");
  const [query, setQuery] = useState(DEMO_QUERY);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);

  const handleFarmerIdChange = useCallback((id: string) => {
    setFarmerId(id);
  }, []);

  function onImageChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) {
      setImagePreview(null);
      setImageBase64(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      setImagePreview(dataUrl);
      setImageBase64(dataUrl);
    };
    reader.readAsDataURL(file);
  }

  async function onAsk(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const data = await askAdvice(farmerId, query, imageBase64);
      setResult(data);
      setStatus("Advice generated.");
      setTab("ask");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setBusy(false);
    }
  }

  function useSampleQuery(sample: string) {
    setQuery(sample);
    setTab("ask");
    setStatus("Sample question loaded — save farm profile if needed, then ask.");
  }

  return (
    <div className="page">
      <div className="sky" aria-hidden />
      <header className="hero">
        <p className="brand">KrishiAi</p>
        <h1>Decide with field context, not chat guesses.</h1>
        <p className="lede">
          Save your farm profile, browse schemes and crop guides, then get a multi-agent recommendation grounded in
          tools and evidence.
        </p>
        <nav className="tabs" aria-label="Main sections">
          <button
            type="button"
            className={tab === "ask" ? "tab active" : "tab"}
            onClick={() => setTab("ask")}
          >
            Ask advisor
          </button>
          <button
            type="button"
            className={tab === "hub" ? "tab active" : "tab"}
            onClick={() => setTab("hub")}
          >
            Knowledge hub
          </button>
        </nav>
      </header>

      <main className="layout">
        {tab === "hub" ? (
          <KnowledgeHub onUseQuery={useSampleQuery} />
        ) : (
          <>
            <FarmContextForm
              onFarmerIdChange={handleFarmerIdChange}
              onStatus={setStatus}
              onError={setError}
              disabled={busy}
            />

            <section className="panel ask" aria-labelledby="ask-title">
              <h2 id="ask-title">Ask KrishiAi</h2>
              <form onSubmit={onAsk} className="ask-form">
                <label>
                  Your question
                  <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={5} required />
                </label>
                <label>
                  Crop leaf photo (optional)
                  <input type="file" accept="image/*" onChange={onImageChange} disabled={busy} />
                </label>
                {imagePreview && (
                  <img src={imagePreview} alt="Upload preview" className="image-preview" />
                )}
                <button type="submit" disabled={busy}>
                  {busy ? "Thinking…" : "Get recommendation"}
                </button>
              </form>
              {status && <p className="status ok">{status}</p>}
              {error && <p className="status err">{error}</p>}
            </section>
          </>
        )}

        {tab === "ask" && result && <QueryResultPanel result={result} />}
      </main>
    </div>
  );
}
