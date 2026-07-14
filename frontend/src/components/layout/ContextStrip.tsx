import { useLumenUi } from "../../stores/lumenUiStore";
import { formatCnpj, formatCompanyName, formatCompetencia, formatRegimeLabel, ieDisplay } from "../../utils/formatters";
import { Badge } from "../ui/Badge";

export function ContextStrip() {
  const { selectedCompany, selectedPeriod } = useLumenUi();

  return (
    <section className="context-strip">
      <div>
        <span className="context-label">Empresa</span>
        <strong>{selectedCompany ? formatCompanyName(selectedCompany.razao_social) : "Nenhuma empresa ativa"}</strong>
      </div>
      <div>
        <span className="context-label">CNPJ / IE</span>
        <strong>
          {selectedCompany ? `${formatCnpj(selectedCompany.cnpj)} / ${ieDisplay(selectedCompany.inscricao_estadual)}` : "-"}
        </strong>
      </div>
      <div>
        <span className="context-label">Competência</span>
        <strong>{selectedPeriod ? formatCompetencia(selectedPeriod) : "Sem competência"}</strong>
      </div>
      <div>
        <span className="context-label">Regime</span>
        <Badge tone="muted">{formatRegimeLabel(selectedCompany?.regime_label)}</Badge>
      </div>
    </section>
  );
}
