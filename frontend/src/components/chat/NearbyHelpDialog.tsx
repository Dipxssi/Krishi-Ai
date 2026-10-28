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

interface NearbyHelpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  language?: string;
  initialDistrict?: string;
}

export function NearbyHelpDialog({
  open,
  onOpenChange,
  language = "en",
  initialDistrict = "",
}: NearbyHelpDialogProps) {
  const [searchInput, setSearchInput] = useState(initialDistrict);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [data, setData] = useState<NearbyHelpResponse | null>(null);
  const [locationUsed, setLocationUsed] = useState(false);

  const isHindi = language === "hi";
  const isKannada = language === "kn";

  const dialogTitle = isHindi
    ? "सत्यापित कृषि सहायता केंद्र (KVK)"
    : isKannada
    ? "ದೃಢೀಕೃತ ಕೃಷಿ ಸಹಾಯ ಕೇಂದ್ರಗಳು (KVK)"
    : "Verified Agricultural Centers (KVK)";

  const dialogDesc = isHindi
    ? "अपने जिले या पिनकोड के अनुसार आधिकारिक आईसीएआर कृषि विज्ञान केंद्र और विशेषज्ञ खोजें।"
    : isKannada
    ? "ನಿಮ್ಮ ಜಿಲ್ಲೆ ಅಥವಾ ಪಿನ್‌ಕೋಡ್ ಆಧಾರದ ಮೇಲೆ ಅಧಿಕೃತ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ ಮತ್ತು ತಜ್ಞರನ್ನು ಹುಡುಕಿ."
    : "Locate verified ICAR Krishi Vigyan Kendras (KVKs) and official government agriculture extension offices.";

  const handleDeviceLocation = () => {
    if (!navigator.geolocation) {
      setErrorMsg(
        isHindi
          ? "आपके ब्राउज़र में लोकेशन की सुविधा उपलब्ध नहीं है। कृपया जिला दर्ज करें।"
          : isKannada
          ? "ನಿಮ್ಮ ಬ್ರೌಸರ್‌ನಲ್ಲಿ ಸ್ಥಳ ಹುಡುಕಾಟ ಲಭ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ಜಿಲ್ಲೆಯ ಹೆಸರನ್ನು ನಮೂದಿಸಿ."
          : "Geolocation is not supported by your browser. Please search by district or PIN code."
      );
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
          setErrorMsg(err instanceof Error ? err.message : "Failed to load nearby centers");
        } finally {
          setLoading(false);
        }
      },
      (_geoErr) => {
        setLoading(false);
        let msg = "Location permission denied. Please enter your district or PIN code below.";
        if (isHindi) {
          msg = "लोकेशन की अनुमति नहीं मिली। कृपया नीचे अपना जिला या पिन कोड दर्ज करें।";
        } else if (isKannada) {
          msg = "ಸ್ಥಳ ಅನುಮತಿ ನಿರಾಕರಿಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ಕೆಳಗೆ ನಿಮ್ಮ ಜಿಲ್ಲೆ ಅಥವಾ ಪಿನ್ ಕೋಡ್ ನಮೂದಿಸಿ.";
        }
        setErrorMsg(msg);
      },
      { timeout: 10000 }
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
      setErrorMsg(err instanceof Error ? err.message : "Failed to search centers");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto p-5 sm:p-6 rounded-2xl">
        <DialogHeader className="space-y-1 text-left">
          <div className="flex items-center gap-2">
            <div className="rounded-xl bg-emerald-600/10 p-2 text-emerald-600 dark:text-emerald-400">
              <Building2 className="size-5" />
            </div>
            <DialogTitle className="text-xl font-bold">{dialogTitle}</DialogTitle>
          </div>
          <DialogDescription className="text-xs sm:text-sm text-muted-foreground">
            {dialogDesc}
          </DialogDescription>
        </DialogHeader>

        <div className="mt-3 space-y-4">
          {/* Action Row: Location Button + Search Input */}
          <div className="flex flex-col gap-2.5 sm:flex-row">
            <Button
              type="button"
              variant="outline"
              onClick={handleDeviceLocation}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl border-emerald-600/30 bg-emerald-50/50 hover:bg-emerald-100/60 dark:bg-emerald-950/20 text-emerald-800 dark:text-emerald-300 font-medium text-xs sm:text-sm h-10 px-3.5"
            >
              <Navigation className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
              <span>
                {isHindi
                  ? "डिवाइस लोकेशन का उपयोग करें"
                  : isKannada
                  ? "ಪ್ರಸ್ತುತ ಸ್ಥಳ ಬಳಸಿ"
                  : "Use Device Location"}
              </span>
            </Button>

            <form onSubmit={handleSearch} className="flex-1 flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder={
                    isHindi
                      ? "जिला या 6-अंकीय पिन कोड दर्ज करें..."
                      : isKannada
                      ? "ಜಿಲ್ಲೆ ಅಥವಾ 6-ಅಂಕಿಯ ಪಿನ್ ಕೋಡ್..."
                      : "Enter district or 6-digit PIN code..."
                  }
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="pl-9 rounded-xl h-10 text-sm"
                />
              </div>
              <Button type="submit" disabled={loading || !searchInput.trim()} className="rounded-xl h-10 px-4">
                {loading ? <Loader2 className="size-4 animate-spin" /> : isHindi ? "खोजें" : isKannada ? "ಹುಡುಕಿ" : "Search"}
              </Button>
            </form>
          </div>

          {/* Feedback & Error */}
          {errorMsg && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/80 dark:border-amber-900/50 dark:bg-amber-950/30 p-3 text-xs sm:text-sm text-amber-900 dark:text-amber-200 flex items-start gap-2">
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Loading Indicator */}
          {loading && (
            <div className="py-8 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
              <Loader2 className="size-6 animate-spin text-emerald-600" />
              <span>
                {isHindi
                  ? "आधिकारिक कृषि केंद्रों की खोज जारी है..."
                  : isKannada
                  ? "ಅಧಿಕೃತ ಕೃಷಿ ಕೇಂದ್ರಗಳನ್ನು ಹುಡುಕಲಾಗುತ್ತಿದೆ..."
                  : "Searching verified ICAR agricultural centers..."}
              </span>
            </div>
          )}

          {/* Centers List */}
          {!loading && data && data.results && data.results.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                <span>
                  {data.results.length}{" "}
                  {isHindi
                    ? "सत्यापित केंद्र मिले"
                    : isKannada
                    ? "ದೃಢೀಕೃತ ಕೇಂದ್ರಗಳು"
                    : "Verified Centers Found"}
                </span>
                {locationUsed && (
                  <span className="text-emerald-700 dark:text-emerald-400 normal-case font-medium">
                    Sorted by distance
                  </span>
                )}
              </div>

              {data.results.map((center) => (
                <CenterCard key={center.id} center={center} language={language} />
              ))}
            </div>
          )}

          {/* Fallback & Toll-free advisory when no exact results or before search */}
          {!loading && data && data.results && data.results.length === 0 && (
            <div className="rounded-2xl border border-border/80 bg-muted/40 p-4 space-y-3">
              <p className="text-sm text-foreground/90">
                {data.fallback_notice ||
                  (isHindi
                    ? "आपके क्षेत्र के लिए कोई स्थानीय केवीके सीधे सूचीबद्ध नहीं मिला। आप राष्ट्रीय किसान कॉल सेंटर से निःशुल्क संपर्क कर सकते हैं।"
                    : isKannada
                    ? "ನೀವು ನಮೂದಿಸಿದ ಸ್ಥಳಕ್ಕೆ ನಿಖರ ಕೆವಿಕೆ ದೊರೆಯಲಿಲ್ಲ. ರಾಷ್ಟ್ರೀಯ ಕಿಸಾನ್ ಕಾಲ್ ಸೆಂಟರ್ ಸಂಪರ್ಕಿಸಿ."
                    : "No verified local Krishi Vigyan Kendra was found for the exact location provided.")}
              </p>

              <div className="rounded-xl border border-emerald-600/20 bg-emerald-500/10 p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="text-xs font-semibold uppercase tracking-wider text-emerald-800 dark:text-emerald-300">
                    {isHindi
                      ? "राष्ट्रीय किसान कॉल सेंटर (टोल-फ्री)"
                      : isKannada
                      ? "ರಾಷ್ಟ್ರೀಯ ಕಿಸಾನ್ ಕಾಲ್ ಸೆಂಟರ್ (ಟೋಲ್-ಫ್ರೀ)"
                      : "National Kisan Call Centre (Toll-Free)"}
                  </div>
                  <div className="text-lg font-bold text-foreground">1800-180-1551</div>
                  <div className="text-xs text-muted-foreground">
                    {isHindi
                      ? "सभी भारतीय भाषाओं में सुबह 6:00 से रात 10:00 बजे तक मुफ्त सेवा"
                      : isKannada
                      ? "ಎಲ್ಲಾ ಭಾರತೀಯ ಭಾಷೆಗಳಲ್ಲಿ ಬೆಳಿಗ್ಗೆ 6 ರಿಂದ ರಾತ್ರಿ 10 ರವರೆಗೆ ಉಚಿತ ಸೇವೆ"
                      : "Toll-free advisory in local languages from 6:00 AM to 10:00 PM"}
                  </div>
                </div>

                <a
                  href="tel:18001801551"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2 text-xs sm:text-sm font-semibold text-white hover:bg-emerald-700 transition-colors"
                >
                  <Phone className="size-3.5" />
                  <span>Call 1800-180-1551</span>
                </a>
              </div>

              <div className="pt-1 text-xs text-muted-foreground flex items-center justify-between">
                <span>Official ICAR Portal Directory:</span>
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

          {/* Initial state notice when dialog is opened and no search performed yet */}
          {!loading && !data && (
            <div className="rounded-2xl border border-dashed border-border/80 bg-muted/20 p-5 text-center space-y-3">
              <MapPin className="size-8 mx-auto text-muted-foreground/60" />
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">
                  {isHindi
                    ? "कृषि विज्ञान केंद्र (KVK) सीधे भारत सरकार और कृषि विश्वविद्यालयों द्वारा संचालित होते हैं।"
                    : isKannada
                    ? "ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರಗಳು (ಕೆ.ವಿ.ಕೆ) ಕೃಷಿ ವಿಶ್ವವಿದ್ಯಾಲಯಗಳು ಮತ್ತು ಐಸಿಎಆರ್ ಅಡಿಯಲ್ಲಿ ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತವೆ."
                    : "Krishi Vigyan Kendras (KVKs) are official agricultural extension centers operated under ICAR and state agricultural universities."}
                </p>
                <p className="text-xs text-muted-foreground">
                  {isHindi
                    ? "फसल में गंभीर बीमारी, अज्ञात कीट या कीटनाशक खुराक की सटीक पुष्टि के लिए अपने जिले के केंद्र से संपर्क करें।"
                    : isKannada
                    ? "ಬೆಳೆಯ ಗಂಭೀರ ರೋಗ ಅಥವಾ ಕೀಟನಾಶಕ ಪ್ರಮಾಣದ ನಿಖರ ಸಲಹೆಗಾಗಿ ನಿಮ್ಮ ಜಿಲ್ಲಾ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ."
                    : "Use your device location or enter your district above to view the verified office address, helpline, and agronomists."}
                </p>
              </div>

              <div className="pt-2 flex flex-wrap items-center justify-center gap-4 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-400 font-medium">
                  <ShieldCheck className="size-3.5" /> Verified ICAR Records
                </span>
                <span>•</span>
                <span className="inline-flex items-center gap-1">
                  <Phone className="size-3.5" /> Toll-Free 1800-180-1551
                </span>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function CenterCard({ center, language }: { center: NearbyHelpItem; language: string }) {
  const isHindi = language === "hi";
  const isKannada = language === "kn";

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
              Verified ICAR
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
              Helpline: <strong className="text-foreground">{center.helpline}</strong>
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
              <span>{isHindi ? "पोर्टल" : isKannada ? "ವೆಬ್‌ಸೈಟ್" : "Official Portal"}</span>
              <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
