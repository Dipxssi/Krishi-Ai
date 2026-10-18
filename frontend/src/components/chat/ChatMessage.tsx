import { Copy, RefreshCw, ThumbsDown, ThumbsUp, Sprout } from "lucide-react";
import { toast } from "sonner";
import { AdviceResult } from "@/components/chat/AdviceResult";
import { AgentIndicator } from "@/components/chat/AgentIndicator";
import type { ChatMessageData } from "@/data/mockChats";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: ChatMessageData;
  onRegenerate?: (() => void) | undefined;
  onFeedback?: ((value: "up" | "down") => void) | undefined;
  onOpenDetails?: (() => void) | undefined;
}

export function ChatMessage({
  message,
  onRegenerate,
  onFeedback,
  onOpenDetails,
}: ChatMessageProps) {
  const isUser = message.role === "user";

  const copy = async () => {
    try {
      const text = message.queryResult?.final_recommendation || message.content;
      await navigator.clipboard.writeText(text);
      toast.success("Response copied");
    } catch {
      toast.error("Could not copy the response");
    }
  };

  if (isUser) {
    return (
      <div className="flex animate-in fade-in slide-in-from-bottom-2 justify-end gap-3 duration-300">
        <div className="max-w-[85%] rounded-3xl rounded-br-lg bg-primary px-5 py-3.5 text-primary-foreground shadow-soft sm:max-w-[70%]">
          {message.imagePreview && (
            <img
              src={message.imagePreview}
              alt="Attached leaf"
              className="mb-3 max-h-40 w-full rounded-2xl object-cover"
            />
          )}
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
        <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-earth text-xs font-semibold text-earth-foreground">
          FU
        </span>
      </div>
    );
  }

  return (
    <div className="flex animate-in fade-in slide-in-from-bottom-2 gap-3 duration-300">
      <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-full bg-gradient-leaf shadow-soft">
        <Sprout className="size-4 text-primary-foreground" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        {message.agent && <AgentIndicator agent={message.agent} />}
        <p className="text-sm font-semibold text-foreground">Krishi AI</p>
        <div className="mt-2 rounded-3xl rounded-tl-lg border border-border bg-card px-5 py-4 shadow-soft">
          {message.queryResult ? (
            <AdviceResult
              result={message.queryResult}
              compact
              onOpenScores={onOpenDetails}
            />
          ) : (
            <FormattedContent content={message.content} />
          )}
        </div>
        <div className="mt-2 flex items-center gap-1">
          <IconAction label="Copy response" onClick={copy} icon={Copy} />
          {onRegenerate && (
            <IconAction label="Regenerate response" onClick={onRegenerate} icon={RefreshCw} />
          )}
          {onFeedback && (
            <>
              <IconAction
                label="Good response"
                onClick={() => onFeedback("up")}
                icon={ThumbsUp}
                active={message.feedback === "up"}
              />
              <IconAction
                label="Bad response"
                onClick={() => onFeedback("down")}
                icon={ThumbsDown}
                active={message.feedback === "down"}
              />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function IconAction({
  label,
  onClick,
  icon: Icon,
  active,
}: {
  label: string;
  onClick: () => void;
  icon: typeof Copy;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
      className={cn(
        "grid size-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        active && "bg-accent text-accent-foreground",
      )}
    >
      <Icon className="size-4" />
    </button>
  );
}

/** Lightweight markdown-ish renderer: paragraphs, bullets, numbered lists, **bold**. */
function FormattedContent({ content }: { content: string }) {
  const blocks = content.split(/\n{2,}/);

  return (
    <div className="grid gap-3 text-sm leading-relaxed text-foreground">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        const isBullet = lines.every((l) => /^\s*[•\-*]\s+/.test(l));
        const isNumbered = lines.every((l) => /^\s*\d+\.\s+/.test(l));

        if (isBullet) {
          return (
            <ul key={i} className="ml-1 grid gap-1.5">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2.5">
                  <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" />
                  <span>{inline(l.replace(/^\s*[•\-*]\s+/, ""))}</span>
                </li>
              ))}
            </ul>
          );
        }

        if (isNumbered) {
          return (
            <ol key={i} className="ml-1 grid gap-1.5">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2.5">
                  <span className="min-w-5 shrink-0 font-semibold text-primary">{j + 1}.</span>
                  <span>{inline(l.replace(/^\s*\d+\.\s+/, ""))}</span>
                </li>
              ))}
            </ol>
          );
        }

        return <p key={i}>{inline(block)}</p>;
      })}
    </div>
  );
}

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i} className="font-semibold">
        {part.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}
