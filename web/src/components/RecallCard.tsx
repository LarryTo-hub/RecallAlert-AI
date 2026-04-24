import type { Recall } from "@/api/client";
import SeverityBadge from "./SeverityBadge";

interface Props {
  recall: Recall;
  severity?: string | null;
  index?: number;
}

const statusColors: Record<string, string> = {
  ACTIVE: "text-red-400",
  CLOSED: "text-emerald-400",
  TERMINATED: "text-emerald-400",
  COMPLETED: "text-emerald-400",
};

/** Normalise raw API status values to canonical display labels. */
function normalizeStatus(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const lower = raw.trim().toLowerCase();
  if (lower === "ongoing" || lower === "on going" || lower === "on-going") return "ACTIVE";
  return raw.trim().toUpperCase();
}

/** Convert YYYYMMDD → MM/DD/YYYY; leave other formats unchanged. */
function formatDate(val: string | null | undefined): string {
  if (!val) return "";
  const m = val.trim().match(/^(\d{4})(\d{2})(\d{2})$/);
  return m ? `${m[2]}/${m[3]}/${m[1]}` : val.trim();
}

export default function RecallCard({ recall, severity }: Props) {
  const displayStatus = normalizeStatus(recall.status);
  const statusCls = statusColors[displayStatus ?? ""] ?? "text-gray-500";
  const sourceLabel = recall.source?.startsWith("FDA") ? "FDA" : "USDA";
  const sourceCls = sourceLabel === "FDA"
    ? "bg-primary/20 text-primary-light border border-primary/30"
    : "bg-emerald-900/40 text-emerald-400 border border-emerald-700/40";

  return (
    <article
      className="bg-navy-800 rounded-xl border border-navy-700 p-4 hover:border-navy-600 transition-colors"
      aria-label={`Recall: ${recall.product_description ?? "Unknown product"}`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${sourceCls}`}>
            {sourceLabel}
          </span>
          {severity && <SeverityBadge severity={severity} />}
          {recall.product_type && (
            <span className="text-xs text-slate-400 bg-navy-700 px-2 py-0.5 rounded-full">
              {recall.product_type}
            </span>
          )}
        </div>
        {displayStatus && (
          <span className={`text-xs font-medium shrink-0 ${statusCls}`}>
            {displayStatus}
          </span>
        )}
      </div>

      {/* Brand / product */}
      {recall.brand_name && (
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-0.5">
          {recall.brand_name}
        </p>
      )}
      <h3 className="font-semibold text-white text-sm leading-snug mb-2 line-clamp-2">
        {recall.product_description ?? "Unknown product"}
      </h3>

      {/* Reason */}
      {recall.reason_for_recall && (
        <p className="text-sm text-slate-400 line-clamp-2 mb-3">
          {recall.reason_for_recall}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-navy-700">
        <div className="flex flex-col gap-0.5">
          {recall.company_name && <span>{recall.company_name}</span>}
          {recall.affected_area && <span>Area: {recall.affected_area}</span>}
        </div>
        <div className="flex items-center gap-3">
          <span>{formatDate(recall.report_date ?? recall.recall_initiation_date)}</span>
          {recall.url && (
            <a
              href={recall.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary-light font-medium hover:underline"
              aria-label="View official recall page"
            >
              Details ↗
            </a>
          )}
        </div>
      </div>

      {/* Recall number */}
      {recall.recall_number && (
        <p className="mt-1.5 text-xs text-navy-600">#{recall.recall_number}</p>
      )}
    </article>
  );
}
