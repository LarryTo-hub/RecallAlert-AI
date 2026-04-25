import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPantry, addPantryItem, deletePantryItem, clearPantry,
  ocrReceipt, matchPantry, pantryExportUrl, type OcrItem, type MatchResult,
} from "@/api/client";
import SeverityBadge from "@/components/SeverityBadge";
import { SkeletonRow } from "@/components/Skeleton";
import { useTranslation } from "@/i18n/LanguageContext";

export default function Pantry() {
  const qc = useQueryClient();
  const { t } = useTranslation();
  const [form, setForm] = useState({ product_name: "", brand: "", lot_code: "" });
  const [ocrItems, setOcrItems] = useState<(OcrItem & { checked: boolean })[]>([]);
  const [ocrPreview, setOcrPreview] = useState<string | null>(null);
  const [matches, setMatches] = useState<MatchResult[] | null>(null);
  const [closedMatches, setClosedMatches] = useState<MatchResult[]>([]);
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
      showToast(t("pantry.itemAdded"));
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
      showToast(t("pantry.pantryCleared"));
    },
  });

  const ocrMutation = useMutation({
    mutationFn: ocrReceipt,
    onSuccess: ({ items }) => {
      setOcrItems(items.map((i) => ({ ...i, checked: true })));
    },
    onError: (e: Error) => showToast(t("pantry.ocrFailed", { msg: e.message })),
  });

  const matchMutation = useMutation({
    mutationFn: matchPantry,
    onSuccess: ({ matches: m, closed_matches: cm }) => {
      setMatches(m);
      setClosedMatches(cm ?? []);
    },
    onError: (e: Error) => showToast(t("pantry.matchFailed", { msg: e.message })),
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
    showToast(t("pantry.addedFromReceipt", { n: String(selected.length) }));
  };

  const items = data?.items ?? [];

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Toast */}
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-emerald-600 text-white text-sm px-4 py-2.5 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      <h1 className="text-xl font-bold text-white mb-5">{t("pantry.title")}</h1>

      {/* Add item form */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-4 mb-4">
        <h2 className="font-semibold text-sm text-slate-300 mb-3">{t("pantry.addManually")}</h2>
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
            placeholder={t("pantry.productName")}
            value={form.product_name}
            onChange={(e) => setForm((f) => ({ ...f, product_name: e.target.value }))}
            className="border border-navy-700 bg-navy-900 text-white placeholder-slate-500 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
            aria-label="Product name"
          />
          <div className="flex gap-2">
            <input
              placeholder={t("pantry.brand")}
              value={form.brand}
              onChange={(e) => setForm((f) => ({ ...f, brand: e.target.value }))}
              className="flex-1 border border-navy-700 bg-navy-900 text-white placeholder-slate-500 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              aria-label="Brand"
            />
            <input
              placeholder={t("pantry.lotCode")}
              value={form.lot_code}
              onChange={(e) => setForm((f) => ({ ...f, lot_code: e.target.value }))}
              className="flex-1 border border-navy-700 bg-navy-900 text-white placeholder-slate-500 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
              aria-label="Lot code"
            />
          </div>
          <button
            type="submit"
            disabled={addMutation.isPending}
            className="bg-primary text-white text-sm font-medium rounded-lg py-2 hover:bg-primary-dark transition-colors disabled:opacity-60"
          >
            {addMutation.isPending ? t("pantry.adding") : t("pantry.addToPantry")}
          </button>
        </form>
      </section>

      {/* OCR upload */}
      <section className="bg-navy-800 rounded-xl border border-navy-700 p-4 mb-4">
        <h2 className="font-semibold text-sm text-slate-300 mb-3">{t("pantry.scanReceipt")}</h2>
        <div
          className="border-2 border-dashed border-navy-700 rounded-xl p-6 text-center cursor-pointer hover:border-primary/50 transition-colors"
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
            <div className="w-12 h-12 mx-auto mb-3 text-slate-500">
              <svg fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z" />
              </svg>
            </div>
          )}
          <p className="text-sm text-slate-400">
            {ocrMutation.isPending ? t("pantry.scanningReceipt") : t("pantry.uploadHint")}
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
            <p className="text-xs text-slate-500 mb-2">Review extracted items:</p>
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
                    className="rounded accent-primary"
                  />
                  <span className="font-medium text-white">{item.product_name}</span>
                  {item.brand && <span className="text-slate-400">· {item.brand}</span>}
                  {item.lot_code && <span className="text-slate-500 text-xs">Lot: {item.lot_code}</span>}
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
          className="flex-1 flex items-center justify-center gap-1.5 bg-primary text-white text-sm font-medium rounded-lg py-2.5 hover:bg-primary-dark transition-colors disabled:opacity-60"
        >
          {matchMutation.isPending ? t("pantry.checking") : t("pantry.checkRecalls")}
        </button>
        <a
          href={pantryExportUrl()}
          download="pantry.csv"
          className="px-3 py-2.5 bg-navy-800 border border-navy-700 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-navy-700 transition-colors"
          aria-label={t("pantry.exportCsv")}
        >
          {t("pantry.exportCsv")}
        </a>
        <button
          onClick={() => {
            if (confirm(t("pantry.clearConfirm", { n: String(items.length) }))) clearMutation.mutate();
          }}
          disabled={items.length === 0}
          className="px-3 py-2.5 bg-navy-800 border border-red-900/50 text-red-400 rounded-lg text-sm hover:bg-red-900/20 transition-colors disabled:opacity-40"
          aria-label={t("pantry.clear")}
        >
          {t("pantry.clear")}
        </button>
      </div>

      {/* Active match results */}
      {matches !== null && (
        <section className="bg-navy-800 border border-navy-700 rounded-xl p-4 mb-4">
          <h2 className="font-semibold text-sm text-slate-300 mb-2">
            {matches.length === 0 && closedMatches.length === 0
              ? t("pantry.noMatchFound")
              : matches.length === 0
              ? t("pantry.noActiveMatches")
              : t("pantry.matchesFound", { n: String(matches.length) })}
          </h2>
          {matches.map((m, i) => (
            <div key={i} className="bg-navy-900 rounded-lg border border-red-900/40 p-3 mb-2">
              <div className="flex items-center gap-2 mb-1">
                <SeverityBadge severity={m.parsed.severity} />
                <span className="text-sm font-medium text-white line-clamp-1">
                  {m.recall.product_description}
                </span>
              </div>
              <p className="text-xs text-slate-400 mb-1">{m.parsed.reason_summary}</p>
              <p className="text-xs text-primary-light">
                {t("pantry.yourItems", { items: m.matched_items.map((it) => it.brand ? `${it.brand} ${it.product_name}` : it.product_name).join(", ") })}
              </p>
            </div>
          ))}
        </section>
      )}

      {/* Closed/terminated recall history */}
      {closedMatches.length > 0 && (
        <section className="bg-navy-800 border border-navy-700 rounded-xl p-4 mb-4">
          <h2 className="font-semibold text-sm text-slate-400 mb-1">
            {t("pantry.closedRecallsTitle")}
          </h2>
          <p className="text-xs text-slate-500 mb-3">{t("pantry.closedRecallsHint")}</p>
          {closedMatches.map((m, i) => {
            const refDate = m.recall.recall_initiation_date || m.recall.report_date;
            return (
              <div key={i} className="bg-navy-900 rounded-lg border border-navy-700 p-3 mb-2 opacity-80">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-slate-700 text-slate-400">
                    {t("pantry.recallClosed")}
                  </span>
                  <span className="text-sm font-medium text-slate-300 line-clamp-1">
                    {m.recall.product_description}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mb-1">{m.parsed.reason_summary}</p>
                <p className="text-xs text-amber-400/80">
                  {refDate
                    ? t("pantry.discardIfBefore", { date: refDate })
                    : t("pantry.discardIfPurchased")}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">
                  {t("pantry.yourItems", { items: m.matched_items.map((it) => it.brand ? `${it.brand} ${it.product_name}` : it.product_name).join(", ") })}
                </p>
              </div>
            );
          })}
        </section>
      )}

      {/* Pantry list */}
      <section>
        <h2 className="font-semibold text-sm text-slate-300 mb-2">
          {t("pantry.itemsCount", { n: String(items.length) })}
        </h2>
        {isLoading ? (
          <div className="bg-navy-800 rounded-xl border border-navy-700 divide-y divide-navy-700">
            {Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} />)}
          </div>
        ) : items.length === 0 ? (
          <p className="text-center text-slate-500 text-sm py-8">
            {t("pantry.noItems")}
          </p>
        ) : (
          <div className="bg-navy-800 rounded-xl border border-navy-700 divide-y divide-navy-700">
            {items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <div className="w-2 h-2 rounded-full bg-primary/60 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{item.product_name}</p>
                  <p className="text-xs text-slate-500">
                    {[item.brand, item.lot_code ? `Lot: ${item.lot_code}` : null]
                      .filter(Boolean)
                      .join(" · ") || "No brand/lot"}
                  </p>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(item.id)}
                  className="p-1.5 text-slate-600 hover:text-red-400 transition-colors rounded-lg hover:bg-red-900/20"
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
