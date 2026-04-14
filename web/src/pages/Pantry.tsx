import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPantry, addPantryItem, deletePantryItem, clearPantry,
  ocrReceipt, matchPantry, pantryExportUrl, type OcrItem, type MatchResult,
} from "@/api/client";
import SeverityBadge from "@/components/SeverityBadge";
import { SkeletonRow } from "@/components/Skeleton";

export default function Pantry() {
  const qc = useQueryClient();
  const [form, setForm] = useState({ product_name: "", brand: "", lot_code: "" });
  const [ocrItems, setOcrItems] = useState<(OcrItem & { checked: boolean })[]>([]);
  const [ocrPreview, setOcrPreview] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchResult[] | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["pantry"],
    queryFn: fetchPantry,
  });

  const addMutation = useMutation({
    mutationFn: addPantryItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pantry"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      setForm({ product_name: "", brand: "", lot_code: "" });
      showToast("Item added to pantry");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePantryItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pantry"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const clearMutation = useMutation({
    mutationFn: clearPantry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pantry"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      showToast("Pantry cleared");
    },
  });

  const ocrMutation = useMutation({
    mutationFn: ocrReceipt,
    onSuccess: ({ items }) => {
      setOcrItems(items.map((i) => ({ ...i, checked: true })));
    },
    onError: (e: Error) => showToast(`OCR failed: ${e.message}`),
  });

  const matchMutation = useMutation({
    mutationFn: matchPantry,
    onSuccess: ({ matches: m }) => setMatches(m),
    onError: (e: Error) => showToast(`Match failed: ${e.message}`),
  });

  const handleOcrFile = (file: File) => {
    setOcrPreview(URL.createObjectURL(file));
    ocrMutation.mutate(file);
  };

  const addOcrItems = async () => {
    const selected = ocrItems.filter((i) => i.checked);
    for (const item of selected) {
      await addMutation.mutateAsync({
        product_name: item.product_name,
        brand: item.brand ?? undefined,
        lot_code: item.lot_code ?? undefined,
      });
    }
    setOcrItems([]);
    setOcrPreview(null);
    showToast(`Added ${selected.length} items from receipt`);
  };

  const items = data?.items ?? [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-success text-white text-sm px-4 py-2.5 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      <h1 className="text-xl font-bold text-gray-900 mb-5">My Pantry</h1>

      {/* Add item form */}
      <section className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <h2 className="font-semibold text-sm text-gray-700 mb-3">Add Item Manually</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!form.product_name.trim()) return;
            addMutation.mutate({
              product_name: form.product_name,
              brand: form.brand || undefined,
              lot_code: form.lot_code || undefined,
            });
          }}
          className="flex flex-col gap-2"
        >
          <input
            required
            placeholder="Product name *"
            value={form.product_name}
            onChange={(e) => setForm((f) => ({ ...f, product_name: e.target.value }))}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            aria-label="Product name"
          />
          <div className="flex gap-2">
            <input
              placeholder="Brand (optional)"
              value={form.brand}
              onChange={(e) => setForm((f) => ({ ...f, brand: e.target.value }))}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              aria-label="Brand"
            />
            <input
              placeholder="Lot code (optional)"
              value={form.lot_code}
              onChange={(e) => setForm((f) => ({ ...f, lot_code: e.target.value }))}
              className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              aria-label="Lot code"
            />
          </div>
          <button
            type="submit"
            disabled={addMutation.isPending}
            className="bg-primary text-white text-sm font-medium rounded-lg py-2 hover:bg-primary-dark transition-colors disabled:opacity-60"
          >
            {addMutation.isPending ? "Adding…" : "Add to Pantry"}
          </button>
        </form>
      </section>

      {/* OCR upload */}
      <section className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
        <h2 className="font-semibold text-sm text-gray-700 mb-3">Scan Receipt</h2>
        <div
          className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center cursor-pointer hover:border-primary/40 transition-colors"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const file = e.dataTransfer.files[0];
            if (file) handleOcrFile(file);
          }}
          role="button"
          aria-label="Upload receipt image"
        >
          {ocrPreview ? (
            <img src={ocrPreview} alt="Receipt preview" className="max-h-32 mx-auto rounded-lg mb-2 object-contain" />
          ) : (
            <span className="text-4xl block mb-2" aria-hidden="true">📷</span>
          )}
          <p className="text-sm text-gray-500">
            {ocrMutation.isPending ? "Scanning receipt…" : "Tap to upload or drag & drop a receipt photo"}
          </p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleOcrFile(file);
          }}
          aria-label="Receipt file input"
        />

        {/* OCR confirmation list */}
        {ocrItems.length > 0 && (
          <div className="mt-3">
            <p className="text-xs text-gray-500 mb-2">Review extracted items:</p>
            <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
              {ocrItems.map((item, i) => (
                <label key={i} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={(e) =>
                      setOcrItems((prev) =>
                        prev.map((it, j) => j === i ? { ...it, checked: e.target.checked } : it)
                      )
                    }
                    className="rounded"
                  />
                  <span className="font-medium">{item.product_name}</span>
                  {item.brand && <span className="text-gray-400">· {item.brand}</span>}
                  {item.lot_code && <span className="text-gray-400 text-xs">Lot: {item.lot_code}</span>}
                </label>
              ))}
            </div>
            <button
              onClick={addOcrItems}
              disabled={addMutation.isPending || ocrItems.every((i) => !i.checked)}
              className="mt-3 w-full bg-primary text-white text-sm font-medium rounded-lg py-2 hover:bg-primary-dark transition-colors disabled:opacity-60"
            >
              Add Selected to Pantry
            </button>
          </div>
        )}
      </section>

      {/* Action row */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => matchMutation.mutate()}
          disabled={matchMutation.isPending || items.length === 0}
          className="flex-1 flex items-center justify-center gap-1.5 bg-orange-500 text-white text-sm font-medium rounded-lg py-2.5 hover:bg-orange-600 transition-colors disabled:opacity-60"
        >
          <span aria-hidden="true">🔍</span>
          {matchMutation.isPending ? "Checking…" : "Check Against Recalls"}
        </button>
        <a
          href={pantryExportUrl()}
          download="pantry.csv"
          className="px-3 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-colors"
          aria-label="Export pantry as CSV"
        >
          ⬇ CSV
        </a>
        <button
          onClick={() => {
            if (confirm(`Clear all ${items.length} pantry items?`)) clearMutation.mutate();
          }}
          disabled={items.length === 0}
          className="px-3 py-2.5 bg-white border border-red-200 text-red-500 rounded-lg text-sm hover:bg-red-50 transition-colors disabled:opacity-40"
          aria-label="Clear pantry"
        >
          Clear
        </button>
      </div>

      {/* Match results */}
      {matches !== null && (
        <section className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-4">
          <h2 className="font-semibold text-sm text-orange-800 mb-2">
            {matches.length === 0 ? "✅ No matches found — your pantry looks safe!" : `⚠️ ${matches.length} potential match(es) found`}
          </h2>
          {matches.map((m, i) => (
            <div key={i} className="bg-white rounded-lg border border-orange-100 p-3 mb-2">
              <div className="flex items-center gap-2 mb-1">
                <SeverityBadge severity={m.parsed.severity} />
                <span className="text-sm font-medium text-gray-800 line-clamp-1">
                  {m.recall.product_description}
                </span>
              </div>
              <p className="text-xs text-gray-500 mb-1">{m.parsed.reason_summary}</p>
              <p className="text-xs text-orange-700">
                Your items: {m.matched_items.map((it) => it.product_name).join(", ")}
              </p>
            </div>
          ))}
        </section>
      )}

      {/* Pantry list */}
      <section>
        <h2 className="font-semibold text-sm text-gray-700 mb-2">
          Items ({items.length})
        </h2>
        {isLoading ? (
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
            {Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} />)}
          </div>
        ) : items.length === 0 ? (
          <p className="text-center text-gray-400 text-sm py-8">
            No items yet. Add products manually or scan a receipt.
          </p>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
            {items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <span className="text-lg" aria-hidden="true">
                  {item.source === "receipt" ? "🧾" : "✏️"}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{item.product_name}</p>
                  <p className="text-xs text-gray-400">
                    {[item.brand, item.lot_code ? `Lot: ${item.lot_code}` : null]
                      .filter(Boolean)
                      .join(" · ") || "No brand/lot"}
                  </p>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(item.id)}
                  className="p-1.5 text-gray-400 hover:text-red-500 transition-colors rounded-lg hover:bg-red-50"
                  aria-label={`Remove ${item.product_name}`}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
