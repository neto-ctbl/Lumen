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
