import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  fetchKnowledgeSummary,
  getFarmer,
  saveFarmer,
  type FarmContext,
} from "./api";

const FARMER_ID_KEY = "krishiai_farmer_id";

const SOIL_TYPES = ["loam", "clay", "sandy", "silt", "black", "red", "alluvial"] as const;
const SEASONS = ["kharif", "rabi", "zaid"] as const;
const LANGUAGES = ["English", "Hindi", "Marathi", "Telugu", "Tamil", "Kannada", "Bengali", "Punjabi"] as const;

const CROP_GROWTH_STAGES: Record<string, string[]> = {
  cotton: ["germination", "squaring", "flowering", "boll_formation", "boll_opening", "harvest"],
  maize: ["germination", "vegetative", "tasseling", "silking", "grain_filling", "harvest"],
  onion: ["nursery", "transplant", "vegetative", "bulb_formation", "maturity", "harvest"],
  potato: ["sprouting", "vegetative", "tuber_initiation", "tuber_bulking", "maturation", "harvest"],
  rice: ["nursery", "transplant", "tillering", "panicle_initiation", "flowering", "harvest"],
  tomato: ["nursery", "transplant", "vegetative", "flowering", "fruiting", "harvest"],
  wheat: ["germination", "tillering", "jointing", "flowering", "grain_filling", "harvest"],
};

const DEFAULT_FORM = {
  location: "Nashik",
  crop: "tomato",
  farm_area_acres: 2,
  growth_stage: "fruiting",
  soil_type: "loam",
  soil_n: 40,
  soil_p: 30,
  soil_k: 40,
  irrigation_available: true,
  budget: 20000,
  preferred_language: "English",
  season: "kharif",
};

type FormState = typeof DEFAULT_FORM;

function profileToForm(profile: FarmContext): FormState {
  const npk = profile.soil_npk ?? {};
  return {
    location: profile.location,
    crop: profile.crop ?? DEFAULT_FORM.crop,
    farm_area_acres: profile.farm_area_acres,
    growth_stage: profile.growth_stage ?? DEFAULT_FORM.growth_stage,
    soil_type: profile.soil_type ?? DEFAULT_FORM.soil_type,
    soil_n: npk.n ?? DEFAULT_FORM.soil_n,
    soil_p: npk.p ?? DEFAULT_FORM.soil_p,
    soil_k: npk.k ?? DEFAULT_FORM.soil_k,
    irrigation_available: profile.irrigation_available ?? DEFAULT_FORM.irrigation_available,
    budget: profile.budget ?? DEFAULT_FORM.budget,
    preferred_language: profile.preferred_language ?? DEFAULT_FORM.preferred_language,
    season: profile.season ?? DEFAULT_FORM.season,
  };
}

function formToPayload(farmerId: string, form: FormState): FarmContext {
  return {
    farmer_id: farmerId,
    location: form.location.trim(),
    farm_area_acres: form.farm_area_acres,
    crop: form.crop || null,
    growth_stage: form.growth_stage || null,
    soil_type: form.soil_type || null,
    soil_npk: { n: form.soil_n, p: form.soil_p, k: form.soil_k },
    irrigation_available: form.irrigation_available,
    budget: form.budget,
    preferred_language: form.preferred_language,
    season: form.season || null,
  };
}

type FarmContextFormProps = {
  onFarmerIdChange: (farmerId: string) => void;
  onStatus?: (message: string | null) => void;
  onError?: (message: string | null) => void;
  disabled?: boolean;
};

export default function FarmContextForm({
  onFarmerIdChange,
  onStatus,
  onError,
  disabled = false,
}: FarmContextFormProps) {
  const [farmerId, setFarmerId] = useState(
    () => localStorage.getItem(FARMER_ID_KEY) ?? "farmer-001",
  );
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [cropOptions, setCropOptions] = useState<string[]>(Object.keys(CROP_GROWTH_STAGES));
  const [busy, setBusy] = useState(false);
  const [loadNote, setLoadNote] = useState<string | null>(null);

  const growthStages = useMemo(() => {
    const stages = CROP_GROWTH_STAGES[form.crop.toLowerCase()];
    return stages ?? ["vegetative", "flowering", "fruiting", "harvest"];
  }, [form.crop]);

  const applyProfile = useCallback((profile: FarmContext) => {
    setForm(profileToForm(profile));
  }, []);

  const loadProfile = useCallback(
    async (id: string, silent = false) => {
      setBusy(true);
      if (!silent) {
        onError?.(null);
        onStatus?.(null);
      }
      try {
        const profile = await getFarmer(id);
        applyProfile(profile);
        setLoadNote(`Loaded profile for ${id}.`);
        onFarmerIdChange(id);
        localStorage.setItem(FARMER_ID_KEY, id);
      } catch {
        setLoadNote(`No saved profile for ${id} — fill in fields and save.`);
      } finally {
        setBusy(false);
      }
    },
    [applyProfile, onError, onFarmerIdChange, onStatus],
  );

  useEffect(() => {
    onFarmerIdChange(farmerId);
  }, [farmerId, onFarmerIdChange]);

  useEffect(() => {
    loadProfile(farmerId, true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- load once on mount

  useEffect(() => {
    fetchKnowledgeSummary()
      .then((summary) => {
        if (summary.crops_covered.length > 0) {
          setCropOptions(summary.crops_covered.map((c) => c.toLowerCase()));
        }
      })
      .catch(() => {
        /* keep default crop list */
      });
  }, []);

  useEffect(() => {
    if (!growthStages.includes(form.growth_stage)) {
      setForm((prev) => ({ ...prev, growth_stage: growthStages[0] ?? prev.growth_stage }));
    }
  }, [form.growth_stage, growthStages]);

  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onLoad() {
    await loadProfile(farmerId.trim());
  }

  async function onSave(e: FormEvent) {
    e.preventDefault();
    const id = farmerId.trim();
    if (!id) return;

    setBusy(true);
    onError?.(null);
    onStatus?.(null);
    try {
      const payload = formToPayload(id, form);
      const action = await saveFarmer(payload);
      localStorage.setItem(FARMER_ID_KEY, id);
      onFarmerIdChange(id);
      setLoadNote(action === "created" ? `Created profile for ${id}.` : `Updated profile for ${id}.`);
      onStatus?.(action === "created" ? `Farm profile created for ${id}.` : `Farm profile updated for ${id}.`);
    } catch (err) {
      onError?.(err instanceof Error ? err.message : "Failed to save farm profile");
    } finally {
      setBusy(false);
    }
  }

  const formDisabled = disabled || busy;

  return (
    <section className="panel farm" aria-labelledby="farm-title">
      <h2 id="farm-title">Farm context</h2>
      <p className="farm-hint">
        Agents use this profile for weather, market, soil, and profit estimates. Save before asking a question.
      </p>

      <form onSubmit={onSave} className="farm-form">
        <div className="form-grid">
          <label>
            Farmer ID
            <input
              value={farmerId}
              onChange={(e) => setFarmerId(e.target.value)}
              required
              disabled={formDisabled}
            />
          </label>
          <div className="form-actions-inline">
            <button type="button" className="btn-secondary" onClick={() => void onLoad()} disabled={formDisabled}>
              Load profile
            </button>
          </div>

          <label>
            Location (mandi / district)
            <input
              value={form.location}
              onChange={(e) => patch("location", e.target.value)}
              required
              disabled={formDisabled}
            />
          </label>
          <label>
            Crop
            <select
              value={form.crop}
              onChange={(e) => patch("crop", e.target.value)}
              required
              disabled={formDisabled}
            >
              {cropOptions.map((c) => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
          </label>

          <label>
            Area (acres)
            <input
              type="number"
              min={0.1}
              step={0.1}
              value={form.farm_area_acres}
              onChange={(e) => patch("farm_area_acres", Number(e.target.value))}
              required
              disabled={formDisabled}
            />
          </label>
          <label>
            Growth stage
            <select
              value={form.growth_stage}
              onChange={(e) => patch("growth_stage", e.target.value)}
              disabled={formDisabled}
            >
              {growthStages.map((stage) => (
                <option key={stage} value={stage}>
                  {stage.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </label>

          <label>
            Soil type
            <select
              value={form.soil_type}
              onChange={(e) => patch("soil_type", e.target.value)}
              disabled={formDisabled}
            >
              {SOIL_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Season
            <select value={form.season} onChange={(e) => patch("season", e.target.value)} disabled={formDisabled}>
              {SEASONS.map((s) => (
                <option key={s} value={s}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </option>
              ))}
            </select>
          </label>

          <fieldset className="npk-fieldset">
            <legend>Soil NPK (kg/ha)</legend>
            <div className="npk-grid">
              <label>
                N
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={form.soil_n}
                  onChange={(e) => patch("soil_n", Number(e.target.value))}
                  disabled={formDisabled}
                />
              </label>
              <label>
                P
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={form.soil_p}
                  onChange={(e) => patch("soil_p", Number(e.target.value))}
                  disabled={formDisabled}
                />
              </label>
              <label>
                K
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={form.soil_k}
                  onChange={(e) => patch("soil_k", Number(e.target.value))}
                  disabled={formDisabled}
                />
              </label>
            </div>
          </fieldset>

          <label>
            Budget (INR)
            <input
              type="number"
              min={0}
              step={500}
              value={form.budget}
              onChange={(e) => patch("budget", Number(e.target.value))}
              disabled={formDisabled}
            />
          </label>
          <label>
            Preferred language
            <select
              value={form.preferred_language}
              onChange={(e) => patch("preferred_language", e.target.value)}
              disabled={formDisabled}
            >
              {LANGUAGES.map((lang) => (
                <option key={lang} value={lang}>
                  {lang}
                </option>
              ))}
            </select>
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={form.irrigation_available}
              onChange={(e) => patch("irrigation_available", e.target.checked)}
              disabled={formDisabled}
            />
            Irrigation available
          </label>
        </div>

        <div className="form-actions">
          <button type="submit" disabled={formDisabled}>
            {busy ? "Saving…" : "Save farm profile"}
          </button>
        </div>
      </form>

      {loadNote && <p className="farm-load-note">{loadNote}</p>}
    </section>
  );
}
