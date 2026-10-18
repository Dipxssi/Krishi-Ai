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
  const [selectedCrop, setSelectedCrop] = useState<string>("");

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
      const data = await askAdvice(farmerId, query, imageBase64, selectedCrop || undefined, "mobilenetv3");
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
                <div className="camera-guidance" role="region" aria-label="Photo guidelines for diagnosis">
                  <div className="guidance-header">
                    <span className="guidance-tag">Photo Guidelines</span>
                    <p className="guidance-title">For accurate plant disease diagnosis:</p>
                  </div>
                  <ul className="guidance-list">
                    <li>
                      <strong>Single leaf:</strong> Photograph a single, fully visible leaf centered in the frame.
                    </li>
                    <li>
                      <strong>Plain neutral background:</strong> Place the leaf flat against a plain white paper or neutral surface (avoid outdoor soil, weeds, or hands).
                    </li>
                    <li>
                      <strong>Good lighting:</strong> Capture in bright daylight without strong cast shadows or sunny glare.
                    </li>
                    <li>
                      <strong>No surrounding foliage:</strong> Keep stems, weeds, and other garden clutter out of view.
                    </li>
                  </ul>
                  <p className="guidance-note">
                    Note: Complex field backgrounds (soil, weeds, shadows) may cause misclassification.
                  </p>
                </div>
                <label>
                  Crop for this inquiry / leaf photo (optional)
                  <select
                    value={selectedCrop}
                    onChange={(e) => setSelectedCrop(e.target.value)}
                    disabled={busy}
                    className="select-crop-inquiry"
                  >
                    <option value="">Auto-detect from question</option>
                    <option value="tomato">Tomato</option>
                    <option value="onion">Onion</option>
                    <option value="potato">Potato</option>
                    <option value="maize">Maize (Corn)</option>
                    <option value="wheat">Wheat</option>
                    <option value="rice">Rice</option>
                    <option value="cotton">Cotton</option>
                  </select>
                </label>
                <div className="leaf-upload-card">
                  <div className="leaf-upload-header">
                    <div className="leaf-upload-title-row">
                      <span className="leaf-upload-icon">🍃</span>
                      <span className="leaf-upload-title">Crop Leaf Photo (Optional)</span>
                      <span className="default-model-badge">Default: MobileNetV3 AI</span>
                    </div>
                    <span className="leaf-upload-subtitle">
                      Instant foliar disease screening for Tomato, Potato, and Maize (Corn).
                    </span>
                  </div>

                  {!imagePreview ? (
                    <label className="leaf-file-dropzone">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={onImageChange}
                        disabled={busy}
                        className="leaf-file-input"
                      />
                      <span className="dropzone-icon">📷</span>
                      <span className="dropzone-text">Choose or drop a leaf photo</span>
                      <span className="dropzone-hint">Supports JPG, PNG, WEBP · Single leaf against plain background</span>
                    </label>
                  ) : (
                    <div className="leaf-preview-container">
                      <div className="leaf-preview-img-box">
                        <img src={imagePreview} alt="Uploaded leaf preview" className="leaf-preview-img" />
                      </div>
                      <div className="leaf-preview-meta">
                        <span className="leaf-ready-badge">✓ Leaf Attached for MobileNetV3 Analysis</span>
                        <p className="leaf-ready-note">
                          MobileNetV3 will automatically screen plant identity and foliar disease symptoms when you submit.
                        </p>
                        <button
                          type="button"
                          className="btn-remove-leaf"
                          onClick={() => {
                            setImagePreview(null);
                            setImageBase64(null);
                          }}
                          disabled={busy}
                        >
                          Remove photo
                        </button>
                      </div>
                    </div>
                  )}
                </div>

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
