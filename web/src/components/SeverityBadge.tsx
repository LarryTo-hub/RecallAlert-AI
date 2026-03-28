interface Props {
  severity?: string | null;
  className?: string;
}

const map: Record<string, { label: string; cls: string }> = {
  high: { label: "HIGH", cls: "bg-red-100 text-red-700 border-red-200" },
  medium: { label: "MEDIUM", cls: "bg-orange-100 text-orange-700 border-orange-200" },
  low: { label: "LOW", cls: "bg-yellow-100 text-yellow-700 border-yellow-200" },
};

export default function SeverityBadge({ severity, className = "" }: Props) {
  const key = (severity ?? "").toLowerCase();
  const { label, cls } = map[key] ?? {
    label: "UNKNOWN",
    cls: "bg-gray-100 text-gray-600 border-gray-200",
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
