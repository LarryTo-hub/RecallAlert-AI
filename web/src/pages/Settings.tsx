import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { triggerFetch, fetchStats } from "@/api/client";
import { useQuery } from "@tanstack/react-query";

const INTERVALS = [
  { value: "15", label: "Every 15 minutes" },
  { value: "30", label: "Every 30 minutes" },
  { value: "60", label: "Every hour" },
  { value: "120", label: "Every 2 hours" },
];

export default function Settings() {
  const qc = useQueryClient();
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

  const fetchMutation = useMutation({
    mutationFn: triggerFetch,
    onSuccess: ({ count }) => {
      qc.invalidateQueries({ queryKey: ["recalls"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      if (typeof count === "number") {
        showToast(`Fetched ${count} recalls successfully`);
      } else {
        showToast("Fetch triggered successfully");
      }
    },
    onError: (e: Error) => showToast(`Fetch failed: ${e.message}`, false),
  });

  return (
    <div className="max-w-lg mx-auto px-4 py-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg
          ${toast.ok ? "bg-emerald-600" : "bg-primary"}`}>
          {toast.msg}
        </div>
      )}

      <h1 className="text-xl font-bold text-white mb-5">Settings</h1>

      {/* Status card */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-3">
          System Status
        </h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-400">Recalls cached</span>
            <span className="font-medium text-white">{stats?.total_recalls ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Active recalls</span>
            <span className="font-medium text-red-400">{stats?.active_recalls ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Last updated</span>
            <span className="font-medium text-slate-300 text-xs">
              {stats?.cache_updated_at
                ? new Date(stats.cache_updated_at).toLocaleString()
                : "Never"}
            </span>
          </div>
          <div className="flex justify-between items-center pt-1 border-t border-navy-700 mt-2">
            <span className="text-slate-400">Gemini AI</span>
            <span className="text-xs font-medium text-emerald-400 bg-emerald-900/40 px-2 py-0.5 rounded-full">
              gemini-2.0-flash
            </span>
          </div>
        </div>
      </section>

      {/* Manual fetch */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-1">
          Manual Fetch
        </h2>
        <p className="text-xs text-slate-400 mb-3">
          Immediately fetch the latest FDA and USDA recalls and update the cache.
        </p>
        <button
          onClick={() => fetchMutation.mutate()}
          disabled={fetchMutation.isPending}
          className="w-full bg-primary text-white font-medium rounded-lg py-2.5 text-sm hover:bg-primary-dark transition-colors disabled:opacity-60"
        >
          {fetchMutation.isPending ? "Fetching…" : "Fetch Recalls Now"}
        </button>
      </section>

      {/* Polling interval */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-1">
          Polling Interval
        </h2>
        <p className="text-xs text-slate-400 mb-3">
          Set FETCH_INTERVAL_MINUTES in your .env / Render environment variables to change the server-side interval.
          This preference is saved locally.
        </p>
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

      {/* Database backend */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5 mb-4">
        <h2 className="font-semibold text-white mb-1">
          Storage Backend
        </h2>
        <p className="text-xs text-slate-400 mb-2">
          Configure via <code className="bg-navy-700 text-primary-light px-1 rounded">STORE_BACKEND</code> env var:
        </p>
        <div className="flex flex-col gap-2 text-sm">
          <div className="flex items-center gap-3 p-3 bg-navy-900 rounded-lg border border-navy-700">
            <div>
              <p className="font-medium text-white">SQLite (default)</p>
              <p className="text-xs text-slate-400">Set <code className="bg-navy-700 text-primary-light px-1 rounded">STORE_BACKEND=sqlite</code></p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-navy-900 rounded-lg border border-navy-700">
            <div>
              <p className="font-medium text-white">Firebase / Firestore</p>
              <p className="text-xs text-slate-400">Set <code className="bg-navy-700 text-primary-light px-1 rounded">STORE_BACKEND=firebase</code> + <code className="bg-navy-700 text-primary-light px-1 rounded">FIREBASE_CRED_PATH</code></p>
            </div>
          </div>
        </div>
      </section>

      {/* About */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-5">
        <h2 className="font-semibold text-white mb-3">
          About
        </h2>
        <div className="space-y-1 text-xs text-slate-400">
          <p>RecallAlert AI — version 1.0.0</p>
          <p>Powered by Google Gemini 2.0 Flash</p>
          <p>Data sources: FDA, USDA FSIS</p>
          <p className="pt-1 text-slate-500">
            Recall data is provided for informational purposes. Always check official FDA/USDA websites for authoritative recall information.
          </p>
        </div>
      </section>
    </div>
  );
}
