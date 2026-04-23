export function SkeletonCard() {
  return (
    <div className="bg-navy-800 rounded-xl border border-navy-700 p-4 animate-pulse">
      <div className="flex gap-2 mb-2">
        <div className="h-5 w-12 bg-navy-700 rounded-full" />
        <div className="h-5 w-16 bg-navy-700 rounded-full" />
      </div>
      <div className="h-3 w-20 bg-navy-700 rounded mb-1" />
      <div className="h-4 w-3/4 bg-navy-700 rounded mb-2" />
      <div className="h-3 w-full bg-navy-750 rounded mb-1" />
      <div className="h-3 w-2/3 bg-navy-750 rounded" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 p-3 animate-pulse">
      <div className="h-8 w-8 bg-navy-700 rounded-full shrink-0" />
      <div className="flex-1 space-y-1">
        <div className="h-3 w-1/2 bg-navy-700 rounded" />
        <div className="h-3 w-1/3 bg-navy-750 rounded" />
      </div>
    </div>
  );
}
