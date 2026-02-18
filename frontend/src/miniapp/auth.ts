import type {
  CurrentUser,
  MiniAppPhoneLogin,
  TicketFlowPermissions,
} from "@/lib/api";

const MINIAPP_AUTH_STORAGE_KEY = "rent_market_miniapp_auth_session_v1";

export type MiniAppAuthSession = {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
  roles: string[];
  roleSlugs: string[];
  permissions: TicketFlowPermissions;
  user: CurrentUser;
};

function decodeBase64Url(input: string): string {
  const normalized = input.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (normalized.length % 4)) % 4);
  return atob(normalized + padding);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

function readAccessTokenClaims(accessToken: string): {
  expMs: number | null;
  roles: string[];
  roleSlugs: string[];
} {
  try {
    const parts = accessToken.split(".");
    if (parts.length < 2) {
      return { expMs: null, roles: [], roleSlugs: [] };
    }
    const payload = JSON.parse(decodeBase64Url(parts[1])) as {
      exp?: unknown;
      roles?: unknown;
      role_slugs?: unknown;
    };
    return {
      expMs: typeof payload.exp === "number" ? payload.exp * 1000 : null,
      roles: toStringArray(payload.roles),
      roleSlugs: toStringArray(payload.role_slugs),
    };
  } catch {
    return { expMs: null, roles: [], roleSlugs: [] };
  }
}

export function createMiniAppAuthSession(
  loginResult: MiniAppPhoneLogin,
): MiniAppAuthSession {
  const claims = readAccessTokenClaims(loginResult.access);
  if (!claims.expMs) {
    throw new Error("Access token does not contain a valid exp claim.");
  }

  return {
    accessToken: loginResult.access,
    refreshToken: loginResult.refresh,
    accessTokenExpiresAt: claims.expMs,
    roles: loginResult.roles.length ? loginResult.roles : claims.roles,
    roleSlugs: loginResult.role_slugs.length
      ? loginResult.role_slugs
      : claims.roleSlugs,
    permissions: loginResult.permissions,
    user: loginResult.user,
  };
}

export function isMiniAppSessionExpired(session: MiniAppAuthSession): boolean {
  return Date.now() >= session.accessTokenExpiresAt;
}

export function saveMiniAppAuthSession(session: MiniAppAuthSession): void {
  localStorage.setItem(MINIAPP_AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearMiniAppAuthSession(): void {
  localStorage.removeItem(MINIAPP_AUTH_STORAGE_KEY);
}

export function loadMiniAppAuthSession(): MiniAppAuthSession | null {
  const serialized = localStorage.getItem(MINIAPP_AUTH_STORAGE_KEY);
  if (!serialized) {
    return null;
  }

  try {
    const parsed = JSON.parse(serialized) as Partial<MiniAppAuthSession>;
    if (
      !parsed.accessToken ||
      !parsed.refreshToken ||
      typeof parsed.accessTokenExpiresAt !== "number" ||
      !parsed.permissions ||
      !parsed.user
    ) {
      clearMiniAppAuthSession();
      return null;
    }

    const claims = readAccessTokenClaims(parsed.accessToken);
    const normalized: MiniAppAuthSession = {
      accessToken: parsed.accessToken,
      refreshToken: parsed.refreshToken,
      accessTokenExpiresAt:
        typeof parsed.accessTokenExpiresAt === "number"
          ? parsed.accessTokenExpiresAt
          : claims.expMs ?? 0,
      roles: toStringArray(parsed.roles ?? claims.roles),
      roleSlugs: toStringArray(parsed.roleSlugs ?? claims.roleSlugs),
      permissions: parsed.permissions,
      user: parsed.user,
    };

    if (!normalized.accessToken || !normalized.refreshToken) {
      clearMiniAppAuthSession();
      return null;
    }

    if (isMiniAppSessionExpired(normalized)) {
      clearMiniAppAuthSession();
      return null;
    }

    return normalized;
  } catch {
    clearMiniAppAuthSession();
    return null;
  }
}
