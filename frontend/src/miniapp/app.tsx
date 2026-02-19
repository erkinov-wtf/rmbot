import { AlertTriangle, LogOut, ShieldCheck, Smartphone } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";
import { verifyMiniAppTelegramInitData } from "@/lib/api";
import {
  clearMiniAppAuthSession,
  createMiniAppAuthSession,
  loadMiniAppAuthSession,
  saveMiniAppAuthSession,
  type MiniAppAuthSession,
} from "@/miniapp/auth";
import { MobileTicketFlow } from "@/miniapp/mobile-ticket-flow";
import {
  getTelegramMiniAppContext,
  prepareTelegramMiniApp,
  type TelegramMiniAppContext,
} from "@/miniapp/telegram";

type ViewState = "loading" | "ready";

type MissingAccessState = {
  telegramId: number | null;
  username: string | null;
};

function toErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export default function MiniApp() {
  const { t } = useI18n();
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [session, setSession] = useState<MiniAppAuthSession | null>(null);
  const [notice, setNotice] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [missingAccess, setMissingAccess] = useState<MissingAccessState | null>(
    null,
  );
  const [authContext, setAuthContext] = useState<TelegramMiniAppContext | null>(
    null,
  );
  const [isProfileSheetOpen, setIsProfileSheetOpen] = useState(false);

  const logout = useCallback((nextNotice = "") => {
    clearMiniAppAuthSession();
    setSession(null);
    setNotice(nextNotice);
    setIsProfileSheetOpen(false);
  }, []);

  const authenticateWithTelegram = useCallback(
    async (context: TelegramMiniAppContext) => {
      if (!context.initData) {
        setErrorMessage(
          context.isTelegramWebView
            ? t("Telegram initData is missing. Reopen mini app from bot.")
            : t("Open this page from Telegram bot mini app button."),
        );
        return;
      }

      setIsAuthenticating(true);
      setErrorMessage("");
      setMissingAccess(null);

      try {
        const result = await verifyMiniAppTelegramInitData(context.initData);
        if (!result.user_exists) {
          clearMiniAppAuthSession();
          setSession(null);
          setMissingAccess({
            telegramId: result.telegram_id,
            username: result.username,
          });
          setNotice("");
          return;
        }
        const nextSession = createMiniAppAuthSession(result);
        saveMiniAppAuthSession(nextSession);
        setSession(nextSession);
        setNotice("");
      } catch (error) {
        clearMiniAppAuthSession();
        setSession(null);
        setErrorMessage(
          toErrorMessage(
            error,
            t("Could not authenticate Telegram mini app session."),
          ),
        );
      } finally {
        setIsAuthenticating(false);
      }
    },
    [t],
  );

  useEffect(() => {
    prepareTelegramMiniApp();
    const context = getTelegramMiniAppContext();
    setAuthContext(context);

    const stored = loadMiniAppAuthSession();
    if (stored) {
      setSession(stored);
      setViewState("ready");
      return;
    }

    if (!context.initData) {
      setViewState("ready");
      setErrorMessage(
        context.isTelegramWebView
          ? t("Telegram initData is missing. Reopen mini app from bot.")
          : t("Open this page from Telegram bot mini app button."),
      );
      return;
    }

    void authenticateWithTelegram(context).finally(() => {
      setViewState("ready");
    });
  }, [authenticateWithTelegram, t]);

  useEffect(() => {
    if (!session) {
      return;
    }

    const remainingMs = session.accessTokenExpiresAt - Date.now();
    if (remainingMs <= 0) {
      logout(t("Session expired. Reopen mini app from Telegram."));
      return;
    }

    const timer = window.setTimeout(() => {
      logout(t("Session expired. Reopen mini app from Telegram."));
    }, remainingMs + 1000);

    return () => {
      window.clearTimeout(timer);
    };
  }, [logout, session, t]);

  const displayName = useMemo(() => {
    if (!session?.user) {
      return t("Mini App User");
    }
    const fullName = `${session.user.first_name ?? ""} ${session.user.last_name ?? ""}`.trim();
    return fullName || session.user.username;
  }, [session, t]);

  if (viewState === "loading") {
    return (
      <main className="rm-shell flex items-center justify-center">
        <p className="text-sm text-slate-600">{t("Preparing mini app...")}</p>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="rm-shell px-3 py-4 sm:px-4">
        <section className="mx-auto w-full max-w-md space-y-4">
          <div className="rm-panel p-5">
            <p className="inline-flex items-center gap-2 rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
              <Smartphone className="h-4 w-4" />
              {t("Telegram Mini App")}
            </p>
            <h1 className="mt-3 text-2xl font-bold text-slate-900">{t("Ticket Flow")}</h1>
            <p className="mt-2 text-sm text-slate-600">
              {t("Authentication is handled through Telegram mini app init data.")}
            </p>
          </div>

          <section className="rm-panel p-5">
            {isAuthenticating ? (
              <p className="text-sm text-slate-600">{t("Authenticating with Telegram...")}</p>
            ) : null}

            {notice ? (
              <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {notice}
              </p>
            ) : null}

            {errorMessage ? (
              <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {errorMessage}
              </p>
            ) : null}

            {missingAccess ? (
              <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                <p className="inline-flex items-center gap-2 font-semibold">
                  <AlertTriangle className="h-4 w-4" />
                  {t("Access not approved yet")}
                </p>
                <p className="mt-1 text-xs">
                  {t("Telegram account is not linked to an active user.")}
                </p>
                {missingAccess.telegramId ? (
                  <p className="mt-1 text-xs">
                    {t("Telegram ID: {{id}}", { id: missingAccess.telegramId })}
                  </p>
                ) : null}
                {missingAccess.username ? (
                  <p className="mt-1 text-xs">
                    {t("Username: @{{username}}", {
                      username: missingAccess.username,
                    })}
                  </p>
                ) : null}
                <p className="mt-1 text-xs">
                  {t("Ask admin to approve and link your access request.")}
                </p>
              </div>
            ) : null}

            <div className="mt-4">
              <Button
                type="button"
                className="h-11 w-full"
                disabled={isAuthenticating || !authContext?.initData}
                onClick={() => {
                  if (!authContext) {
                    return;
                  }
                  void authenticateWithTelegram(authContext);
                }}
              >
                {t("Recheck Access")}
              </Button>
            </div>

            {!authContext?.isTelegramWebView ? (
              <p className="mt-3 text-xs text-slate-500">
                {t("Open this page from Telegram bot using the mini app button.")}
              </p>
            ) : null}
          </section>
        </section>
      </main>
    );
  }

  return (
    <>
      <main className="rm-shell px-2 py-3 sm:px-3">
        <div className="mx-auto w-full max-w-md space-y-3">
          <section className="rm-panel px-3 py-2">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="inline-flex items-center gap-1 rounded-full bg-cyan-50 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-cyan-800">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {t("Mini App")}
                </p>
                <p className="mt-1 truncate text-sm font-semibold text-slate-900">
                  {displayName}
                </p>
              </div>

              <Button
                type="button"
                variant="outline"
                className="h-9 px-3"
                onClick={() => setIsProfileSheetOpen(true)}
              >
                {t("My Profile")}
              </Button>
            </div>
          </section>

          <MobileTicketFlow
            accessToken={session.accessToken}
            permissions={session.permissions}
          />
        </div>
      </main>

      {isProfileSheetOpen ? (
        <div className="fixed inset-0 z-50 flex items-end">
          <button
            type="button"
            className="absolute inset-0 bg-slate-900/45"
            onClick={() => setIsProfileSheetOpen(false)}
          />
          <section className="relative z-10 w-full rounded-t-2xl border border-slate-200 bg-white p-4 shadow-2xl">
            <div className="mx-auto mb-3 h-1.5 w-12 rounded-full bg-slate-300" />
            <p className="text-sm font-semibold text-slate-900">{displayName}</p>
            <p className="text-xs text-slate-500">
              @{session.user.username} {session.user.phone ? `• ${session.user.phone}` : ""}
            </p>

            <div className="mt-3 flex flex-wrap gap-2">
              {session.roles.length ? (
                session.roles.map((role) => (
                  <span key={role} className="rm-role-pill">
                    {role}
                  </span>
                ))
              ) : (
                <span className="text-xs text-slate-500">{t("No roles")}</span>
              )}
            </div>

            <Button
              type="button"
              className="mt-4 h-11 w-full"
              onClick={() =>
                logout(t("Session cleared. Reopen mini app from Telegram."))
              }
            >
              <LogOut className="mr-2 h-4 w-4" />
              {t("Logout")}
            </Button>
          </section>
        </div>
      ) : null}
    </>
  );
}
