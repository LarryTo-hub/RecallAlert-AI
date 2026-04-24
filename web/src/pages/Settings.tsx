import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerFetch, fetchStats } from "@/api/client";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "@/i18n/LanguageContext";
import { LANGUAGES } from "@/i18n/translations";

export default function Settings() {
  const qc = useQueryClient();
  const { t, lang, setLang } = useTranslation();
  const [interval, setInterval] = useState(
    () => localStorage.getItem("fetch_interval") ?? "60"
  );
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  };

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  const INTERVALS = [
    { value: "15", label: t("settings.every15") },
    { value: "30", label: t("settings.every30") },
    { value: "60", label: t("settings.everyHour") },
    { value: "120", label: t("settings.every2h") },
  ];

  const fetchMutation = useMutation({
    mutationFn: triggerFetch,
    onSuccess: ({ count }) => {
      qc.invalidateQueries({ queryKey: ["recalls"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (typeof count === "number") {
        showToast(t("settings.fetchSuccess", { n: count }));
      } else {
        showToast(t("settings.fetchTriggered"));
      }
    },
    onError: (e: Error) => showToast(t("settings.fetchFailed", { error: e.message }), false),
  });

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg
          ${toast.ok ? "bg-emerald-600" : "bg-primary"}`}>
          {toast.msg}
        </div>
      )}

      <h1 className="text-xl font-bold text-white mb-5">{t("settings.title")}</h1>

      {/* Status card */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-3">{t("settings.systemStatus")}</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">{t("settings.recallsCached")}</span>
            <span className="font-medium text-white">{stats?.total_recalls ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">{t("settings.activeRecalls")}</span>
            <span className="font-medium text-red-400">{stats?.active_recalls ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">{t("settings.lastUpdated")}</span>
            <span className="font-medium text-slate-300 text-xs">
              {stats?.cache_updated_at
                ? new Date(stats.cache_updated_at).toLocaleString()
                : t("settings.never")}
            </span>
          </div>
          <div className="flex justify-between items-center pt-1 border-t border-navy-700 mt-2">
            <span className="text-slate-400">{t("settings.geminiAi")}</span>
            <span className="text-xs font-medium text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded-full">
              gemini-2.0-flash
            </span>
          </div>
        </div>
      </section>

      {/* Manual fetch */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-1">{t("settings.manualFetch")}</h2>
        <p className="text-xs text-slate-400 mb-3">{t("settings.fetchHint")}</p>
        <button
          onClick={() => fetchMutation.mutate()}
          disabled={fetchMutation.isPending}
          className="w-full bg-primary text-white font-medium rounded-lg py-2.5 text-sm hover:bg-primary-dark transition-colors disabled:opacity-60"
        >
          {fetchMutation.isPending ? t("settings.fetching") : t("settings.fetchNow")}
        </button>
      </section>

      {/* Polling interval */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-1">{t("settings.pollingInterval")}</h2>
        <p className="text-xs text-slate-400 mb-3">{t("settings.pollingHint")}</p>
        <div className="flex flex-col gap-2">
          {INTERVALS.map((i) => (
            <label key={i.value} className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="radio"
                name="interval"
                value={i.value}
                checked={interval === i.value}
                onChange={() => {
                  setInterval(i.value);
                  localStorage.setItem("fetch_interval", i.value);
                }}
                className="accent-primary"
              />
              <span className="text-sm text-slate-300">{i.label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* App Language */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-3">{t("settings.appLanguage")}</h2>
        <div className="grid grid-cols-3 gap-2">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              onClick={() => setLang(l.code)}
              className={`py-2 px-3 rounded-lg text-sm font-medium border transition-colors
                ${lang === l.code
                  ? "bg-primary text-white border-primary"
                  : "bg-navy-900 text-slate-300 border-navy-700 hover:border-navy-600 hover:text-white"}`}
              aria-pressed={lang === l.code}
            >
              {l.label}
            </button>
          ))}
        </div>
      </section>

      {/* About */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5">
        <h2 className="font-semibold text-white mb-3">{t("settings.about")}</h2>
        <div className="space-y-1 text-xs text-slate-400">
          <p>{t("settings.aboutVersion")}</p>
          <p>{t("settings.aboutPowered")}</p>
          <p>{t("settings.aboutSources")}</p>
          <p className="pt-1 text-slate-500">{t("settings.aboutDisclaimer")}</p>
        </div>
      </section>
    </div>
  );
}
