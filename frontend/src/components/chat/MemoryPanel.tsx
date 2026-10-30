import { useEffect, useState } from "react";
import { Brain } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { getAuthUser } from "@/lib/authSession";
import { clearProfileMemory, loadProfileMemory } from "@/lib/conversationMemory";
import {
  clearOfflinePack,
  ensureOfflinePackSynced,
  getOfflinePackMeta,
} from "@/lib/offlinePack";

interface MemoryPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MemoryPanel({ open, onOpenChange }: MemoryPanelProps) {
  const user = getAuthUser();
  const { t } = useI18n();
  const [memory, setMemory] = useState("");
  const [packMeta, setPackMeta] = useState(() => getOfflinePackMeta());
  const [packBusy, setPackBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMemory(loadProfileMemory(user?.farmer_id));
    setPackMeta(getOfflinePackMeta());
    setPackBusy(true);
    void ensureOfflinePackSynced()
      .then(() => setPackMeta(getOfflinePackMeta()))
      .finally(() => setPackBusy(false));
  }, [open, user?.farmer_id]);

  const clearMemory = () => {
    clearProfileMemory(user?.farmer_id);
    setMemory("");
    toast.success(t("settings.memoryCleared"));
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="flex w-full max-w-full flex-col gap-0 overflow-hidden border-l border-border/80 bg-background p-0 sm:max-w-md"
      >
        <div className="shrink-0 border-b border-border/70 bg-gradient-to-br from-accent/80 via-card to-card px-6 pt-6 pr-14 pb-5">
          <SheetHeader className="space-y-3 text-left">
            <span className="grid size-11 place-items-center rounded-2xl bg-gradient-leaf shadow-soft">
              <Brain className="size-5 text-primary-foreground" aria-hidden="true" />
            </span>
            <div>
              <SheetTitle className="font-display text-2xl">{t("settings.memoryTitle")}</SheetTitle>
              <SheetDescription className="mt-1.5 text-sm leading-relaxed">
                {t("settings.memoryBody")}
              </SheetDescription>
            </div>
          </SheetHeader>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="grid gap-5">
            <div className="grid gap-2 rounded-2xl border border-border/70 bg-card p-3.5">
              <div>
                <p className="text-sm font-semibold text-foreground">{t("settings.memoryTitle")}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {t("settings.memoryBody")}
                </p>
              </div>
              <div
                className="min-h-24 w-full rounded-xl border border-border/80 bg-muted/20 px-3 py-2.5 text-sm whitespace-pre-wrap text-foreground"
                aria-live="polite"
              >
                {memory.trim() ? (
                  memory
                ) : (
                  <span className="text-muted-foreground">{t("settings.memoryEmpty")}</span>
                )}
              </div>
              <Button
                type="button"
                variant="ghost"
                className="w-fit rounded-xl text-muted-foreground"
                onClick={clearMemory}
                disabled={!memory.trim()}
              >
                {t("settings.memoryClear")}
              </Button>
            </div>

            <div className="grid gap-2 rounded-2xl border border-border/70 bg-card p-3.5">
              <div>
                <p className="text-sm font-semibold text-foreground">{t("settings.packTitle")}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {t("settings.packBody")}
                </p>
                {packBusy ? (
                  <p className="mt-2 text-xs text-muted-foreground">{t("settings.packSyncing")}</p>
                ) : packMeta ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {t("settings.packStatus", {
                      version: packMeta.version,
                      count: packMeta.entryCount,
                    })}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">
                    {t("settings.packMissing")}
                  </p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                {!packMeta && (
                  <Button
                    type="button"
                    className="rounded-xl"
                    disabled={packBusy}
                    onClick={() => {
                      void (async () => {
                        setPackBusy(true);
                        try {
                          await ensureOfflinePackSynced();
                          setPackMeta(getOfflinePackMeta());
                          if (getOfflinePackMeta()) {
                            toast.success(t("settings.packDownloaded"));
                          } else {
                            toast.error(t("settings.packFail"));
                          }
                        } catch (error) {
                          toast.error(error instanceof Error ? error.message : t("settings.packFail"));
                        } finally {
                          setPackBusy(false);
                        }
                      })();
                    }}
                  >
                    {packBusy ? t("settings.packDownloading") : t("settings.packRetry")}
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-xl text-muted-foreground"
                  disabled={!packMeta || packBusy}
                  onClick={() => {
                    void (async () => {
                      await clearOfflinePack();
                      setPackMeta(null);
                      toast.success(t("settings.packCleared"));
                    })();
                  }}
                >
                  {t("settings.packClear")}
                </Button>
              </div>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
