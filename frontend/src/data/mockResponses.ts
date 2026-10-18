import type { AgentId } from "./mockChats";

const CROP_WORDS = ["crop", "sow", "seed", "fertilizer", "fertiliser", "irrigation", "soil", "wheat", "rice", "harvest", "season", "plant", "yield", "grow"];
const DISEASE_WORDS = ["pest", "disease", "insect", "fungus", "yellow", "spot", "wilt", "bug", "borer", "rot", "blight", "leaves", "leaf"];
const FINANCE_WORDS = ["loan", "credit", "kisan", "money", "finance", "financial", "subsidy", "scheme", "insurance", "cost", "price", "expense", "budget", "bank"];

export function detectAgent(question: string): AgentId {
  const q = question.toLowerCase();
  const score = (words: string[]) => words.filter((w) => q.includes(w)).length;
  const finance = score(FINANCE_WORDS);
  const disease = score(DISEASE_WORDS);
  const crop = score(CROP_WORDS);
  const best = Math.max(finance, disease, crop);
  if (best === 0) return "general";
  if (finance === best) return "finance";
  if (disease === best) return "disease";
  return "crop";
}

const RESPONSES: Record<AgentId, string[]> = {
  disease: [
    `Yellowing or damaged leaves usually point to one of four causes: nutrient deficiency, excess water, poor drainage, or a disease or pest attack.

Here are some things you can check:

1. Check soil moisture at about 10 cm depth.
2. Look for fungal signs such as spots, powder or mould.
3. Note whether older or newer leaves are affected first.
4. Consider a nitrogen deficiency if the whole plant looks pale.

If you tell me the crop age, soil type, and what the leaves look like, I can help narrow down the possible cause.`,
    `Pest problems are easier to manage when identified early.

A simple inspection routine:

• Check the underside of leaves for eggs and small insects
• Walk the field diagonally and inspect 10 plants at 5 spots
• Note any sticky residue, holes, trails or curling

Low-cost management options:

1. Yellow or blue sticky traps to monitor and reduce numbers
2. Removal of heavily infested plant parts
3. A neem-based spray applied in the evening
4. Crop rotation next season to break the pest cycle

Describe the insect or the damage pattern and I can suggest a more specific approach.`,
  ],
  crop: [
    `Good crop decisions come from matching the crop to your field conditions.

Please consider:

1. **Soil type** — sandy, loam or clay
2. **Water source** — canal, borewell or rain-fed
3. **Season** — kharif, rabi or summer
4. **Local market demand and storage**

General guidance:

• Loam soil with steady water suits wheat or rice
• Light soil with limited water suits millets, groundnut or mustard
• Small plots near towns often earn more from vegetables

Share your soil type, water source and district and I will shortlist a few suitable options.`,
    `For healthy growth, nutrients work best in split applications rather than one heavy dose.

A practical plan:

• **Before sowing** — organic matter and a balanced basal dose
• **Early growth** — nitrogen for leaf and tiller development
• **Flowering stage** — potassium with light nitrogen

Also remember:

1. Irrigate at the critical growth stages instead of fixed dates.
2. Keep weeds controlled in the first 30–40 days.
3. Get a soil test once a year to avoid over-fertilising.`,
  ],
  finance: [
    `You may be eligible for different agricultural loan options depending on your farming activity, location and financial requirements.

You can explore:

• Crop loans
• Equipment loans
• Kisan Credit Card facilities
• Agricultural development loans

For a real recommendation, we would eventually connect Krishi AI to a financial information service.`,
    `Farm finances become much easier to manage with a simple written plan.

Try this structure:

1. **Fixed costs** — land, rent, equipment repayment
2. **Variable costs** — seed, fertiliser, labour, fuel
3. **Expected income** — yield multiplied by an achievable price
4. **Buffer** — keep 10–15% aside for weather or pest surprises

Support options worth checking:

• Crop insurance for weather loss
• Input subsidies for seed and irrigation
• Short-term credit facilities for seasonal costs

This is demo guidance only, not a financial recommendation.`,
  ],
  general: [
    `Happy to help with that.

Krishi AI can assist with:

• Crop selection, sowing and irrigation planning
• Diseases, pests and leaf problems
• Fertiliser and soil health questions
• Agricultural loans, costs and support schemes

Tell me a little about your farm — crop, soil type, water source and location — and I will give more specific guidance.

Note: this is a demonstration response from a frontend prototype.`,
    `Here is how I would approach that.

1. Describe the problem in as much detail as you can.
2. Mention the crop, its age and the current weather.
3. Add anything you already tried.

With those details, the right Krishi AI agent can give practical next steps. In this prototype the responses are illustrative examples.`,
  ],
};

export function getMockResponse(question: string, variant = 0) {
  const agent = detectAgent(question);
  const options = RESPONSES[agent];
  return { agent, content: options[variant % options.length] as string };
}

export const SUGGESTED_PROMPTS = [
  { emoji: "🌾", text: "My crop leaves are turning yellow" },
  { emoji: "🐛", text: "How can I control pests in my crop?" },
  { emoji: "💰", text: "How can I get an agricultural loan?" },
  { emoji: "🌱", text: "Which crop is best for my land?" },
];
