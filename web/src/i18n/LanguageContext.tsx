import { createContext, useContext, useState, type ReactNode } from "react";
import { translations, type LangCode, type Strings } from "./translations";

interface LanguageContextValue {
  lang: LangCode;
  setLang: (l: LangCode) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextValue>({
  lang: "en",
  setLang: () => undefined,
  t: (key) => key,
});

function getNestedValue(obj: Strings, key: string): string {
  const parts = key.split(".");
  let val: unknown = obj;
  for (const part of parts) {
    if (val && typeof val === "object") {
      val = (val as Record<string, unknown>)[part];
    } else {
      return key;
    }
  }
  return typeof val === "string" ? val : key;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(() => {
    const stored = localStorage.getItem("app_language");
    return (stored as LangCode) ?? "en";
  });

  const setLang = (l: LangCode) => {
    setLangState(l);
    localStorage.setItem("app_language", l);
  };

  const t = (key: string, vars?: Record<string, string | number>): string => {
    const dict = translations[lang] ?? translations.en;
    let result = getNestedValue(dict, key);
    // Fallback to English if not found in current language
    if (result === key) {
      result = getNestedValue(translations.en, key);
    }
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        result = result.replace(`{${k}}`, String(v));
      }
    }
    return result;
  };

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  return useContext(LanguageContext);
}
