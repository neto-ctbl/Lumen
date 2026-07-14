import { useEffect, useMemo, useState } from "react";

import { Card } from "../../components/ui/Card";
import { fetchCompanies } from "../../services/lumenService";
import { useLumenUi } from "../../stores/lumenUiStore";
import type { CompanySummary } from "../../types/company";
import { formatCnpj, formatCompanyName, formatRegimeLabel, ieDisplay } from "../../utils/formatters";

type CompaniesPageProps = {
  onOpenCompany: (to: string) => void;
};

export function CompaniesPage({ onOpenCompany }: CompaniesPageProps) {
  const { selectedPeriod, setSelectedCompanyId } = useLumenUi();
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    void fetchCompanies(search).then((response) => setCompanies(response.items));
  }, [search]);

  const companyCountLabel = useMemo(() => {
    if (companies.length === 1) {
      return "1 empresa exibida";
    }
    return `${companies.length} empresas exibidas`;
  }, [companies.length]);

  return (
    <div className="page-grid companies-page">
      <div className="companies-summary">{companyCountLabel}</div>

      <Card className="companies-toolbar">
        <div className="companies-toolbar-left">
          <label className="companies-search">
            <span>Buscar empresas</span>
            <input
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Razao social, apelido ou CNPJ"
              type="search"
              value={search}
            />
          </label>
        </div>

        <div className="companies-toolbar-actions">
          <button className="button button-secondary" type="button">
            Score
          </button>
          <button className="button button-secondary" type="button">
            Filtros avancados
          </button>
        </div>
      </Card>

      <section className="companies-grid">
        {companies.map((company) => (
          <article className="company-card" key={company.id}>
            <div className="company-card-top">
              <div className="company-card-avatar">
                {company.nome_fantasia?.slice(0, 2).toUpperCase() ??
                  company.razao_social.slice(0, 2).toUpperCase()}
              </div>
              <div className="company-card-heading">
                <strong>{formatCompanyName(company.razao_social)}</strong>
                <span>{formatCompanyName(company.nome_fantasia ?? company.apelido_pasta ?? "Empresa sem apelido")}</span>
              </div>
              <div className="company-card-score">{company.active ? "10" : "00"}</div>
            </div>

            <div className="company-card-grid">
              <div className="company-card-field">
                <span>CNPJ</span>
                <strong>{formatCnpj(company.cnpj)}</strong>
              </div>
              <div className="company-card-field">
                <span>Município</span>
                <strong>{formatCompanyName(company.municipio)}</strong>
              </div>
              <div className="company-card-field">
                <span>Inscricao estadual</span>
                <strong>{ieDisplay(company.inscricao_estadual)}</strong>
              </div>
              <div className="company-card-field">
                <span>Regime</span>
                <strong>{formatRegimeLabel(company.regime_label)}</strong>
              </div>
            </div>

            <div className="company-card-footer">
              <div className="company-card-badges">
                <span className="company-pill company-pill-dark">Ações</span>
                <span className="company-pill">Read-only</span>
                <span className="company-pill">{company.active ? "Ativa" : "Inativa"}</span>
              </div>
              <button
                className="company-card-open"
                onClick={() => {
                  setSelectedCompanyId(company.id);
                  onOpenCompany(`/lumen/empresa/${company.id}?companyId=${company.id}&period=${selectedPeriod}`);
                }}
                type="button"
              >
                ›
              </button>
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
