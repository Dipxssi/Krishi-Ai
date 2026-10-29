import type { QueryResponse } from "@/api";

export type AgentId = "crop" | "disease" | "finance" | "general";

export interface Agent {
  id: AgentId;
  emoji: string;
  name: string;
  description: string;
}

export const AGENTS: Record<AgentId, Agent> = {
  crop: {
    id: "crop",
    emoji: "🌱",
    name: "Crop Advisor",
    description: "Helps with crop cultivation and farming practices.",
  },
  disease: {
    id: "disease",
    emoji: "🐛",
    name: "Disease & Pest Advisor",
    description: "Helps identify and understand crop diseases and pests.",
  },
  finance: {
    id: "finance",
    emoji: "💰",
    name: "Financial Advisor",
    description: "Helps with agricultural finance and financial questions.",
  },
  general: {
    id: "general",
    emoji: "🤖",
    name: "General Agriculture Assistant",
    description: "Handles general agricultural questions.",
  },
};

export type MessageDeliveryStatus = "waiting" | "sending" | "auth_required" | "failed";

export interface ChatMessageData {
  id: string;
  role: "user" | "assistant";
  content: string;
  agent?: AgentId | undefined;
  feedback?: "up" | "down" | undefined;
  requestId?: string | undefined;
  imagePreview?: string | undefined;
  /** Full backend payload — used for scores, confidence, and rich UI. */
  queryResult?: QueryResponse | undefined;
  /** Offline outbox placeholder until the real API answer arrives. */
  deliveryStatus?: MessageDeliveryStatus | undefined;
  outboxId?: string | undefined;
}

export interface Conversation {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessageData[];
}

const now = Date.now();

let seq = 0;
export const newId = () => `id-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export const MOCK_CONVERSATIONS: Conversation[] = [
  {
    id: "c1",
    title: "Yellow leaves in my wheat crop",
    updatedAt: now - 1000 * 60 * 20,
    messages: [
      {
        id: "c1m1",
        role: "user",
        content: "My wheat crop leaves are turning yellow. What should I do?",
      },
      {
        id: "c1m2",
        role: "assistant",
        agent: "disease",
        content: `Yellowing leaves in wheat can happen for several reasons, including nutrient deficiency, excess water, poor drainage, or disease.

Here are some things you can check:

1. Check soil moisture — waterlogged roots often cause yellowing.
2. Look for signs of fungal infection such as spots or powdery patches.
3. Check whether older or newer leaves are affected first.
4. Consider whether the crop may have a nitrogen deficiency.

If you tell me the crop age, soil type, and what the leaves look like, I can help narrow down the possible cause.`,
      },
    ],
  },
  {
    id: "c2",
    title: "Best fertilizer for rice",
    updatedAt: now - 1000 * 60 * 60 * 5,
    messages: [
      { id: "c2m1", role: "user", content: "Which fertilizer is best for rice?" },
      {
        id: "c2m2",
        role: "assistant",
        agent: "crop",
        content: `Rice responds well to a balanced nutrient plan rather than a single product.

A typical approach looks like this:

• **Basal dose** at transplanting — nitrogen, phosphorus and potassium together
• **First top dressing** around tillering — mostly nitrogen
• **Second top dressing** at panicle initiation — nitrogen with some potassium

Practical tips:

1. Apply nitrogen in splits so it is not lost to water.
2. Keep 2–3 cm of standing water while top dressing.
3. Add zinc if leaves show pale bands, which is common in rice soils.

A soil test from your local agriculture office gives the most accurate dose for your field.`,
      },
    ],
  },
  {
    id: "c3",
    title: "How to apply for Kisan loan?",
    updatedAt: now - 1000 * 60 * 60 * 26,
    messages: [
      { id: "c3m1", role: "user", content: "How can I get an agricultural loan?" },
      {
        id: "c3m2",
        role: "assistant",
        agent: "finance",
        content: `You may be eligible for different agricultural loan options depending on your farming activity, location and financial requirements.

You can explore:

• Crop loans
• Equipment loans
• Kisan Credit Card facilities
• Agricultural development loans

Documents usually requested:

1. Identity proof
2. Land records or tenancy proof
3. A simple crop plan with expected costs

For a real recommendation, we would eventually connect Krishi AI to a financial information service.`,
      },
    ],
  },
  {
    id: "c4",
    title: "Tomato pest problem",
    updatedAt: now - 1000 * 60 * 60 * 50,
    messages: [
      { id: "c4m1", role: "user", content: "Small insects are eating my tomato leaves." },
      {
        id: "c4m2",
        role: "assistant",
        agent: "disease",
        content: `Tomato leaf damage is often caused by whitefly, aphids, leaf miner or fruit borer.

How to identify:

1. Sticky leaves with tiny white insects underneath → whitefly
2. Curled shoots with clusters of soft insects → aphids
3. Pale winding trails inside the leaf → leaf miner
4. Holes in fruit with dark droppings → fruit borer

Low-cost steps you can try:

• Install yellow sticky traps around the field
• Remove and destroy badly affected leaves
• Use a neem-based spray in the evening
• Rotate away from tomato/chilli next season

Share a photo description of the insect and I can narrow it down further.`,
      },
    ],
  },
  {
    id: "c5",
    title: "Government farming schemes",
    updatedAt: now - 1000 * 60 * 60 * 72,
    messages: [
      { id: "c5m1", role: "user", content: "What government schemes can help my farm?" },
      {
        id: "c5m2",
        role: "assistant",
        agent: "finance",
        content: `Support programmes for farmers usually fall into a few categories:

• Income support payments
• Crop insurance against weather loss
• Subsidies for seeds, equipment and irrigation
• Soil health and testing programmes
• Market linkage and storage support

To check what applies to you, it helps to know your state, land size and main crop. In this demo the scheme list is illustrative only.`,
      },
    ],
  },
  {
    id: "c6",
    title: "Best crop for this season",
    updatedAt: now - 1000 * 60 * 60 * 96,
    messages: [
      { id: "c6m1", role: "user", content: "Which crop is best for my land this season?" },
      {
        id: "c6m2",
        role: "assistant",
        agent: "crop",
        content: `Choosing a crop depends on four practical factors:

1. **Soil type** — sandy, loam or clay
2. **Water availability** — canal, borewell or rain-fed
3. **Season** — kharif, rabi or summer
4. **Nearby market demand**

General guidance:

• Loam soil with reliable water → wheat or rice depending on season
• Sandy soil with limited water → pearl millet, groundnut or mustard
• Small plot near a town → vegetables give quicker returns

Tell me your soil type, water source and district and I will suggest two or three suitable options.`,
      },
    ],
  },
];
