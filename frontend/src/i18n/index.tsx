import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

import {
  type AppLanguage,
  type TranslationParams,
  translateMessage,
} from "@/i18n/messages";
export type { AppLanguage } from "@/i18n/messages";

const LANGUAGE_STORAGE_KEY = "rent_market_frontend_language_v1";
const SUPPORTED_LANGUAGES: AppLanguage[] = ["en", "ru", "uz"];

type I18nContextValue = {
  language: AppLanguage;
  setLanguage: (language: AppLanguage) => void;
  t: (key: string, params?: TranslationParams) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

function normalizeLanguage(raw: string | null | undefined): AppLanguage {
  if (!raw) {
    return "uz";
  }
  const normalized = raw.trim().toLowerCase();
  if (normalized.startsWith("ru")) {
    return "ru";
  }
  if (normalized.startsWith("en")) {
    return "en";
  }
  if (normalized.startsWith("uz")) {
    return "uz";
  }
  return "uz";
}

type TelegramUserLike = {
  language_code?: string;
};

function readTelegramLanguageCode(): string | null {
  const user = (window as Window & {
    Telegram?: {
      WebApp?: {
        initDataUnsafe?: {
          user?: TelegramUserLike;
        };
      };
    };
  }).Telegram?.WebApp?.initDataUnsafe?.user;
  return typeof user?.language_code === "string" ? user.language_code : null;
}

function readStoredLanguage(): AppLanguage | null {
  const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
  if (!stored) {
    return null;
  }
  const normalized = normalizeLanguage(stored);
  return SUPPORTED_LANGUAGES.includes(normalized) ? normalized : null;
}

function detectFallbackLanguage(): AppLanguage {
  const telegramLanguage = readTelegramLanguageCode();
  if (telegramLanguage) {
    return normalizeLanguage(telegramLanguage);
  }
  if (typeof navigator !== "undefined" && navigator.language) {
    return normalizeLanguage(navigator.language);
  }
  return "uz";
}

export function resolveInitialLanguage(): AppLanguage {
  const stored = readStoredLanguage();
  if (stored) {
    return stored;
  }
  return detectFallbackLanguage();
}

type I18nProviderProps = {
  children: ReactNode;
  initialLanguage?: AppLanguage;
  persistLanguagePreference?: boolean;
};

export function I18nProvider({
  children,
  initialLanguage,
  persistLanguagePreference = true,
}: I18nProviderProps) {
  const [language, setLanguageState] = useState<AppLanguage>(() => {
    if (initialLanguage) {
      return normalizeLanguage(initialLanguage);
    }
    if (persistLanguagePreference) {
      return resolveInitialLanguage();
    }
    return detectFallbackLanguage();
  });

  const setLanguage = useCallback((nextLanguage: AppLanguage) => {
    const normalized = normalizeLanguage(nextLanguage);
    setLanguageState(normalized);
    if (!persistLanguagePreference) {
      return;
    }
    localStorage.setItem(LANGUAGE_STORAGE_KEY, normalized);
  }, [persistLanguagePreference]);

  const t = useCallback(
    (key: string, params?: TranslationParams) =>
      translateMessage(key, language, params),
    [language],
  );

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      t,
    }),
    [language, setLanguage, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used inside I18nProvider.");
  }
  return context;
}

export const LANGUAGE_OPTIONS: ReadonlyArray<{
  value: AppLanguage;
  label: string;
}> = [
  { value: "uz", label: "UZ" },
  { value: "en", label: "EN" },
  { value: "ru", label: "RU" },
];
