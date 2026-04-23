import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchRecalls, fetchStats, triggerFetch } from "@/api/client";
import RecallCard from "@/components/RecallCard";
import { SkeletonCard } from "@/components/Skeleton";

const SOURCES = ["All", "FDA", "USDA"];
const STATUSES = ["All", "ACTIVE", "CLOSED", "TERMINATED"];
const SORTS: Array<{ value: "latest" | "oldest"; label: string }> = [
  { value: "latest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
];

export default function Dashboard() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [source, setSource] = useState("All");
  const [status, setStatus] = useState("All");
  const [sort, setSort] = useState<"latest" | "oldest">("latest");
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  const params = {
    limit: LIMIT,
    offset,
    source: source !== "All" ? source : undefined,
    status: status !== "All" ? status : undefined,
    sort,
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ["recalls", params],
    queryFn: () => fetchRecalls(params),
  });

  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });

  const refresh = useMutation({
    mutationFn: triggerFetch,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["recalls"] }),
  });

  const recalls = data?.recalls ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-white">Recall Feed</h1>
          {data?.updated_at && (
            <p className="text-xs text-slate-500 mt-0.5">
              Updated {new Date(data.updated_at).toLocaleString()}
            </p>
          )}
        </div>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
          className="flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-60 font-medium"
          aria-label="Refresh recalls"
        >
          {refresh.isPending ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label: "Total Recalls", value: stats.total_recalls, color: "text-white" },
            { label: "Active", value: stats.active_recalls, color: "text-red-400" },
            { label: "My Pantry", value: stats.pantry_items, color: "text-primary-light" },
          ].map((s) => (
            <div key={s.label} className="bg-navy-800 rounded-xl border border-navy-700 p-3 text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-slate-500 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-4">
        <div className="flex gap-1">
          {SOURCES.map((s) => (
            <button
              key={s}
              onClick={() => { setSource(s); setOffset(0); }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors
                ${source === s ? "bg-primary text-white" : "bg-navy-800 text-slate-400 border border-navy-700 hover:border-navy-600 hover:text-white"}`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => { setStatus(s); setOffset(0); }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors
                ${status === s ? "bg-navy-600 text-white" : "bg-navy-800 text-slate-400 border border-navy-700 hover:border-navy-600 hover:text-white"}`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="ml-auto">
          <select
            value={sort}
            onChange={(e) => { setSort(e.target.value as "latest" | "oldest"); setOffset(0); }}
            className="text-xs border border-navy-700 rounded-full px-3 py-1.5 bg-navy-800 text-slate-400 cursor-pointer hover:border-navy-600 focus:outline-none"
            aria-label="Sort order"
          >
            {SORTS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* CTA */}
      <button
        onClick={() => navigate("/pantry")}
        className="w-full mb-5 flex items-center justify-center gap-2 bg-primary/10 border border-primary/30 text-primary-light font-medium rounded-xl py-3 text-sm hover:bg-primary/15 transition-colors"
      >
        Check My Pantry Against These Recalls
      </button>

      {/* Recall list */}
      {isError && (
        <div className="text-center py-12 text-red-400">
          Failed to load recalls. Make sure the API server is running.
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : recalls.length === 0 ? (
        <div className="text-center py-12 text-slate-500">No recalls found for these filters.</div>
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {recalls.map((r, i) => (
              <RecallCard key={`${r.recall_number ?? i}-${r.source}`} recall={r} index={i} />
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-6 text-sm text-slate-500">
            <button
              onClick={() => setOffset(Math.max(0, offset - LIMIT))}
              disabled={offset === 0}
              className="px-3 py-1.5 border border-navy-700 rounded-lg hover:bg-navy-800 hover:text-white transition-colors disabled:opacity-40"
            >
              ← Prev
            </button>
            <span>
              {offset + 1}–{Math.min(offset + recalls.length, total)} of {total}
            </span>
            <button
              onClick={() => setOffset(offset + LIMIT)}
              disabled={offset + LIMIT >= total}
              className="px-3 py-1.5 border border-navy-700 rounded-lg hover:bg-navy-800 hover:text-white transition-colors disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
