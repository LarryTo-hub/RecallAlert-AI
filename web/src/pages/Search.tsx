import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRecalls } from "@/api/client";
import RecallCard from "@/components/RecallCard";
import { SkeletonCard } from "@/components/Skeleton";

export default function Search() {
  const [query, setQuery] = useState("");
  const [committed, setCommitted] = useState("");
  const [source, setSource] = useState("");
  const [status, setStatus] = useState("");

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["search", committed, source, status],
    queryFn: () =>
      fetchRecalls({
        limit: 50,
        q: committed || undefined,
        source: source || undefined,
        status: status || undefined,
      }),
    enabled: committed.length > 0 || source.length > 0 || status.length > 0,
  });

  const recalls = data?.recalls ?? [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <h1 className="text-xl font-bold text-white mb-4">Search Recalls</h1>

      {/* Search input */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setCommitted(query.trim());
        }}
        className="flex gap-2 mb-4"
      >
        <input
          type="search"
          placeholder="Search product, brand, company, reason…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 border border-navy-700 bg-navy-800 text-white placeholder-slate-500 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
          aria-label="Search recalls"
        />
        <button
          type="submit"
          className="bg-primary text-white px-4 rounded-xl font-medium text-sm hover:bg-primary-dark transition-colors"
          aria-label="Search"
        >
          Search
        </button>
      </form>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 mb-5">
        <select
          value={source}
          onChange={(e) => { setSource(e.target.value); setCommitted(query.trim()); }}
          className="border border-navy-700 bg-navy-800 text-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
          aria-label="Filter by source"
        >
          <option value="">All sources</option>
          <option value="FDA">FDA</option>
          <option value="USDA">USDA</option>
        </select>

        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setCommitted(query.trim()); }}
          className="border border-navy-700 bg-navy-800 text-slate-300 rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="ACTIVE">Active</option>
          <option value="CLOSED">Closed</option>
          <option value="TERMINATED">Terminated</option>
        </select>

        {(committed || source || status) && (
          <button
            onClick={() => {
              setQuery("");
              setCommitted("");
              setSource("");
              setStatus("");
            }}
            className="px-3 py-2 text-xs text-slate-400 border border-navy-700 bg-navy-800 rounded-lg hover:bg-navy-700 hover:text-white transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Results */}
      {(isLoading || isFetching) && (committed || source || status) ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : !committed && !source && !status ? (
        <div className="text-center py-16 text-slate-500">
          <p className="text-sm">Enter a search term to find recalls</p>
        </div>
      ) : recalls.length === 0 ? (
        <div className="text-center py-12 text-slate-500 text-sm">
          No results found for "{committed}".
        </div>
      ) : (
        <>
          <p className="text-xs text-slate-500 mb-3">{recalls.length} result(s)</p>
          <div className="flex flex-col gap-3">
            {recalls.map((r, i) => (
              <RecallCard key={`${r.recall_number ?? i}-${r.source}`} recall={r} index={i} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
