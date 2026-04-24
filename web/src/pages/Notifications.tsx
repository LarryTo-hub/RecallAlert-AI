import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  saveNotificationSettings,
  saveEmailSettings, getEmailSettings,
} from "@/api/client";
import { useTranslation } from "@/i18n/LanguageContext";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "vi", label: "Tiếng Việt" },
  { code: "zh", label: "中文" },
  { code: "ko", label: "한국어" },
  { code: "fr", label: "Français" },
];

const THRESHOLDS = [
  { value: "all", label: "All severities" },
  { value: "medium+", label: "Medium & High only" },
  { value: "high", label: "High only" },
];

const SOURCES = [
  { value: "both", label: "FDA + USDA" },
  { value: "fda", label: "FDA only" },
  { value: "usda", label: "USDA only" },
];

export default function Notifications() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [notifyNewOnly, setNotifyNewOnly] = useState(true);
  const [language, setLanguage] = useState(
    () => localStorage.getItem("language") ?? "en"
  );
  const [threshold, setThreshold] = useState(
    () => localStorage.getItem("severity_threshold") ?? "all"
  );
  const [sources, setSources] = useState(
    () => localStorage.getItem("sources") ?? "both"
  );
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const { data: emailData } = useQuery({
    queryKey: ["emailSettings"],
    queryFn: getEmailSettings,
  });

  useEffect(() => {
    if (emailData?.email) setEmail(emailData.email);
    if (emailData?.notify_new_only !== undefined) setNotifyNewOnly(emailData.notify_new_only);
  }, [emailData]);

  const saveMutation = useMutation({
    mutationFn: () =>
      Promise.all([
        saveEmailSettings({ email, notify_new_only: notifyNewOnly }),
        saveNotificationSettings({
          language,
          severity_threshold: threshold,
          sources,
        }),
      ]),
    onSuccess: () => {
      localStorage.setItem("language", language);
      localStorage.setItem("severity_threshold", threshold);
      localStorage.setItem("sources", sources);
      showToast(t("notif.saved"));
    },
    onError: (e: Error) => showToast(t("notif.saveFailed", { error: e.message }), false),
  });

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg
          ${toast.ok ? "bg-emerald-600" : "bg-primary"}`}>
          {toast.msg}
        </div>
      )}

      <h1 className="text-xl font-bold text-white mb-5">{t("notif.title")}</h1>

      {/* Email setup */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-1">
          {t("notif.emailAlerts")}
        </h2>
        <p className="text-xs text-slate-400 mb-3">
          {t("notif.emailHint")}
        </p>

        <label className="block text-xs text-slate-400 mb-1" htmlFor="email">
          {t("notif.emailAddress")}
        </label>
        <input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border border-navy-700 bg-navy-900 text-white placeholder-slate-500 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
      </section>

      {/* Email preference */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-3">
          {t("notif.emailPrefs")}
        </h2>
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="radio"
              name="notify_pref"
              checked={notifyNewOnly}
              onChange={() => setNotifyNewOnly(true)}
              className="accent-primary"
            />
            <div>
              <span className="text-sm text-white font-medium">{t("notif.newOnly")}</span>
              <p className="text-xs text-slate-400">{t("notif.newOnlyHint")}</p>
            </div>
          </label>
          <label className="flex items-center gap-2.5 cursor-pointer">
            <input
              type="radio"
              name="notify_pref"
              checked={!notifyNewOnly}
              onChange={() => setNotifyNewOnly(false)}
              className="accent-primary"
            />
            <div>
              <span className="text-sm text-white font-medium">{t("notif.allMatches")}</span>
              <p className="text-xs text-slate-400">{t("notif.allMatchesHint")}</p>
            </div>
          </label>
        </div>
      </section>

      {/* Language */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-3">
          {t("notif.alertLanguage")}
        </h2>
        <div className="grid grid-cols-3 gap-2">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => setLanguage(lang.code)}
              className={`py-2 px-3 rounded-lg text-sm font-medium border transition-colors
                ${language === lang.code
                  ? "bg-primary text-white border-primary"
                  : "bg-navy-900 text-slate-300 border-navy-700 hover:border-navy-600 hover:text-white"}`}
              aria-pressed={language === lang.code}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </section>

      {/* Severity threshold */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-3">
          {t("notif.severityThreshold")}
        </h2>
        <div className="flex flex-col gap-2">
          {THRESHOLDS.map((t) => (
            <label key={t.value} className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="radio"
                name="threshold"
                value={t.value}
                checked={threshold === t.value}
                onChange={() => setThreshold(t.value)}
                className="accent-primary"
              />
              <span className="text-sm text-slate-300">{t.label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* Sources */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-5">
        <h2 className="font-semibold text-white mb-3">
          {t("notif.recallSources")}
        </h2>
        <div className="flex flex-col gap-2">
          {SOURCES.map((s) => (
            <label key={s.value} className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="radio"
                name="sources"
                value={s.value}
                checked={sources === s.value}
                onChange={() => setSources(s.value)}
                className="accent-primary"
              />
              <span className="text-sm text-slate-300">{s.label}</span>
            </label>
          ))}
        </div>
      </section>

      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
        className="w-full bg-primary text-white font-semibold rounded-xl py-3 hover:bg-primary-dark transition-colors disabled:opacity-60"
      >
        {saveMutation.isPending ? t("notif.saving") : t("notif.save")}
      </button>
    </div>
  );
}
