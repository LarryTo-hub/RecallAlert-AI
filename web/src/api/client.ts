/** Typed API client for the RecallAlert FastAPI backend. */

const BASE = import.meta.env.VITE_API_URL ?? "";

export function getTelegramId(): number {
  return Number(localStorage.getItem("telegram_id") ?? "0");
}

export function setTelegramId(id: number): void {
  localStorage.setItem("telegram_id", String(id));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Recall {
  source: string;
  recall_number: string | null;
  brand_name: string | null;
  product_description: string | null;
  product_type: string | null;
  reason_for_recall: string | null;
  company_name: string | null;
  status: string | null;
  affected_area: string | null;
  report_date: string | null;
  recall_initiation_date: string | null;
  url: string | null;
}

export interface PantryItem {
  id: number;
  user_id: number;
  product_name: string;
  brand: string | null;
  lot_code: string | null;
  source: string;
  added_at: string;
}

export interface AlertRecord {
  id: number;
  user_id: number;
  recall_id: number | null;
  recall_number: string | null;
  message: string;
  status: string;
  created_at: string;
  responded_at: string | null;
}

export interface OcrItem {
  product_name: string;
  brand: string | null;
  lot_code: string | null;
}

export interface Stats {
  total_recalls: number;
  active_recalls: number;
  pantry_items: number;
  total_alerts: number;
  disposed: number;
  ignored: number;
  cache_updated_at: string | null;
}

export interface MatchResult {
  recall: Recall;
  parsed: { severity: string; reason_summary: string; products: string[]; brands: string[] };
  matched_items: { product_name: string; brand: string | null; lot_code: string | null }[];
}

// ── Recalls ────────────────────────────────────────────────────────────────

export async function fetchRecalls(params?: {
  limit?: number;
  offset?: number;
  source?: string;
  status?: string;
  q?: string;
}): Promise<{ total: number; recalls: Recall[]; updated_at: string | null }> {
  const sp = new URLSearchParams();
  if (params?.limit) sp.set("limit", String(params.limit));
  if (params?.offset) sp.set("offset", String(params.offset));
  if (params?.source) sp.set("source", params.source);
  if (params?.status) sp.set("status", params.status);
  if (params?.q) sp.set("q", params.q);
  return request(`/api/recalls?${sp}`);
}

export async function triggerFetch(): Promise<{ count: number }> {
  return request("/api/fetch", { method: "POST" });
}

// ── Pantry ─────────────────────────────────────────────────────────────────

export async function fetchPantry(): Promise<{ items: PantryItem[] }> {
  return request(`/api/pantry?telegram_id=${getTelegramId()}`);
}

export async function addPantryItem(body: {
  product_name: string;
  brand?: string;
  lot_code?: string;
}): Promise<PantryItem> {
  return request(`/api/pantry?telegram_id=${getTelegramId()}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deletePantryItem(id: number): Promise<void> {
  return request(`/api/pantry/${id}?telegram_id=${getTelegramId()}`, { method: "DELETE" });
}

export async function clearPantry(): Promise<{ deleted: number }> {
  return request(`/api/pantry?telegram_id=${getTelegramId()}`, { method: "DELETE" });
}

export function pantryExportUrl(): string {
  return `${BASE}/api/pantry/export?telegram_id=${getTelegramId()}`;
}

// ── OCR ────────────────────────────────────────────────────────────────────

export async function ocrReceipt(file: File): Promise<{ items: OcrItem[] }> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/api/ocr`, { method: "POST", body: fd });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "OCR failed");
  }
  return res.json();
}

// ── Match ──────────────────────────────────────────────────────────────────

export async function matchPantry(): Promise<{ matches: MatchResult[] }> {
  return request(`/api/match?telegram_id=${getTelegramId()}`, { method: "POST" });
}

// ── Alerts ─────────────────────────────────────────────────────────────────

export async function fetchAlerts(status?: string): Promise<{ alerts: AlertRecord[] }> {
  const sp = new URLSearchParams({ telegram_id: String(getTelegramId()) });
  if (status) sp.set("status", status);
  return request(`/api/alerts?${sp}`);
}

export async function updateAlertFeedback(
  id: number,
  status: "disposed" | "ignored"
): Promise<AlertRecord> {
  return request(`/api/alerts/${id}/feedback?telegram_id=${getTelegramId()}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

// ── Telegram ───────────────────────────────────────────────────────────────

export async function testTelegram(chat_id: number, language: string): Promise<{ status: string }> {
  return request("/api/telegram/test", {
    method: "POST",
    body: JSON.stringify({ chat_id, language }),
  });
}

export async function saveNotificationSettings(body: {
  telegram_id: number;
  language: string;
  severity_threshold: string;
  sources: string;
}): Promise<unknown> {
  return request("/api/notifications/settings", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Stats ──────────────────────────────────────────────────────────────────

export async function fetchStats(): Promise<Stats> {
  return request(`/api/stats?telegram_id=${getTelegramId()}`);
}

// ── Chat (AI) ──────────────────────────────────────────────────────────────

export async function sendChatMessage(message: string): Promise<{ reply: string }> {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message, telegram_id: getTelegramId() }),
  });
}
