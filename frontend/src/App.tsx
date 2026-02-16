import { Clock3, LogOut, Server, ShieldCheck, UserRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { InventoryAdmin } from "@/components/inventory/inventory-admin";
import { Button } from "@/components/ui/button";
import {
  getCurrentUser,
  getHealth,
  type CurrentUser,
  type LoginTokens,
} from "@/lib/api";
import {
  clearAuthSession,
  createAuthSession,
  loadAuthSession,
  saveAuthSession,
  type AuthSession,
} from "@/lib/auth";

type HealthState = "idle" | "loading" | "ok" | "error";
type ProfileState = "idle" | "loading" | "ok" | "error";
const INVENTORY_MANAGE_ROLES = new Set(["super_admin", "ops_manager", "master"]);

export default function App() {
  const [isAuthHydrated, setIsAuthHydrated] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [authNotice, setAuthNotice] = useState("");

  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [profileState, setProfileState] = useState<ProfileState>("idle");
  const [profileMessage, setProfileMessage] = useState("");

  const [healthState, setHealthState] = useState<HealthState>("idle");
  const [healthMessage, setHealthMessage] = useState(
    "Backend health has not been checked yet.",
  );

  const accessTokenExpiresAtLabel = useMemo(() => {
    if (!session) {
      return "";
    }
    return new Date(session.accessTokenExpiresAt).toLocaleString();
  }, [session]);

  const displayName = useMemo(() => {
    if (!currentUser) {
      return "";
    }
    const name = `${currentUser.first_name ?? ""} ${currentUser.last_name ?? ""}`.trim();
    return name || currentUser.username;
  }, [currentUser]);

  const effectiveRoleTitles = useMemo(() => {
    if (currentUser?.roles?.length) {
      return currentUser.roles;
    }
    return session?.roles ?? [];
  }, [currentUser, session]);

  const effectiveRoleSlugs = useMemo(() => {
    if (currentUser?.role_slugs?.length) {
      return currentUser.role_slugs;
    }
    return session?.roleSlugs ?? [];
  }, [currentUser, session]);

  const canManageInventory = useMemo(
    () =>
      effectiveRoleSlugs.some((slug) => INVENTORY_MANAGE_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );

  const logout = useCallback((noticeMessage = "") => {
    clearAuthSession();
    setSession(null);
    setCurrentUser(null);
    setProfileState("idle");
    setProfileMessage("");
    setHealthState("idle");
    setHealthMessage("Backend health has not been checked yet.");
    setAuthNotice(noticeMessage);
  }, []);

  const handleLoggedIn = useCallback((tokens: LoginTokens) => {
    const nextSession = createAuthSession(tokens);
    saveAuthSession(nextSession);
    setSession(nextSession);
    setAuthNotice("");
  }, []);

  const loadProfile = useCallback(
    async (activeSession: AuthSession) => {
      setProfileState("loading");
      setProfileMessage("");

      try {
        const profile = await getCurrentUser(activeSession.accessToken);
        setCurrentUser(profile);
        setProfileState("ok");
      } catch (error) {
        const message =
          error instanceof Error
            ? error.message
            : "Failed to load current user profile.";
        setCurrentUser(null);
        setProfileState("error");
        setProfileMessage(message);

        const normalized = message.toLowerCase();
        if (
          normalized.includes("token") ||
          normalized.includes("401") ||
          normalized.includes("not authenticated")
        ) {
          logout("Session expired or invalid. Please log in again.");
        }
      }
    },
    [logout],
  );

  useEffect(() => {
    const stored = loadAuthSession();
    setSession(stored);
    setIsAuthHydrated(true);
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    const remainingMs = session.accessTokenExpiresAt - Date.now();
    if (remainingMs <= 0) {
      logout("Session expired. Please log in again.");
      return;
    }

    const timerId = window.setTimeout(() => {
      logout("Session expired. Please log in again.");
    }, remainingMs + 1000);

    return () => {
      window.clearTimeout(timerId);
    };
  }, [session, logout]);

  useEffect(() => {
    if (!session) {
      return;
    }
    void loadProfile(session);
  }, [session, loadProfile]);

  const checkBackendHealth = async () => {
    setHealthState("loading");

    try {
      const payload = await getHealth();
      setHealthState("ok");
      setHealthMessage(`Backend is reachable. Status: ${payload.status}.`);
    } catch (error) {
      setHealthState("error");
      if (
        error instanceof TypeError &&
        error.message.toLowerCase().includes("fetch")
      ) {
        setHealthMessage(
          "Request failed at browser level (likely CORS or backend not reachable).",
        );
        return;
      }
      setHealthMessage(
        error instanceof Error
          ? error.message
          : "Health check failed with an unknown error.",
      );
    }
  };

  if (!isAuthHydrated) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50">
        <p className="text-sm text-slate-600">Preparing authentication...</p>
      </main>
    );
  }

  if (!session) {
    return <LoginForm onLoggedIn={handleLoggedIn} noticeMessage={authNotice} />;
  }

  return (
    <main className="min-h-[100svh] bg-[radial-gradient(circle_at_top,#eaf3ff_0%,#f8fafc_40%,#ffffff_100%)] px-4 py-6 sm:px-6 sm:py-8 md:px-8 md:py-10">
      <section className="mx-auto flex w-full max-w-5xl flex-col gap-4 sm:gap-6">
        <header className="rounded-2xl border border-slate-200 bg-white/90 p-5 shadow-xl backdrop-blur sm:p-6 md:p-8">
          <p className="inline-flex w-fit items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
            <ShieldCheck className="h-4 w-4" />
            Authenticated area
          </p>
          <div className="mt-4 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div className="space-y-2">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl md:text-4xl">
                Rent Market Frontend
              </h1>
              <p className="inline-flex items-start gap-2 text-sm text-slate-600">
                <Clock3 className="mt-0.5 h-4 w-4 shrink-0" />
                Access token expires at: {accessTokenExpiresAtLabel}
              </p>
            </div>
            <Button
              variant="outline"
              className="h-11 w-full text-sm font-semibold sm:w-auto"
              onClick={() => logout()}
            >
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </Button>
          </div>
        </header>

        <div className="grid gap-4 md:grid-cols-2 md:gap-6">
          <article className="rounded-xl border border-slate-200 bg-white/90 p-5 shadow-md backdrop-blur sm:p-6">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <UserRound className="h-4 w-4" />
              Current User
            </div>
            {profileState === "loading" ? (
              <p className="text-sm text-slate-700">Loading profile...</p>
            ) : null}
            {profileState === "error" ? (
              <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {profileMessage}
              </p>
            ) : null}
            {currentUser ? (
              <div className="space-y-3 text-sm text-slate-700">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Name</p>
                  <p className="mt-1 font-semibold text-slate-900">{displayName}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Username</p>
                  <p className="mt-1">{currentUser.username}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Roles</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {effectiveRoleTitles.length ? (
                      effectiveRoleTitles.map((roleTitle) => (
                        <span
                          key={roleTitle}
                          className="rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700"
                        >
                          {roleTitle}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-600">No roles</span>
                    )}
                  </div>
                </div>
              </div>
            ) : null}
          </article>

          <article className="rounded-xl border border-slate-200 bg-white/90 p-5 shadow-md backdrop-blur sm:p-6">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <Server className="h-4 w-4" />
              Backend Connection Check
            </div>
            <p
              className={
                healthState === "error"
                  ? "rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                  : "text-sm text-slate-700"
              }
            >
              {healthMessage}
            </p>
            <div className="mt-4">
              <Button
                onClick={checkBackendHealth}
                disabled={healthState === "loading"}
                className="h-11 w-full text-sm font-semibold sm:w-auto"
              >
                {healthState === "loading" ? "Checking..." : "Check /misc/health"}
              </Button>
            </div>
          </article>
        </div>

        <InventoryAdmin
          accessToken={session.accessToken}
          canManage={canManageInventory}
          roleTitles={effectiveRoleTitles}
          roleSlugs={effectiveRoleSlugs}
        />
      </section>
    </main>
  );
}
