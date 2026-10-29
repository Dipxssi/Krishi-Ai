import { useState } from "react";
import {
  ExternalLink,
  Loader2,
  MapPin,
  Navigation,
  Phone,
  Search,
  ShieldCheck,
  Building2,
  AlertCircle,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  fetchNearbyAgriculturalHelp,
  type NearbyHelpItem,
  type NearbyHelpResponse,
} from "@/api";
import { useI18n } from "@/hooks/useI18n";

interface NearbyHelpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  language?: string;
  initialDistrict?: string;
}

export function NearbyHelpDialog({
  open,
  onOpenChange,
  initialDistrict = "",
}: NearbyHelpDialogProps) {
  const { t } = useI18n();
  const [searchInput, setSearchInput] = useState(initialDistrict);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [data, setData] = useState<NearbyHelpResponse | null>(null);
  const [locationUsed, setLocationUsed] = useState(false);

  const handleDeviceLocation = () => {
    if (!navigator.geolocation) {
      setErrorMsg(t("nearby.noGeo"));
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          const res = await fetchNearbyAgriculturalHelp({ lat, lon, limit: 5 });
          setData(res);
          setLocationUsed(true);
        } catch (err: unknown) {
          setErrorMsg(err instanceof Error ? err.message : t("nearby.loadFail"));
        } finally {
          setLoading(false);
        }
      },
      () => {
        setLoading(false);
        setErrorMsg(t("nearby.permDenied"));
      },
      { timeout: 10000 },
    );
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const queryStr = searchInput.trim();
    if (!queryStr) return;

    setLoading(true);
    setErrorMsg(null);
    setLocationUsed(false);

    try {
      const isPin = /^\d{6}$/.test(queryStr);
      const res = await fetchNearbyAgriculturalHelp({
        district: isPin ? undefined : queryStr,
        pincode: isPin ? queryStr : undefined,
        query: queryStr,
        limit: 5,
      });
      setData(res);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : t("nearby.searchFail"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100vw-1.5rem)] max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl p-4 sm:w-full sm:p-6">
        <DialogHeader className="space-y-1 text-left">
          <div className="flex items-center gap-2">
            <div className="rounded-xl bg-emerald-600/10 p-2 text-emerald-600 dark:text-emerald-400">
              <Building2 className="size-5" />
            </div>
            <DialogTitle className="text-xl font-bold">{t("nearby.title")}</DialogTitle>
          </div>
          <DialogDescription className="text-xs sm:text-sm text-muted-foreground">
            {t("nearby.desc")}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-3 space-y-4">
          <div className="flex flex-col gap-2.5 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              onClick={handleDeviceLocation}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl border-emerald-600/30 bg-emerald-50/50 hover:bg-emerald-100/60 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-300 font-medium text-xs sm:text-sm h-10 px-3.5"
            >
              <Navigation className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <span>{t("nearby.useLocation")}</span>
            </Button>

            <form onSubmit={handleSearch} className="flex-1 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder={t("nearby.placeholder")}
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="pl-9 rounded-xl h-10 text-sm"
                />
              </div>
              <Button type="submit" disabled={loading || !searchInput.trim()} className="rounded-xl h-10 px-4">
                {loading ? <Loader2 className="size-4 animate-spin" /> : t("nearby.search")}
              </Button>
            </form>
          </div>

          {errorMsg && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/30 p-3 text-xs sm:text-sm text-amber-900 dark:text-amber-200 flex items-start gap-2">
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {loading && (
            <div className="py-8 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
              <Loader2 className="size-6 animate-spin text-emerald-600" />
              <span>{t("nearby.searching")}</span>
            </div>
          )}

          {!loading && data && data.results && data.results.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <span>
                  {data.results.length} {t("nearby.found")}
                </span>
                {locationUsed && (
                  <span className="text-emerald-700 dark:text-emerald-400 normal-case font-medium">
                    {t("nearby.sorted")}
                  </span>
                )}
              </div>

              {data.results.map((center) => (
                <CenterCard key={center.id} center={center} />
              ))}
            </div>
          )}

          {!loading && data && data.results && data.results.length === 0 && (
            <div className="rounded-2xl border border-border/80 bg-muted/40 p-4 space-y-3">
              <p className="text-sm text-foreground/90">
                {data.fallback_notice || t("nearby.empty")}
              </p>

              <div className="rounded-xl border border-emerald-600/20 bg-emerald-500/10 p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="text-xs font-semibold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
                    {t("nearby.kcc")}
                  </div>
                  <div className="text-lg font-bold text-foreground">1800-180-1551</div>
                  <div className="text-xs text-muted-foreground">{t("nearby.kccHours")}</div>
                </div>

                <a
                  href="tel:18001801551"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-emerald-700 transition-colors"
                >
                  <Phone className="size-3.5" />
                  <span>{t("nearby.call")}</span>
                </a>
              </div>

              <div className="pt-1 text-xs text-muted-foreground flex items-center justify-between">
                <span>{t("nearby.portalDir")}</span>
                <a
                  href="https://kvk.icar.gov.in"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
                >
                  kvk.icar.gov.in
                  <ExternalLink className="size-3" />
                </a>
              </div>
            </div>
          )}

          {!loading && !data && (
            <div className="rounded-2xl border border-dashed border-border/80 bg-muted/20 p-5 text-center space-y-3">
              <MapPin className="size-8 mx-auto text-muted-foreground/60" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">{t("nearby.intro")}</p>
                <p className="text-xs text-muted-foreground">{t("nearby.introHint")}</p>
              </div>

              <div className="pt-2 flex flex-wrap items-center justify-center gap-4 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-medium">
                  <ShieldCheck className="size-3.5" /> {t("nearby.verifiedBadge")}
                </span>
                <span>•</span>
                <span className="inline-flex items-center gap-1">
                  <Phone className="size-3.5" /> {t("nearby.tollFree")}
                </span>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CenterCard({ center }: { center: NearbyHelpItem }) {
  const { t } = useI18n();

  return (
    <div className="rounded-2xl border border-border/80 bg-card p-4 space-y-2.5 transition-all hover:border-emerald-600/40 hover:shadow-soft">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 flex-wrap">
            <h4 className="font-semibold text-sm sm:text-base text-foreground leading-snug">
              {center.name}
            </h4>
            <Badge
              variant="outline"
              className="border-emerald-600/30 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-800 dark:text-emerald-300 text-[10px] py-0 px-2 font-medium"
            >
              <ShieldCheck className="size-3 mr-1" />
              {t("nearby.verifiedIcar")}
            </Badge>
          </div>
          {center.host_institution && (
            <p className="text-xs text-muted-foreground mt-0.5">{center.host_institution}</p>
          )}
        </div>

        {center.distance_km != null && (
          <span className="shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full bg-emerald-600/10 text-emerald-800 dark:text-emerald-300">
            {center.distance_km.toFixed(1)} km
          </span>
        )}
      </div>

      <div className="text-xs text-muted-foreground flex items-start gap-1.5">
        <MapPin className="size-3.5 shrink-0 mt-0.5 text-muted-foreground/80" />
        <span className="leading-relaxed">{center.address}</span>
      </div>

      <div className="pt-1 border-t border-border/50 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-3">
          {center.phone && (
            <a
              href={`tel:${center.phone}`}
              className="inline-flex items-center gap-1 font-medium text-foreground hover:text-primary transition-colors"
            >
              <Phone className="size-3 text-emerald-600" />
              <span>{center.phone}</span>
            </a>
          )}
          {center.helpline && (
            <span className="text-muted-foreground hidden sm:inline">
              {t("nearby.helpline")} <strong className="text-foreground">{center.helpline}</strong>
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {center.website && (
            <a
              href={center.website}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-primary hover:underline font-medium"
            >
              <span>{t("nearby.portal")}</span>
              <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
