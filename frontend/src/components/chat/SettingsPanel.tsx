import { useEffect, useState } from "react";
import { MapPinned } from "lucide-react";
import { toast } from "sonner";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { FarmProfileForm } from "@/components/FarmProfileForm";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { useI18n } from "@/hooks/useI18n";
import { getAuthUser } from "@/lib/authSession";
import {
  clearProfileMemory,
  loadProfileMemory,
  saveProfileMemory,
} from "@/lib/conversationMemory";
import {
  clearOfflinePack,
  downloadOfflinePack,
  getOfflinePackMeta,
} from "@/lib/offlinePack";
import { probeApiReachable } from "@/lib/apiReachability";

interface SettingsPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClearAll: () => void;
}

export function SettingsPanel({ open, onOpenChange, onClearAll }: SettingsPanelProps) {
  const user = getAuthUser();
  const { t } = useI18n();
  const [memory, setMemory] = useState("");
  const [packMeta, setPackMeta] = useState(() => getOfflinePackMeta());
  const [packBusy, setPackBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setMemory(loadProfileMemory(user?.farmer_id));
    setPackMeta(getOfflinePackMeta());
  }, [open, user?.farmer_id]);

  const saveMemory = () => {
    saveProfileMemory(memory, user?.farmer_id);
    toast.success(t("settings.memorySaved"));
  };

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
              <MapPinned className="size-5 text-primary-foreground" aria-hidden="true" />
            </span>
            <div>
              <SheetTitle className="font-display text-2xl">{t("settings.title")}</SheetTitle>
              <SheetDescription className="mt-1.5 text-sm leading-relaxed">
                {t("settings.body")}
              </SheetDescription>
            </div>
          </SheetHeader>
          {user && (
            <p className="mt-4 rounded-2xl border border-border/60 bg-card/80 px-3.5 py-2.5 text-xs text-muted-foreground">
              {t("settings.signedIn")}{" "}
              <span className="font-semibold text-foreground">{user.name}</span>
              <span className="mx-1.5 text-border">·</span>
              {user.email}
            </p>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="grid gap-5">
            <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/70 bg-muted/30 px-3.5 py-3">
              <p className="text-sm font-medium text-foreground">{t("settings.language")}</p>
              <LanguageSwitcher />
            </div>

            <div className="grid gap-2 rounded-2xl border border-border/70 bg-card p-3.5">
              <div>
                <p className="text-sm font-semibold text-foreground">{t("settings.packTitle")}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {t("settings.packBody")}
                </p>
                {packMeta ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {t("settings.packStatus", {
                      version: packMeta.version,
                      count: packMeta.entryCount,
                    })}
                  </p>
                ) : (
                  <p className="mt-2 text-xs text-amber-800 dark:text-amber-200">{t("settings.packMissing")}</p>
                )}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  className="rounded-xl"
                  disabled={packBusy}
                  onClick={() => {
                    void (async () => {
                      setPackBusy(true);
                      try {
                        const online = await probeApiReachable();
                        if (!online && !(await fetch("/offline-pack/v1.json", { method: "HEAD" }).then((r) => r.ok).catch(() => false))) {
                          // Still try app-origin static file (works on Vercel even if API is down).
                        }
                        await downloadOfflinePack();
                        setPackMeta(getOfflinePackMeta());
                        toast.success(t("settings.packDownloaded"));
                      } catch (error) {
                        toast.error(error instanceof Error ? error.message : t("settings.packFail"));
                      } finally {
                        setPackBusy(false);
                      }
                    })();
                  }}
                >
                  {packBusy ? t("settings.packDownloading") : t("settings.packDownload")}
                </Button>
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

            <div className="grid gap-2 rounded-2xl border border-border/70 bg-card p-3.5">
              <div>
                <p className="text-sm font-semibold text-foreground">{t("settings.memoryTitle")}</p>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                  {t("settings.memoryBody")}
                </p>
              </div>
              <textarea
                value={memory}
                onChange={(e) => setMemory(e.target.value)}
                rows={5}
                placeholder={t("settings.memoryPh")}
                className="min-h-24 w-full resize-y rounded-xl border border-border/80 bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              <div className="flex flex-wrap gap-2">
                <Button type="button" className="rounded-xl" onClick={saveMemory}>
                  {t("settings.memorySave")}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="rounded-xl text-muted-foreground"
                  onClick={clearMemory}
                  disabled={!memory.trim()}
                >
                  {t("settings.memoryClear")}
                </Button>
              </div>
            </div>

            {open && (
              <FarmProfileForm
                submitLabel={t("settings.save")}
                onSaved={() => onOpenChange(false)}
              />
            )}

            <div className="border-t border-border/70 pt-2">
              <Button
                variant="ghost"
                className="w-full rounded-xl text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => {
                  onClearAll();
                  onOpenChange(false);
                  toast.success(t("settings.deletedAll"));
                }}
              >
                {t("settings.deleteAll")}
              </Button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
