import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { AdviceResult } from "@/components/chat/AdviceResult";
import type { QueryResponse } from "@/api";

interface AdviceDetailsPanelProps {
  result: QueryResponse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AdviceDetailsPanel({ result, open, onOpenChange }: AdviceDetailsPanelProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 overflow-hidden border-l border-border/80 bg-background p-0 sm:max-w-lg"
      >
        <div className="shrink-0 border-b border-border/70 bg-gradient-to-br from-accent/80 via-card to-card px-6 pt-6 pr-14 pb-5">
          <SheetHeader className="space-y-2 text-left">
            <SheetTitle className="font-display text-2xl">Advice details</SheetTitle>
            <SheetDescription className="text-sm leading-relaxed">
              Confidence, decision scores, and the full recommendation for this reply.
            </SheetDescription>
          </SheetHeader>
          {result?.request_id && (
            <p className="mt-3 font-mono text-[11px] text-muted-foreground">
              Request {result.request_id}
            </p>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {result ? <AdviceResult result={result} /> : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
