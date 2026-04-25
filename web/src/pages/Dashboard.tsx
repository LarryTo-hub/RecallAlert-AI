import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchRecalls, fetchStats, triggerFetch } from "@/api/client";
import RecallCard from "@/components/RecallCard";
import { SkeletonCard } from "@/components/Skeleton";
import { useTranslation } from "@/i18n/LanguageContext";

const SOURCES = ["All", "FDA", "USDA"];

export default function Dashboard() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [source, setSource] = useState("All");
  const [status, setStatus] = useState("All");
  const [sort, setSort] = useState<"latest" | "oldest">("latest");
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const LIMIT = 20;

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    setQ(searchInput.trim());
    setOffset(0);
  }, [searchInput]);

  const handleSearchClear = useCallback(() => {
    setSearchInput("");
    setQ("");
    setOffset(0);
  }, []);

  const STATUSES = [
    { label: t("dash.statusAll"), value: "All" },
    { label: t("dash.statusActive"), value: "ACTIVE" },
    { label: t("dash.statusInactive"), value: "INACTIVE" },
  ];
  const SORTS = [
    { value: "latest" as const, label: t("dash.newestFirst") },
    { value: "oldest" as const, label: t("dash.oldestFirst") },
  ];

  const params = {
    limit: LIMIT,
    offset,
    source: source !== "All" ? source : undefined,
    status: status !== "All" ? status : undefined,
    sort,
    q: q || undefined,
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
          <h1 className="text-xl font-bold text-white">{t("dash.title")}</h1>
          {data?.updated_at && (
            <p className="text-xs text-slate-500 mt-0.5">
              {t("dash.updated", { date: new Date(data.updated_at).toLocaleString() })}
            </p>
          )}
        </div>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
          className="flex items-center gap-1.5 text-sm bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-60 font-medium"
          aria-label={t("dash.refresh")}
        >
          {refresh.isPending ? t("dash.refreshing") : t("dash.refresh")}
        </button>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          {[
            { label: t("dash.totalRecalls"), value: stats.total_recalls, color: "text-white" },
            { label: t("dash.active"), value: stats.active_recalls, color: "text-red-400" },
            { label: t("dash.myPantry"), value: stats.pantry_items, color: "text-primary-light" },
          ].map((s) => (
            <div key={s.label} className="bg-navy-800 rounded-xl border border-navy-700 p-3 text-center">
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
              <p className="text-xs text-slate-500 mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* Search bar */}
      <form onSubmit={handleSearch} className="relative mb-4">
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder={t("dash.searchPlaceholder")}
          className="w-full bg-navy-800 border border-navy-700 text-white placeholder-slate-500 rounded-xl px-4 py-2.5 pr-20 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
        {q && (
          <button
            type="button"
            onClick={handleSearchClear}
            className="absolute right-16 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-lg leading-none px-1"
            aria-label="Clear search"
          >✕</button>
        )}
        <button
          type="submit"
          className="absolute right-2 top-1/2 -translate-y-1/2 bg-primary text-white text-xs font-medium px-3 py-1.5 rounded-lg hover:bg-primary-dark transition-colors"
        >Search</button>
      </form>

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
              key={s.value}
              onClick={() => { setStatus(s.value); setOffset(0); }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors
                ${status === s.value ? "bg-navy-600 text-white" : "bg-navy-800 text-slate-400 border border-navy-700 hover:border-navy-600 hover:text-white"}`}
            >
              {s.label}
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
        {t("dash.checkPantry")}
      </button>

      {/* Recall list */}
      {isError && (
        <div className="text-center py-12 text-red-400">
          {t("dash.loadFailed")}
        </div>
      )}

      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : recalls.length === 0 ? (
        <div className="text-center py-12 text-slate-500">{t("dash.noResults")}</div>
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
              {t("dash.prev")}
            </button>
            <span>
              {offset + 1}–{Math.min(offset + recalls.length, total)} of {total}
            </span>
            <button
              onClick={() => setOffset(offset + LIMIT)}
              disabled={offset + LIMIT >= total}
              className="px-3 py-1.5 border border-navy-700 rounded-lg hover:bg-navy-800 hover:text-white transition-colors disabled:opacity-40"
            >
              {t("dash.next")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
