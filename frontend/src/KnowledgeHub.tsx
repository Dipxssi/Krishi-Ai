import { useEffect, useState } from "react";
import {
  fetchCropArticles,
  fetchKnowledgeSummary,
  fetchLoans,
  fetchSchemes,
  type CropArticle,
  type KnowledgeSummary,
  type Loan,
  type Scheme,
} from "./api";

const CATEGORY_LABELS: Record<string, string> = {
  income_support: "Income support",
  crop_insurance: "Crop insurance",
  irrigation_subsidy: "Irrigation",
  equipment_subsidy: "Equipment",
  soil_support: "Soil health",
  production_support: "Production",
  infrastructure_subsidy: "Infrastructure",
  infrastructure_loan: "Infrastructure loan",
  labor_support: "Labor",
  women_farmer: "Women farmers",
  credit_support: "Credit",
};

const LOAN_CATEGORY_LABELS: Record<string, string> = {
  crop_loan: "Crop loan",
  term_loan: "Term loan",
  short_term: "Short term",
  equipment_loan: "Equipment",
  allied_loan: "Allied activities",
  micro_loan: "Micro loan",
  green_loan: "Green finance",
  post_harvest: "Post-harvest",
};

const SAMPLE_QUERIES = [
  "Should I plant tomato now given weather and market prices?",
  "Potato soil potassium low at tuber stage — what fertilizer?",
  "Maize profit estimate for 2 acres with my budget?",
  "What government subsidy is available for drip irrigation?",
  "Can I get a KCC loan for potato harvest costs?",
];

type Props = {
  onUseQuery: (query: string) => void;
};

export default function KnowledgeHub({ onUseQuery }: Props) {
  const [summary, setSummary] = useState<KnowledgeSummary | null>(null);
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [loans, setLoans] = useState<Loan[]>([]);
  const [articles, setArticles] = useState<CropArticle[]>([]);
  const [category, setCategory] = useState<string>("");
  const [loanCategory, setLoanCategory] = useState<string>("");
  const [search, setSearch] = useState("");
  const [cropFilter, setCropFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [sum, schemeData, loanData, cropData] = await Promise.all([
          fetchKnowledgeSummary(),
          fetchSchemes(category || undefined, search || undefined),
          fetchLoans(loanCategory || undefined),
          fetchCropArticles(cropFilter || undefined, search || undefined),
        ]);
        if (cancelled) return;
        setSummary(sum);
        setSchemes(schemeData.items);
        setLoans(
          search
            ? loanData.items.filter((loan) => matchesLoanSearch(loan, search))
            : loanData.items,
        );
        setArticles(cropData.items);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load knowledge");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [category, loanCategory, search, cropFilter]);

  return (
    <section className="panel hub" aria-labelledby="hub-title">
      <div className="hub-header">
        <div>
          <h2 id="hub-title">Knowledge hub</h2>
          <p className="hub-lede">
            Browse schemes, loans, and crop guides for all supported crops. Sample questions cover tomato, potato, and
            maize.
          </p>
        </div>
        {summary && (
          <div className="hub-stats">
            <span>{summary.scheme_count} schemes</span>
            <span>{summary.loan_count} loans</span>
            <span>{summary.crop_article_count} guides</span>
          </div>
        )}
      </div>

      <div className="sample-queries">
        {SAMPLE_QUERIES.map((q) => (
          <button key={q} type="button" className="sample-chip" onClick={() => onUseQuery(q)}>
            {q}
          </button>
        ))}
      </div>

      <div className="hub-filters hub-filters-wide">
        <label>
          Search
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="drip, KCC, tomato, potassium…"
          />
        </label>
        <label>
          Scheme category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All schemes</option>
            {(summary?.scheme_categories ?? []).map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c] ?? c.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Loan type
          <select value={loanCategory} onChange={(e) => setLoanCategory(e.target.value)}>
            <option value="">All loans</option>
            {Object.entries(LOAN_CATEGORY_LABELS).map(([c, label]) => (
              <option key={c} value={c}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Crop guide
          <select value={cropFilter} onChange={(e) => setCropFilter(e.target.value)}>
            <option value="">All crops</option>
            {(summary?.crops_covered ?? []).map((c) => (
              <option key={c} value={c}>
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </option>
            ))}
            <option value="__general__">General (all crops)</option>
          </select>
        </label>
      </div>

      {loading && <p className="status">Loading knowledge…</p>}
      {error && <p className="status err">{error}</p>}

      {!loading && !error && (
        <div className="hub-grid hub-grid-three">
          <div className="hub-column">
            <h3>Government schemes</h3>
            <div className="card-grid">
              {schemes.map((s) => (
                <article key={s.id} className="scheme-card">
                  <p className="card-tag">{CATEGORY_LABELS[s.category] ?? s.category}</p>
                  <h4>{s.name}</h4>
                  <p className="card-benefit">{s.benefit}</p>
                  <p className="card-meta">
                    <strong>Who:</strong> {s.eligibility}
                  </p>
                  <p className="card-meta">
                    <strong>Apply:</strong> {s.how_to_apply}
                  </p>
                  {s.link && (
                    <a href={s.link} target="_blank" rel="noreferrer" className="card-link">
                      Official portal →
                    </a>
                  )}
                </article>
              ))}
            </div>
          </div>

          <div className="hub-column">
            <h3>Agricultural loans</h3>
            <div className="card-grid">
              {loans.map((loan) => (
                <article key={loan.id} className="loan-card">
                  <p className="card-tag">{LOAN_CATEGORY_LABELS[loan.category] ?? loan.category}</p>
                  <h4>{loan.name}</h4>
                  <p className="card-benefit">
                    {loan.effective_rate_with_subvention_percent != null
                      ? `Effective ~${loan.effective_rate_with_subvention_percent}%`
                      : `${loan.interest_rate_percent}% interest`}
                    {loan.max_amount_inr != null ? ` · up to ₹${loan.max_amount_inr.toLocaleString("en-IN")}` : ""}
                  </p>
                  <p className="card-meta">
                    <strong>Repayment:</strong> {loan.repayment_period ?? "Varies"}
                  </p>
                  <p className="card-meta">
                    <strong>Who:</strong> {loan.eligibility}
                  </p>
                  <p className="card-meta">
                    <strong>Apply:</strong> {loan.where_to_apply}
                  </p>
                </article>
              ))}
            </div>
          </div>

          <div className="hub-column">
            <h3>Crop guides</h3>
            <div className="card-grid">
              {articles.map((a) => (
                <article key={a.id} className="guide-card">
                  {a.crop && <p className="card-tag">{a.crop}</p>}
                  {!a.crop && <p className="card-tag">General</p>}
                  <h4>{a.title}</h4>
                  <p className="card-text">{a.text}</p>
                </article>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function matchesLoanSearch(loan: Loan, needle: string): boolean {
  const q = needle.toLowerCase();
  return (
    loan.name.toLowerCase().includes(q) ||
    loan.category.toLowerCase().includes(q) ||
    loan.eligibility.toLowerCase().includes(q) ||
    loan.where_to_apply.toLowerCase().includes(q)
  );
}
