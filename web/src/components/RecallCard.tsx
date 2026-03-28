import type { Recall } from "@/api/client";
import SeverityBadge from "./SeverityBadge";

interface Props {
  recall: Recall;
  severity?: string | null;
  index?: number;
}

const statusColors: Record<string, string> = {
  ACTIVE: "text-red-600",
  CLOSED: "text-gray-500",
  TERMINATED: "text-green-600",
};

export default function RecallCard({ recall, severity, index }: Props) {
  const statusCls = statusColors[(recall.status ?? "").toUpperCase()] ?? "text-gray-500";
  const sourceLabel = recall.source?.startsWith("FDA") ? "FDA" : "USDA";
  const sourceCls = sourceLabel === "FDA"
    ? "bg-blue-100 text-blue-700"
    : "bg-green-100 text-green-700";

  return (
    <article
      className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow"
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
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
              {recall.product_type}
            </span>
          )}
        </div>
        {recall.status && (
          <span className={`text-xs font-medium shrink-0 ${statusCls}`}>
            {recall.status}
          </span>
        )}
      </div>

      {/* Brand / product */}
      {recall.brand_name && (
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-0.5">
          {recall.brand_name}
        </p>
      )}
      <h3 className="font-semibold text-gray-900 text-sm leading-snug mb-2 line-clamp-2">
        {recall.product_description ?? "Unknown product"}
      </h3>

      {/* Reason */}
      {recall.reason_for_recall && (
        <p className="text-sm text-gray-600 line-clamp-2 mb-3">
          {recall.reason_for_recall}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-gray-400 pt-2 border-t border-gray-100">
        <div className="flex flex-col gap-0.5">
          {recall.company_name && <span>{recall.company_name}</span>}
          {recall.affected_area && <span>Area: {recall.affected_area}</span>}
        </div>
        <div className="flex items-center gap-3">
          <span>{recall.report_date ?? recall.recall_initiation_date ?? ""}</span>
          {recall.url && (
            <a
              href={recall.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary font-medium hover:underline"
              aria-label="View official recall page"
            >
              Details ↗
            </a>
          )}
        </div>
      </div>

      {/* Recall number */}
      {recall.recall_number && (
        <p className="mt-1.5 text-xs text-gray-300">#{recall.recall_number}</p>
      )}
    </article>
  );
}
