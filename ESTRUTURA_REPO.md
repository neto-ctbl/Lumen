# Estrutura inicial esperada do repositório Lumen

Data de referência: 2026-08-20

Este documento descreve a organização inicial recomendada para o monorepo do Lumen. A estrutura foi pensada para facilitar trabalho incremental com Codex, separando backend, frontend, agente local, infra, documentação e scripts operacionais.

## Árvore esperada

## Observação sobre o Stage S1

A árvore completa abaixo é o alvo evolutivo do monorepo, não a exigência física imediata do primeiro patch.

No Stage S1 existe apenas o subconjunto mínimo para:

- infraestrutura local com PostgreSQL e Redis;
- backend FastAPI mínimo;
- worker stub;
- frontend React/Vite mínimo;
- scripts PowerShell de desenvolvimento;
- smoke E2E inicial.

Os demais diretórios e arquivos da árvore completa devem surgir nos stages posteriores, conforme `PLANO_DESENVOLVIMENTO.md`.

## Portas locais reservadas do Lumen no S1

- API FastAPI: `8000`
- Frontend Vite: `5175`
- PostgreSQL host: `5435`
- Redis host: `6382`

O `infra/docker-compose.yml` do Lumen deve definir `name: lumen` para evitar conflito de project name com outros projetos locais.

```txt
lumen/
├─ .env.example
├─ .gitignore
├─ README.md
├─ requirements.txt
├─ ESTRUTURA_REPO.md
├─ PLANO_DESENVOLVIMENTO.md
│
├─ backend/
│  ├─ alembic.ini
│  ├─ alembic/
│  │  ├─ env.py
│  │  ├─ script.py.mako
│  │  └─ versions/
│  │
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ main.py
│  │  │
│  │  ├─ api/
│  │  │  ├─ __init__.py
│  │  │  └─ v1/
│  │  │     ├─ __init__.py
│  │  │     ├─ api.py
│  │  │     └─ endpoints/
│  │  │        ├─ auth.py
│  │  │        ├─ health.py
│  │  │        ├─ worker.py
│  │  │        ├─ companies.py
│  │  │        ├─ periods.py
│  │  │        ├─ dashboard.py
│  │  │        ├─ cockpit.py
│  │  │        ├─ deliveries.py
│  │  │        ├─ evidences.py
│  │  │        ├─ divergences.py
│  │  │        ├─ installments.py
│  │  │        ├─ integrations.py
│  │  │        └─ webhooks/
│  │  │           ├─ econtrole.py
│  │  │           └─ acessorias.py
│  │  │
│  │  ├─ core/
│  │  │  ├─ config.py
│  │  │  ├─ security.py
│  │  │  ├─ logging.py
│  │  │  ├─ enums.py
│  │  │  ├─ periods.py
│  │  │  ├─ cnpj.py
│  │  │  └─ paths.py
│  │  │
│  │  ├─ db/
│  │  │  ├─ base.py
│  │  │  ├─ session.py
│  │  │  └─ seed.py
│  │  │
│  │  ├─ models/
│  │  │  ├─ organization.py
│  │  │  ├─ user.py
│  │  │  ├─ external_company.py
│  │  │  ├─ company_activity_type.py
│  │  │  ├─ fiscal_period.py
│  │  │  ├─ fiscal_obligation.py
│  │  │  ├─ fiscal_obligation_rule.py
│  │  │  ├─ fiscal_obligation_status.py
│  │  │  ├─ fiscal_evidence.py
│  │  │  ├─ fiscal_alert.py
│  │  │  ├─ fiscal_installment.py
│  │  │  ├─ integration_account.py
│  │  │  ├─ integration_sync_run.py
│  │  │  ├─ watcher_file_event.py
│  │  │  ├─ econet_cnae_cache.py
│  │  │  ├─ sittax_company_snapshot.py
│  │  │  ├─ sittax_apuracao_snapshot.py
│  │  │  ├─ sittax_difal_snapshot.py
│  │  │  ├─ sittax_fiscal_document_snapshot.py
│  │  │  ├─ sittax_task_snapshot.py
│  │  │  ├─ acessorias_company_snapshot.py
│  │  │  ├─ acessorias_delivery_snapshot.py
│  │  │  ├─ dominio_payroll.py
│  │  │  └─ audit_log.py
│  │  │
│  │  ├─ schemas/
│  │  │  ├─ auth.py
│  │  │  ├─ company.py
│  │  │  ├─ period.py
│  │  │  ├─ dashboard.py
│  │  │  ├─ cockpit.py
│  │  │  ├─ delivery.py
│  │  │  ├─ evidence.py
│  │  │  ├─ divergence.py
│  │  │  ├─ installment.py
│  │  │  ├─ integration.py
│  │  │  └─ worker.py
│  │  │
│  │  ├─ services/
│  │  │  ├─ audit.py
│  │  │  ├─ auth.py
│  │  │  ├─ periods.py
│  │  │  ├─ companies.py
│  │  │  ├─ obligations.py
│  │  │  ├─ evidences.py
│  │  │  ├─ reconciliation.py
│  │  │  ├─ alerts.py
│  │  │  ├─ dctfweb_origins.py
│  │  │  ├─ factor_r.py
│  │  │  ├─ installments.py
│  │  │  ├─ pdf/
│  │  │  │  ├─ text_extract.py
│  │  │  │  ├─ classify_tax.py
│  │  │  │  ├─ parse_das.py
│  │  │  │  ├─ parse_darf.py
│  │  │  │  ├─ parse_icms.py
│  │  │  │  ├─ parse_iss.py
│  │  │  │  ├─ parse_installment.py
│  │  │  │  └─ parse_dominio_payroll.py
│  │  │  └─ integrations/
│  │  │     ├─ econtrole/
│  │  │     │  ├─ client.py
│  │  │     │  ├─ mapper.py
│  │  │     │  ├─ errors.py
│  │  │     │  └─ sync.py
│  │  │     ├─ acessorias/
│  │  │     │  ├─ client.py
│  │  │     │  ├─ mapper.py
│  │  │     │  └─ sync.py
│  │  │     ├─ sittax/
│  │  │     │  ├─ client.py
│  │  │     │  ├─ session.py
│  │  │     │  ├─ mapper.py
│  │  │     │  └─ sync.py
│  │  │     ├─ dominio/
│  │  │     │  ├─ payroll_importer.py
│  │  │     │  └─ mapper.py
│  │  │     └─ econet/
│  │  │        ├─ assisted_session.py
│  │  │        ├─ client.py
│  │  │        ├─ parser.py
│  │  │        └─ cache.py
│  │  │
│  │  └─ worker/
│  │     ├─ __init__.py
│  │     ├─ queue.py
│  │     ├─ runner.py
│  │     ├─ jobs.py
│  │     └─ tasks/
│  │        ├─ sync_econtrole.py
│  │        ├─ sync_acessorias.py
│  │        ├─ sync_sittax.py
│  │        ├─ scan_fiscal_files.py
│  │        ├─ process_pdf_evidences.py
│  │        ├─ import_dominio_payroll.py
│  │        ├─ enrich_cnaes_econet.py
│  │        ├─ reconcile_fiscal_period.py
│  │        ├─ scan_dctfweb_origins.py
│  │        ├─ scan_installment_risks.py
│  │        └─ generate_fiscal_alerts.py
│  │
│  ├─ scripts/
│  │  ├─ check_sittax_connection.py
│  │  ├─ create_initial_admin.py
│  │  ├─ seed_obligations.py
│  │  ├─ seed_obligation_rules.py
│  │  ├─ seed_periods.py
│  │  ├─ sync_acessorias_deliveries.py
│  │  ├─ sync_econtrole_companies.py
│  │  ├─ sync_sittax_companies.py
│  │  ├─ sync_sittax_apuracoes.py
│  │  └─ sync_sittax_operational.py
│  │
│  └─ tests/
│     ├─ conftest.py
│     ├─ test_health.py
│     ├─ test_auth.py
│     ├─ test_companies_sync.py
│     ├─ test_acessorias_sync.py
│     ├─ test_reconciliation.py
│     ├─ test_pdf_parsers.py
│     ├─ test_dctfweb_origins.py
│     ├─ test_installments.py
│     └─ test_worker.py
│
├─ frontend/
│  ├─ package.json
│  ├─ package-lock.json
│  ├─ vite.config.ts
│  ├─ tsconfig.json
│  ├─ index.html
│  ├─ playwright.config.ts
│  ├─ src/
│  │  ├─ main.tsx
│  │  ├─ app/
│  │  │  ├─ LumenShell.tsx
│  │  │  ├─ lumenRoutes.tsx
│  │  │  └─ queryClient.ts
│  │  │
│  │  ├─ components/
│  │  │  ├─ layout/
│  │  │  │  ├─ Sidebar.tsx
│  │  │  │  ├─ Topbar.tsx
│  │  │  │  └─ ContextStrip.tsx
│  │  │  ├─ selectors/
│  │  │  │  ├─ CompanyDropdown.tsx
│  │  │  │  └─ PeriodDropdown.tsx
│  │  │  └─ ui/
│  │  │     ├─ Badge.tsx
│  │  │     ├─ Button.tsx
│  │  │     ├─ Card.tsx
│  │  │     ├─ EmptyState.tsx
│  │  │     ├─ Hero.tsx
│  │  │     ├─ KpiCard.tsx
│  │  │     ├─ Progress.tsx
│  │  │     └─ Table.tsx
│  │  │
│  │  ├─ features/
│  │  │  ├─ dashboard/
│  │  │  │  ├─ DashboardPage.tsx
│  │  │  │  ├─ DashboardKpis.tsx
│  │  │  │  └─ UrgentActions.tsx
│  │  │  ├─ cockpit/
│  │  │  │  ├─ CockpitPage.tsx
│  │  │  │  ├─ CockpitFilters.tsx
│  │  │  │  └─ CompanyCockpitTable.tsx
│  │  │  ├─ company/
│  │  │  │  ├─ CompanyPage.tsx
│  │  │  │  ├─ CompanyHero.tsx
│  │  │  │  ├─ CompanyRegistrationCard.tsx
│  │  │  │  ├─ CompanyObligationsTable.tsx
│  │  │  │  ├─ DctfwebOriginCard.tsx
│  │  │  │  ├─ EvidenceTimeline.tsx
│  │  │  │  └─ FactorRCard.tsx
│  │  │  ├─ deliveries/
│  │  │  │  ├─ DeliveriesPage.tsx
│  │  │  │  ├─ DeliverySummary.tsx
│  │  │  │  └─ DeliveryTable.tsx
│  │  │  ├─ evidences/
│  │  │  │  ├─ EvidencesPage.tsx
│  │  │  │  └─ EvidenceCard.tsx
│  │  │  ├─ divergences/
│  │  │  │  ├─ DivergencesPage.tsx
│  │  │  │  └─ DivergenceCard.tsx
│  │  │  ├─ installments/
│  │  │  │  ├─ InstallmentsPage.tsx
│  │  │  │  └─ InstallmentsTable.tsx
│  │  │  └─ integrations/
│  │  │     ├─ IntegrationsPage.tsx
│  │  │     ├─ IntegrationHealthCard.tsx
│  │  │     └─ JobsGrid.tsx
│  │  │
│  │  ├─ services/
│  │  │  ├─ apiClient.ts
│  │  │  ├─ authService.ts
│  │  │  ├─ companiesService.ts
│  │  │  ├─ dashboardService.ts
│  │  │  ├─ deliveriesService.ts
│  │  │  ├─ evidencesService.ts
│  │  │  ├─ divergencesService.ts
│  │  │  ├─ installmentsService.ts
│  │  │  └─ integrationsService.ts
│  │  │
│  │  ├─ stores/
│  │  │  ├─ lumenUiStore.ts
│  │  │  └─ authStore.ts
│  │  │
│  │  ├─ styles/
│  │  │  ├─ tokens.css
│  │  │  ├─ global.css
│  │  │  └─ components.css
│  │  │
│  │  └─ types/
│  │     ├─ company.ts
│  │     ├─ fiscal.ts
│  │     └─ integration.ts
│  │
│  └─ tests_e2e/
│     ├─ auth.spec.ts
│     ├─ shell.spec.ts
│     ├─ dashboard.spec.ts
│     ├─ cockpit.spec.ts
│     ├─ deliveries.spec.ts
│     └─ company.spec.ts
│
├─ agent/
│  ├─ watcher/
│  │  ├─ __init__.py
│  │  ├─ company_resolver.py
│  │  ├─ config.py
│  │  ├─ file_detector.py
│  │  ├─ hash.py
│  │  ├─ path_contract.py
│  │  ├─ payload_builder.py
│  │  └─ period_resolver.py
│  ├─ parsers/
│  │  ├─ __init__.py
│  │  ├─ file_name_classifier.py
│  │  └─ pdf_text_probe.py
│  └─ __init__.py
│
├─ infra/
│  ├─ docker-compose.yml
│  ├─ postgres/
│  │  └─ init/
│  └─ redis/
│
├─ scripts/
│  ├─ dev/
│  │  ├─ run_backend.ps1
│  │  ├─ run_frontend.ps1
│  │  └─ run_worker.ps1
│  └─ ops/
│     ├─ run_reconciliation_period.ps1
│     ├─ run_file_scan.ps1
│     ├─ run_acessorias_sync.ps1
│     └─ run_econtrole_reconcile.ps1
│
├─ docs/
│  ├─ ACESSORIAS_CONTRACT.md
│  ├─ DECISOES.md
│  ├─ RISCOS.md
│  ├─ SECURITY.md
│  ├─ SITTAX_CONTEXT_HANDOFF.md
│  ├─ SITTAX_OBSERVED_CONTRACT.md
│  └─ examples/
│     ├─ README.md
│     ├─ sample_acessorias_delivery.json
│     ├─ sample_sittax_apuracao.json
│     ├─ sample_econtrole_company.json
│     └─ sample_watcher_event.json
│
├─ schemas/
│  ├─ econtrole_company.schema.json
│  ├─ acessorias_delivery.schema.json
│  ├─ sittax_apuracao.schema.json
│  ├─ sittax_company.schema.json
│  ├─ sittax_company_panel.schema.json
│  ├─ sittax_difal.schema.json
│  ├─ sittax_fiscal_document_page.schema.json
│  ├─ sittax_task_page.schema.json
│  ├─ watcher_event.schema.json
│  └─ fiscal_evidence.schema.json
│
└─ data/
   ├─ .gitkeep
   └─ examples/
      └─ README.md
```

## Materializado ate o S8.1

Arquivos e diretorios efetivamente materializados ate o fechamento do S8.1:

- `docs/ECONET_OBSERVED_CONTRACT.md`
- `backend/app/models/econet_cnae_cache.py`
- `backend/app/services/integrations/econet/`
- `backend/alembic/versions/20260721_0009_create_econet_cnae_cache.py`
- `backend/tests/fixtures/econet/`
- `backend/tests/test_econet_fixture_safety.py`
- `backend/tests/test_econet_observed_contract.py`
- `backend/tests/test_econet_parser.py`
- `backend/tests/test_econet_cache.py`
- `backend/tests/test_econet_cnae_cache_model.py`
- `backend/tests/econet_test_utils.py`

Observacao importante:

- os arquivos de sessao assistida, cliente HTTP stateful, endpoint manual, schema publico e sync operacional da Econet continuam apenas planejados e nao devem ser tratados como existentes no repositorio atual.

## Responsabilidades por pasta

### `backend/`

Contém API FastAPI, modelos, schemas, migrations, serviços de domínio, conectores de integração, regras fiscais, jobs e testes.

O backend deve ser a fonte de verdade para:

- status fiscal por empresa/competência;
- regras de conciliação;
- vínculo entre obrigação e evidência;
- origem da DCTFWeb;
- risco de parcelamento;
- cache de integrações;
- auditoria e rastreabilidade.

### `frontend/`

Contém o portal React/Vite. Deve seguir o guia visual do Lumen, mantendo tokens, estrutura de app shell, rotas e componentes reutilizáveis.

Rotas previstas:

```txt
/lumen/painel
/lumen/cockpit
/lumen/empresa/:companyId
/lumen/envios
/lumen/evidencias
/lumen/divergencias
/lumen/parcelamentos
/lumen/integracoes
```

Estado global mínimo:

```ts
type LumenUIState = {
  selectedCompany: CompanySummary | null;
  selectedPeriod: string;
  currentView: string;
  focusMode: boolean;
  filters: Record<string, unknown>;
};
```

### `agent/`

No S10.1 contem o core offline para um caminho de PDF explicitamente fornecido: configuracao lazy, guardas de path, filtro, hash streaming, sinais de pasta, hint de nome, probe `pypdf` e payload v1. Nao ha loop de watcher, cliente HTTP, banco, endpoint ou worker generico.

O futuro agente não decide conciliação final; ele gera sinais, e a autoridade permanece no backend.

### `infra/`

Contém infraestrutura local e de desenvolvimento. Inicialmente deve incluir Docker Compose com PostgreSQL e Redis.

Não versionar volumes locais.

### `scripts/`

Contém scripts de desenvolvimento e operação, especialmente PowerShell para Windows.

Scripts com credenciais locais devem usar `.env` ou arquivo `.local.*` ignorado pelo Git.

### `docs/`

Contém documentação viva do projeto. Toda decisão relevante tomada durante desenvolvimento deve entrar em `docs/DECISOES.md`.

Observações do estado atual em 2026-07-21:

- `docs/SITTAX_CONTEXT_HANDOFF.md` e `docs/SITTAX_OBSERVED_CONTRACT.md` registram a validação final do comportamento real do Sittax.
- O host `api.sittax.com.br` ficou comprovado como sessão web stateful, dependente de `cookie jar`, afinidade e ordem correta das chamadas.
- A documentação antiga que registrava ausência de cookies funcionais no Sittax ficou superada pela validação stateful de 2026-07-20.

### `schemas/`

Contém contratos JSON para payloads de integração, eventos do watcher e datasets de teste.

### `data/`

Pasta reservada para exemplos anonimizados. Arquivos fiscais reais devem ficar fora do Git.

## Convenções de nomes

### Backend

- Models SQLAlchemy no singular: `FiscalEvidence`, `FiscalObligationStatus`.
- Tabelas no plural snake_case: `fiscal_evidences`, `fiscal_obligation_statuses`.
- Services em snake_case por domínio: `reconciliation.py`, `dctfweb_origins.py`.
- Jobs em formato de verbo: `sync_acessorias_deliveries`, `scan_fiscal_files`.

### Frontend

- Componentes em PascalCase.
- Services com sufixo `Service` ou arquivo `*Service.ts`.
- Tipos em `src/types`.
- CSS global apenas para tokens, reset e componentes base; estilos específicos devem ficar junto da feature quando possível.

### Competência

- Backend/API: `YYYY-MM`, exemplo `2026-06`.
- Frontend: exibir `MM/YYYY`, exemplo `06/2026`.

### Inscrição Estadual

- Persistir valor bruto quando disponível.
- Exibir `ISENTO` quando vazio ou nulo.

## Arquivos que devem existir logo no Stage S1

```txt
.gitignore
README.md
requirements.txt
ESTRUTURA_REPO.md
PLANO_DESENVOLVIMENTO.md
.env.example
infra/docker-compose.yml
backend/app/main.py
backend/app/api/v1/endpoints/health.py
frontend/package.json
frontend/src/app/LumenShell.tsx
frontend/src/styles/tokens.css
```

## Arquivos que não devem ser versionados

- `.env` e variações locais.
- Tokens, cookies, sessões assistidas e credenciais.
- Certificados `.pfx`, `.p12`, `.pem`, `.key`.
- PDFs fiscais reais.
- XMLs de notas reais.
- Relatórios reais da Domínio.
- Pastas monitoradas do `G:\EMPRESAS`.
- Resultados Playwright, coverage, logs e dumps.

## Atualizacao S2 em 2026-07-06

No estado real atual, alem do subconjunto minimo do S1, ja foram materializados os blocos tecnicos do S2:

- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/security.py`
- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/app/models/audit_log.py`
- `backend/app/services/audit.py`
- `backend/alembic.ini`
- `backend/alembic/`
- `backend/tests/`
- `pytest.ini` na raiz com `pythonpath = .`

Ainda permanecem fora de escopo neste ponto:

- autenticacao, JWT, usuarios, organizacoes e RBAC
- modelos fiscais do S4
- integracoes externas

## Atualizacao S3 em 2026-07-06

No estado real atual, alem do subconjunto minimo do S1 e da base tecnica do S2, foram materializados os blocos do S3:

- `backend/app/models/organization.py`
- `backend/app/models/user.py`
- `backend/app/models/user_organization.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/scripts/create_initial_admin.py`
- `backend/alembic/versions/20260706_0002_auth_rbac_multitenant.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_rbac.py`

Decisoes materializadas no S3:

- login por email
- RBAC global no usuario com `ADMIN`, `DEV`, `VIEW`
- multi-tenant inicial por `organizations` + `user_organizations`
- organizacao ativa do MVP vinda de `users.default_organization_id`
- `audit_log` permaneceu sem `org_id` e sem `user_id` dedicados neste stage
- healthchecks `GET /healthz` e `GET /api/v1/worker/health` permanecem publicos
- o frontend ainda nao foi protegido para preservar o smoke E2E atual

Ainda permanecem fora de escopo neste ponto:

- modelos fiscais do S4
- integracoes externas
- login visual e protecao de rotas do frontend

## Atualizacao S3.1 em 2026-07-06

No estado real atual, alem dos blocos do S3 backend, foram materializados os arquivos do bridge de autenticacao no frontend:

- `frontend/src/services/apiClient.ts`
- `frontend/src/services/authService.ts`
- `frontend/src/stores/authStore.tsx`
- `frontend/src/features/auth/LoginPage.tsx`
- `frontend/src/features/auth/ProtectedRoute.tsx`
- `frontend/scripts/run_e2e_stack.ps1`
- `frontend/tests_e2e/smoke.spec.ts` atualizado para login e logout

Decisoes materializadas no S3.1:

- `/login` publico
- `/lumen/painel` protegido
- frontend consumindo `POST /api/v1/auth/login`, `GET /api/v1/auth/me` e `POST /api/v1/auth/logout`
- `VITE_API_BASE_URL` como variavel principal com fallback legado para `VITE_LUMEN_API_BASE_URL`
- armazenamento MVP de tokens em `localStorage`, com hardening futuro pendente
- sem refresh automatico complexo neste ponto

Ainda permanecem fora de escopo neste ponto:

- modelos fiscais do S4
- telas fiscais reais do S7 e S8
- integracoes externas

## Atualizacao S4 em 2026-07-07

No estado real atual, alem dos blocos entregues no S3.1 e do microajuste S3.2, foram materializados os arquivos centrais do S4:

- `backend/app/core/enums.py`
- `backend/app/models/external_company.py`
- `backend/app/models/company_activity_type.py`
- `backend/app/models/fiscal_period.py`
- `backend/app/models/fiscal_obligation.py`
- `backend/app/models/fiscal_obligation_rule.py`
- `backend/app/models/fiscal_obligation_status.py`
- `backend/app/models/fiscal_evidence.py`
- `backend/app/models/fiscal_alert.py`
- `backend/app/models/fiscal_installment.py`
- `backend/app/models/integration_account.py`
- `backend/app/models/integration_sync_run.py`
- `backend/app/models/watcher_file_event.py`
- `backend/alembic/versions/20260706_0003_create_fiscal_core.py`
- `backend/scripts/seed_obligations.py`
- `backend/tests/test_models.py`
- `backend/tests/test_obligation_seed.py`

Tabelas materializadas no banco pelo S4:

- `external_companies`
- `company_activity_types`
- `fiscal_periods`
- `fiscal_obligations`
- `fiscal_obligation_rules`
- `fiscal_obligation_statuses`
- `fiscal_evidences`
- `fiscal_alerts`
- `fiscal_installments`
- `integration_accounts`
- `integration_sync_runs`
- `watcher_file_events`

Decisoes materializadas no S4:

- `organization_id` foi adicionado nas tabelas operacionais do nucleo fiscal para preservar o isolamento multi-tenant iniciado no S3
- `fiscal_obligations` permaneceu global com `code` unico para suportar seed padrao do produto
- `fiscal_obligation_rules.organization_id` ficou nullable para permitir regras globais do produto e futuros overrides por tenant sem abrir S5+
- `external_companies` suporta soft delete com `active = false` e `deleted_at_econtrole`
- segredos reais de integracao continuam fora do banco; `integration_accounts.credentials_ref` e apenas referencia futura

Ainda permanecem fora de escopo neste ponto:

- integracoes externas reais
- endpoints fiscais operacionais
- alteracoes de fluxo visual do frontend

## Atualizacao S4.1 em 2026-07-07

No estado real atual, foram materializados os scripts e testes logicos do micro-stage S4.1:

- `backend/scripts/seed_obligation_rules.py`
- `backend/scripts/seed_periods.py`
- `backend/tests/test_obligation_rules_seed.py`
- `backend/tests/test_period_seed.py`

Decisoes materializadas no S4.1:

- o catalogo padrao continua com `13` codigos em `fiscal_obligations`
- as regras-base ficam em `fiscal_obligation_rules` sem migration adicional, com idempotencia por chave logica no seed
- `PIS`, `COFINS` e `EFD_CONTRIBUICOES` passaram a ter regras separadas para `LUCRO_PRESUMIDO` e `LUCRO_REAL`
- as competencias fiscais sao criadas em `fiscal_periods` por organizacao e ano, com suporte a `--org-slug`
- sem `--org-slug`, o seed so aceita o caso de exatamente uma organizacao ativa e emite aviso explicito
- o S4.1 nao gera `fiscal_obligation_statuses` por empresa/competencia
- cada `condition_payload` recebeu metadados minimos de rastreabilidade normativa e marcacao `applicability_is_indicative = true`
- `backend/app/core/enums.py` passa a concentrar tambem o catalogo tecnico de regimes fiscais reconhecidos, incluindo `IMUNE_ISENTA`
- pendencia futura registrada: avaliar inclusao de `DESTDA` no catalogo estadual
- observacao documental: o S4.1 foi um micro-stage complementar de fechamento tecnico, nao um stage originalmente enumerado no plano macro
- pendencia tecnica registrada: avaliar constraint unica futura para `fiscal_obligation_rules` considerando `organization_id`, `obligation_id`, `regime`, `activity_type` e `rule_type`, porque a idempotencia atual depende de lookup na aplicacao e pode sofrer duplicidade transitoria sob execucao paralela

Ainda permanecem fora de escopo neste ponto:

- sincronizacao de empresas por eControle
- integracao Acessorias
- status operacional por empresa/competencia

## Atualizacao S5 em 2026-07-07

No estado real atual, foi materializado o espelho cadastral MVP do eControle com os seguintes arquivos:

- `backend/app/services/integrations/econtrole/__init__.py`
- `backend/app/services/integrations/econtrole/client.py`
- `backend/app/services/integrations/econtrole/mapper.py`
- `backend/app/services/integrations/econtrole/sync.py`
- `backend/app/api/v1/endpoints/webhooks/__init__.py`
- `backend/app/api/v1/endpoints/webhooks/econtrole.py`
- `backend/scripts/sync_econtrole_companies.py`
- `backend/tests/test_econtrole_mapper.py`
- `backend/tests/test_econtrole_sync.py`
- `backend/tests/test_econtrole_webhook.py`

Decisoes materializadas no S5:

- cliente HTTP simples e testavel para listagem de empresas do eControle sem acoplamento de banco
- mapper defensivo com aliases comuns, CNPJ normalizado e preservacao de `raw_econtrole`
- sync de upsert idempotente e soft delete sobre `external_companies`
- webhooks `company-upsert` e `company-delete` protegidos por `X-Lumen-Webhook-Token`
- script `backend/scripts/sync_econtrole_companies.py` com rastreio em `integration_sync_runs`
- auditoria por `record_audit_event`
- o frontend visual e o smoke E2E existente nao mudam neste stage

Ainda permanecem fora de escopo neste ponto:

- integracao Acessorias do S6
- transmissao fiscal
- telas novas de frontend

## Atualizacao S5.1 em 2026-07-08

No estado real atual, o shell fiscal read-only previsto para o portal passou a existir com:

- `backend/app/api/v1/endpoints/lumen.py`
- `backend/app/services/lumen_read_model.py`
- `backend/app/schemas/company.py`
- `backend/app/schemas/period.py`
- `backend/app/schemas/dashboard.py`
- `backend/app/schemas/cockpit.py`
- `backend/app/schemas/delivery.py`
- `backend/app/schemas/evidence.py`
- `backend/app/schemas/divergence.py`
- `backend/app/schemas/installment.py`
- `backend/app/schemas/integration.py`
- `backend/tests/test_lumen_read_endpoints.py`
- `frontend/src/app/lumenRoutes.tsx`
- `frontend/src/stores/lumenUiStore.tsx`
- `frontend/src/services/lumenService.ts`
- `frontend/src/components/layout/`
- `frontend/src/components/selectors/`
- `frontend/src/components/ui/`
- `frontend/src/features/dashboard/`
- `frontend/src/features/cockpit/`
- `frontend/src/features/company/`
- `frontend/src/features/deliveries/`
- `frontend/src/features/evidences/`
- `frontend/src/features/divergences/`
- `frontend/src/features/installments/`
- `frontend/src/features/integrations/`
- `frontend/src/styles/global.css`
- `frontend/src/styles/components.css`

Decisoes materializadas no S5.1:

- os endpoints fiscais do portal usam exclusivamente o prefixo `/api/v1/lumen`
- o roteamento continua manual, preservando o fluxo de `/login`, `ProtectedRoute`, `authStore`, `authService` e `apiClient`
- `selectedCompany`, `selectedPeriod`, `currentView`, `focusMode` e `filters` passam a existir em `lumenUiStore.tsx`
- `external_companies` e `fiscal_periods` alimentam o portal; tabelas operacionais vazias retornam KPIs zerados e listas vazias sem erro
- IE vazia continua bruta no banco e aparece como `ISENTO` apenas na interface
- o regime permanece exposto como `Aguardando Acessorias` enquanto o S6 nao existir
- nenhuma migration nova foi criada
- confirmacao explicita: o S6/Acessorias nao foi iniciado neste stage

## Atualizacao S6.0 em 2026-07-14

No estado real atual, foi materializada apenas a formalizacao documental do contrato oficial do Acessorias com:

- `docs/ACESSORIAS_CONTRACT.md`
- `docs/examples/sample_acessorias_company.json`
- `docs/examples/sample_acessorias_delivery.json`
- `schemas/acessorias_company.schema.json`
- `schemas/acessorias_delivery.schema.json`

Decisoes materializadas no S6.0:

- o Acessorias possui API oficial documentada em `https://api.acessorias.com/documentation`
- a base URL oficial e `https://api.acessorias.com`
- a autenticacao oficial usa `Authorization: Bearer <token>`
- o token deve ser gerado no proprio Sistema Acessorias pela opcao `API Token`
- o limite oficial documentado e `100` requisicoes por minuto
- nao e necessario usar DevTools, HAR ou engenharia reversa para o Acessorias
- o S6 utilizara somente operacoes de consulta
- nenhuma inclusao, edicao, transmissao ou alteracao externa faz parte do S6
- os exemplos e schemas criados sao anonimizados e derivados somente da documentacao oficial

Ainda permanecem fora de escopo neste ponto:

- cliente HTTP do Acessorias
- mapper do Acessorias
- sync de entregas e regime
- endpoint manual de sincronizacao
- migration de snapshots
- alteracao do regime exibido no portal

## Atualizacao S6.1 em 2026-07-14

No estado real atual, o Stage S6 foi materializado com:

- `backend/app/models/acessorias_company_snapshot.py`
- `backend/app/models/acessorias_delivery_snapshot.py`
- `backend/alembic/versions/20260714_0004_create_acessorias_snapshots.py`
- `backend/app/services/integrations/acessorias/__init__.py`
- `backend/app/services/integrations/acessorias/client.py`
- `backend/app/services/integrations/acessorias/mapper.py`
- `backend/app/services/integrations/acessorias/regime.py`
- `backend/app/services/integrations/acessorias/obligation_mapping.py`
- `backend/app/services/integrations/acessorias/sync.py`
- `backend/app/api/v1/endpoints/integrations/__init__.py`
- `backend/app/api/v1/endpoints/integrations/acessorias.py`
- `backend/app/schemas/acessorias.py`
- `backend/scripts/sync_acessorias_deliveries.py`
- `backend/tests/fixtures/acessorias/companies_sample.json`
- `backend/tests/fixtures/acessorias/deliveries_sample.json`
- `backend/tests/test_acessorias_client.py`
- `backend/tests/test_acessorias_mapper.py`
- `backend/tests/test_acessorias_sync.py`
- `backend/tests/test_acessorias_endpoint.py`
- `backend/tests/test_regime_precedence.py`
- `frontend/tests_e2e/integrations.spec.ts`

Decisoes materializadas no S6.1:

- a integracao Acessorias usa somente a API oficial publica e somente endpoints `GET`
- o sync inicial e serial e previsivel: empresas por `ListAll + registrationData`; entregas por empresa e intervalo mensal com `config`
- `acessorias_company_snapshots` e `acessorias_delivery_snapshots` preservam payload bruto anonimizavel e chaves externas para auditoria
- `fiscal_obligation_statuses` so e atualizado quando existe empresa local, obrigacao local mapeada e `Config.Tipo = O`
- `Config.Tipo = T` permanece apenas em snapshot
- o regime oficial do portal passa a priorizar snapshot do Acessorias quando mapeado; sem snapshot o placeholder continua `Aguardando Acessorias`
- o health de Integracoes mostra estado seguro do Acessorias sem expor token, headers ou payload bruto
- o endpoint manual `POST /api/v1/integrations/acessorias/sync` exige `ADMIN|DEV`; `VIEW` recebe `403`
- fixture mode reutiliza os mesmos mappers e servicos, sem exigir token real
- anexos, links temporarios, mutacoes externas, watcher e conciliacao S11 permanecem fora do escopo

Observacao estrutural importante:

- `backend/app/db/base.py` nao exigiu alteracao para o S6 porque o Alembic ja importa `backend.app.models`, e os novos models foram exportados em `backend/app/models/__init__.py`

## Atualizacao S6.2 em 2026-07-30

Arquivos materializados no S6.2:

- `backend/app/services/integrations/acessorias/backfill.py`
- `backend/scripts/backfill_acessorias.py`
- `backend/tests/test_acessorias_backfill.py`
- `backend/tests/test_backfill_acessorias_script.py`
- refinamentos adicionais em `backend/app/services/integrations/acessorias/regime.py`, `mapper.py`, `sync.py` e `backend/scripts/sync_acessorias_deliveries.py`

Decisoes materializadas no S6.2:

- o regime tributario atual oficial do Lumen e resolvido pelo `regime_canonical` de `acessorias_company_snapshots`
- `external_companies` permanece como espelho cadastral do eControle e nao recebeu coluna, tabela auxiliar nem historico de regime
- o backfill do Acessorias foi separado em uma fase cadastral unica e uma fase serial de entregas por competencia
- `integration_sync_runs` continua sendo a trilha de rastreabilidade, agora com metadata de backfill por competencia
- o processo pode ser reiniciado desde o inicio por idempotencia, sem checkpoint extra e sem `--resume` heuristico
- o S6.2 reutiliza apenas os endpoints `GET` oficiais do Acessorias e nao baixa anexos
- o mapeamento de regime passou a cobrir labels reais do Acessorias, incluindo `Filial - Simples Nacional`
- `Filial - Regime Normal` passou a herdar o regime canonico da mesma raiz de CNPJ quando houver um unico candidato mapeado
- `EntGuiaLida` passou a ser normalizado para codigos curtos compativeis com o schema atual
- `--fiscal-only` passou a existir como filtro opcional de entregas no sync mensal e no backfill

Confirmacoes de escopo do S6.2:

- nenhuma migration nova foi criada
- nenhuma tabela nova foi criada
- `external_companies` nao foi alterada
- nenhuma alteracao de frontend foi realizada
- nenhuma transmissao fiscal foi implementada

## Fechamento operacional S6.2 em 2026-08-03

Validacoes registradas no estado real do repositorio:

- `python -m backend.scripts.backfill_acessorias --org-slug neto-contabilidade --from-period 2026-01 --to-period 2026-07`
- resumo final do backfill com `status = SUCCESS`
- conferencia SQL de cobertura cadastral em `acessorias_company_snapshots`
- conferencia SQL de cobertura por competencia em `acessorias_delivery_snapshots`
- conferencia SQL de `fiscal_obligation_statuses` com `last_source = 'ACESSORIAS_API'`
- consulta SQL de duplicidades por `organization_id + external_company_id + external_delivery_id`

Resultados operacionais principais:

- `periods_success = 7` e `periods_failed = 0`
- `companies_received = 221`, `companies_matched = 218`, `companies_unmatched = 3`
- `223` snapshots cadastrais ao final, com `218` empresas locais vinculadas e `5` regimes mapeados na conferencia SQL
- `deliveries_received = 10999` e `delivery_snapshots_created = 10999`
- `statuses_created = 196` e `tasks_skipped = 328`
- `integration_sync_runs` reais do backfill criados para as competencias `2026-01` a `2026-07`, com `run_id` de `101` a `107`
- a consulta de duplicidades retornou `0` linhas

Complemento de fechamento S6.2 em 2026-08-04:

- aliases reais de regime do Acessorias cobertos em teste automatizado, incluindo labels longos de Simples, Lucro Presumido, Lucro Real e filiais
- heranca segura de regime para `Filial - Regime Normal` validada por teste com matriz e filial da mesma raiz de CNPJ
- normalizacao de `EntGuiaLida` validada para evitar `StringDataRightTruncation` em `guide_read_status`
- filtro opcional `--fiscal-only` validado em sync e backfill sem alterar o comportamento padrao quando a flag nao e usada
- suite impactada do Acessorias reexecutada com `29 passed`

Rerun real complementar S6.2 em 2026-08-04:

- `python -m backend.scripts.backfill_acessorias --org-slug neto-contabilidade --from-period 2026-01 --to-period 2026-07 --only-active --fiscal-only`
- `integration_sync_runs` reais do rerun criados para as competencias `2026-01` a `2026-07`, com `run_id` de `116` a `122`
- rerun idempotente confirmado com `delivery_snapshots_created = 0` e apenas `delivery_snapshots_updated` no intervalo
- o filtro `--fiscal-only` registrou `deliveries_filtered_out` em todas as competencias processadas
- a conferencia final de regimes mostrou somente canonicos mapeados: `SIMPLES_NACIONAL`, `LUCRO_PRESUMIDO`, `LUCRO_REAL` e `IMUNE_ISENTA`
- os exemplos reais de `Filial - Regime Normal` e `Filial - Simples Nacional` ficaram persistidos com o canonico esperado

## Fechamento S6 em 2026-07-15

Validacoes finais registradas no estado real do repositorio:

- `docker compose -f .\infra\docker-compose.yml up -d`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
- suites backend do S6 e da regressao do S5 executadas com sucesso
- `.\.venv\Scripts\python.exe -m ruff check .\backend`
- schema das tabelas `acessorias_company_snapshots` e `acessorias_delivery_snapshots` conferido via `psql`
- fixture sync executado duas vezes, confirmando idempotencia de snapshots e runs
- login manual `ADMIN` confirmado no backend local
- endpoint `POST /api/v1/integrations/acessorias/sync` validado em `dry_run`
- validacao real da API oficial confirmada de forma segura por empresa e por cadastro/regime

Observacoes operacionais do fechamento:

- o E2E da tela `Integracoes` passou na suite local, mas a execucao manual pode parecer parada enquanto `run_e2e_stack.ps1` sobe backend dedicado, seed e frontend em portas isoladas
- o `dry_run` amplo de entregas pode ficar longo ou bloquear em handshake TLS externo; para operacao local, o teste recomendado e `--company-id` ou `--skip-deliveries`
- a organizacao autenticada no endpoint HTTP influencia o match com `external_companies`; no ambiente local, `lumen` e `neto-contabilidade` possuem contextos distintos

## Atualizacao S7.0 em 2026-07-15

No estado real atual, foi materializado apenas o micro-stage documental e de seguranca do Sittax com:

- `docs/SITTAX_OBSERVED_CONTRACT.md`
- `docs/DECISOES.md`
- `docs/RISCOS.md`
- `docs/SECURITY.md`
- `backend/tests/fixtures/sittax/`
- `schemas/sittax_company.schema.json`
- `schemas/sittax_apuracao.schema.json`
- `schemas/sittax_difal.schema.json`
- `schemas/sittax_fiscal_document_page.schema.json`
- `schemas/sittax_task_page.schema.json`
- `schemas/sittax_company_panel.schema.json`
- `backend/tests/test_sittax_fixture_safety.py`
- `backend/tests/test_sittax_observed_schemas.py`

Decisoes materializadas no S7.0:

- o Sittax continua sem cliente HTTP real, sem login real e sem sync real
- a apuracao observada e registrada como setter confirmado do contexto de sessao
- DIFAL, painel da empresa e notas fiscais ficam classificados como endpoints contextuais
- `POST /api/v2/painel-contador/transmissao` fica adiado como endpoint ambiguo
- o log bruto `sittax-network-log*.jsonl` passa a ter protecao especifica no `.gitignore`
- o stack E2E dedicado limpa variaveis de integracao para nao depender do `.env` local

Ainda permanecem fora de escopo neste ponto:

- models Sittax
- migration Sittax
- endpoint manual de sync
- health funcional do Sittax
- qualquer chamada externa nova

## Atualizacao S7.1 em 2026-07-15

No estado real atual, foi materializada a fundacao tecnica do cliente Sittax com:

- `backend/app/services/integrations/sittax/__init__.py`
- `backend/app/services/integrations/sittax/errors.py`
- `backend/app/services/integrations/sittax/session.py`
- `backend/app/services/integrations/sittax/client.py`
- `backend/app/services/integrations/sittax/mapper.py`
- `backend/app/schemas/sittax.py`
- `backend/scripts/check_sittax_connection.py`
- `backend/tests/test_sittax_client.py`
- `backend/tests/test_sittax_session.py`
- `backend/tests/test_sittax_mapper.py`
- `backend/tests/test_sittax_connection_script.py`

Decisoes materializadas no S7.1:

- a integracao real continua read-only e limitada a login e listagem de empresas
- a sessao Sittax usa um unico `httpx.Client` por instancia, com exclusao mutua local por `session.exclusive()`
- o JWT permanece somente em memoria e nao vai para banco, snapshots ou logs
- `active_company_cnpj` e `active_period` existem apenas como placeholders nulos para o contexto futuro
- o escritorio e resolvido deterministicamente a partir do payload observado de login
- fixture mode reutiliza os mesmos mappers do cliente real e nao acessa rede
- o script `check_sittax_connection.py` nao imprime PII e nao persiste nada
- a validacao real controlada do S7.1 foi concluida em `2026-07-16` com login aprovado, escritorio resolvido e `157` empresas retornadas
- o contrato real do login confirmou sucesso com `codigo = 200`, mantendo compatibilidade de fixture com `codigo = 0`

Ainda permanecem fora de escopo neste ponto:

- apuracao e definicao real de contexto
- DIFAL, documentos fiscais, painel e tarefas
- snapshots, sync, endpoint manual e health funcional
- models e migration Sittax

## Atualizacao S7.2 em 2026-07-16

No estado real atual, foi materializado o snapshot cadastral read-only do Sittax com:

- `backend/app/models/sittax_company_snapshot.py`
- `backend/alembic/versions/20260716_0005_create_sittax_company_snapshots.py`
- `backend/app/services/integrations/sittax/sync.py`
- `backend/scripts/sync_sittax_companies.py`
- `backend/tests/test_sittax_company_snapshot.py`
- `backend/tests/test_sittax_company_sync.py`
- `backend/tests/test_sync_sittax_companies_script.py`

Decisoes materializadas no S7.2:

- o snapshot Sittax usa identidade da fonte por `organization_id + sittax_company_id`
- a reconciliacao local usa `organization_id + cnpj` contra `external_companies`
- `company_id` do snapshot referencia `external_companies.id` quando houver match univoco
- `state_registration` continua nullable; `ISENTO` permanece apenas para representacao futura de frontend
- `raw_payload` fica somente em `sittax_company_snapshots`
- `integration_sync_runs` guardam apenas contadores, erros sanitizados e metadata segura
- `dry_run` autentica, lista e reconcilia sem persistir snapshots ou runs
- fixture mode reutiliza o mesmo mapper e o mesmo servico, sem rede
- nenhuma ausencia no Sittax gera soft delete local neste micro-stage
- a validacao real final do S7.2 foi concluida em `2026-07-16` com `157` snapshots reais persistidos para `neto-contabilidade`
- a segunda execucao serial do sync confirmou idempotencia real com `snapshots_created = 0`
- a distribuicao real confirmada no banco ficou `MATCHED = 155` e `UNMATCHED = 2`

Ainda permanecem fora de escopo neste ponto:

- apuracao e definicao real de contexto
- DIFAL, documentos fiscais, painel e tarefas
- endpoint de frontend ou botao operacional
- health funcional do Sittax por request
- qualquer mutacao externa

## Atualizacao S7.3 em 2026-07-16

No estado real atual, foi materializada a apuracao read-only do Sittax com:

- `backend/app/models/sittax_apuracao_snapshot.py`
- `backend/alembic/versions/20260716_0006_create_sittax_apuracao_snapshots.py`
- `backend/scripts/sync_sittax_apuracoes.py`
- `backend/tests/test_sittax_apuracao_mapper.py`
- `backend/tests/test_sittax_apuracao_client.py`
- `backend/tests/test_sittax_apuracao_snapshot.py`
- `backend/tests/test_sittax_apuracao_sync.py`
- `backend/tests/test_sync_sittax_apuracoes_script.py`

Decisoes materializadas no S7.3:

- a apuracao usa `empresaCnpj + periodo` como setter real do contexto ativo da sessao
- o contexto da sessao e limpo antes de cada chamada e so e confirmado apos resposta valida com CNPJ e competencia coerentes
- a interface operacional aceita apenas `YYYY-MM`; a chamada ao Sittax converte para `MM/YYYY`
- a competencia precisa existir em `fiscal_periods`; este micro-stage nao cria periodos automaticamente
- o snapshot de apuracao usa idempotencia por `organization_id + sittax_company_snapshot_id + fiscal_period_id`
- o sync de apuracoes e serial por sessao, processa apenas `MATCHED` no lote e continua sem chamar DIFAL, documentos, painel, tarefas ou qualquer mutacao externa

Atualizacao parcial do S7.4 em 2026-07-17:

- a sessao Sittax passou a manter contexto separado por host: `active_apuracao_*` e `active_api_*`
- `backend/app/services/integrations/sittax/client.py` exige confirmacao do host API antes de DIFAL e documentos
- `docs/SITTAX_CONTEXT_HANDOFF.md` registra a sequencia real validada, a dependencia de sessao stateful, os cookies de contexto e a divergencia entre replay stateless e comportamento real do portal
- o handoff real da empresa no host API permanece pendente de evidencia adicional; o macro-stage S7 segue aberto

## Atualizacao S8.2

Arquivos efetivamente materializados no S8.2:

- `backend/app/services/integrations/econet/assisted_session.py`
- `backend/app/services/integrations/econet/client.py`
- `backend/app/schemas/econet.py`
- `backend/app/api/v1/endpoints/integrations/econet.py`
- `backend/tests/test_econet_assisted_session.py`
- `backend/tests/test_econet_client.py`
- `backend/tests/test_econet_endpoint.py`
- `backend/tests/test_econet_health.py`
- `backend/tests/test_econet_session_security.py`
- `scripts/scan/export_econet_session.js`

Ainda nao materializados no fechamento do S8.2:

- `backend/scripts/enrich_cnaes_econet.py`
- qualquer worker, scheduler ou sync em lote da Econet

## Atualizacao S8.3

Arquivos materializados no S8.3:

- `backend/app/models/company_cnae.py`
- `backend/app/services/company_cnae_catalog.py`
- `backend/app/services/factor_r.py`
- `backend/app/services/integrations/econet/activity_classifier.py`
- `backend/app/services/integrations/econet/enrichment.py`
- `backend/app/schemas/nfse.py`
- `backend/scripts/backfill_company_cnaes.py`
- `backend/scripts/enrich_cnaes_econet.py`
- `docs/NFSE_NORMALIZED_CONTRACT.md`

## Addendum S9.2

Arquivos adicionais materializados no S9.2:

- `backend/app/services/integrations/dominio/coverage.py`
- `backend/app/services/integrations/dominio/factor_r_targets.py`
- `backend/app/services/integrations/dominio/selection_scope.py`
- `backend/scripts/export_dominio_factor_r_targets.py`
- `backend/tests/test_export_dominio_factor_r_targets.py`

## Retificacao auditada do Stage S8 em 2026-07-27

Esta secao substitui a leitura anterior que parava no `S8.1`. O repositorio real materializado ate imediatamente antes do commit do `S8.3` contem:

* `S8.0`: contrato observado, fixtures e seguranca
* `S8.1`: parser puro e cache global por CNAE
* `S8.2`: sessao assistida, cliente stateful e endpoints administrativos
* `S8.3`: catalogo `company_cnaes`, enrichment, classificacao, potencial de Fator R e contrato canonico de NFS-e
* `S8.4`: nao iniciado, portanto sem arquivos proprios materializados

### Arvore efetiva do S8

```txt
backend/
├── alembic/
│   └── versions/
│       ├── 20260721_0009_create_econet_cnae_cache.py
│       ├── 20260722_0010_create_company_cnaes.py
│       └── 20260724_0011_expand_econet_mei_occupation_to_text.py
├── app/
│   ├── api/v1/endpoints/
│   │   ├── integrations/econet.py
│   │   ├── lumen.py
│   │   └── webhooks/econtrole.py
│   ├── core/
│   │   ├── config.py
│   │   └── enums.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── company_activity_type.py
│   │   ├── company_cnae.py
│   │   ├── econet_cnae_cache.py
│   │   ├── external_company.py
│   │   └── integration_sync_run.py
│   ├── schemas/
│   │   ├── econet.py
│   │   ├── integration.py
│   │   └── nfse.py
│   └── services/
│       ├── company_cnae_catalog.py
│       ├── factor_r.py
│       ├── lumen_read_model.py
│       └── integrations/
│           ├── econtrole/sync.py
│           └── econet/
│               ├── __init__.py
│               ├── activity_classifier.py
│               ├── assisted_session.py
│               ├── cache.py
│               ├── client.py
│               ├── encoding.py
│               ├── enrichment.py
│               ├── errors.py
│               └── parser.py
├── scripts/
│   ├── backfill_company_cnaes.py
│   └── enrich_cnaes_econet.py
└── tests/
    ├── econet_test_utils.py
    ├── fixtures/
    │   ├── econet/
    │   └── nfse/
    ├── test_backfill_company_cnaes.py
    ├── test_company_cnae_catalog.py
    ├── test_company_cnae_model.py
    ├── test_econet_assisted_session.py
    ├── test_econet_cache.py
    ├── test_econet_client.py
    ├── test_econet_cnae_cache_model.py
    ├── test_econet_endpoint.py
    ├── test_econet_enrichment_endpoint.py
    ├── test_econet_enrichment_service.py
    ├── test_econet_fixture_safety.py
    ├── test_econet_health.py
    ├── test_econet_observed_contract.py
    ├── test_econet_parser.py
    ├── test_econet_session_security.py
    ├── test_econtrole_sync.py
    ├── test_econtrole_webhook.py
    ├── test_enrich_cnaes_econet_script.py
    ├── test_nfse_contract.py
    └── test_nfse_fixture_safety.py
docs/
├── ECONET_OBSERVED_CONTRACT.md
└── NFSE_NORMALIZED_CONTRACT.md
scripts/
└── scan/
    └── export_econet_session.js
```

### Descricao objetiva por arquivo do S8

Migrations:

* `backend/alembic/versions/20260721_0009_create_econet_cnae_cache.py`
  * S8.1.
  * Cria o cache global `econet_cnae_cache`.
* `backend/alembic/versions/20260722_0010_create_company_cnaes.py`
  * S8.3.
  * Cria o catalogo canonico `company_cnaes`.
* `backend/alembic/versions/20260724_0011_expand_econet_mei_occupation_to_text.py`
  * S8.3 corretivo.
  * Evita truncamento da ocupacao de MEI.

Models:

* `backend/app/models/econet_cnae_cache.py`
  * S8.1.
  * Cache global da Econet por CNAE, sem HTML bruto.
* `backend/app/models/company_cnae.py`
  * S8.3.
  * Catalogo canonico de CNAEs ativos por empresa.
* `backend/app/models/company_activity_type.py`
  * Reutilizado no S8.3.
  * Recebe classificacao derivada da Econet com `source = ECONET`.
* `backend/app/models/external_company.py`
  * Relacao de origem do catalogo.
  * Mantem espelho bruto do eControle.
* `backend/app/models/integration_sync_run.py`
  * Reutilizado no S8.3.
  * Registra execucoes do enrichment.
* `backend/app/models/__init__.py`
  * Exporta `EconetCnaeCache` e `CompanyCnae` para metadata e Alembic.

Schemas:

* `backend/app/schemas/econet.py`
  * S8.2 e S8.3.
  * Requests e responses da sessao, enrichment, catalogo de CNAEs e potencial de Fator R.
* `backend/app/schemas/integration.py`
  * Atualizado no S8.3.
  * Health de integracoes com campos especificos da Econet, incluindo cache desatualizado por parser.
* `backend/app/schemas/nfse.py`
  * S8.3.
  * Contrato canonico de NFS-e para o futuro S10.

Services Econet:

* `backend/app/services/integrations/econet/assisted_session.py`
  * S8.2.
  * Sessao em memoria com allowlist de cookies e dominios.
* `backend/app/services/integrations/econet/client.py`
  * S8.2.
  * Cliente HTTP stateful com base URL fixa e bloqueio de path arbitrario.
* `backend/app/services/integrations/econet/encoding.py`
  * S8.3 corretivo.
  * Decodificacao deterministica de HTML a partir de bytes.
* `backend/app/services/integrations/econet/parser.py`
  * S8.1 e S8.3.
  * Parser puro do contrato observado; versao atual `econet-html-v2`.
* `backend/app/services/integrations/econet/cache.py`
  * S8.1 e S8.3.
  * Upsert, TTL e regra de cache fresco dependente do parser atual.
* `backend/app/services/integrations/econet/enrichment.py`
  * S8.3.
  * Orquestra enrichment, politica de cache, rede e consolidacao de resultados.
* `backend/app/services/integrations/econet/activity_classifier.py`
  * S8.3.
  * Classifica tipos de atividade a partir da descricao do CNAE.
* `backend/app/services/integrations/econet/errors.py`
  * S8.1 e S8.2.
  * Erros tipados de parser, sessao, transporte e contrato.
* `backend/app/services/integrations/econet/__init__.py`
  * Atualizado no S8.3.
  * Reexporta parser, sessao, cache, encoding e cliente.

Outros services:

* `backend/app/services/company_cnae_catalog.py`
  * S8.3.
  * Normaliza CNAEs do eControle, sincroniza catalogo e rejeita placeholder `0000000`.
* `backend/app/services/factor_r.py`
  * S8.3.
  * Calcula potencial cadastral de Fator R a partir de CNAEs ativos e cache fresco.
* `backend/app/services/lumen_read_model.py`
  * Atualizado no S8.2 e S8.3.
  * Exposicao read-only de health, CNAEs da empresa e potencial de Fator R.
* `backend/app/services/integrations/econtrole/sync.py`
  * Atualizado no S8.3.
  * Garante sincronizacao atomica entre espelho cadastral e `company_cnaes`.

Endpoints:

* `backend/app/api/v1/endpoints/integrations/econet.py`
  * S8.2 e S8.3.
  * Sessao manual e enrichment administrativo.
* `backend/app/api/v1/endpoints/lumen.py`
  * Atualizado no S8.3.
  * Leitura de `companies/{company_id}/cnaes`, `factor-r-potential` e `integrations/health`.
* `backend/app/api/v1/endpoints/webhooks/econtrole.py`
  * Atualizado no S8.3.
  * Webhook de upsert e delete com sincronizacao do catalogo.

Scripts:

* `scripts/scan/export_econet_session.js`
  * S8.2.
  * Exporta cookies permitidos apos login manual.
* `backend/scripts/backfill_company_cnaes.py`
  * S8.3.
  * Backfill de `external_companies` para `company_cnaes`.
* `backend/scripts/enrich_cnaes_econet.py`
  * S8.3.
  * Cliente operacional da API local para enrichment.

Fixtures:

* `backend/tests/fixtures/econet/`
  * S8.0 a S8.3.
  * Contrato observado sanitizado, incluindo cenarios adicionais de Fator R no S8.3.
* `backend/tests/fixtures/nfse/`
  * S8.3.
  * Contratos sinteticos de NFS-e para `NFSE_ABRASF_204` e `NFSE_NACIONAL_101`.

Testes:

* `backend/tests/econet_test_utils.py`
  * Utilitarios de fixtures da Econet.
* `backend/tests/test_backfill_company_cnaes.py`
  * Backfill do catalogo.
* `backend/tests/test_company_cnae_catalog.py`
  * Regras de normalizacao, placeholder, deduplicacao e desativacao.
* `backend/tests/test_company_cnae_model.py`
  * Invariantes do model `company_cnaes`.
* `backend/tests/test_econet_assisted_session.py`
  * Sessao assistida e seguranca de importacao.
* `backend/tests/test_econet_cache.py`
  * Cache, TTL e parser version.
* `backend/tests/test_econet_client.py`
  * Cliente HTTP e allowlist.
* `backend/tests/test_econet_cnae_cache_model.py`
  * Invariantes do model do cache.
* `backend/tests/test_econet_endpoint.py`
  * Endpoints administrativos de sessao.
* `backend/tests/test_econet_enrichment_endpoint.py`
  * Contrato HTTP do enrichment.
* `backend/tests/test_econet_enrichment_service.py`
  * Regras do service de enrichment.
* `backend/tests/test_econet_fixture_safety.py`
  * Sanitizacao das fixtures da Econet.
* `backend/tests/test_econet_health.py`
  * Health local da Econet.
* `backend/tests/test_econet_observed_contract.py`
  * Manifest e contrato observado.
* `backend/tests/test_econet_parser.py`
  * Parser HTML puro.
* `backend/tests/test_econet_session_security.py`
  * Seguranca da sessao e de cookies.
* `backend/tests/test_econtrole_sync.py`
  * Sync do espelho com catalogo.
* `backend/tests/test_econtrole_webhook.py`
  * Webhooks de upsert e delete.
* `backend/tests/test_enrich_cnaes_econet_script.py`
  * CLI do script de enrichment.
* `backend/tests/test_nfse_contract.py`
  * Contrato Pydantic da NFS-e canonica.
* `backend/tests/test_nfse_fixture_safety.py`
  * Seguranca das fixtures sinteticas de NFS-e.

### Relacoes arquiteturais

```txt
external_companies
    ↓
company_cnaes
    ↓
econet_cnae_cache
    ↓
company_activity_types
    ↓
factor_r_potential
```

Significado:

* eControle e a origem do cadastro bruto
* `company_cnaes` e o catalogo canonico interno
* a Econet enriquece globalmente por CNAE
* a classificacao de atividade e derivada
* Fator R e apenas potencial cadastral
* o uso efetivo por competencia depende do futuro fluxo de NFS-e do S10

### O que nao existe no repositorio

* arquivos temporarios de sessao
* storageState versionado
* HAR ou logs brutos da Econet
* OpenAPI temporario
* XML fiscal real
* qualquer arquivo proprio do `S8.4`


## Atualizacao S9.0

Arquivos materializados no S9.0:

- `backend/app/services/integrations/dominio/__init__.py`
- `backend/app/services/integrations/dominio/contracts.py`
- `backend/app/services/integrations/dominio/competence.py`
- `backend/tests/dominio_test_utils.py`
- `backend/tests/test_dominio_payroll_contract.py`
- `backend/tests/test_dominio_payroll_competence.py`
- `backend/tests/fixtures/dominio/manifest.json`
- `backend/tests/fixtures/dominio/synthetic_contract_samples.json`
- `docs/integrations/DOMINIO_PAYROLL_CONTRACT.md`
- `scripts/collectors/dominio/gerar_resumo_mensal_dominio.py`
- `scripts/collectors/dominio/.env.example`
- `scripts/collectors/dominio/README.md`

Decisoes materializadas no S9.0:

- a integracao com Dominio Folha passa a ser documental
- `source_payroll_competence` e `assessment_competence` ficam separados desde o contrato
- a regra `folha M -> apuracao M+1` foi congelada antes de qualquer persistencia
- o coletor Windows e opcional e desacoplado do backend
- o fluxo automatico preferencial usa uma unica competencia por PDF
- o coletor usa `.partial.pdf`, validacao minima, `os.replace`, SHA-256, manifest lateral e lock local
- o coletor le o `.env` central do Lumen primeiro e aceita `.env` local apenas como fallback opcional
- as configuracoes operacionais do coletor aceitam chaves `DOMINIO_*` no `.env` central com fallback para nomes legados
- fixtures de Dominio sao integralmente sinteticas

Fechamento validado em 2026-07-29:

- testes puros do backend S9.0 aprovados: `17 passed`
- `ruff check` do pacote `backend/app/services/integrations/dominio` aprovado
- `py_compile` e parse AST UTF-8 do coletor aprovados
- requirements do coletor incorporados ao `requirements.txt` central
- execucao funcional real do coletor aprovada para `05/2026`
- PDF final gerado: `scripts/collectors/dominio/Relatorios_Dominio/Resumo_Mensal_05-2026.pdf`
- manifest lateral gerado com `status = SUCCESS`, `payroll_competence = 2026-05` e `assessment_competence = 2026-06`
- hash observado do PDF homologado: `A7BDE8EBFCD1679F8C0D92386AC4EB3E252468E542ACB699ED06B3797EC9C59F`

Ainda nao materializados no S9.0:

- parser offline do PDF
- migration e tabelas `dominio_payroll_imports` e `dominio_payroll_company_movements`
- importador persistente
- endpoint administrativo
- watcher do backend
- frontend
- E2E

## Atualizacao S9.1

Arquivos materializados no S9.1:

- `backend/app/services/integrations/dominio/parser.py`
- `backend/app/services/integrations/dominio/normalization.py`
- `backend/app/services/integrations/dominio/rubrics.py`
- `backend/tests/test_dominio_payroll_parser.py`
- `backend/tests/test_dominio_payroll_normalization.py`
- `backend/tests/test_dominio_payroll_rubrics.py`

Decisoes materializadas no S9.1:

- o parser da Dominio Folha e offline, puro e sem banco
- `pypdf` e o extrator primario do texto do PDF
- `parse_dominio_payroll_pdf(...)` e `parse_dominio_payroll_pages(...)` formam a API publica do stage
- agrupamento de empresa usa `codigo Dominio + CNPJ normalizado + competencia original da folha`
- o parser preserva blocos desconhecidos como `UNKNOWN`
- o parser produz warnings estruturados e excecoes de dominio proprias
- valores monetarios usam `Decimal`; horas do valor informado sao convertidas para minutos
- a origem dos sinais de folha fica preservada em `signal_sources`
- `has_employee` passou a aceitar apenas evidencias inequivocamente trabalhistas
- `843 INSS EMPREGADOR` continua sinalizando `has_inss`, mas nao sinaliza `has_employee`
- perfis somente pro-labore e somente autonomo permanecem fora de `has_employee`

Fechamento validado em 2026-07-29:

- testes especificos do Dominio S9.1 aprovados: `62 passed`
- `ruff check` do pacote `backend/app/services/integrations/dominio` aprovado
- suite completa do backend aprovada: `447 passed, 1 warning`
- `py_compile` do parser e dos contratos aprovado
- Alembic mantido em `20260724_0011 (head)` e sem alteracoes em `backend/alembic/versions`
- validacao real agregada aprovada para `Resumo_Mensal_05-2026.pdf` e `Resumo_Mensal_06-2026.pdf`
- `Resumo_Mensal_05-2026.pdf`: `149` paginas, `137` empresas, `employee_true = 90`, `employee_false = 47`, `employee_only_supported_by_forbidden_codes = 0`, competencia folha `2026-05`, apuracao `2026-06`
- `Resumo_Mensal_06-2026.pdf`: `145` paginas, `137` empresas, `employee_true = 90`, `employee_false = 47`, `employee_only_supported_by_forbidden_codes = 0`, competencia folha `2026-06`, apuracao `2026-07`
- o parser nao introduziu migration, tabela, endpoint, watcher ou frontend

## Atualizacao S9.2

Arquivos materializados no S9.2:

- `backend/app/models/dominio_payroll.py`
- `backend/app/services/integrations/dominio/importer.py`
- `backend/app/services/integrations/dominio/matching.py`
- `backend/scripts/import_dominio_payroll.py`
- `backend/tests/test_dominio_payroll_models.py`
- `backend/tests/test_dominio_payroll_matching.py`
- `backend/tests/test_dominio_payroll_importer.py`
- `backend/tests/test_dominio_payroll_cli.py`
- `backend/alembic/versions/20260730_0012_create_dominio_payroll_tables.py`

Decisoes materializadas no S9.2:

- a persistencia do Dominio Folha usa apenas `dominio_payroll_imports` e `dominio_payroll_company_movements`
- o PDF nao e armazenado no banco; apenas metadados, hash, totais, warnings, `raw_text` sanitizado e resultado extraido
- a idempotencia do arquivo ficou em `organization_id + file_sha256`
- a idempotencia do bloco por empresa ficou em `import_id + source_company_key`
- o matching automatico usa apenas `organization_id + cnpj`
- `source_payroll_competence` e `assessment_competence` permanecem separadas e persistidas como primeiro dia do mes
- `fiscal_period_id` dos movimentos e das evidencias sempre aponta para a competencia de apuracao `M+1`
- `rubrics_summary` ficou resumido em JSONB; nenhuma tabela de rubricas foi criada
- `fiscal_evidences` do stage usam `source = DOMINIO_FOLHA_PDF` e so sao criadas para movimentos `MATCHED`
- o importador registra `integration_sync_runs` e `audit_log` apenas para execucao real; `--dry-run` nao grava nada
- a CLI operacional do stage e `backend/scripts/import_dominio_payroll.py`
- o collector mensal canonico usa filtro `Ativas`, um PDF por competencia e manifest com `selection_scope = ACTIVE_COMPANIES`
- `target_company_count` e `target_list_sha256` pertencem apenas ao escopo `FACTOR_R` e nao devem vazar para imports `Ativas`
- manifests legados com `selection_scope` ausente e `source_filter_name = Ativas` passam a ser inferidos como `ACTIVE_COMPANIES`
- a janela historica de 12 meses para Fator R e montada a partir dos movimentos persistidos; filtro `Fator R` e modo intervalo permanecem opcionais para auditoria, diagnostico ou contingencia

## Atualizacao S9.3

Arquivos materializados no S9.3:

- `backend/app/models/dctfweb_origin.py`
- `backend/app/services/dctfweb_origins.py`
- `backend/scripts/reconcile_dctfweb_origins.py`
- `backend/alembic/versions/20260820_0013_create_dctfweb_origin_assessments.py`
- `backend/tests/test_dctfweb_origins.py`

Decisoes materializadas no S9.3:

- `dctfweb_origin_assessments` e uma visao derivada, multi-tenant e auditavel; nao altera `fiscal_obligation_statuses`;
- o universo avaliado e toda empresa atualmente ativa (`ExternalCompany.active = true`) da organizacao, com limitacao documentada por ainda nao haver historico de ativacao por competencia;
- a cobertura DP consulta apenas imports mensais `ACTIVE_COMPANIES` por competencia de apuracao;
- DCTFWeb e decomposta operacionalmente em eSocial, EFD-Reinf e MIT; eSocial/Domínio aponta DP, REINF/MIT apontam Fiscal;
- `REINF` e sinal Fiscal apenas quando a obrigacao/evidencia canonica for `REINF`; MIT e sinal Fiscal apenas a partir da PA `2025-01` por `PIS`/`COFINS`;
- DCTFWeb observada por entrega Acessorias mapeada, status ou evidencia canonicos nao define origem por si so; ausencia total de sinais persiste `UNDETERMINED` sem alerta;
- alertas reutilizam `fiscal_alerts`, sao idempotentes e resolvidos quando a condicao desaparece; falta de relatorio mensal Dominio gera no maximo um alerta por organizacao/periodo com `company_id = null`;
- o processamento e interno e auditado, sem criar uma integracao externa artificial em `integration_sync_runs`.

## Atualizacao S9.4.0

Arquivos materializados no S9.4.0:

- `backend/app/services/integrations/dominio/monetary_summary.py`
- `backend/app/services/integrations/dominio/enrichment.py`
- `backend/scripts/enrich_dominio_payroll_monetary_summary.py`
- `backend/tests/test_dominio_payroll_monetary_summary.py`
- `backend/tests/test_dominio_payroll_monetary_enrichment.py`
- `backend/tests/test_dominio_payroll_monetary_enrichment_cli.py`

Decisoes materializadas no S9.4.0:

- `rubrics_summary` evoluiu para `schema_version = 2` sem nova migration;
- o shape v2 preserva os campos do S9.2 e acrescenta resumo monetario estruturado, confidence, `unclassified_monetary` e `excluded_monetary`;
- o enrichment historico reprocessa o PDF original e atualiza somente `dominio_payroll_company_movements.rubrics_summary`;
- a classificacao monetaria e conservadora e nao usa `gross_total`, `net_total` ou `raw_text` persistido para preencher lacunas;
- `employer_cpp_observed` e `fgts_observed` sao observacoes do relatorio, nao prova de recolhimento;
- o enrichment e idempotente por igualdade material do JSON resultante.

Validacao operacional do S9.4.0 em 2026-08-21:

- dry-run real dos `12` PDFs de `07/2025` a `06/2026`: `imports_found = 12`, `movements_parsed = 1624`, `movements_matched = 1624`, `movements_would_update = 1624`, `schema_v2 = 1624`, `complete = 505`, `partial = 1112`, `insufficient = 7`, `unclassified_monetary_movements = 1119`;
- persistencia real dos `12` PDFs: `movements_updated = 1624`;
- segunda execucao real: `movements_updated = 0` e `already_enriched = 1624`;
- query agregada posterior confirmou `schema_version = 2` em todos os movimentos do backfill;
- regressao Domínio: `99 passed`;
- regressao S9.3: `14 passed`;
- suite backend completa: `560 passed, 1 warning`.

## Atualizacao S9.4

- `backend/app/models/factor_r_assessment.py`: assessment derivado idempotente por organizacao, empresa e PA.
- `backend/app/services/factor_r_reconciliation.py`: janela, cobertura, estimativa FS12, normalizacao Sittax, reconciliacao e alertas.
- `backend/scripts/reconcile_factor_r.py`: CLI agregada com `--dry-run` e `--json`.
- `backend/scripts/sync_sittax_apuracoes.py`: workflow S7 read-only de snapshots Sittax, executavel diretamente da raiz do repositorio.
- `backend/alembic/versions/20260824_0014_create_factor_r_assessments.py`: persistencia exclusiva do resultado derivado.
- `docs/FACTOR_R_RECONCILIATION.md`: limites de fonte, confidence e regras de reconciliacao.

Funcionamento validado:

- a cobertura usa imports Domínio canônicos `ACTIVE_COMPANIES`; `MOVEMENT_FOUND` e `CONFIRMED_NO_MOVEMENT` sao estados mutuamente exclusivos de cobertura valida, enquanto somente a ausencia do relatorio e `REPORT_MISSING`;
- a janela de 12 meses aplica `folha M -> PA M+1`, sem incluir a folha do proprio PA;
- `fs12_dominio_estimate` deriva exclusivamente de `rubrics_summary` schema v2, com `Decimal`, e nao usa `gross_total`, `raw_text` ou total liquido como preenchimento;
- o join Sittax usa as FKs canonicas de organizacao, empresa e PA; `factor_r_percent` armazenado em pontos percentuais e normalizado internamente para ratio Decimal;
- anexos somente sao considerados observados quando o payload Sittax possuir codigo explicito reconhecido; descricao livre nao infere Anexo III ou V;
- a reconciliacao so amplia `POTENTIAL` para `EFFECTIVE` quando ha potencial CNAE canonico e fator Sittax observado, sem transformar snapshots isolados em novos targets;
- o reconciliador nao altera imports Domínio, movimentos, evidencias, status fiscais ou cache Econet; o sync S7 somente pode acrescentar/atualizar snapshots locais lidos de endpoint externo read-only.

## Atualizacao S9.5-BE

- `backend/app/schemas/lumen_s9.py`: contratos publicos sanitizados para Domínio, DCTFWeb, Factor R e reconciliacao local.
- `backend/app/api/v1/endpoints/lumen.py`: novos GETs e POSTs sob o prefixo publico existente `/api/v1/lumen`.
- `backend/app/services/lumen_read_model.py`: consultas em lote multi-tenant, resumos de assessments e health local Domínio/Sittax.
- `backend/tests/test_lumen_s95_read_endpoints.py`: cobertura de sanitizacao, cobertura de folha, RBAC, isolamento, zero writes e reconciliacao local.

O S9.5-BE nao criou tabelas nem upload de PDF. Todos os GETs leem somente PostgreSQL/cache local; POSTs de reconcile usam dados persistidos e nao acionam integracoes externas. O watcher, frontend e E2E foram concluídos no fechamento operacional abaixo.

## Atualizacao S9.5 operacional

- `backend/app/services/integrations/dominio/watcher.py`: varredura local e conservadora de relatórios Domínio canônicos, sem mover, renomear ou apagar arquivos.
- `backend/scripts/watch_dominio_payroll.py`: CLI `--once`, `--dry-run` e `--json`; o diretório padrão é relativo ao repositório.
- `scripts/dev/run_dominio_payroll_watcher.ps1`: wrapper Windows para iniciar, consultar e parar o watcher contínuo sem duplicar processos por organização.
- `frontend/src/services/lumenService.ts` e `frontend/src/types/lumenS9.ts`: contratos de consumo dos resumos Domínio, DCTFWeb e Fator R.
- `frontend/src/features/dashboard`, `cockpit`, `company` e `integrations`: leitura operacional sem payload bruto nem ações fiscais externas. A Company Page busca os detalhes S9 isoladamente, preserva a página quando um detalhe retorna 404 e recebe `dominio_source_period` já resolvido pelo backend.

O watcher grava somente `integration_sync_runs` agregado e usa o importador canônico para qualquer nova escrita de importação. A saúde local inclui `Watcher Domínio` com o último run, detecção e importação agregados. `dashboard.factor_r.incomplete` significa assessment cujo cálculo não está `COMPUTED`; não equivale à contagem de alertas fiscais.

O fechamento S9.5 valida headings acessíveis para `Origem DCTFWeb`, `Fator R` e `Folha Domínio`; o fixture E2E sintético cobre divergência de threshold e baixa confiança no card de Fator R. S9 está concluído; S10 permanece fora do escopo.

## Atualizacao S5.2, S6.3 e S8.3.2 em 2026-08-20

Arquivos materializados no S5.2:

- `backend/app/services/integrations/econtrole/webhook_completion.py`
- `backend/scripts/backfill_econtrole_companies.py`
- `backend/tests/test_econtrole_webhook_completion.py`
- `backend/tests/test_backfill_econtrole_companies.py`

Arquivos materializados no S6.3:

- `backend/scripts/process_acessorias_retries.py`
- `backend/app/worker/runner.py` atualizado para processar retries vencidos da Acessorias
- `backend/app/api/v1/endpoints/worker.py` atualizado para refletir o processador real
- `backend/tests/test_health.py` atualizado para o contrato novo do worker

Arquivos materializados no S8.3.2:

- `backend/app/data/company_activity_types/company_activity_types_cnae23_concla_mapeamento.json`
- `backend/app/data/company_activity_types/company_activity_types_cnae23_concla_catalogo_completo.json`
- `docs/artifacts/company_activity_types/company_activity_types_cnae23_catalogo_completo_com_anexos.xlsx`
- `backend/scripts/backfill_company_activity_types.py`
- `backend/scripts/export_econet_simples_annex_audit.py`
- `backend/scripts/fetch_econet_simples_annexes_to_xlsx.py`
- `backend/tests/test_company_activity_classifier.py`
- `backend/tests/test_backfill_company_activity_types.py`
- `backend/tests/test_export_econet_simples_annex_audit_script.py`
- `backend/tests/test_fetch_econet_simples_annexes_to_xlsx.py`

Decisoes materializadas nesta etapa:

- o fluxo do eControle agora completa cadastro localmente apos webhook ou reconciliacao, incluindo `company_cnaes`, regime da Acessorias, CNAEs faltantes da Econet e `company_activity_types`
- empresas com `situacao = INATIVA` no eControle passam a ser inativadas localmente sem depender apenas do endpoint de delete
- retries de Acessorias sao persistidos em `integration_sync_runs`, com janela de `24h`, limite de `5` tentativas e estados `PENDING`, `SUCCESS`, `EXHAUSTED` e `CANCELLED`
- o worker deixou de ser apenas stub funcional para o caso de uso de retries da Acessorias, embora o macro-stage S16 ainda nao esteja iniciado
- `company_activity_types` deixam de depender apenas de heuristica textual e passam a usar catalogo canonico CONCLA/CNAE 2.3 versionado no repositorio
- a auditoria de anexos da Econet ficou operacionalizada em planilha, sem persistencia desses anexos no banco

Validacoes reais registradas nesta etapa:

- backfill dry-run do eControle em `2026-08-20` com `228` empresas recebidas, `2` criacoes potenciais, `223` updates potenciais e `3` payloads invalidos por ausencia de `cnpj`
- reprocessamento local do mesmo dry-run com `250` empresas, `28` retries pendentes da Acessorias e `4` CNAEs ainda ausentes no cache da Econet
- processador de retries da Acessorias validado com `15 passed`
- backfill real de `company_activity_types` em `2026-08-12` com `242` empresas ativas, `295` classificacoes criadas e `0` CNAEs sem mapeamento
- auditoria inicial de anexos da planilha com `1331` linhas, `255` `OK`, `9` `prohibited` e `1067` `missing_cache`

## Atualizacao S10.2

- `backend/app/api/v1/endpoints/lumen.py`: `POST /api/v1/lumen/evidences/watcher-event` com autenticacao M2M dedicada.
- `backend/app/schemas/watcher.py`: request/response fechado do watcher-event v1.
- `backend/app/services/watcher_ingest.py`: validacao lexical, resolucao tenant-scoped, fingerprint, idempotencia, evidence minima e auditoria.
- `backend/app/models/watcher_file_event.py`: `normalized_relative_path` e `idempotency_key` unico.
- `backend/app/models/fiscal_evidence.py`: `watcher_event_id` nullable, FK `RESTRICT` e unico.
- `backend/alembic/versions/20260831_0015_add_watcher_ingest_idempotency.py`: schema incremental do ingest.
- `backend/tests/test_watcher_ingest.py`: cobertura de auth, resolucao, replay, evidence e constraints.
- Hierarquia operacional materializada: parser de conteudo define identificacao principal/canonica; nome do arquivo e somente hint auxiliar/evidencia complementar; pasta fornece somente contexto de empresa e competencia.
- Fechamento validado: teste focado `10 passed`, backend `653 passed`, Ruff limpo, frontend typecheck e `7` E2E aprovados; contagens read-only preservadas em `watcher_file_events=0`, `fiscal_evidences=1717` e `fiscal_obligation_statuses=196`.

S10.2 nao materializou watcher continuo, client HTTP do agent, worker, parser fiscal, OCR ou frontend novo.

## Atualizacao S10.3

- `agent/watcher/scanner.py`: polling incremental restrito a PDFs na gramatica fiscal allowlisted.
- `agent/watcher/state.py`: state e health JSON locais com escrita atomica; sem token, PDF, texto ou dados fiscais extraidos.
- `agent/watcher/client.py`: POST M2M metadata-only para o endpoint S10.2, sem JWT ou tenant no body.
- `agent/watcher/runtime.py` e `agent/watcher/main.py`: baseline sem flood, estabilidade, retry limitado, restart e `--once`/`--status` sanitizado.
- `scripts/dev/run_fiscal_watcher.ps1`: runner foreground que usa a `.venv` e herda somente configuracao de ambiente.
- `backend/tests/test_watcher_scanner.py`, `test_watcher_state.py`, `test_watcher_client.py` e `test_watcher_runtime.py`: cobertura offline com `tmp_path`, inclusive client-to-endpoint sem rede externa.

O polling e o mecanismo primario para compatibilidade com unidade de rede. Nenhum piloto real, service/task Windows, parser fiscal, XML/NFS-e, OCR, worker ou frontend de watcher foi materializado; esses itens permanecem em S10.4 ou S11.3.
## Atualizacao S10.4

- `backend/app/models/watcher_agent_health.py` e migration `20260902_0016`: ultimo heartbeat sanitizado por organizacao.
- `backend/app/services/watcher_health.py` e `watcher_reprocess.py`: estado derivado e retry administrativo explicito de eventos sem evidence.
- `scripts/ops/run_fiscal_watcher_supervised.ps1`: supervisor foreground Windows com backoff.
- Integracoes consulta a saude read-only; nao controla o processo nem transmite documentos.
- `backend/tests/test_watcher_reprocess.py`: matching tardio, estados nao resolvidos, idempotencia, isolamento de tenant e ausencia de mutacao de obrigacoes.
- `frontend/tests_e2e/s10_watcher_health.spec.ts`: estados humanos, redacao de payload e viewport movel do card read-only.
- A fase 1 do piloto real confirmou o baseline local e o heartbeat M2M na root oficial sem ingestao de arquivo. O state local e `agent/.state/` continuam artefatos operacionais ignorados pelo Git.
