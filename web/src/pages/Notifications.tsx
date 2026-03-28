import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  testTelegram, saveNotificationSettings, setTelegramId, getTelegramId,
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
  const [chatId, setChatId] = useState(getTelegramId() || "");
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

  const testMutation = useMutation({
    mutationFn: () => testTelegram(Number(chatId), language),
    onSuccess: () => {
      setTelegramId(Number(chatId));
      showToast("Test message sent! Check your Telegram.");
    },
    onError: (e: Error) => showToast(`Failed: ${e.message}`, false),
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      saveNotificationSettings({
        telegram_id: Number(chatId) || getTelegramId(),
        language,
        severity_threshold: threshold,
        sources,
      }),
    onSuccess: () => {
      localStorage.setItem("language", language);
      localStorage.setItem("severity_threshold", threshold);
      localStorage.setItem("sources", sources);
      if (chatId) setTelegramId(Number(chatId));
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

      {/* Telegram setup */}
      <section className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h2 className="font-semibold text-gray-800 mb-1 flex items-center gap-2">
          <span aria-hidden="true">✈️</span> Telegram Alerts
        </h2>
        <p className="text-xs text-gray-500 mb-3">
          Connect your Telegram account to receive instant recall alerts.{" "}
          <a
            href="https://t.me/RecallAlertBot"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary font-medium hover:underline"
          >
            Open @RecallAlertBot →
          </a>
        </p>

        <label className="block text-xs text-gray-600 mb-1" htmlFor="chat-id">
          Your Telegram Chat ID
        </label>
        <div className="flex gap-2">
          <input
            id="chat-id"
            type="number"
            placeholder="e.g. 123456789"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button
            onClick={() => testMutation.mutate()}
            disabled={!chatId || testMutation.isPending}
            className="bg-primary text-white text-sm font-medium px-4 rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-60"
          >
            {testMutation.isPending ? "…" : "Test"}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1.5">
          To get your Chat ID: message @userinfobot on Telegram.
        </p>
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
