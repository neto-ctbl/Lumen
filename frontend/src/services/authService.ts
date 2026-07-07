import { apiRequest } from "./apiClient";

export type AuthSession = {
  accessToken: string;
  refreshToken: string | null;
  tokenType: string;
  expiresIn: number;
};

export type OrganizationSummary = {
  id: number;
  is_active: boolean;
  name: string;
  slug: string;
};

export type AuthUser = {
  email: string;
  full_name: string | null;
  global_role: string;
  id: number;
  is_active: boolean;
  last_login_at: string | null;
  last_logout_at: string | null;
  organization: OrganizationSummary;
  token_version: number;
};

type LoginPayload = {
  email: string;
  password: string;
};

type LoginResponse = {
  access_token: string;
  expires_in: number;
  refresh_token: string | null;
  token_type: string;
};

const authStorageKey = "lumen.auth.session";

export function readStoredSession(): AuthSession | null {
  const rawValue = window.localStorage.getItem(authStorageKey);
  if (!rawValue) {
    return null;
  }

  try {
    return JSON.parse(rawValue) as AuthSession;
  } catch {
    window.localStorage.removeItem(authStorageKey);
    return null;
  }
}

export function writeStoredSession(session: AuthSession) {
  window.localStorage.setItem(authStorageKey, JSON.stringify(session));
}

export function clearStoredSession() {
  window.localStorage.removeItem(authStorageKey);
}

export async function loginRequest(payload: LoginPayload): Promise<AuthSession> {
  const response = await apiRequest<LoginResponse>("/api/v1/auth/login", {
    auth: false,
    body: payload,
    method: "POST",
  });

  return {
    accessToken: response.access_token,
    expiresIn: response.expires_in,
    refreshToken: response.refresh_token,
    tokenType: response.token_type,
  };
}

export async function fetchCurrentUser(accessToken?: string): Promise<AuthUser> {
  if (accessToken) {
    return apiRequest<AuthUser>("/api/v1/auth/me", {
      auth: false,
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });
  }

  return apiRequest<AuthUser>("/api/v1/auth/me");
}

export async function logoutRequest(refreshToken: string | null) {
  return apiRequest<{ status: string }>("/api/v1/auth/logout", {
    body: { refresh_token: refreshToken },
    method: "POST",
  });
}
