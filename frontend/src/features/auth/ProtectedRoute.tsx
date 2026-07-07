import { PropsWithChildren, useEffect } from "react";

import { useAuth } from "../../stores/authStore";

type ProtectedRouteProps = PropsWithChildren<{
  onReject: () => void;
}>;

export function ProtectedRoute({ children, onReject }: ProtectedRouteProps) {
  const { isAuthenticated, status } = useAuth();

  useEffect(() => {
    if (status !== "loading" && !isAuthenticated) {
      onReject();
    }
  }, [isAuthenticated, onReject, status]);

  if (status === "loading") {
    return (
      <main className="app-shell">
        <section className="hero-card auth-card">
          <span className="eyebrow">Lumen Auth Bridge</span>
          <h1>Validando sessao</h1>
          <p>Conferindo usuario, perfil global e organizacao ativa.</p>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
