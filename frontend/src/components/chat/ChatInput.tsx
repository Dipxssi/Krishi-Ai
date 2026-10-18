import { useRef, useState } from "react";
import { Paperclip, SendHorizontal, X } from "lucide-react";
import { toast } from "sonner";

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const canSend = (value.trim().length > 0 || !!imageBase64) && !disabled;

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
        Live backend advice — verify critical spray/dose decisions with a local expert or KVK.
      </p>
    </div>
  );
}
