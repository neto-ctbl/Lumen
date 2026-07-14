import { useLumenUi } from "../../stores/lumenUiStore";

const navItems = [
  { label: "Painel", path: "/lumen/painel" },
  { label: "Cockpit", path: "/lumen/cockpit" },
  { label: "Empresas", path: "/lumen/empresas" },
  { label: "Envios", path: "/lumen/envios" },
  { label: "Evidências", path: "/lumen/evidencias" },
  { label: "Divergências", path: "/lumen/divergencias" },
  { label: "Parcelamentos", path: "/lumen/parcelamentos" },
  { label: "Integrações", path: "/lumen/integracoes" },
];

type SidebarProps = {
  mobileOpen: boolean;
  onNavigate: (to: string) => void;
  onToggleMobile: () => void;
};

export function Sidebar({ mobileOpen, onNavigate, onToggleMobile }: SidebarProps) {
  const { currentView } = useLumenUi();

  return (
    <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
      <div className="sidebar-brand">
        <span className="sidebar-mark">L</span>
        <div>
          <strong>Lumen</strong>
          <small>Fiscal read-only</small>
        </div>
        <button className="sidebar-close" onClick={onToggleMobile} type="button">
          Fechar
        </button>
      </div>

      <nav className="sidebar-nav" aria-label="Rotas principais">
        {navItems.map((item) => {
          const active = currentView !== "empresa"
            ? item.path.endsWith(currentView)
            : item.path === "/lumen/empresas" && currentView === "empresa";

          return (
            <button
              key={item.path}
              className={`sidebar-link ${active ? "sidebar-link-active" : ""}`}
              onClick={() => {
                onNavigate(item.path);
                onToggleMobile();
              }}
              type="button"
            >
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
