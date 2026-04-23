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
        <div className="w-80 h-[26rem] bg-navy-900 rounded-2xl shadow-2xl border border-navy-700 flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-navy-800 border-b border-navy-700 px-4 py-3 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 text-primary">
                <svg fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                </svg>
              </div>
              <div>
                <p className="text-white font-semibold text-sm leading-tight">RecallAlert AI</p>
                <p className="text-slate-400 text-xs">Food safety assistant</p>
              </div>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-slate-400 hover:text-white text-2xl leading-none"
              aria-label="Close chat"
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2 bg-navy-950">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-primary text-white rounded-br-sm"
                      : "bg-navy-800 text-slate-200 rounded-bl-sm border border-navy-700"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-navy-800 border border-navy-700 text-slate-400 px-3 py-2 rounded-2xl rounded-bl-sm text-sm">
                  <span className="animate-pulse">Thinking…</span>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input row */}
          <div className="border-t border-navy-700 p-2 flex gap-2 flex-shrink-0 bg-navy-800">
            <input
              ref={inputRef}
              className="flex-1 text-sm border border-navy-700 bg-navy-900 text-white placeholder-slate-500 rounded-full px-3 py-1.5 outline-none focus:border-primary/60 transition-colors"
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
        className="w-13 h-13 w-12 h-12 bg-navy-800 hover:bg-navy-700 border border-navy-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-105"
        aria-label={open ? "Close AI chat" : "Open AI chat"}
      >
        {open ? (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 9.75a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375m-13.5 3.01c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.184-4.183a1.14 1.14 0 01.778-.332 48.294 48.294 0 005.83-.498c1.585-.233 2.708-1.626 2.708-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
          </svg>
        )}
      </button>
    </div>
  );
}
