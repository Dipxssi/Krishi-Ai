interface SuggestedPromptProps {
  emoji: string;
  text: string;
  onSelect: (text: string) => void;
}

export function SuggestedPrompt({ emoji, text, onSelect }: SuggestedPromptProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(text)}
      className="group flex w-full items-center gap-3 rounded-2xl border border-border bg-card p-4 text-left shadow-soft transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lift focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <span aria-hidden="true" className="grid size-9 place-items-center rounded-xl bg-secondary">
        {emoji}
      </span>
      <span className="text-sm font-medium text-foreground">{text}</span>
    </button>
  );
}
