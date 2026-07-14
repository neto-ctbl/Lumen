import { useState } from "react";

import { ContextStrip } from "../components/layout/ContextStrip";
import { Sidebar } from "../components/layout/Sidebar";
import { Topbar } from "../components/layout/Topbar";
import { renderLumenRoute, getLumenRouteTitle } from "./lumenRoutes";
import { LumenUiProvider } from "../stores/lumenUiStore";
import { useAuth } from "../stores/authStore";

type LumenShellProps = {
  navigate: (to: string, options?: { replace?: boolean }) => void;
  onLogoutComplete: () => void;
  pathname: string;
};

export function LumenShell({ navigate, onLogoutComplete, pathname }: LumenShellProps) {
  const { logout, user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const title = getLumenRouteTitle(pathname);

  async function handleLogout() {
    await logout();
    onLogoutComplete();
  }

  return (
    <LumenUiProvider navigate={navigate} pathname={pathname}>
      <main className="portal-shell">
        <Sidebar
          mobileOpen={mobileOpen}
          onNavigate={(to) => navigate(to)}
          onToggleMobile={() => setMobileOpen((current) => !current)}
        />

        <section className="shell-content">
          <Topbar
            onLogout={handleLogout}
            onToggleSidebar={() => setMobileOpen((current) => !current)}
            title={title}
          />
          <ContextStrip />

          <div className="user-strip">
            <span>{user?.full_name ?? user?.email ?? "Nao identificado"}</span>
            <small>
              {user?.organization.name ?? "Sem organizacao"} · {user?.global_role ?? "Sem role"}
            </small>
          </div>

          {renderLumenRoute({
            pathname,
            onNavigate: (to) => navigate(to),
          })}
        </section>
      </main>
    </LumenUiProvider>
  );
}
