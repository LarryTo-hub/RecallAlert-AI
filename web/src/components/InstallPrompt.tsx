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
        bg-white rounded-xl shadow-xl border border-gray-200 p-4"
      role="dialog"
      aria-label="Install RecallAlert AI"
    >
      <div className="flex items-start gap-3">
        <span className="text-3xl shrink-0" aria-hidden="true">🔔</span>
        <div className="flex-1">
          <p className="font-semibold text-gray-900 text-sm">Add to Home Screen</p>
          <p className="text-xs text-gray-500 mt-0.5">
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
          className="px-3 py-2 text-sm text-gray-500 hover:text-gray-700"
          aria-label="Dismiss"
        >
          Later
        </button>
        <button
          onClick={() => dismiss(true)}
          className="px-3 py-2 text-sm text-gray-400 hover:text-gray-600 text-xs"
          aria-label="Don't ask again"
        >
          Never
        </button>
      </div>
    </div>
  );
}
