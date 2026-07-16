# Estrutura inicial esperada do repositório Lumen

Data de referência: 2026-07-03

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
│  │  │  ├─ sittax_snapshots.py
│  │  │  ├─ acessorias_snapshots.py
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
│  │  ├─ create_initial_admin.py
│  │  ├─ seed_obligations.py
│  │  ├─ seed_periods.py
│  │  ├─ run_reconciliation_once.py
│  │  └─ run_file_scan_once.py
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
│  ├─ README.md
│  ├─ watcher/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ main.py
│  │  ├─ file_detector.py
│  │  ├─ company_resolver.py
│  │  ├─ period_resolver.py
│  │  ├─ hash.py
│  │  └─ client.py
│  └─ parsers/
│     ├─ __init__.py
│     ├─ file_name_classifier.py
│     └─ pdf_text_probe.py
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
│  ├─ BASELINE_LUMEN.md
│  ├─ DECISOES.md
│  ├─ RISCOS.md
│  ├─ INTEGRATION_CONTRACTS.md
│  ├─ API_CONTRACTS.md
│  ├─ DATA_MODEL.md
│  ├─ FRONTEND_STYLE_GUIDE.md
│  ├─ WATCHER_GUIDE.md
│  ├─ PDF_PARSERS.md
│  ├─ RECONCILIATION_RULES.md
│  ├─ DCTFWEB_RULES.md
│  ├─ FATOR_R_RULES.md
│  ├─ SECURITY.md
│  ├─ RUNBOOK_LOCAL.md
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
│  ├─ watcher_event.schema.json
│  └─ fiscal_evidence.schema.json
│
└─ data/
   ├─ .gitkeep
   └─ examples/
      └─ README.md
```

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

Contém o watcher/agent local responsável por monitorar pastas fiscais, detectar arquivos novos, extrair metadados básicos, calcular hash e enviar eventos para a API.

O agente não deve decidir sozinho uma conciliação final. Ele gera evidências e sinais. A conciliação pertence ao backend.

### `infra/`

Contém infraestrutura local e de desenvolvimento. Inicialmente deve incluir Docker Compose com PostgreSQL e Redis.

Não versionar volumes locais.

### `scripts/`

Contém scripts de desenvolvimento e operação, especialmente PowerShell para Windows.

Scripts com credenciais locais devem usar `.env` ou arquivo `.local.*` ignorado pelo Git.

### `docs/`

Contém documentação viva do projeto. Toda decisão relevante tomada durante desenvolvimento deve entrar em `docs/DECISOES.md`.

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
