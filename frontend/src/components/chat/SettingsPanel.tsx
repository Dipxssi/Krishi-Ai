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

interface SettingsPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onClearAll: () => void;
}

export function SettingsPanel({ open, onOpenChange, onClearAll }: SettingsPanelProps) {
  const user = getAuthUser();
  const { t } = useI18n();

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
