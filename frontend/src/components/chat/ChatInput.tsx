import { useEffect, useMemo, useRef, useState } from "react";
import { Mic, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { toast } from "sonner";
import { transcribeAudio } from "@/api";
import { useI18n } from "@/hooks/useI18n";
import { loadFarmProfile } from "@/lib/farmProfile";

interface ChatInputProps {
  onSend: (
    text: string,
    imageBase64?: string | null,
    cropHint?: string | null,
    options?: { fromVoice?: boolean },
  ) => void;
  disabled?: boolean | undefined;
  preferredLanguage?: string | null | undefined;
}

/** Only pin Whisper for Indic languages; English/default lets Groq auto-detect (+ server-side hi/kn recovery). */
function whisperLanguageHint(preferred?: string | null): string | undefined {
  if (!preferred) return undefined;
  const clean = preferred.trim().toLowerCase();
  if (clean.startsWith("kn") || clean.includes("kannada")) return "kn";
  if (clean.startsWith("hi") || clean.includes("hindi")) return "hi";
  return undefined;
}

function resolveWhisperHint(
  preferredLanguage?: string | null,
  locale?: string | null,
): string | undefined {
  // Farm preference first (UI may stay English while farmer speaks Hindi).
  try {
    const farmLang = loadFarmProfile().preferred_language;
    const fromFarm = whisperLanguageHint(farmLang);
    if (fromFarm) return fromFarm;
  } catch {
    /* ignore */
  }
  return whisperLanguageHint(preferredLanguage) ?? whisperLanguageHint(locale);
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("read-fail"));
    reader.readAsDataURL(file);
  });
}

const LEAF_CROPS = ["tomato", "potato", "maize"] as const;

function normalizeLeafCrop(raw: string | null | undefined): string {
  if (!raw?.trim()) return "";
  const key = raw.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (key === "corn" || key === "maize_corn") return "maize";
  if (key === "tomatoes") return "tomato";
  if (key === "potatoes") return "potato";
  return key;
}

export function ChatInput({ onSend, disabled, preferredLanguage }: ChatInputProps) {
  const { t, locale } = useI18n();
  const [value, setValue] = useState("");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [cropHint, setCropHint] = useState<string>("");
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const fromVoiceRef = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const canSend = (value.trim().length > 0 || !!imageBase64) && !disabled && !recording && !transcribing;

  const profileCrop = useMemo(() => {
    try {
      return (loadFarmProfile().crop ?? "").trim();
    } catch {
      return "";
    }
  }, [imageBase64]);

  const profileCropNorm = normalizeLeafCrop(profileCrop);
  const profileIsKnownLeaf = (LEAF_CROPS as readonly string[]).includes(profileCropNorm);

  useEffect(() => () => {
    if (recorderRef.current) {
      recorderRef.current.onstop = null;
      recorderRef.current.onerror = null;
    }
    recorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const transcribe = async (blob: Blob) => {
    setTranscribing(true);
    try {
      if (blob.size > 25 * 1024 * 1024) {
        throw new Error(t("input.tooLarge"));
      }
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
        reader.onerror = () => reject(new Error(t("input.readRecording")));
        reader.readAsDataURL(blob);
      });
      const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
      const result = await transcribeAudio(
        base64,
        blob.type || "audio/webm",
        `recording.${ext}`,
        resolveWhisperHint(preferredLanguage, locale),
      );
      fromVoiceRef.current = true;
      setValue(result.text);
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
          textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
        }
      });
      toast.success(t("input.transcribed"));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t("input.transcribeFail"));
    } finally {
      setTranscribing(false);
    }
  };

  const toggleRecording = async () => {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      toast.error(t("input.noMic"));
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const options = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? { mimeType: "audio/webm;codecs=opus" }
        : undefined;
      const recorder = new MediaRecorder(stream, options);
      recorderRef.current = recorder;
      chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onerror = () => {
        recorder.onstop = null;
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setRecording(false);
        toast.error(t("input.audioFail"));
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        if (blob.size) void transcribe(blob);
      };
      recorder.start();
      setRecording(true);
    } catch {
      toast.error(t("input.micDenied"));
    }
  };

  const submit = () => {
    if (!canSend) return;
    const text =
      value.trim() ||
      (imageBase64
        ? t("input.diagnoseLeaf")
        : "");
    if (!text) return;
    const fromVoice = fromVoiceRef.current;
    fromVoiceRef.current = false;
    // Empty cropHint = Auto-detect — MobileNet chooses tomato/potato/maize from the image.
    onSend(text, imageBase64, cropHint || undefined, { fromVoice });
    setValue("");
    setImageBase64(null);
    setCropHint("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const onPickImage = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error(t("input.needImage"));
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.error(t("input.imageSize"));
      return;
    }
    try {
      const dataUrl = await fileToDataUrl(file);
      // Default Auto-detect so MobileNet predicts the crop; farmer can override.
      setCropHint("");
      setImageBase64(dataUrl);
      toast.success(t("input.attached"));
    } catch {
      toast.error(t("input.readFail"));
    }
  };

  return (
    <div className="border-t border-border bg-background/85 px-3 py-3 backdrop-blur sm:px-6 sm:py-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="mx-auto flex w-full max-w-3xl flex-col gap-2 rounded-3xl border border-border bg-card p-2 shadow-soft focus-within:border-primary/50"
      >
        {imageBase64 && (
          <div className="flex flex-wrap items-start gap-3 px-2 pt-2">
            <img
              src={imageBase64}
              alt={t("input.altLeaf")}
              className="h-16 w-16 shrink-0 rounded-xl object-cover border border-border"
            />
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <label htmlFor="crop-hint-select" className="text-xs font-medium text-muted-foreground">
                {t("input.leafCrop")}
              </label>
              <select
                id="crop-hint-select"
                value={cropHint}
                onChange={(e) => setCropHint(e.target.value)}
                className="h-8 w-full max-w-xs rounded-lg border border-border bg-background px-2.5 text-xs font-medium text-foreground focus:border-primary focus:outline-none"
              >
                <option value="">{t("input.autoDetect")}</option>
                {profileCrop && !profileIsKnownLeaf && (
                  <option value={profileCropNorm || profileCrop.toLowerCase()}>
                    {t("input.profileCrop", { crop: profileCrop })}
                  </option>
                )}
                <option value="tomato">{t("input.tomato")}</option>
                <option value="potato">{t("input.potato")}</option>
                <option value="maize">{t("input.maize")}</option>
                <option value="other">{t("input.other")}</option>
              </select>
            </div>
            <button
              type="button"
              aria-label={t("input.remove")}
              onClick={() => {
                setImageBase64(null);
                setCropHint("");
              }}
              className="grid size-8 place-items-center rounded-full bg-muted text-muted-foreground hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
        )}

        <div className="flex items-end gap-1.5 sm:gap-2">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              void onPickImage(e.target.files?.[0]);
              e.currentTarget.value = "";
            }}
          />
          <button
            type="button"
            aria-label={t("input.attach")}
            onClick={() => fileRef.current?.click()}
            disabled={disabled}
            className="grid size-9 shrink-0 place-items-center rounded-2xl text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50 sm:size-10"
          >
            <Paperclip className="size-5" />
          </button>

          <label htmlFor="chat-composer" className="sr-only">
            {t("input.messageAria")}
          </label>
          <textarea
            id="chat-composer"
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => {
              fromVoiceRef.current = false;
              setValue(e.target.value);
              const el = e.currentTarget;
              el.style.height = "auto";
              el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={t("input.placeholder")}
            className="max-h-44 min-h-9 min-w-0 flex-1 resize-none bg-transparent py-2 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none sm:min-h-10 sm:py-2.5"
          />

          <button
            type="button"
            aria-label={recording ? t("input.stopRecord") : t("input.record")}
            title={recording ? t("input.stopRecord") : t("input.record")}
            onClick={() => void toggleRecording()}
            disabled={disabled || transcribing}
            className="grid size-9 shrink-0 place-items-center rounded-2xl text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50 sm:size-10"
          >
            {recording ? <Square className="size-4 fill-current" /> : <Mic className="size-5" />}
          </button>

          <button
            type="submit"
            disabled={!canSend}
            aria-label={t("input.send")}
            className="grid size-9 shrink-0 place-items-center rounded-2xl bg-gradient-leaf text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:bg-none disabled:bg-muted disabled:text-muted-foreground sm:size-10"
          >
            <SendHorizontal className="size-5" />
          </button>
        </div>
      </form>
      <p className="mx-auto mt-2 max-w-3xl px-1 text-center text-[11px] leading-snug text-muted-foreground sm:text-xs">
        {transcribing
          ? t("input.transcribing")
          : recording
            ? t("input.recording")
            : t("input.disclaimer")}
      </p>
    </div>
  );
}
