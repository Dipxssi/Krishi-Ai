import { Copy, RefreshCw, ThumbsDown, ThumbsUp, Sprout, Volume2, VolumeX } from "lucide-react";
import { toast } from "sonner";
import { AdviceResult } from "@/components/chat/AdviceResult";
import { AgentIndicator } from "@/components/chat/AgentIndicator";
import type { ChatMessageData } from "@/data/mockChats";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

interface ChatMessageProps {
  message: ChatMessageData;
  onRegenerate?: (() => void) | undefined;
  onFeedback?: ((value: "up" | "down") => void) | undefined;
  onOpenDetails?: (() => void) | undefined;
  onSpeak?: (() => void) | undefined;
  isSpeaking?: boolean;
}

export function ChatMessage({
  message,
  onRegenerate,
  onFeedback,
  onOpenDetails,
  onSpeak,
  isSpeaking = false,
}: ChatMessageProps) {
  const { t } = useI18n();
  const isUser = message.role === "user";

  const copy = async () => {
    try {
      const text = message.queryResult?.final_recommendation || message.content;
      await navigator.clipboard.writeText(text);
      toast.success(t("chat.copyOk"));
    } catch {
      toast.error(t("chat.copyFail"));
    }
  };

  if (isUser) {
    return (
      <div className="flex animate-in fade-in slide-in-from-bottom-2 justify-end gap-2 duration-300 sm:gap-3">
        <div className="max-w-[min(100%,24rem)] min-w-0 rounded-3xl rounded-br-lg bg-primary px-3.5 py-3 text-primary-foreground shadow-soft sm:max-w-[70%] sm:px-5 sm:py-3.5">
          {message.imagePreview && (
            <img
              src={message.imagePreview}
              alt={t("input.altLeaf")}
              className="mb-3 max-h-40 w-full rounded-2xl object-cover"
            />
          )}
          <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </p>
        </div>
        <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-earth text-xs font-semibold text-earth-foreground sm:size-9">
          FU
        </span>
      </div>
    );
  }

  return (
    <div className="flex animate-in fade-in slide-in-from-bottom-2 gap-2 duration-300 sm:gap-3">
      <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-full bg-gradient-leaf shadow-soft sm:size-9">
        <Sprout className="size-4 text-primary-foreground" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1 overflow-hidden">
        {message.agent && <AgentIndicator agent={message.agent} />}
        <p className="text-sm font-semibold text-foreground">Krishi AI</p>
        <div className="mt-2 min-w-0 rounded-3xl rounded-tl-lg border border-border bg-card px-3.5 py-3.5 shadow-soft sm:px-5 sm:py-4">
          {message.deliveryStatus && !message.queryResult && (
            <p
              className={cn(
                "mb-3 rounded-2xl px-3 py-2 text-xs font-medium",
                message.deliveryStatus === "waiting" && "bg-amber-500/10 text-amber-800 dark:text-amber-200",
                message.deliveryStatus === "sending" && "bg-primary/10 text-primary",
                message.deliveryStatus === "auth_required" && "bg-destructive/10 text-destructive",
                message.deliveryStatus === "failed" && "bg-destructive/10 text-destructive",
              )}
            >
              {message.deliveryStatus === "waiting" && t("chat.delivery.waiting")}
              {message.deliveryStatus === "sending" && t("chat.delivery.sending")}
              {message.deliveryStatus === "auth_required" && t("chat.delivery.auth")}
              {message.deliveryStatus === "failed" && t("chat.delivery.failed")}
            </p>
          )}
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
        <div className="mt-2 flex flex-wrap items-center gap-1">
          {!message.deliveryStatus && (
            <IconAction label={t("chat.copy")} onClick={copy} icon={Copy} />
          )}
          {onSpeak && !message.deliveryStatus && (
            <IconAction
              label={isSpeaking ? t("chat.stopSpeak") : t("chat.speak")}
              onClick={onSpeak}
              icon={isSpeaking ? VolumeX : Volume2}
            />
          )}
          {onRegenerate && !message.deliveryStatus && (
            <IconAction label={t("chat.regenerate")} onClick={onRegenerate} icon={RefreshCw} />
          )}
          {onFeedback && !message.deliveryStatus && (
            <>
              <IconAction
                label={t("chat.good")}
                onClick={() => onFeedback("up")}
                icon={ThumbsUp}
                active={message.feedback === "up"}
              />
              <IconAction
                label={t("chat.bad")}
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
    <div className="grid min-w-0 gap-3 text-sm leading-relaxed break-words text-foreground">
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
                  <span className="min-w-0">{inline(l.replace(/^\s*[•\-*]\s+/, ""))}</span>
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
                  <span className="min-w-0">{inline(l.replace(/^\s*\d+\.\s+/, ""))}</span>
                </li>
              ))}
            </ol>
          );
        }

        return <p key={i} className="min-w-0">{inline(block)}</p>;
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
