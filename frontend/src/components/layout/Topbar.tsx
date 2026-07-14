import { Button } from "../ui/Button";
import { CompanyDropdown } from "../selectors/CompanyDropdown";
import { PeriodDropdown } from "../selectors/PeriodDropdown";

type TopbarProps = {
  onLogout: () => Promise<void>;
  onToggleSidebar: () => void;
  title: string;
};

export function Topbar({ onLogout, onToggleSidebar, title }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-title">
        <button className="menu-button" onClick={onToggleSidebar} type="button">
          Menu
        </button>
        <div>
          <span className="eyebrow">Lumen Fiscal Cockpit</span>
          <h2>{title}</h2>
        </div>
      </div>

      <div className="topbar-controls">
        <CompanyDropdown />
        <PeriodDropdown />
        <Button
          className="logout-button"
          onClick={() => {
            void onLogout();
          }}
          variant="secondary"
        >
          Sair
        </Button>
      </div>
    </header>
  );
}
