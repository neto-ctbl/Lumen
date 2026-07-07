import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";

import { LumenShell } from "./app/LumenShell";
import { LoginPage } from "./features/auth/LoginPage";
import { ProtectedRoute } from "./features/auth/ProtectedRoute";
import { AuthProvider, useAuth } from "./stores/authStore";
import "./styles/tokens.css";

type NavigateOptions = {
  replace?: boolean;
};

function RedirectTo({
  navigate,
  options,
  to,
}: {
  navigate: (to: string, options?: NavigateOptions) => void;
  options?: NavigateOptions;
  to: string;
}) {
  useEffect(() => {
    navigate(to, options);
  }, [navigate, options, to]);

  return null;
}

function AppRoutes({
  navigate,
  pathname,
}: {
  navigate: (to: string, options?: NavigateOptions) => void;
  pathname: string;
}) {
  const { isAuthenticated } = useAuth();

  if (pathname === "/login") {
    return isAuthenticated ? (
      <RedirectTo navigate={navigate} options={{ replace: true }} to="/lumen/painel" />
    ) : (
      <LoginPage onLoginSuccess={() => navigate("/lumen/painel", { replace: true })} />
    );
  }

  if (pathname.startsWith("/lumen/painel")) {
    return (
      <ProtectedRoute onReject={() => navigate("/login", { replace: true })}>
        <LumenShell onLogoutComplete={() => navigate("/login", { replace: true })} />
      </ProtectedRoute>
    );
  }

  return (
    <RedirectTo
      navigate={navigate}
      options={{ replace: true }}
      to={isAuthenticated ? "/lumen/painel" : "/login"}
    />
  );
}

function App() {
  const [pathname, setPathname] = useState(() => window.location.pathname || "/");

  useEffect(() => {
    const handlePopState = () => setPathname(window.location.pathname || "/");
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(to: string, options: NavigateOptions = {}) {
    if (options.replace) {
      window.history.replaceState({}, "", to);
    } else if (window.location.pathname !== to) {
      window.history.pushState({}, "", to);
    }

    setPathname(window.location.pathname || "/");
  }

  return (
    <AuthProvider onUnauthorized={() => navigate("/login", { replace: true })}>
      <AppRoutes navigate={navigate} pathname={pathname} />
    </AuthProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
