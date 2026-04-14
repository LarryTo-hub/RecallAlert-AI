import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAlerts, updateAlertFeedback, fetchStats, type AlertRecord } from "@/api/client";
import { SkeletonRow } from "@/components/Skeleton";

const FILTERS = ["all", "sent", "disposed", "ignored"] as const;
type Filter = typeof FILTERS[number];

const statusStyle: Record<string, string> = {
  sent: "bg-blue-100 text-blue-700",
  disposed: "bg-green-100 text-green-700",
  ignored: "bg-gray-100 text-gray-500",
};

function AlertRow({ alert }: { alert: AlertRecord }) {
  const qc = useQueryClient();

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
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      {/* Status + date row */}
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${statusStyle[alert.status] ?? "bg-gray-100 text-gray-500"}`}>
          {alert.status.toUpperCase()}
        </span>
        <span className="text-xs text-gray-400">
          {new Date(alert.created_at).toLocaleString()}
        </span>
      </div>

      {/* Message preview */}
      <p className="text-sm text-gray-700 line-clamp-3 whitespace-pre-line mb-3">{alert.message}</p>

      {/* Recall number */}
      {alert.recall_number && (
        <p className="text-xs text-gray-400 mb-3">Recall #{alert.recall_number}</p>
      )}

      {/* Feedback buttons — only show if still "sent" */}
      {alert.status === "sent" && (
        <div className="flex gap-2">
          <button
            onClick={() => mutation.mutate({ status: "disposed" })}
            disabled={mutation.isPending}
            className="flex-1 text-xs font-medium bg-green-50 text-green-700 border border-green-200 rounded-lg py-2 hover:bg-green-100 transition-colors disabled:opacity-60"
          >
            ✅ Mark Disposed
          </button>
          <button
            onClick={() => mutation.mutate({ status: "ignored" })}
            disabled={mutation.isPending}
            className="flex-1 text-xs font-medium bg-gray-50 text-gray-600 border border-gray-200 rounded-lg py-2 hover:bg-gray-100 transition-colors disabled:opacity-60"
          >
            Ignore
          </button>
        </div>
      )}
    </div>
  );
}

export default function Alerts() {
  const [filter, setFilter] = useState<Filter>("all");

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
      <h1 className="text-xl font-bold text-gray-900 mb-4">Alert History</h1>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label: "Total Alerts", value: stats.total_alerts },
            { label: "Disposed", value: stats.disposed },
            { label: "Ignored", value: stats.ignored },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-3 text-center">
              <p className="text-2xl font-bold text-gray-800">{s.value}</p>
              <p className="text-xs text-gray-500 mt-0.5">{s.label}</p>
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
              ${filter === f ? "bg-primary text-white" : "bg-white text-gray-600 border border-gray-200 hover:border-gray-300"}`}
          >
            {f}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-white rounded-xl border border-gray-200 p-4">
              <SkeletonRow />
            </div>
          ))}
        </div>
      ) : alerts.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">
          No alerts yet. Add items to your pantry to start receiving recall alerts.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {alerts.map((a) => <AlertRow key={a.id} alert={a} />)}
        </div>
      )}
    </div>
  );
}
