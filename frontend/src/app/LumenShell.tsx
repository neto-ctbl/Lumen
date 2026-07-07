import { useAuth } from "../stores/authStore";

const routeTitle = (pathname: string): string => {
  if (pathname.startsWith("/lumen/painel")) {
    return "Painel";
  }

  return "Portal";
};

type LumenShellProps = {
  onLogoutComplete: () => void;
};

export function LumenShell({ onLogoutComplete }: LumenShellProps) {
  const { logout, user } = useAuth();
  const currentPath = window.location.pathname;
  const title = routeTitle(currentPath);

  async function handleLogout() {
    await logout();
    onLogoutComplete();
  }

  return (
    <main className="app-shell">
      <section className="hero-card portal-card">
        <div className="portal-topbar">
          <div>
            <span className="eyebrow">Lumen Fiscal Cockpit</span>
            <h1>{title}</h1>
          </div>

          <button className="secondary-button" onClick={() => void handleLogout()} type="button">
            Sair
          </button>
        </div>

        <p>
          Ponte minima de autenticacao do S3.1 conectada ao backend JWT do Lumen,
          preservando o shell atual enquanto as telas fiscais reais continuam fora do
          escopo.
        </p>

        <div className="status-grid identity-grid">
          <article>
            <strong>Usuario</strong>
            <span>{user?.full_name ?? user?.email ?? "Nao identificado"}</span>
          </article>
          <article>
            <strong>Email</strong>
            <span>{user?.email ?? "Nao identificado"}</span>
          </article>
          <article>
            <strong>Role global</strong>
            <span>{user?.global_role ?? "Nao identificado"}</span>
          </article>
          <article>
            <strong>Organizacao ativa</strong>
            <span>{user?.organization.name ?? "Nao identificada"}</span>
          </article>
        </div>

        <div className="status-grid">
          <article>
            <strong>Frontend</strong>
            <span>Vite em 5175 com rota /login</span>
          </article>
          <article>
            <strong>API</strong>
            <span>FastAPI em 8000 com /api/v1/auth/me</span>
          </article>
          <article>
            <strong>Tenant</strong>
            <span>{user?.organization.slug ?? "Sem tenant ativo"}</span>
          </article>
        </div>

        <code className="route-pill">{currentPath || "/lumen/painel"}</code>
      </section>
    </main>
  );
}
