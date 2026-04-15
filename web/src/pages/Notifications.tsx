import { useState, useEffect } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  saveNotificationSettings,
  saveEmailSettings, getEmailSettings,
} from "@/api/client";

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
      showToast("Settings saved");
    },
    onError: (e: Error) => showToast(`Failed: ${e.message}`, false),
  });

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg
          ${toast.ok ? "bg-success" : "bg-primary"}`}>
          {toast.msg}
        </div>
      )}

      <h1 className="text-xl font-bold text-gray-900 mb-5">Notifications</h1>

      {/* Email setup */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="font-semibold text-gray-800 mb-1 flex items-center gap-2">
          <span aria-hidden="true">📧</span> Email Alerts
        </h2>
        <p className="text-xs text-gray-500 mb-3">
          Enter your email to receive food recall alerts when items in your pantry are affected.
        </p>

        <label className="block text-xs text-gray-600 mb-1" htmlFor="email">
          Your Email Address
        </label>
        <input
          id="email"
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
        />
      </section>

      {/* Email preference */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span aria-hidden="true">🔔</span> Email Preferences
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
              <span className="text-sm text-gray-700 font-medium">New recalls only</span>
              <p className="text-xs text-gray-400">Only email me when a brand new recall matches my pantry.</p>
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
              <span className="text-sm text-gray-700 font-medium">All pantry matches</span>
              <p className="text-xs text-gray-400">Email me for any recall, including existing ones, that matches my pantry.</p>
            </div>
          </label>
        </div>
      </section>

      {/* Language */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span aria-hidden="true">🌐</span> Alert Language
        </h2>
        <div className="grid grid-cols-3 gap-2">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => setLanguage(lang.code)}
              className={`py-2 px-3 rounded-lg text-sm font-medium border transition-colors
                ${language === lang.code
                  ? "bg-primary text-white border-primary"
                  : "bg-white text-gray-700 border-gray-200 hover:border-gray-300"}`}
              aria-pressed={language === lang.code}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </section>

      {/* Severity threshold */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span aria-hidden="true">⚠️</span> Severity Threshold
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
              <span className="text-sm text-gray-700">{t.label}</span>
            </label>
          ))}
        </div>
      </section>

      {/* Sources */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 mb-5">
        <h2 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <span aria-hidden="true">📡</span> Recall Sources
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
              <span className="text-sm text-gray-700">{s.label}</span>
            </label>
          ))}
        </div>
      </section>

      <button
        onClick={() => saveMutation.mutate()}
        disabled={saveMutation.isPending}
        className="w-full bg-primary text-white font-semibold rounded-xl py-3 hover:bg-primary-dark transition-colors disabled:opacity-60"
      >
        {saveMutation.isPending ? "Saving…" : "Save Settings"}
      </button>
    </div>
  );
}
