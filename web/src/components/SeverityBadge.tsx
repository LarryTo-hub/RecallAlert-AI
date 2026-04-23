interface Props {
  severity?: string | null;
  className?: string;
}

const map: Record<string, { label: string; cls: string }> = {
  high: { label: "HIGH", cls: "bg-red-900/40 text-red-400 border-red-700/50" },
  medium: { label: "MEDIUM", cls: "bg-amber-900/40 text-amber-400 border-amber-700/50" },
  low: { label: "LOW", cls: "bg-yellow-900/30 text-yellow-400 border-yellow-700/40" },
};

export default function SeverityBadge({ severity, className = "" }: Props) {
  const key = (severity ?? "").toLowerCase();
  const { label, cls } = map[key] ?? {
    label: "UNKNOWN",
    cls: "bg-navy-700 text-slate-400 border-navy-600",
  };

  return (
    <span
      className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${cls} ${className}`}
      aria-label={`Severity: ${label}`}
    >
      {label}
    </span>
  );
}
