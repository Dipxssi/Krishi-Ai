export type Locale = "en" | "hi" | "kn";

export const LOCALES: { id: Locale; nativeLabel: string; englishLabel: string }[] = [
  { id: "en", nativeLabel: "English", englishLabel: "English" },
  { id: "hi", nativeLabel: "हिन्दी", englishLabel: "Hindi" },
  { id: "kn", nativeLabel: "ಕನ್ನಡ", englishLabel: "Kannada" },
];

export const DEFAULT_LOCALE: Locale = "en";
