import {
  Activity,
  LogOut,
  Package,
  Server,
  ShieldCheck,
  UserRound,
} from "lucide-react";
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
import { cn } from "@/lib/utils";

type HealthState = "idle" | "loading" | "ok" | "error";
type ProfileState = "idle" | "loading" | "ok" | "error";
type Section = "inventory" | "system";

const INVENTORY_MANAGE_ROLES = new Set(["super_admin", "ops_manager", "master"]);

export default function App() {
  const [isAuthHydrated, setIsAuthHydrated] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [authNotice, setAuthNotice] = useState("");

  const [section, setSection] = useState<Section>("inventory");

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

  const displayName = useMemo(() => {
    if (!currentUser) {
      return "Authenticated User";
    }
    const name = `${currentUser.first_name ?? ""} ${currentUser.last_name ?? ""}`.trim();
    return name || currentUser.username;
  }, [currentUser]);

  const canManageInventory = useMemo(
    () => effectiveRoleSlugs.some((slug) => INVENTORY_MANAGE_ROLES.has(slug)),
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
          error instanceof Error ? error.message : "Failed to load current user profile.";
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
      if (error instanceof TypeError && error.message.toLowerCase().includes("fetch")) {
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
    <main className="min-h-[100svh] bg-slate-50 p-3 sm:p-5">
      <div className="mx-auto grid w-full max-w-7xl gap-4 lg:grid-cols-[220px_1fr]">
        <aside className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            <ShieldCheck className="h-4 w-4" />
            Rent Market
          </p>
          <p className="mt-2 text-sm text-slate-700">Admin workspace</p>

          <div className="mt-4 space-y-2">
            <button
              type="button"
              className={cn(
                "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                section === "inventory"
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
              )}
              onClick={() => setSection("inventory")}
            >
              <span className="inline-flex items-center gap-2">
                <Package className="h-4 w-4" />
                Inventory
              </span>
            </button>

            <button
              type="button"
              className={cn(
                "w-full rounded-md border px-3 py-2 text-left text-sm transition",
                section === "system"
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
              )}
              onClick={() => setSection("system")}
            >
              <span className="inline-flex items-center gap-2">
                <Server className="h-4 w-4" />
                System
              </span>
            </button>
          </div>

          <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Token Expires</p>
            <p className="mt-1 text-xs text-slate-700">{accessTokenExpiresAtLabel}</p>
          </div>

          <Button
            variant="outline"
            className="mt-4 h-10 w-full"
            onClick={() => logout()}
          >
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </Button>
        </aside>

        <section className="space-y-4">
          <header className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-semibold text-slate-900">{displayName}</p>
                {currentUser ? (
                  <p className="text-xs text-slate-500">@{currentUser.username}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2">
                  {effectiveRoleTitles.length ? (
                    effectiveRoleTitles.map((roleTitle) => (
                      <span
                        key={roleTitle}
                        className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-xs text-slate-700"
                      >
                        {roleTitle}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">No roles</span>
                  )}
                </div>
              </div>

              <Button
                variant="outline"
                className="h-10 w-full sm:w-auto"
                onClick={checkBackendHealth}
                disabled={healthState === "loading"}
              >
                <Activity className="mr-2 h-4 w-4" />
                {healthState === "loading" ? "Checking..." : "Check Backend"}
              </Button>
            </div>

            {profileState === "error" ? (
              <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {profileMessage}
              </p>
            ) : null}

            <p
              className={cn(
                "mt-3 rounded-md border px-3 py-2 text-sm",
                healthState === "error"
                  ? "border-rose-200 bg-rose-50 text-rose-700"
                  : healthState === "ok"
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-slate-200 bg-slate-50 text-slate-700",
              )}
            >
              {healthMessage}
            </p>
          </header>

          {section === "inventory" ? (
            <InventoryAdmin
              accessToken={session.accessToken}
              canManage={canManageInventory}
              roleTitles={effectiveRoleTitles}
              roleSlugs={effectiveRoleSlugs}
            />
          ) : (
            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
                <UserRound className="h-4 w-4" />
                System Overview
              </p>
              <p className="mt-2 text-sm text-slate-700">
                Use the <strong>Inventory</strong> menu to manage categories, items, and parts.
              </p>
            </section>
          )}
        </section>
      </div>
    </main>
  );
}
