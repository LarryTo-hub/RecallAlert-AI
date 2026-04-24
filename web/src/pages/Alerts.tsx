import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAlerts, updateAlertFeedback, fetchStats, type AlertRecord } from "@/api/client";
import { SkeletonRow } from "@/components/Skeleton";
import { useTranslation } from "@/i18n/LanguageContext";

const FILTERS = ["all", "sent", "disposed", "ignored"] as const;
type Filter = typeof FILTERS[number];

const statusStyle: Record<string, string> = {
  sent: "bg-primary/20 text-primary-light border border-primary/30",
  disposed: "bg-emerald-900/40 text-emerald-400 border border-emerald-700/40",
  ignored: "bg-navy-700 text-slate-500",
};

function AlertRow({ alert }: { alert: AlertRecord }) {
  const qc = useQueryClient();
  const { t } = useTranslation();

  const mutation = useMutation({
    mutationFn: ({ status }: { status: "disposed" | "ignored" }) =>
      updateAlertFeedback(alert.id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alerts"] });
      qc.invalidateQueries({ queryKey: ["pantry"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  return (
    <div className="bg-navy-800 rounded-xl border border-navy-700 p-4">
      {/* Status + date row */}
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusStyle[alert.status] ?? "bg-navy-700 text-slate-500"}`}>
          {alert.status.toUpperCase()}
        </span>
        <span className="text-xs text-slate-500">
          {new Date(alert.created_at).toLocaleString()}
        </span>
      </div>

      {/* Message preview */}
      <p className="text-sm text-slate-300 line-clamp-3 whitespace-pre-line mb-3">{alert.message}</p>

      {/* Recall number */}
      {alert.recall_number && (
        <p className="text-xs text-slate-500 mb-3">Recall #{alert.recall_number}</p>
      )}

      {/* Feedback buttons — only show if still "sent" */}
      {alert.status === "sent" && (
        <div className="flex gap-2">
          <button
            onClick={() => mutation.mutate({ status: "disposed" })}
            disabled={mutation.isPending}
            className="flex-1 text-xs font-medium bg-emerald-900/40 text-emerald-400 border border-emerald-700/40 rounded-lg py-2 hover:bg-emerald-900/60 transition-colors disabled:opacity-60"
          >
            {t("alerts.markDisposed")}
          </button>
          <button
            onClick={() => mutation.mutate({ status: "ignored" })}
            disabled={mutation.isPending}
            className="flex-1 text-xs font-medium bg-navy-700 text-slate-400 border border-navy-600 rounded-lg py-2 hover:bg-navy-600 hover:text-white transition-colors disabled:opacity-60"
          >
            {t("alerts.ignore")}
          </button>
        </div>
      )}
    </div>
  );
}

export default function Alerts() {
  const [filter, setFilter] = useState<Filter>("all");
  const { t } = useTranslation();

  const { data, isLoading } = useQuery({
    queryKey: ["alerts", filter],
    queryFn: () => fetchAlerts(filter === "all" ? undefined : filter),
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  const alerts = data?.alerts ?? [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-4">{t("alerts.title")}</h1>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label: t("alerts.total"), value: stats.total_alerts },
            { label: t("alerts.disposed"), value: stats.disposed },
            { label: t("alerts.ignored"), value: stats.ignored },
          ].map((s) => (
            <div key={s.label} className="bg-navy-800 rounded-xl border border-navy-700 p-3 text-center">
              <p className="text-2xl font-bold text-white">{s.value}</p>
              <p className="text-xs text-slate-500 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors capitalize
              ${filter === f ? "bg-primary text-white" : "bg-navy-800 text-slate-400 border border-navy-700 hover:border-navy-600 hover:text-white"}`}
          >
            {t(`alerts.filter${f.charAt(0).toUpperCase()}${f.slice(1)}`)}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-navy-800 rounded-xl border border-navy-700 p-4">
              <SkeletonRow />
            </div>
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-sm">
          {t("alerts.noAlerts")}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {alerts.map((a) => <AlertRow key={a.id} alert={a} />)}
        </div>
      )}
    </div>
  );
}
