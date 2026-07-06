const routeTitle = (pathname: string): string => {
  if (pathname.startsWith("/lumen/painel")) {
    return "Painel";
  }

  return "Inicial";
};

export function LumenShell() {
  const currentPath = window.location.pathname;
  const title = routeTitle(currentPath);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <span className="eyebrow">Lumen Fiscal Cockpit</span>
        <h1>{title}</h1>
        <p>
          Base tecnica minima do Stage S1 com frontend Vite, backend FastAPI,
          Docker Compose local e healthchecks operacionais.
        </p>
        <div className="status-grid">
          <article>
            <strong>Frontend</strong>
            <span>Vite em 5175</span>
          </article>
          <article>
            <strong>API</strong>
            <span>FastAPI em 8000</span>
          </article>
          <article>
            <strong>Infra</strong>
            <span>Postgres 5435 e Redis 6382</span>
          </article>
        </div>
        <code className="route-pill">{currentPath || "/lumen/painel"}</code>
      </section>
    </main>
  );
}
