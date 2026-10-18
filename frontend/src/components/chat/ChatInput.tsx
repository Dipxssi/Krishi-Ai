import { useEffect, useRef, useState } from "react";
import { Mic, Paperclip, SendHorizontal, Square, X } from "lucide-react";
import { toast } from "sonner";
import { transcribeAudio } from "@/api";

interface ChatInputProps {
  onSend: (text: string, imageBase64?: string | null) => void;
  disabled?: boolean | undefined;
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Could not read image"));
    reader.readAsDataURL(file);
  });
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const canSend = (value.trim().length > 0 || !!imageBase64) && !disabled && !recording && !transcribing;

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
        throw new Error("Recording is too large. Please record a shorter question.");
      }
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
        reader.onerror = () => reject(new Error("Could not read recording."));
        reader.readAsDataURL(blob);
      });
      const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
      const result = await transcribeAudio(base64, blob.type || "audio/webm", `recording.${ext}`);
      setValue(result.text);
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
          textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
        }
      });
      toast.success("Speech transcribed. Review it, then send your question.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not transcribe the recording.");
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
      toast.error("This browser does not support audio recording.");
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
        toast.error("Audio recording failed. Please try again.");
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
      toast.error("Microphone access was denied or is unavailable.");
    }
  };

  const submit = () => {
    if (!canSend) return;
    const text =
      value.trim() ||
      (imageBase64
        ? "Please diagnose this leaf image and suggest safe next steps."
        : "");
    if (!text) return;
    onSend(text, imageBase64);
    setValue("");
    setImageBase64(null);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const onPickImage = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error("Please attach an image file.");
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.error("Image must be under 8MB.");
      return;
    }
    try {
      const dataUrl = await fileToDataUrl(file);
      setImageBase64(dataUrl);
      toast.success("Leaf photo attached");
    } catch {
      toast.error("Could not read that image.");
    }
  };

  return (
    <div className="border-t border-border bg-background/85 px-4 py-4 backdrop-blur sm:px-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="mx-auto flex w-full max-w-3xl flex-col gap-2 rounded-3xl border border-border bg-card p-2 shadow-soft focus-within:border-primary/50"
      >
        {imageBase64 && (
          <div className="flex items-start gap-3 px-2 pt-2">
            <img
              src={imageBase64}
              alt="Attached leaf"
              className="h-16 w-16 rounded-xl object-cover"
            />
            <button
              type="button"
              aria-label="Remove attachment"
              onClick={() => setImageBase64(null)}
              className="grid size-8 place-items-center rounded-full bg-muted text-muted-foreground hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
        )}

        <div className="flex items-end gap-2">
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
            aria-label="Attach a leaf photo"
            onClick={() => fileRef.current?.click()}
            disabled={disabled}
            className="grid size-10 shrink-0 place-items-center rounded-2xl text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
          >
            <Paperclip className="size-5" />
          </button>

          <label htmlFor="chat-composer" className="sr-only">
            Message Krishi AI
          </label>
          <textarea
            id="chat-composer"
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => {
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
            placeholder="Ask Krishi AI about farming, crops, pests, finance..."
            className="max-h-44 min-h-10 flex-1 resize-none bg-transparent py-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none"
          />

          <button
            type="button"
            aria-label={recording ? "Stop recording" : "Record a voice question"}
            title={recording ? "Stop recording" : "Record a voice question"}
            onClick={() => void toggleRecording()}
            disabled={disabled || transcribing}
            className="grid size-10 shrink-0 place-items-center rounded-2xl text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
          >
            {recording ? <Square className="size-4 fill-current" /> : <Mic className="size-5" />}
          </button>

          <button
            type="submit"
            disabled={!canSend}
            aria-label="Send message"
            className="grid size-10 shrink-0 place-items-center rounded-2xl bg-gradient-leaf text-primary-foreground transition-opacity disabled:cursor-not-allowed disabled:bg-none disabled:bg-muted disabled:text-muted-foreground"
          >
            <SendHorizontal className="size-5" />
          </button>
        </div>
      </form>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted-foreground">
        {transcribing ? "Transcribing your recording…" : recording ? "Recording… select stop when finished." : "Live backend advice — verify critical spray/dose decisions with a local expert or KVK."}
      </p>
    </div>
  );
}
