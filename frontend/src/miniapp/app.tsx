import { LogOut, PhoneCall, ShieldCheck, Smartphone } from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { TicketFlow } from "@/components/ticket/ticket-flow";
import { Button } from "@/components/ui/button";
import { loginMiniAppWithPhone } from "@/lib/api";
import {
  clearMiniAppAuthSession,
  createMiniAppAuthSession,
  loadMiniAppAuthSession,
  saveMiniAppAuthSession,
  type MiniAppAuthSession,
} from "@/miniapp/auth";

type ViewState = "loading" | "ready";

function normalizePhoneInput(value: string): string {
  return value.trim().replace(/\s+/g, "").replace(/-/g, "");
}

export default function MiniApp() {
  const [viewState, setViewState] = useState<ViewState>("loading");
  const [session, setSession] = useState<MiniAppAuthSession | null>(null);
  const [notice, setNotice] = useState("");

  const [phone, setPhone] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const logout = useCallback((nextNotice = "") => {
    clearMiniAppAuthSession();
    setSession(null);
    setNotice(nextNotice);
    setPhone("");
    setErrorMessage("");
  }, []);

  useEffect(() => {
    const stored = loadMiniAppAuthSession();
    setSession(stored);
    setViewState("ready");
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    const remainingMs = session.accessTokenExpiresAt - Date.now();
    if (remainingMs <= 0) {
      logout("Session expired. Sign in again.");
      return;
    }

    const timer = window.setTimeout(() => {
      logout("Session expired. Sign in again.");
    }, remainingMs + 1000);

    return () => {
      window.clearTimeout(timer);
    };
  }, [logout, session]);

  const handlePhoneLogin = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setErrorMessage("");
      setIsSubmitting(true);

      try {
        // TODO: Replace temporary phone login with official Telegram Mini App auth (initData).
        const loginResult = await loginMiniAppWithPhone(normalizePhoneInput(phone));
        const nextSession = createMiniAppAuthSession(loginResult);
        saveMiniAppAuthSession(nextSession);
        setSession(nextSession);
        setNotice("");
      } catch (error) {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Could not authenticate with phone number.",
        );
      } finally {
        setIsSubmitting(false);
      }
    },
    [phone],
  );

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
              Sign in with your phone number to open create/review/qc flows.
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Temporary dev login. Telegram `initData` auth will replace this.
            </p>
          </div>

          <form className="rm-panel p-5" onSubmit={handlePhoneLogin}>
            <label
              htmlFor="miniapp-phone"
              className="text-xs font-semibold uppercase tracking-wide text-slate-600"
            >
              Phone Number
            </label>
            <div className="relative mt-2">
              <PhoneCall className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                id="miniapp-phone"
                className="rm-input h-12 pl-10"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                placeholder="+998901234567"
                required
              />
            </div>

            {notice ? (
              <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
                {notice}
              </p>
            ) : null}
            {errorMessage ? (
              <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {errorMessage}
              </p>
            ) : null}

            <Button
              type="submit"
              className="mt-4 h-12 w-full"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Signing in..." : "Open Mini App"}
            </Button>
          </form>
        </section>
      </main>
    );
  }

  return (
    <main className="rm-shell px-2 py-3 sm:px-3">
      <div className="mx-auto w-full max-w-4xl space-y-3">
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
              onClick={() => logout()}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </section>

        <TicketFlow
          accessToken={session.accessToken}
          currentUserId={session.user.id}
          canCreate={session.permissions.can_create}
          canReview={session.permissions.can_open_review_panel}
          canWork={false}
          canQc={session.permissions.can_qc}
          roleSlugs={session.roleSlugs}
          showWorkTab={false}
          restrictTabsByPermission
          syncRouteWithUrl={false}
        />
      </div>
    </main>
  );
}
