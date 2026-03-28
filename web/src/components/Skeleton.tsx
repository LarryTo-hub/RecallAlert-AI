export function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 animate-pulse">
      <div className="flex gap-2 mb-2">
        <div className="h-5 w-12 bg-gray-200 rounded-full" />
        <div className="h-5 w-16 bg-gray-200 rounded-full" />
      </div>
      <div className="h-3 w-20 bg-gray-200 rounded mb-1" />
      <div className="h-4 w-3/4 bg-gray-200 rounded mb-2" />
      <div className="h-3 w-full bg-gray-100 rounded mb-1" />
      <div className="h-3 w-2/3 bg-gray-100 rounded" />
    </div>
  );
}

export function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 p-3 animate-pulse">
      <div className="h-8 w-8 bg-gray-200 rounded-full shrink-0" />
      <div className="flex-1 space-y-1">
        <div className="h-3 w-1/2 bg-gray-200 rounded" />
        <div className="h-3 w-1/3 bg-gray-100 rounded" />
      </div>
    </div>
  );
}
