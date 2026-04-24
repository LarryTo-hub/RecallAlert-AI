import { useEffect, useState } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("install-dismissed")) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const install = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") setVisible(false);
    setDeferredPrompt(null);
  };

  const dismiss = (forever = false) => {
    if (forever) localStorage.setItem("install-dismissed", "1");
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      className="fixed bottom-20 md:bottom-6 left-4 right-4 md:left-auto md:right-6 md:w-80 z-50
        bg-navy-800 rounded-xl shadow-2xl border border-navy-700 p-4"
      role="dialog"
      aria-label="Install RecallAlert AI"
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 text-primary shrink-0 mt-0.5">
          <svg fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
          </svg>
        </div>
        <div className="flex-1">
          <p className="font-semibold text-white text-sm">Add to Home Screen</p>
          <p className="text-xs text-slate-400 mt-0.5">
            Install RecallAlert AI for instant access and offline support.
          </p>
        </div>
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={install}
          className="flex-1 bg-primary text-white text-sm font-medium rounded-lg py-2 hover:bg-primary-dark transition-colors"
        >
          Install
        </button>
        <button
          onClick={() => dismiss(false)}
          className="px-3 py-2 text-sm text-slate-400 hover:text-white"
          aria-label="Dismiss"
        >
          Later
        </button>
        <button
          onClick={() => dismiss(true)}
          className="px-3 py-2 text-sm text-slate-500 hover:text-slate-300 text-xs"
          aria-label="Don't ask again"
        >
          Never
        </button>
      </div>
    </div>
  );
}
