import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { ApiError, configureApiClient } from "../services/apiClient";
import {
  type AuthSession,
  type AuthUser,
  clearStoredSession,
  fetchCurrentUser,
  loginRequest,
  logoutRequest,
  readStoredSession,
  writeStoredSession,
} from "../services/authService";

type AuthStatus = "anonymous" | "authenticated" | "loading";

type AuthContextValue = {
  errorMessage: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  session: AuthSession | null;
  status: AuthStatus;
  user: AuthUser | null;
};

type AuthProviderProps = PropsWithChildren<{
  onUnauthorized: () => void;
}>;

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, onUnauthorized }: AuthProviderProps) {
  const [session, setSession] = useState<AuthSession | null>(() => readStoredSession());
  const [user, setUser] = useState<AuthUser | null>(null);
  const [status, setStatus] = useState<AuthStatus>(() =>
    readStoredSession() ? "loading" : "anonymous",
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const clearAuthState = useCallback(
    (shouldRedirect: boolean) => {
      clearStoredSession();
      setSession(null);
      setUser(null);
      setErrorMessage(null);
      setStatus("anonymous");

      if (shouldRedirect) {
        onUnauthorized();
      }
    },
    [onUnauthorized],
  );

  useEffect(() => {
    configureApiClient({
      getAccessToken: () => session?.accessToken ?? null,
      onUnauthorized: () => clearAuthState(true),
    });
  }, [clearAuthState, session]);

  const refreshProfile = useCallback(async () => {
    if (!session?.accessToken) {
      setStatus("anonymous");
      setUser(null);
      return;
    }

    setStatus("loading");
    setErrorMessage(null);

    try {
      const currentUser = await fetchCurrentUser(session.accessToken);
      setUser(currentUser);
      setStatus("authenticated");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        clearAuthState(true);
        return;
      }

      setErrorMessage(
        error instanceof Error ? error.message : "Nao foi possivel validar a sessao.",
      );
      setStatus("anonymous");
    }
  }, [clearAuthState, session]);

  useEffect(() => {
    if (!session?.accessToken) {
      return;
    }

    void refreshProfile();
  }, [refreshProfile, session]);

  const login = useCallback(async (email: string, password: string) => {
    setStatus("loading");
    setErrorMessage(null);

    try {
      const nextSession = await loginRequest({ email, password });
      writeStoredSession(nextSession);
      setSession(nextSession);
      const currentUser = await fetchCurrentUser(nextSession.accessToken);
      setUser(currentUser);
      setStatus("authenticated");
    } catch (error) {
      clearStoredSession();
      setSession(null);
      setUser(null);
      setStatus("anonymous");
      setErrorMessage(
        error instanceof Error ? error.message : "Nao foi possivel fazer login.",
      );
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest(session?.refreshToken ?? null);
    } catch {
      // Ignore logout request failures; local cleanup still must happen.
    } finally {
      clearAuthState(true);
    }
  }, [clearAuthState, session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      errorMessage,
      isAuthenticated: status === "authenticated" && user !== null,
      login,
      logout,
      refreshProfile,
      session,
      status,
      user,
    }),
    [errorMessage, login, logout, refreshProfile, session, status, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider.");
  }

  return context;
}
