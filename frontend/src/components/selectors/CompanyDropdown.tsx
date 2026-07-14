import { useState } from "react";

import { useLumenUi } from "../../stores/lumenUiStore";
import { formatCnpj, formatCompanyName } from "../../utils/formatters";

export function CompanyDropdown() {
  const {
    companies,
    companySearch,
    loadingSelectors,
    selectedCompany,
    setCompanySearch,
    setSelectedCompanyId,
  } = useLumenUi();
  const [open, setOpen] = useState(false);

  return (
    <div className="selector">
      <button
        aria-label="Selecionar empresa"
        aria-expanded={open}
        className="selector-trigger"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <span className="selector-label">Empresa</span>
        <strong>
          {selectedCompany
            ? formatCompanyName(selectedCompany.nome_fantasia ?? selectedCompany.razao_social)
            : "Selecionar"}
        </strong>
      </button>

      {open ? (
        <div className="selector-panel">
          <input
            aria-label="Buscar empresa"
            className="selector-search"
            onChange={(event) => setCompanySearch(event.target.value)}
            placeholder="Buscar por razao social, apelido ou CNPJ"
            value={companySearch}
          />

          <div className="selector-list">
            {loadingSelectors ? <span className="selector-empty">Carregando empresas...</span> : null}
            {!loadingSelectors && companies.length === 0 ? (
              <span className="selector-empty">Nenhuma empresa ativa encontrada.</span>
            ) : null}
            {companies.map((company) => (
              <button
                key={company.id}
                className="selector-option"
                onClick={() => {
                  setSelectedCompanyId(company.id);
                  setOpen(false);
                }}
                type="button"
              >
                <strong>{formatCompanyName(company.razao_social)}</strong>
                <small>{formatCnpj(company.cnpj)}</small>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
