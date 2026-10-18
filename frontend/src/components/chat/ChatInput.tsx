import { useRef, useState } from "react";
import { Paperclip, SendHorizontal } from "lucide-react";
import { toast } from "sonner";

interface ChatInputProps {
  onSend: (text: string) => void;
  disabled?: boolean | undefined;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim().length > 0 && !disabled;

  const submit = () => {
    if (!canSend) return;
    onSend(value.trim());
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  return (
    <div className="border-t border-border bg-background/85 px-4 py-4 backdrop-blur sm:px-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="mx-auto flex w-full max-w-3xl items-end gap-2 rounded-3xl border border-border bg-card p-2 shadow-soft focus-within:border-primary/50"
      >
        <button
          type="button"
          aria-label="Attach a file"
          onClick={() => toast("Attachments are not available in this demo.")}
          className="grid size-10 shrink-0 place-items-center rounded-2xl text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
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
      </form>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted-foreground">
        Demo prototype — responses are illustrative examples, not professional advice.
      </p>
    </div>
  );
}
