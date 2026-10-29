import type { FarmContext } from "@/api";
import { loadFarmProfile } from "@/lib/farmProfile";
import { loadOfflinePack, rankPackEntries } from "@/lib/offlinePack";
import { getLocale } from "@/lib/i18n";

export type OfflineAdviceResult = {
  content: string;
  source: "pack" | "farm_profile" | "fallback";
};

function farmTips(profile: FarmContext, question: string, locale: string): string[] {
  const tips: string[] = [];
  const crop = (profile.crop || "").trim();
  const soil = (profile.soil_type || "").trim();
  const location = (profile.location || "").trim();
  const q = question.toLowerCase();

  if (locale.startsWith("hi")) {
    if (crop) tips.push(`आपकी प्रोफ़ाइल फसल: ${crop}. उसी फसल के लिए स्थानीय KVK से खुराक/छिड़काव जाँचें।`);
    if (soil) tips.push(`मिट्टी (${soil}): जल निकासी और नमी जाँचें; जलभराव से पीली पत्तियाँ हो सकती हैं।`);
    if (location) tips.push(`स्थान: ${location}. मौसम और ज़िला सलाह के लिए ऑनलाइन होने पर विस्तृत जवाब आएगा।`);
    if (/yellow|पीली|पीला|leaf|पत्ति/.test(q)) {
      tips.push("पीली पत्तियाँ: नमी, नाइट्रोजन कमी, या फफूंद की जाँच करें। अभी कोई तेज़ रसायन न डालें।");
    }
    if (/pest|कीट|insect/.test(q)) {
      tips.push("कीट: प्रभावित पत्तियाँ हटाएँ; नीम-आधारित उपाय आज़मा सकते हैं जब तक विस्तृत सलाह न मिले।");
    }
    if (/loan|ऋण|कर्ज|finance|पैसा/.test(q)) {
      tips.push("वित्त: KCC / स्थानीय बैंक या सहकारी समिति से पूछें; ऑनलाइन होने पर योजना विवरण मिलेगा।");
    }
  } else if (locale.startsWith("kn")) {
    if (crop) tips.push(`ನಿಮ್ಮ ಪ್ರೊಫೈಲ್ ಬೆಳೆ: ${crop}. ಡೋಸ್/ಸಿಂಪಡಣೆಗೆ ಸ್ಥಳೀಯ KVK ಪರಿಶೀಲಿಸಿ.`);
    if (soil) tips.push(`ಮಣ್ಣು (${soil}): ನೀರು ಹರಿಯುವಿಕೆ ಮತ್ತು ತೇವ ಪರಿಶೀಲಿಸಿ.`);
    if (location) tips.push(`ಸ್ಥಳ: ${location}. ಆನ್‌ಲೈನ್ ಆದಾಗ ವಿವರವಾದ ಉತ್ತರ ಬರುತ್ತದೆ.`);
    if (/yellow|ಹಳದಿ|leaf|ಎಲೆ/.test(q)) {
      tips.push("ಹಳದಿ ಎಲೆಗಳು: ತೇವ, ನೈಟ್ರೋಜನ್ ಕೊರತೆ ಅಥವಾ ಶಿಲೀಂಧ್ರ ಪರಿಶೀಲಿಸಿ. ಈಗ ತೀವ್ರ ರಾಸಾಯನಿಕ ಬಳಸಬೇಡಿ.");
    }
    if (/pest|ಕೀಟ|insect/.test(q)) {
      tips.push("ಕೀಟ: ಬಾಧಿತ ಎಲೆಗಳನ್ನು ತೆಗೆಯಿರಿ; ವಿವರ ಸಲಹೆ ಬರುವವರೆಗೆ ಬೇವು ಆಧಾರಿತ ಕ್ರಮ.");
    }
    if (/loan|ಸಾಲ|finance/.test(q)) {
      tips.push("ಹಣಕಾಸು: KCC / ಸ್ಥಳೀಯ ಬ್ಯಾಂಕ್ ಕೇಳಿ; ಆನ್‌ಲೈನ್‌ನಲ್ಲಿ ಯೋಜನೆ ವಿವರ ಸಿಗುತ್ತದೆ.");
    }
  } else {
    if (crop) tips.push(`Your profile crop is ${crop}. Confirm spray/dose with a local KVK for that crop.`);
    if (soil) tips.push(`Soil noted as ${soil}: check drainage and moisture — waterlogging often yellows leaves.`);
    if (location) tips.push(`Location: ${location}. A detailed, location-aware answer will arrive when you are back online.`);
    if (/yellow|leaf|leaves|chlorosis/.test(q)) {
      tips.push("Yellow leaves: check moisture, nitrogen shortage, or early fungus. Avoid strong chemicals until verified.");
    }
    if (/pest|insect|bug|worm/.test(q)) {
      tips.push("Pests: remove badly hit leaves; neem-based options are safer until a verified plan arrives.");
    }
    if (/loan|credit|kcc|finance|money|budget/.test(q)) {
      tips.push("Finance: ask about KCC / local cooperative credit; scheme details load when you reconnect.");
    }
  }

  return tips;
}

function preface(locale: string): string {
  if (locale.startsWith("hi")) {
    return "आप ऑफ़लाइन हैं — यह एक त्वरित सुझाव है। सवाल कतार में है; ऑनलाइन होने पर विस्तृत जाँच शुदा जवाब आएगा।";
  }
  if (locale.startsWith("kn")) {
    return "ನೀವು ಆಫ್‌ಲೈನ್ ಇದ್ದೀರಿ — ಇದು ತ್ವರಿತ ಸಲಹೆ. ಪ್ರಶ್ನೆ ಸರದಿಯಲ್ಲಿದೆ; ಆನ್‌ಲೈನ್ ಆದಾಗ ಪರಿಶೀಲಿತ ವಿವರ ಉತ್ತರ ಬರುತ್ತದೆ.";
  }
  return "You’re offline — this is a quick suggestion. Your question is queued; a verified detailed answer will arrive when you’re back online.";
}

/**
 * Build a short offline suggestion from the downloaded pack + farm profile.
 * Not a full LLM; Phase 3 pack improves match quality.
 */
export async function buildOfflineAdvice(question: string): Promise<OfflineAdviceResult> {
  const locale = getLocale();
  const profile = loadFarmProfile();
  const lines: string[] = [preface(locale), ""];

  const pack = await loadOfflinePack().catch(() => null);
  if (pack) {
    const hits = rankPackEntries(question, pack, locale, profile.crop);
    if (hits.length > 0) {
      lines.push(hits[0].title);
      lines.push(hits[0].answer);
      if (hits[1]) {
        lines.push("");
        lines.push(`${hits[1].title}: ${hits[1].answer.split("\n")[0]}`);
      }
      const tips = farmTips(profile, question, locale);
      if (tips.length) {
        lines.push("");
        lines.push(...tips.slice(0, 2).map((t) => `• ${t}`));
      }
      return { content: lines.join("\n"), source: "pack" };
    }
  }

  const tips = farmTips(profile, question, locale);
  if (tips.length) {
    lines.push(...tips.map((t) => `• ${t}`));
    return { content: lines.join("\n"), source: "farm_profile" };
  }

  if (locale.startsWith("hi")) {
    lines.push("अभी विस्तृत सलाह उपलब्ध नहीं। सवाल सहेजा गया है — कनेक्ट होते ही कृषि AI जवाब देगा।");
  } else if (locale.startsWith("kn")) {
    lines.push("ಈಗ ವಿವರ ಸಲಹೆ ಲಭ್ಯವಿಲ್ಲ. ಪ್ರಶ್ನೆ ಉಳಿಸಲಾಗಿದೆ — ಸಂಪರ್ಕ ಬಂದಾಗ ಕೃಷಿ AI ಉತ್ತರಿಸುತ್ತದೆ.");
  } else {
    lines.push(
      "No detailed offline tip matched yet. Your question is saved — Krishi AI will answer when the connection returns.",
    );
  }
  return { content: lines.join("\n"), source: "fallback" };
}
