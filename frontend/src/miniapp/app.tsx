import { AlertTriangle, LogOut, ShieldCheck, Smartphone } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
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

  const logout = useCallback((nextNotice = "") => {
    clearMiniAppAuthSession();
    setSession(null);
    setNotice(nextNotice);
  }, []);

  const authenticateWithTelegram = useCallback(
    async (context: TelegramMiniAppContext) => {
      if (!context.initData) {
        setErrorMessage(
          context.isTelegramWebView
            ? "Telegram initData is missing. Reopen mini app from bot."
            : "Open this page from Telegram bot mini app button.",
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
          toErrorMessage(error, "Could not authenticate Telegram mini app session."),
        );
      } finally {
        setIsAuthenticating(false);
      }
    },
    [],
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
          ? "Telegram initData is missing. Reopen mini app from bot."
          : "Open this page from Telegram bot mini app button.",
      );
      return;
    }

    void authenticateWithTelegram(context).finally(() => {
      setViewState("ready");
    });
  }, [authenticateWithTelegram]);

  useEffect(() => {
    if (!session) {
      return;
    }

    const remainingMs = session.accessTokenExpiresAt - Date.now();
    if (remainingMs <= 0) {
      logout("Session expired. Reopen mini app from Telegram.");
      return;
    }

    const timer = window.setTimeout(() => {
      logout("Session expired. Reopen mini app from Telegram.");
    }, remainingMs + 1000);

    return () => {
      window.clearTimeout(timer);
    };
  }, [logout, session]);

  const displayName = useMemo(() => {
    if (!session?.user) {
      return "Mini App User";
    }
    const fullName = `${session.user.first_name ?? ""} ${session.user.last_name ?? ""}`.trim();
    return fullName || session.user.username;
  }, [session]);

  if (viewState === "loading") {
    return (
      <main className="rm-shell flex items-center justify-center">
        <p className="text-sm text-slate-600">Preparing mini app...</p>
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
              Telegram Mini App
            </p>
            <h1 className="mt-3 text-2xl font-bold text-slate-900">Ticket Flow</h1>
            <p className="mt-2 text-sm text-slate-600">
              Authentication is handled through Telegram mini app init data.
            </p>
          </div>

          <section className="rm-panel p-5">
            {isAuthenticating ? (
              <p className="text-sm text-slate-600">Authenticating with Telegram...</p>
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
                  Access not approved yet
                </p>
                <p className="mt-1 text-xs">
                  Your Telegram account is not linked to an active user.
                </p>
                {missingAccess.telegramId ? (
                  <p className="mt-1 text-xs">Telegram ID: {missingAccess.telegramId}</p>
                ) : null}
                {missingAccess.username ? (
                  <p className="mt-1 text-xs">Username: @{missingAccess.username}</p>
                ) : null}
                <p className="mt-1 text-xs">
                  Ask admin to approve and link your access request.
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
                Recheck Access
              </Button>
            </div>

            {!authContext?.isTelegramWebView ? (
              <p className="mt-3 text-xs text-slate-500">
                Open this page from Telegram bot using the mini app button.
              </p>
            ) : null}
          </section>
        </section>
      </main>
    );
  }

  return (
    <main className="rm-shell px-2 py-3 sm:px-3">
      <div className="mx-auto w-full max-w-md space-y-3">
        <section className="rm-panel p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="inline-flex items-center gap-2 rounded-full bg-cyan-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-800">
                <ShieldCheck className="h-4 w-4" />
                Mini App
              </p>
              <p className="mt-2 text-sm font-semibold text-slate-900">{displayName}</p>
              <p className="text-xs text-slate-500">
                @{session.user.username} {session.user.phone ? `• ${session.user.phone}` : ""}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {session.roles.length ? (
                  session.roles.map((role) => (
                    <span key={role} className="rm-role-pill">
                      {role}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-slate-500">No roles</span>
                )}
              </div>
            </div>

            <Button
              type="button"
              variant="outline"
              className="h-10"
              onClick={() => logout("Session cleared. Reopen mini app from Telegram.")}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </section>

        <MobileTicketFlow
          accessToken={session.accessToken}
          permissions={session.permissions}
        />
      </div>
    </main>
  );
}
