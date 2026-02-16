import {
  CalendarClock,
  LogOut,
  Package,
  ShieldCheck,
  Sparkles,
  Ticket,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AccessRequestsAdmin } from "@/components/account/access-requests-admin";
import { AttendanceAdmin } from "@/components/attendance/attendance-admin";
import { LoginForm } from "@/components/auth/login-form";
import { InventoryAdmin } from "@/components/inventory/inventory-admin";
import { TicketFlow } from "@/components/ticket/ticket-flow";
import { XpAdmin } from "@/components/xp/xp-admin";
import { Button } from "@/components/ui/button";
import {
  getCurrentUser,
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

type ProfileState = "idle" | "loading" | "ok" | "error";
type Section = "inventory" | "attendance" | "tickets" | "access_requests" | "xp_admin";

const INVENTORY_MANAGE_ROLES = new Set(["super_admin", "ops_manager", "master"]);
const TICKET_CREATE_ROLES = new Set(["super_admin", "master"]);
const TICKET_REVIEW_ROLES = new Set(["super_admin", "ops_manager"]);
const TICKET_WORK_ROLES = new Set(["super_admin", "technician"]);
const TICKET_QC_ROLES = new Set(["super_admin", "qc_inspector"]);
const ACCESS_REQUEST_MANAGE_ROLES = new Set(["super_admin", "ops_manager"]);
const ATTENDANCE_MANAGE_ROLES = new Set(["super_admin", "ops_manager", "master"]);
const XP_MANAGE_ROLES = new Set(["super_admin", "ops_manager", "admin"]);

function parseSectionFromPath(pathname: string): Section {
  if (pathname.startsWith("/access-requests")) {
    return "access_requests";
  }
  if (pathname.startsWith("/attendance")) {
    return "attendance";
  }
  if (pathname.startsWith("/tickets")) {
    return "tickets";
  }
  if (pathname.startsWith("/xp-admin") || pathname.startsWith("/system")) {
    return "xp_admin";
  }
  return "inventory";
}

function sectionRootPath(section: Section): string {
  if (section === "access_requests") {
    return "/access-requests";
  }
  if (section === "attendance") {
    return "/attendance";
  }
  if (section === "tickets") {
    return "/tickets/create";
  }
  if (section === "xp_admin") {
    return "/xp-admin";
  }
  return "/inventory/items";
}

export default function App() {
  const [isAuthHydrated, setIsAuthHydrated] = useState(false);
  const [session, setSession] = useState<AuthSession | null>(null);
  const [authNotice, setAuthNotice] = useState("");

  const [section, setSection] = useState<Section>(() =>
    parseSectionFromPath(window.location.pathname),
  );

  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [profileState, setProfileState] = useState<ProfileState>("idle");
  const [profileMessage, setProfileMessage] = useState("");

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
  const canCreateTicket = useMemo(
    () => effectiveRoleSlugs.some((slug) => TICKET_CREATE_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );
  const canReviewTicket = useMemo(
    () => effectiveRoleSlugs.some((slug) => TICKET_REVIEW_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );
  const canWorkTicket = useMemo(
    () => effectiveRoleSlugs.some((slug) => TICKET_WORK_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );
  const canQcTicket = useMemo(
    () => effectiveRoleSlugs.some((slug) => TICKET_QC_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );
  const canManageAccessRequests = useMemo(
    () => effectiveRoleSlugs.some((slug) => ACCESS_REQUEST_MANAGE_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );
  const canManageAttendance = useMemo(
    () => effectiveRoleSlugs.some((slug) => ATTENDANCE_MANAGE_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );
  const canManageXp = useMemo(
    () => effectiveRoleSlugs.some((slug) => XP_MANAGE_ROLES.has(slug)),
    [effectiveRoleSlugs],
  );

  const navigateSection = useCallback((nextSection: Section) => {
    const nextPath = sectionRootPath(nextSection);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setSection(nextSection);
  }, []);

  const logout = useCallback((noticeMessage = "") => {
    clearAuthSession();
    setSession(null);
    setCurrentUser(null);
    setProfileState("idle");
    setProfileMessage("");
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

  useEffect(() => {
    const onPopState = () => {
      setSection(parseSectionFromPath(window.location.pathname));
    };

    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
    };
  }, []);

  if (!isAuthHydrated) {
    return (
      <main className="rm-shell flex items-center justify-center">
        <p className="text-sm text-slate-600">Preparing authentication...</p>
      </main>
    );
  }

  if (!session) {
    return <LoginForm onLoggedIn={handleLoggedIn} noticeMessage={authNotice} />;
  }

  return (
    <main className="rm-shell">
      <div className="mx-auto grid w-full max-w-[1480px] gap-4 lg:grid-cols-[248px_1fr]">
        <aside className="rm-panel rm-animate-enter sticky top-4 h-fit p-4">
          <p
            className={cn(
              "inline-flex items-center gap-2 rounded-full bg-cyan-50 px-3 py-1",
              "text-xs font-semibold uppercase tracking-wide text-cyan-800",
            )}
          >
            <ShieldCheck className="h-4 w-4" />
            Rent Market
          </p>
          <p className="mt-2 text-sm text-slate-700">Operations workspace</p>

          <div className="mt-4 space-y-2">
            <button
              type="button"
              className={cn(
                "rm-menu-btn w-full text-left",
                section === "inventory"
                  ? "rm-menu-btn-active"
                  : "rm-menu-btn-idle",
              )}
              onClick={() => navigateSection("inventory")}
            >
              <span className="inline-flex items-center gap-2">
                <Package className="h-4 w-4" />
                Inventory
              </span>
            </button>

            <button
              type="button"
              className={cn(
                "rm-menu-btn w-full text-left",
                section === "attendance"
                  ? "rm-menu-btn-active"
                  : "rm-menu-btn-idle",
              )}
              onClick={() => navigateSection("attendance")}
            >
              <span className="inline-flex items-center gap-2">
                <CalendarClock className="h-4 w-4" />
                Attendance
              </span>
            </button>

            <button
              type="button"
              className={cn(
                "rm-menu-btn w-full text-left",
                section === "tickets"
                  ? "rm-menu-btn-active"
                  : "rm-menu-btn-idle",
              )}
              onClick={() => navigateSection("tickets")}
            >
              <span className="inline-flex items-center gap-2">
                <Ticket className="h-4 w-4" />
                Tickets
              </span>
            </button>

            <button
              type="button"
              className={cn(
                "rm-menu-btn w-full text-left",
                section === "access_requests"
                  ? "rm-menu-btn-active"
                  : "rm-menu-btn-idle",
              )}
              onClick={() => navigateSection("access_requests")}
            >
              <span className="inline-flex items-center gap-2">
                <Users className="h-4 w-4" />
                Access Requests
              </span>
            </button>

            <button
              type="button"
              className={cn(
                "rm-menu-btn w-full text-left",
                section === "xp_admin"
                  ? "rm-menu-btn-active"
                  : "rm-menu-btn-idle",
              )}
              onClick={() => navigateSection("xp_admin")}
            >
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                XP Control
              </span>
            </button>
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
          <header className="rm-panel rm-animate-enter p-4">
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
                      className="rm-role-pill"
                    >
                      {roleTitle}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-slate-500">No roles</span>
                )}
              </div>
            </div>

            {profileState === "error" ? (
              <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {profileMessage}
              </p>
            ) : null}
          </header>

          {section === "inventory" ? (
            <InventoryAdmin
              accessToken={session.accessToken}
              canManage={canManageInventory}
              roleTitles={effectiveRoleTitles}
              roleSlugs={effectiveRoleSlugs}
            />
          ) : section === "attendance" ? (
            <AttendanceAdmin
              accessToken={session.accessToken}
              canManage={canManageAttendance}
              roleTitles={effectiveRoleTitles}
              roleSlugs={effectiveRoleSlugs}
            />
          ) : section === "tickets" ? (
            <TicketFlow
              accessToken={session.accessToken}
              currentUserId={currentUser?.id ?? null}
              canCreate={canCreateTicket}
              canReview={canReviewTicket}
              canWork={canWorkTicket}
              canQc={canQcTicket}
              roleTitles={effectiveRoleTitles}
              roleSlugs={effectiveRoleSlugs}
            />
          ) : section === "access_requests" ? (
            <AccessRequestsAdmin
              accessToken={session.accessToken}
              canManage={canManageAccessRequests}
              roleTitles={effectiveRoleTitles}
              roleSlugs={effectiveRoleSlugs}
            />
          ) : (
            <XpAdmin
              accessToken={session.accessToken}
              canManage={canManageXp}
              roleTitles={effectiveRoleTitles}
              roleSlugs={effectiveRoleSlugs}
            />
          )}
        </section>
      </div>
    </main>
  );
}
