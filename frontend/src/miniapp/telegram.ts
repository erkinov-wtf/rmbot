type TelegramWebAppUser = {
  id?: number;
  username?: string;
  language_code?: string;
};

type TelegramWebAppUnsafeData = {
  user?: TelegramWebAppUser;
};

type TelegramWebApp = {
  initData?: string;
  initDataUnsafe?: TelegramWebAppUnsafeData;
  ready?: () => void;
  expand?: () => void;
};

type TelegramGlobal = {
  WebApp?: TelegramWebApp;
};

declare global {
  interface Window {
    Telegram?: TelegramGlobal;
  }
}

export type TelegramMiniAppContext = {
  initData: string;
  telegramId: number | null;
  username: string | null;
  languageCode: string | null;
  isTelegramWebView: boolean;
};

function initDataFromQueryString(): string {
  const params = new URLSearchParams(window.location.search);
  const fromQuery =
    params.get("init_data") ??
    params.get("initData") ??
    params.get("tgWebAppData");
  return fromQuery ? fromQuery.trim() : "";
}

function initDataFromHash(): string {
  const hash = window.location.hash.startsWith("#")
    ? window.location.hash.slice(1)
    : window.location.hash;
  if (!hash) {
    return "";
  }
  const params = new URLSearchParams(hash);
  const fromHash =
    params.get("init_data") ??
    params.get("initData") ??
    params.get("tgWebAppData");
  return fromHash ? fromHash.trim() : "";
}

export function prepareTelegramMiniApp(): void {
  const webApp = window.Telegram?.WebApp;
  if (!webApp) {
    return;
  }
  webApp.ready?.();
  webApp.expand?.();
}

export function getTelegramMiniAppContext(): TelegramMiniAppContext {
  const webApp = window.Telegram?.WebApp;
  const initData =
    (webApp?.initData ?? "").trim() ||
    initDataFromQueryString() ||
    initDataFromHash();
  const unsafeUser = webApp?.initDataUnsafe?.user;
  const telegramId =
    typeof unsafeUser?.id === "number" && unsafeUser.id > 0
      ? unsafeUser.id
      : null;
  const username =
    typeof unsafeUser?.username === "string" && unsafeUser.username.trim()
      ? unsafeUser.username.trim()
      : null;
  const languageCode =
    typeof unsafeUser?.language_code === "string" &&
    unsafeUser.language_code.trim()
      ? unsafeUser.language_code.trim()
      : null;
  return {
    initData,
    telegramId,
    username,
    languageCode,
    isTelegramWebView: Boolean(webApp),
  };
}
