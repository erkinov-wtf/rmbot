import type { LoginTokens } from "@/lib/api";

const AUTH_STORAGE_KEY = "rent_market_auth_session_v1";

export type AuthSession = {
  accessToken: string;
  refreshToken: string;
  accessTokenExpiresAt: number;
  roles: string[];
  roleSlugs: string[];
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

export function createAuthSession(tokens: LoginTokens): AuthSession {
  const claims = readAccessTokenClaims(tokens.access);
  const accessTokenExpiresAt = claims.expMs;
  if (!accessTokenExpiresAt) {
    throw new Error("Access token does not contain a valid exp claim.");
  }
  return {
    accessToken: tokens.access,
    refreshToken: tokens.refresh,
    accessTokenExpiresAt,
    roles: claims.roles,
    roleSlugs: claims.roleSlugs,
  };
}

export function isSessionExpired(session: AuthSession): boolean {
  return Date.now() >= session.accessTokenExpiresAt;
}

export function loadAuthSession(): AuthSession | null {
  const serialized = localStorage.getItem(AUTH_STORAGE_KEY);
  if (!serialized) {
    return null;
  }

  try {
    const parsed = JSON.parse(serialized) as Partial<AuthSession>;
    const claims = parsed.accessToken
      ? readAccessTokenClaims(parsed.accessToken)
      : { expMs: null, roles: [], roleSlugs: [] };
    const normalized: AuthSession = {
      accessToken: parsed.accessToken ?? "",
      refreshToken: parsed.refreshToken ?? "",
      accessTokenExpiresAt:
        typeof parsed.accessTokenExpiresAt === "number"
          ? parsed.accessTokenExpiresAt
          : claims.expMs ?? 0,
      roles: toStringArray(parsed.roles ?? claims.roles),
      roleSlugs: toStringArray(parsed.roleSlugs ?? claims.roleSlugs),
    };

    if (
      !normalized.accessToken ||
      !normalized.refreshToken ||
      typeof normalized.accessTokenExpiresAt !== "number"
    ) {
      clearAuthSession();
      return null;
    }

    if (isSessionExpired(normalized)) {
      clearAuthSession();
      return null;
    }
    return normalized;
  } catch {
    clearAuthSession();
    return null;
  }
}

export function saveAuthSession(session: AuthSession): void {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearAuthSession(): void {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}
