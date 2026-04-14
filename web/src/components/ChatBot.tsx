import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "@/api/client";

interface Message {
  role: "user" | "bot";
  text: string;
}

async function sendChat(message: string): Promise<string> {
  const data = await sendChatMessage(message);
  return data.reply;
}

const WELCOME: Message = {
  role: "bot",
  text: "Hi! I'm RecallAlert AI. Ask me about food recalls, disposal instructions, or whether your pantry items are affected.",
};

export default function ChatBot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scroll to latest message whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    try {
      const reply = await sendChat(text);
      setMessages((prev) => [...prev, { role: "bot", text: reply }]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: `Sorry, I couldn't respond right now: ${msg}` },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    /* Positioned above mobile bottom nav (bottom-20) and flush right on desktop */
    <div className="fixed bottom-20 md:bottom-6 right-4 z-40 flex flex-col items-end gap-2">
      {/* ── Chat panel ── */}
      {open && (
        <div className="w-80 h-[26rem] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-primary px-4 py-3 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <span className="text-lg" aria-hidden>🤖</span>
              <div>
                <p className="text-white font-semibold text-sm leading-tight">RecallAlert AI</p>
                <p className="text-red-200 text-xs">Food safety assistant</p>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-white/70 hover:text-white text-2xl leading-none"
              aria-label="Close chat"
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2 bg-gray-50">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-primary text-white rounded-br-sm"
                      : "bg-white text-gray-800 rounded-bl-sm shadow-sm border border-gray-100"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-100 shadow-sm text-gray-400 px-3 py-2 rounded-2xl rounded-bl-sm text-sm">
                  <span className="animate-pulse">Thinking…</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input row */}
          <div className="border-t border-gray-100 p-2 flex gap-2 flex-shrink-0 bg-white">
            <input
              ref={inputRef}
              className="flex-1 text-sm border border-gray-200 rounded-full px-3 py-1.5 outline-none focus:border-primary transition-colors"
              placeholder="Ask about recalls…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              disabled={loading}
              maxLength={500}
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="bg-primary hover:bg-primary-dark disabled:opacity-40 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm flex-shrink-0 transition-colors"
              aria-label="Send message"
            >
              ↑
            </button>
          </div>
        </div>
      )}

      {/* ── Toggle button ── */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-13 h-13 w-12 h-12 bg-primary hover:bg-primary-dark text-white rounded-full shadow-lg flex items-center justify-center text-xl transition-all hover:scale-105"
        aria-label={open ? "Close AI chat" : "Open AI chat"}
      >
        {open ? "×" : "💬"}
      </button>
    </div>
  );
}
