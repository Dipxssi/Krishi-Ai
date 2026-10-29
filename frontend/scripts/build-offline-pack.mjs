/**
 * Build public/offline-pack/v1.json from backend curated knowledge
 * (crops.json, schemes.json, loans.json) — same source the online RAG uses.
 *
 * Usage: node scripts/build-offline-pack.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..", "..");
const knowledgeDir = join(root, "backend", "data", "knowledge");
const outPath = join(__dirname, "..", "public", "offline-pack", "v1.json");

function loadJson(name) {
  return JSON.parse(readFileSync(join(knowledgeDir, name), "utf8"));
}

function uniq(arr) {
  return [...new Set(arr.filter(Boolean))];
}

function keywordsFromText(text, extra = []) {
  const stop = new Set([
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "when",
    "are",
    "is",
    "to",
    "of",
    "in",
    "on",
    "a",
    "an",
    "or",
    "be",
    "by",
    "at",
    "as",
    "if",
    "not",
    "may",
    "can",
    "use",
    "using",
  ]);
  const words = String(text)
    .toLowerCase()
    .split(/[^a-z0-9₹]+/i)
    .filter((w) => w.length > 2 && !stop.has(w));
  return uniq([...extra, ...words]).slice(0, 24);
}

function cropKeywords(crop) {
  if (!crop) return [];
  const map = {
    tomato: ["tomato", "टमाटर", "ಟೊಮೇಟೊ"],
    potato: ["potato", "आलू", "ಆಲೂಗಡ್ಡೆ"],
    onion: ["onion", "प्याज", "ಈರುಳ್ಳಿ"],
    maize: ["maize", "corn", "मक्का", "ಜೋಳ"],
    wheat: ["wheat", "गेहूं", "ಗೋಧಿ"],
    rice: ["rice", "paddy", "धान", "चावल", "ಭತ್ತ"],
    cotton: ["cotton", "कपास", "ಹತ್ತಿ"],
  };
  return map[crop] || [crop];
}

const crops = loadJson("crops.json");
const schemes = loadJson("schemes.json");
const loans = loadJson("loans.json");

const entries = [];

for (const row of crops) {
  const crop = row.crop || null;
  entries.push({
    id: `crop-${row.id}`,
    lang: "en",
    crop,
    keywords: keywordsFromText(`${row.title} ${row.text}`, [
      ...cropKeywords(crop),
      ...(crop ? [crop] : ["general", "farm", "irrigation", "soil", "budget"]),
    ]),
    title: row.title,
    answer: `${row.text}\n\n(Offline tip from Krishi AI crop knowledge. Confirm spray/dose with your local KVK when online.)`,
    source: "backend/data/knowledge/crops.json",
  });
}

for (const row of schemes) {
  const kws = Array.isArray(row.keywords) ? row.keywords : [];
  const cropList = Array.isArray(row.crops) ? row.crops : [];
  const answer = [
    row.benefit,
    `Eligibility: ${row.eligibility}`,
    `Apply: ${row.how_to_apply}`,
    row.link ? `More: ${row.link}` : null,
  ]
    .filter(Boolean)
    .join(" ");

  entries.push({
    id: `scheme-${row.id}`,
    lang: "en",
    crop: cropList[0] || null,
    keywords: keywordsFromText(`${row.name} ${row.benefit} ${kws.join(" ")}`, [
      "scheme",
      "subsidy",
      "yojana",
      "government",
      ...kws,
      ...cropList.flatMap(cropKeywords),
    ]),
    title: row.name,
    answer: `${answer}\n\n(Offline scheme summary. Verify current rates on the official portal when online.)`,
    source: "backend/data/knowledge/schemes.json",
  });
}

for (const row of loans) {
  const rate =
    row.effective_rate_with_subvention_percent != null
      ? `Effective ~${row.effective_rate_with_subvention_percent}% with subvention (listed ${row.interest_rate_percent}%).`
      : `Interest ~${row.interest_rate_percent}%.`;
  const max =
    row.max_amount_inr != null ? `Up to ₹${Number(row.max_amount_inr).toLocaleString("en-IN")}.` : "";
  const docs = Array.isArray(row.documents) ? row.documents.join(", ") : "";

  entries.push({
    id: `loan-${row.id}`,
    lang: "en",
    crop: null,
    keywords: keywordsFromText(`${row.name} ${row.category} loan credit finance kcc bank`, [
      "loan",
      "credit",
      "kcc",
      "finance",
      "bank",
      "interest",
      row.category,
    ]),
    title: row.name,
    answer: `${rate} ${max} Eligibility: ${row.eligibility}. Apply: ${row.where_to_apply}. Documents: ${docs}. Repayment: ${row.repayment_period}.\n\n(Offline loan orientation. Bank terms may vary — confirm when online.)`,
    source: "backend/data/knowledge/loans.json",
  });
}

const pack = {
  version: "1.1.0",
  updatedAt: new Date().toISOString().slice(0, 10),
  modelHint: null,
  builtFrom: [
    "backend/data/knowledge/crops.json",
    "backend/data/knowledge/schemes.json",
    "backend/data/knowledge/loans.json",
  ],
  entryCount: entries.length,
  entries,
};

mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, `${JSON.stringify(pack, null, 2)}\n`, "utf8");
console.log(`Wrote ${entries.length} entries → ${outPath}`);
