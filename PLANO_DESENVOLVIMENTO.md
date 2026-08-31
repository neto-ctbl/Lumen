# Plano de Desenvolvimento - Lumen Fiscal Cockpit

Data de referência: 2026-07-03

## Visão geral

Status global: planejamento inicial para desenvolvimento com Codex.

Objetivo: desenvolver o Lumen como portal fiscal independente, integrado ao ecossistema da Neto Contabilidade, capaz de consolidar obrigações, evidências, entregas, divergências, parcelamentos, Fator R e DCTFWeb por empresa e competência.

Princípio de execução: cada stage deve ser implementado, testado e documentado antes de avançar para o próximo. O Codex deve receber escopo fechado por stage, sem antecipar integrações futuras.

## Regras gerais para todos os stages

### Segurança e escopo

- Não versionar segredos, tokens, cookies, certificados, sessões assistidas ou arquivos fiscais reais.
- Não burlar CAPTCHA.
- Não automatizar transmissão fiscal.
- Não acionar recálculo, transmissão ou envio em sistemas externos sem etapa humana explícita e autorização futura.
- Tratar Sittax como integração somente leitura até confirmação formal.
- Tratar Econet com login assistido e cache; nunca tentar contornar login/captcha.
- OCR é fallback, não caminho padrão.

### Critérios mínimos de validação por stage

Todo stage deve terminar com:

- testes automatizados criados ou atualizados;
- migrations aplicáveis quando houver mudança de banco;
- documentação atualizada quando houver decisão de domínio;
- endpoints protegidos por autenticação/RBAC quando aplicável;
- logs ou auditoria quando houver job, integração ou mutação relevante;
- comandos de validação registrados no fechamento do stage.

### Perfis de acesso iniciais

- `ADMIN`: acesso completo e operações administrativas.
- `DEV`: acesso técnico e execução de jobs/syncs em ambiente autorizado.
- `VIEW`: leitura operacional do cockpit, sem disparar jobs sensíveis nem alterar regras.

### Departamentos padrão

- `FISCAL`
- `DP`
- `COMPARTILHADO`
- `SISTEMA`

### Formato de competência

- Banco/API: `YYYY-MM`.
- Interface: `MM/YYYY`.

---

## S0 - Kickoff, baseline e decisões congeladas

Status: concluido em 2026-07-07

Objetivo:
- Travar o baseline funcional, arquitetural e visual do Lumen antes de escrever código estrutural.

Escopo:
- Consolidar documentação inicial.
- Registrar decisões que não devem ser reabertas sem motivo forte.
- Definir limites de MVP e fora de escopo.

Entregáveis:
- `docs/BASELINE_LUMEN.md`
- `docs/DECISOES.md`
- `docs/RISCOS.md`
- `docs/SECURITY.md`
- `docs/FRONTEND_STYLE_GUIDE.md`
- `docs/RECONCILIATION_RULES.md`

Decisões a registrar:
- Lumen é projeto separado do eControle.
- eControle é fonte cadastral; Acessórias é fonte oficial de regime e entregas.
- Integração eControle por API + webhook + reconciliação periódica.
- Domínio sem robô de tela; usar relatórios/PDFs/arquivos.
- Econet com login assistido, sessão persistente e cache por CNAE.
- Watcher é fonte de evidências, não de decisão final isolada.
- DCTFWeb por folha/eSocial pertence ao DP quando for único fator gerador.

Validação:
- Documentos existem e cobrem escopo, fora de escopo, riscos e decisões.
- README aponta para os documentos principais.

Aceite:
- Baseline versionado e pronto para Codex executar stages sem ambiguidade crítica.

---

## S1 - Estrutura do repo, infra local e healthchecks

Status: concluído

Objetivo:
- Criar monorepo limpo, reproduzível e pronto para desenvolvimento incremental.

Escopo:
- Estrutura inicial de pastas.
- Docker Compose com PostgreSQL e Redis.
- Backend FastAPI mínimo.
- Frontend React/Vite mínimo.
- `.env.example`.
- Healthchecks da API e worker.

Entregáveis:
- Estrutura conforme `ESTRUTURA_REPO.md`.
- `infra/docker-compose.yml`.
- `backend/app/main.py`.
- `backend/app/api/v1/endpoints/health.py`.
- `backend/app/api/v1/endpoints/worker.py` com health básico.
- `frontend/package.json`, `vite.config.ts`, `src/main.tsx`.
- Scripts dev em `scripts/dev/`.

Entregues:
- `.env.example`.
- `infra/docker-compose.yml` com `name: lumen`.
- PostgreSQL em host `5435`.
- Redis em host `6382`.
- backend FastAPI mínimo.
- `GET /healthz`.
- `GET /api/v1/worker/health`.
- worker stub.
- frontend React/Vite em `5175`.
- smoke E2E Playwright.
- scripts PowerShell em `scripts/dev`.
- `README.md` e `ESTRUTURA_REPO.md` alinhados ao S1.

Portas locais reservadas para evitar conflito com eControle, CertHub e Scribere:
- API Lumen: `8000`
- Frontend Lumen: `5175`
- PostgreSQL host: `5435`
- Redis host: `6382`

Decisão técnica registrada:
- Docker Compose com project name fixo `lumen` para evitar conflito com CertHub, eControle e Scribere.

Validação:
```bash
docker compose -f infra/docker-compose.yml up -d
pip install -r requirements.txt
uvicorn backend.app.main:app --reload --port 8000
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/worker/health
cd frontend && npm install && npm run dev
```


Checklist de aceite validado localmente:
- Docker Compose sobe Postgres e Redis.
- Postgres responde.
- Redis responde `PONG`.
- API sobe.
- `/healthz` responde.
- `/api/v1/worker/health` responde.
- worker stub executa.
- frontend sobe em `5175`.
- `/lumen/painel` abre.
- `npm run typecheck` passa.
- `npm run test:e2e` passa.

Pendências técnicas não bloqueantes:
- normalizar encoding dos arquivos Markdown em tarefa separada;
- manter uso obrigatório de `.venv` local para evitar Python global;
- CertHub deve ser subido pelo compose próprio quando necessário, pois um container antigo `certhub-redis` foi removido manualmente durante a limpeza.

Aceite:
- API responde healthcheck.
- Redis e Postgres sobem localmente.
- Frontend abre página inicial sem erro.
- `.env` real não é versionado.

---

## S2 - Core backend: config, DB, migrations, auditoria e testes

Status: concluído em 2026-07-06

Objetivo:
- Criar a base técnica do backend para suportar domínio, integrações e jobs.

Escopo:
- Configuração por ambiente.
- Sessão DB.
- Alembic.
- Base declarativa SQLAlchemy.
- Serviço de auditoria.
- Harness de testes com banco isolado.

Entregáveis:
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/core/logging.py`
- `backend/app/db/session.py`
- `backend/app/db/base.py`
- `backend/alembic/`
- Modelo `audit_log`.
- Testes de config, DB e health.

Validação:
```bash
alembic -c backend/alembic.ini upgrade head
pytest backend/tests/test_health.py backend/tests/test_db.py
ruff check backend
```

Aceite:
- Migrations sobem do zero.
- Testes passam em ambiente limpo.
- Logs estruturados funcionam.
- Auditoria consegue registrar evento simples.

Entregues:
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/security.py` com utilitários mínimos sem JWT/RBAC
- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/app/models/__init__.py`
- `backend/app/models/audit_log.py`
- `backend/app/services/audit.py`
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- migration inicial `20260706_0001_create_audit_log.py`
- `backend/tests/conftest.py`
- `backend/tests/test_health.py`
- `backend/tests/test_config.py`
- `backend/tests/test_db.py`
- `backend/tests/test_audit.py`

Validação executada:
- `alembic -c backend/alembic.ini upgrade head`
- `pytest backend/tests/test_health.py backend/tests/test_config.py backend/tests/test_db.py backend/tests/test_audit.py`
- `ruff check backend`
- `Invoke-RestMethod http://localhost:8000/healthz`
- `Invoke-RestMethod http://localhost:8000/api/v1/worker/health`
- `cd frontend && npm run typecheck && npm run test:e2e`
- `alembic -c backend/alembic.ini downgrade base`
- `alembic -c backend/alembic.ini upgrade head`

Pendências:
- warning de deprecação do `fastapi.testclient` na stack atual; não bloqueia o stage

Decisões novas:
- healthchecks do S1 permanecem independentes de conexão obrigatória com banco
- banco de teste padrão do backend: `postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test`
- `audit_log` usa coluna física `metadata` mapeada para atributo Python `event_metadata`

## Fechamento tecnico S2 em 2026-07-06

Registro complementar de fechamento do Stage S2:

- status confirmado como concluido em `2026-07-06`
- entregaveis confirmados: config backend, logging basico, security minimo sem JWT/RBAC, DB session, SQLAlchemy Base, Alembic, migration `20260706_0001_create_audit_log`, model `audit_log`, service de auditoria, testes backend e `pytest.ini`
- validacoes registradas: `docker compose -f .\infra\docker-compose.yml ps`, `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select * from alembic_version;"`, `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "\dt"`, `pytest .\backend\tests\test_health.py .\backend\tests\test_config.py .\backend\tests\test_db.py .\backend\tests\test_audit.py`, `ruff check .\backend`
- resultado dos testes backend S2: `8 passed, 1 warning`
- banco principal confirmado em Alembic head `20260706_0001`
- tabelas confirmadas no banco principal: `alembic_version`, `audit_log`
- pendencia nao bloqueante registrada explicitamente: warning de deprecacao do `fastapi.testclient` / Starlette-httpx
- decisoes novas confirmadas: healthchecks S1 independentes de conexao obrigatoria com banco, banco principal padrao `lumen`, banco de teste padrao `lumen_test`, `pytest.ini` com `pythonpath = .`, testes backend usando `LUMEN_TEST_DATABASE_URL`

---

## S3 - Autenticação, RBAC e multi-tenant

Status: concluido em 2026-07-06

Objetivo:
- Proteger o Lumen e preparar isolamento por organização.

Escopo:
- Usuários, organizações e associação usuário-organização.
- Login JWT.
- Refresh/logout/me.
- RBAC `ADMIN`, `DEV`, `VIEW`.
- `org_id` como base de isolamento.

Entregáveis:
- Models: `organizations`, `users`, `user_organizations` ou equivalente.
- Endpoints:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/me`
- Dependências FastAPI para usuário atual e permissões.
- Seed de usuário admin local.

Validação:
```bash
pytest backend/tests/test_auth.py backend/tests/test_rbac.py
```

Aceite:
- Rotas protegidas exigem token.
- `VIEW` não executa mutações administrativas.
- Dados são filtrados por `org_id`.

Entregues:
- `backend/app/models/organization.py`
- `backend/app/models/user.py`
- `backend/app/models/user_organization.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/scripts/create_initial_admin.py`
- migration `backend/alembic/versions/20260706_0002_auth_rbac_multitenant.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_rbac.py`
- correção do harness de testes em `backend/tests/conftest.py` para voltar a respeitar `LUMEN_TEST_DATABASE_URL`

Validação executada:
- `docker compose -f .\infra\docker-compose.yml up -d`
- `alembic -c .\backend\alembic.ini upgrade head`
- `alembic -c .\backend\alembic.ini downgrade -1`
- `alembic -c .\backend\alembic.ini upgrade head`
- `pytest .\backend\tests\test_config.py .\backend\tests\test_health.py .\backend\tests\test_db.py .\backend\tests\test_audit.py .\backend\tests\test_auth.py .\backend\tests\test_rbac.py`
- `ruff check .\backend`
- `cd frontend && npm run typecheck && npm run test:e2e`

Pendências:
- warning de deprecação do `fastapi.testclient` / Starlette-httpx continua na stack atual
- o frontend ainda não possui login visual nem proteção de rotas; isso permanece para stage futuro
- por incompatibilidade prática de `passlib+bcrypt` nesta stack Windows, `backend/app/core/security.py` mantém `CryptContext` como caminho principal e usa fallback direto de `bcrypt` quando o backend do `passlib` falha no autoteste interno

Decisões novas:
- login oficial do S3 por email
- JWT com claims `sub`, `org_id`, `role`, `type`, `exp`, `iat`, `jti`, `ver`
- access token padrão de 15 minutos e refresh token padrão de 7 dias
- logout MVP por incremento de `token_version` e `last_logout_at`
- RBAC global no usuário com `ADMIN`, `DEV`, `VIEW`
- multi-tenant inicial por `organizations` e `user_organizations`
- organização ativa do MVP vinda de `users.default_organization_id`
- `audit_log` permaneceu sem `org_id` ou `user_id` dedicados no S3
- `GET /healthz` e `GET /api/v1/worker/health` permanecem públicos
- o smoke E2E atual do frontend em `/lumen/painel` permanece sem autenticação para não quebrar o fluxo vigente

## Fechamento tecnico S3 em 2026-07-06

Registro complementar de fechamento do Stage S3:

- status confirmado como concluido em `2026-07-06`
- entregaveis confirmados: auth JWT, RBAC global, multi-tenant inicial, deps FastAPI de auth, seed admin local idempotente, migration `20260706_0002_auth_rbac_multitenant`, testes de auth e RBAC
- correcao obrigatoria aplicada antes do fechamento: inconsistência entre `TEST_DATABASE_URL` e `LUMEN_TEST_DATABASE_URL` no harness de testes
- validações registradas: `docker compose -f .\infra\docker-compose.yml ps`, `alembic -c .\backend\alembic.ini upgrade head`, `alembic -c .\backend\alembic.ini downgrade -1`, `alembic -c .\backend\alembic.ini upgrade head`, `pytest .\backend\tests\test_config.py .\backend\tests\test_health.py .\backend\tests\test_db.py .\backend\tests\test_audit.py .\backend\tests\test_auth.py .\backend\tests\test_rbac.py`, `ruff check .\backend`, `cd frontend && npm run typecheck && npm run test:e2e`
- resultado dos testes backend S3: `22 passed, 1 warning`
- head confirmado no banco principal: `20260706_0002`
- tabelas confirmadas no S3: `organizations`, `users`, `user_organizations` e `audit_log`
- frontend smoke E2E mantido sem proteção de login para preservar `/lumen/painel`

---

## S3.1 - Frontend auth bridge

Status: concluido em 2026-07-06

Objetivo:
- Criar uma ponte minima entre o frontend e a autenticacao do S3 backend, deixando de expor o portal inteiro como publico.

Escopo:
- rota `/login`
- protecao de `/lumen/painel`
- login/logout/me no frontend
- store simples de autenticacao
- shell exibindo usuario, role global e organizacao ativa
- redirecionamento para `/login` em respostas `401`
- E2E cobrindo login e logout

Entregaveis:
- `frontend/src/services/apiClient.ts`
- `frontend/src/services/authService.ts`
- `frontend/src/stores/authStore.tsx`
- `frontend/src/features/auth/LoginPage.tsx`
- `frontend/src/features/auth/ProtectedRoute.tsx`
- ajuste de `frontend/src/main.tsx`
- ajuste de `frontend/src/app/LumenShell.tsx`
- ajuste de `frontend/tests_e2e/smoke.spec.ts`
- `frontend/scripts/run_e2e_stack.ps1`

Validacao:
```bash
cd frontend && npm run typecheck
cd frontend && npm run test:e2e
pytest backend/tests/test_auth.py backend/tests/test_rbac.py
ruff check backend
```

Aceite:
- `/login` abre sem token
- `/lumen/painel` exige autenticacao
- usuario autenticado ve email ou nome e organizacao ativa
- logout retorna para `/login`
- S4 nao e iniciado

Entregues:
- `frontend/src/services/apiClient.ts`
- `frontend/src/services/authService.ts`
- `frontend/src/stores/authStore.tsx`
- `frontend/src/features/auth/LoginPage.tsx`
- `frontend/src/features/auth/ProtectedRoute.tsx`
- `frontend/scripts/run_e2e_stack.ps1`
- `frontend/tests_e2e/smoke.spec.ts` atualizado para login e logout
- CORS local do backend ajustado para o frontend manual em `5175` e para o frontend isolado de E2E em `4176`

Validacao executada:
- `cd frontend && npm run typecheck`
- `cd frontend && npm run test:e2e`
- `pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py`
- `ruff check .\backend`

Pendencias:
- tokens seguem em `localStorage` no MVP; hardening futuro deve revisar armazenamento
- refresh automatico complexo continua fora de escopo
- warning do backend ligado a `passlib+bcrypt` continua aparecendo no boot do ambiente de teste, sem quebrar a autenticacao

Decisoes novas:
- `VITE_API_BASE_URL` passa a ser a variavel principal do frontend
- `VITE_LUMEN_API_BASE_URL` permanece apenas como fallback de compatibilidade
- o E2E usa stack dedicada em portas isoladas para nao depender de backend/frontend manuais
- S4 nao foi iniciado

## Fechamento tecnico S3.1 em 2026-07-06

Registro complementar de fechamento do Stage S3.1:

- status confirmado como concluido em `2026-07-06`
- entregaveis confirmados: login page, protected route, auth store simples, shell autenticado, logout, smoke E2E autenticado e script local de stack E2E
- validacoes registradas: `cd frontend && npm run typecheck`, `cd frontend && npm run test:e2e`, `pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py`, `ruff check .\backend`
- resultado dos testes frontend S3.1: `1 passed`
- resultado dos testes backend reaproveitados para S3.1: `14 passed, 1 warning`
- confirmacao explicita: S4 nao foi iniciado neste complemento

---

## S3.2 - Microajuste tecnico passlib/bcrypt

Status: concluido em 2026-07-06

Objetivo:
- remover o warning de compatibilidade do passlib/bcrypt no Windows sem alterar o fluxo funcional de autenticacao.

Entregues:
- pin de compatibilidade em `requirements.txt`: `bcrypt>=4.1.3,<5.0.0`
- shim minimo em `backend/app/core/security.py` para expor `bcrypt.__about__.__version__` antes do `CryptContext`
- remocao do warning `(trapped) error reading bcrypt version` no fluxo real do Lumen

Validacao executada:
- `python -m backend.scripts.create_initial_admin`
- `pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py`
- `ruff check .\backend`
- `cd frontend && npm run test:e2e`

Resultado:
- seed admin executou sem warning do bcrypt
- auth/RBAC: `14 passed, 1 warning` conhecido de Starlette/httpx
- ruff: `All checks passed`
- E2E: `1 passed`

Pendencias:
- warning de deprecacao do `fastapi.testclient` / Starlette-httpx permanece como pendencia nao bloqueante
- revisar estrategia de hash/senha no S18/hardening; o shim atual e solucao pragmatica de compatibilidade para MVP

Decisoes novas:
- manter `passlib` `1.7.4` no MVP
- fixar `bcrypt` em faixa `<5.0.0`
- aplicar shim local em `security.py` antes do `CryptContext` para evitar warning no Windows
- nao migrar estrategia de hash agora para evitar mudanca estrutural desnecessaria

Confirmacao:
- S4 nao foi iniciado
- nenhum modelo fiscal foi criado
- nenhum endpoint foi alterado
- nenhuma migration foi adicionada

---

## S4 - Modelo fiscal core e seeds iniciais

Status: concluido em 2026-07-07

Objetivo:
- Modelar o núcleo fiscal do Lumen antes das integrações externas.

Escopo:
- Empresas espelhadas.
- Competências.
- Obrigações.
- Status por empresa/competência.
- Evidências.
- Alertas.
- Parcelamentos.
- Runs de integração.

Entregáveis:
- Models/tabelas:
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
- Seeds para obrigações principais:
  - `DAS`
  - `DIFAL`
  - `ICMS`
  - `ISS`
  - `PIS`
  - `COFINS`
  - `PROTEGE`
  - `DCTFWEB`
  - `REINF`
  - `EFD_CONTRIBUICOES`
  - `DEFIS`
  - `DASN_SIMEI`
  - `PARCELAMENTO`
- Enum de status de conciliação:
  - `CONFIRMADO_ARQUIVO_ACESSORIAS`
  - `CONFIRMADO_API`
  - `CONFIRMADO_ARQUIVO`
  - `PENDENTE`
  - `PENDENTE_SEM_ARQUIVO`
  - `DIVERGENTE`
  - `DISPENSADO_AUTOMATICAMENTE`
  - `NAO_APLICAVEL`
  - `BAIXA_CONFIANCA`
  - `CONFERENCIA_MANUAL`

Validação:
```bash
alembic -c backend/alembic.ini upgrade head
python -m backend.scripts.seed_obligations
pytest backend/tests/test_models.py backend/tests/test_obligation_seed.py
```

Aceite:
- Banco sobe com entidades centrais.
- Seeds são idempotentes.
- Exclusão futura de empresa suportada por soft delete.

---

## Fechamento tecnico S4 em 2026-07-07

Registro complementar de fechamento do Stage S4:

- status confirmado como concluido em `2026-07-07`
- entregues: `backend/app/core/enums.py`, os 12 models fiscais do S4, migration `backend/alembic/versions/20260706_0003_create_fiscal_core.py`, seed `backend/scripts/seed_obligations.py`, testes `backend/tests/test_models.py` e `backend/tests/test_obligation_seed.py`, alem da atualizacao de `backend/app/models/__init__.py`
- banco principal confirmado em Alembic head `20260706_0003`
- tabelas confirmadas no S4: `external_companies`, `company_activity_types`, `fiscal_periods`, `fiscal_obligations`, `fiscal_obligation_rules`, `fiscal_obligation_statuses`, `fiscal_evidences`, `fiscal_alerts`, `fiscal_installments`, `integration_accounts`, `integration_sync_runs` e `watcher_file_events`
- validacoes registradas: `docker compose -f .\infra\docker-compose.yml up -d`, `docker compose -f .\infra\docker-compose.yml ps`, `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`, `.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations`, `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_models.py .\backend\tests\test_obligation_seed.py -q`, `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_config.py .\backend\tests\test_health.py .\backend\tests\test_db.py .\backend\tests\test_audit.py .\backend\tests\test_auth.py .\backend\tests\test_rbac.py -q`, `ruff check .\backend`, `cd .\frontend && npm run typecheck`, `cd .\frontend && npm run test:e2e`, `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini downgrade -1`, `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
- seed validado com exatamente `13` obrigacoes principais e segunda execucao idempotente com `created=0 updated=0 total=13`
- rollback validado para `20260706_0002` removendo apenas as tabelas do S4, seguido de novo upgrade para `20260706_0003`
- pendencia nao bloqueante: warning conhecido de deprecacao do `fastapi.testclient` / Starlette-httpx
- decisoes novas: enums Python + colunas `String` sem PostgreSQL ENUM nativo neste stage; `fiscal_obligations` global com `code` unico; `fiscal_obligation_rules.organization_id` nullable para regras globais do produto e futuros overrides por tenant
- confirmacao explicita: nenhum endpoint fiscal operacional novo, nenhuma integracao externa real, nenhum bypass de CAPTCHA e nenhuma alteracao de fluxo visual do frontend

## Fechamento tecnico S4.1 em 2026-07-07

Registro complementar de fechamento do micro-stage S4.1:

- observacao documental: o S4.1 foi tratado como micro-stage complementar de fechamento tecnico e nao como stage originalmente enumerado na sequencia macro do plano
- status confirmado como concluido em `2026-07-07`
- entregues: `backend/scripts/seed_obligation_rules.py`, `backend/scripts/seed_periods.py`, complemento seguro em `backend/scripts/seed_obligations.py`, `backend/tests/test_obligation_rules_seed.py` e `backend/tests/test_period_seed.py`
- nenhuma migration adicional foi criada porque as tabelas do S4 ja suportam o catalogo logico e os periodos
- validacoes registradas: `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`, `.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations`, `.\.venv\Scripts\python.exe -m backend.scripts.seed_obligation_rules`, `.\.venv\Scripts\python.exe -m backend.scripts.seed_periods --year 2026`, `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select count(*) from fiscal_obligations;"`, `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select count(*) from fiscal_obligation_rules;"`, `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select competencia from fiscal_periods order by competencia;"`, `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_obligation_seed.py .\backend\tests\test_obligation_rules_seed.py .\backend\tests\test_period_seed.py -q`, `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_models.py .\backend\tests\test_auth.py .\backend\tests\test_rbac.py -q`, `ruff check .\backend`, `cd .\frontend && npm run typecheck`, `cd .\frontend && npm run test:e2e`
- catalogo principal preservado com `13` codigos em `fiscal_obligations`
- regras-base sem duplicidade em `fiscal_obligation_rules`, incluindo separacao de `PIS`, `COFINS` e `EFD_CONTRIBUICOES` entre `LUCRO_PRESUMIDO` e `LUCRO_REAL`
- competencias 2026 sem duplicidade em `fiscal_periods`
- cada `condition_payload` passou a registrar `authority`, `jurisdiction_scope`, `normative_source_key`, `applicability_is_indicative = true` e `final_applicability_source`
- complemento registrado: regime fiscal canonico `IMUNE_ISENTA` adicionado ao catalogo tecnico, com label futuro `Imune/Isenta`
- nenhuma migration nova foi criada neste complemento, nenhuma obrigacao nova foi criada e nenhuma aplicabilidade real por empresa foi inferida para imunes/isentas
- pendencia futura registrada: avaliar inclusao de `DESTDA` no catalogo estadual para cenarios de Simples Nacional com ST, antecipacao ou DIFAL
- pendencia tecnica registrada: avaliar constraint unica futura para `fiscal_obligation_rules` considerando campos nullable `organization_id`, `obligation_id`, `regime`, `activity_type` e `rule_type`; motivo: o seed e idempotente por aplicacao, mas execucao paralela pode gerar duplicidade transitoria sem trava/constraint no banco
- confirmacao explicita: o micro-stage nao gera `fiscal_obligation_statuses` por empresa/competencia, nao cria integracoes externas, nao inicia eControle nem Acessorias e nao adiciona endpoints fiscais operacionais

## S5 - Integração eControle: espelho cadastral

Status: concluido

Objetivo:
- Sincronizar empresas do eControle para o Lumen sem acoplamento direto de banco.

Escopo:
- Cliente eControle.
- Import inicial.
- Webhook de upsert/soft delete.
- Reconciliação periódica.
- Detecção de divergências cadastrais básicas.

Entregáveis:
- `backend/app/services/integrations/econtrole/client.py`
- `mapper.py` e `sync.py`.
- Endpoints webhook:
  - `POST /api/v1/webhooks/econtrole/company-upsert`
  - `POST /api/v1/webhooks/econtrole/company-delete`
- Job `sync_econtrole_companies`.
- Campos mínimos em `external_companies`:
  - CNPJ, razão social, nome fantasia, apelido/pasta, situação, CNAEs, IE, IM, município, UF, raw payload.

Validação:
```bash
pytest backend/tests/test_econtrole_mapper.py backend/tests/test_econtrole_sync.py backend/tests/test_econtrole_webhook.py
```

Aceite:
- Upsert idempotente.
- Soft delete não apaga histórico fiscal.
- IE vazia é preservada como nula no banco e exibível como `ISENTO` no front.
- Divergência cadastral pode gerar alerta/auditoria.

---

## Fechamento tecnico S5 em 2026-07-07

Registro complementar de fechamento do Stage S5:

- status confirmado como concluido em `2026-07-07`
- entregues: `backend/app/services/integrations/econtrole/__init__.py`, `backend/app/services/integrations/econtrole/client.py`, `backend/app/services/integrations/econtrole/mapper.py`, `backend/app/services/integrations/econtrole/sync.py`, `backend/app/api/v1/endpoints/webhooks/__init__.py`, `backend/app/api/v1/endpoints/webhooks/econtrole.py`, `backend/scripts/sync_econtrole_companies.py`, `backend/tests/test_econtrole_mapper.py`, `backend/tests/test_econtrole_sync.py` e `backend/tests/test_econtrole_webhook.py`, alem do wiring em `backend/app/api/v1/api.py` e `backend/app/core/config.py`
- nenhuma migration adicional foi criada porque o schema existente de `external_companies`, `integration_sync_runs`, `audit_log` e `organizations` suportou o escopo do espelho cadastral
- validacoes registradas: `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`, `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econtrole_mapper.py .\backend\tests\test_econtrole_sync.py .\backend\tests\test_econtrole_webhook.py -q`, `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py .\backend\tests\test_models.py .\backend\tests\test_obligation_seed.py .\backend\tests\test_obligation_rules_seed.py .\backend\tests\test_period_seed.py -q`, `ruff check .\backend`, `cd .\frontend && npm run typecheck` e `cd .\frontend && npm run test:e2e`
- webhook de upsert e soft delete confirmado em `POST /api/v1/webhooks/econtrole/company-upsert` e `POST /api/v1/webhooks/econtrole/company-delete`, ambos protegidos por `X-Lumen-Webhook-Token`
- espelho cadastral confirmado em `external_companies` com upsert idempotente por `(organization_id, cnpj)`, reativacao apos soft delete e preservacao de `raw_econtrole`
- rastreabilidade confirmada em `integration_sync_runs` para o job `sync_econtrole_companies`
- decisoes novas: CNPJ normalizado para 14 digitos no espelho local; IE vazia/whitespace vira `NULL` e `ISENTO` so e preservado quando vier explicitamente do payload; webhooks nao usam JWT e falham com `401` se `ECONTROLE_WEBHOOK_TOKEN` estiver ausente ou invalido; organizacao e resolvida por `org_slug` ou fallback MVP de unica organizacao ativa; cliente HTTP usa timeout configuravel e path placeholder isolada `GET /companies`
- pendencia nao bloqueante registrada na validacao: a primeira tentativa de regressao backend em paralelo competiu pelo mesmo banco `lumen_test`; em execucao serial a suite passou integralmente sem ajuste de codigo do S5
- confirmacao explicita: o S5 nao cria `fiscal_obligation_statuses`, nao inicia Acessorias, nao cria frontend novo, nao usa banco direto do eControle e nao inicia S6

## S5.1 - Frontend fiscal funcional read-only com empresas reais

Status: parcialmente concluido

Objetivo:
- Entregar o primeiro portal fiscal funcional do Lumen, visualmente aderente ao shell previsto, consumindo apenas dados reais ja persistidos ate o S5.

Escopo:
- Endpoints read-only em `/api/v1/lumen/*`.
- Protecao por autenticacao e RBAC (`VIEW`, `ADMIN`, `DEV`).
- Frontend fiscal funcional com roteamento manual preservado.
- Estados vazios honestos quando tabelas operacionais ainda estiverem vazias.

Entregaveis backend:
- `GET /api/v1/lumen/companies?search=`
- `GET /api/v1/lumen/periods`
- `GET /api/v1/lumen/dashboard?period=YYYY-MM`
- `GET /api/v1/lumen/cockpit?period=YYYY-MM&companyId=&status=&department=&source=`
- `GET /api/v1/lumen/companies/{id}/summary?period=YYYY-MM`
- `GET /api/v1/lumen/deliveries?period=YYYY-MM&companyId=`
- `GET /api/v1/lumen/evidences?period=YYYY-MM&companyId=`
- `GET /api/v1/lumen/divergences?period=YYYY-MM&companyId=`
- `GET /api/v1/lumen/installments?period=YYYY-MM&companyId=`
- `GET /api/v1/lumen/integrations/health`
- `backend/app/services/lumen_read_model.py`
- `backend/tests/test_lumen_read_endpoints.py`

Entregaveis frontend:
- `frontend/src/app/LumenShell.tsx`
- `frontend/src/app/lumenRoutes.tsx`
- `frontend/src/stores/lumenUiStore.tsx`
- `frontend/src/services/lumenService.ts`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/layout/Topbar.tsx`
- `frontend/src/components/layout/ContextStrip.tsx`
- `frontend/src/components/selectors/CompanyDropdown.tsx`
- `frontend/src/components/selectors/PeriodDropdown.tsx`
- `frontend/src/components/ui/Badge.tsx`
- `frontend/src/components/ui/Button.tsx`
- `frontend/src/components/ui/Card.tsx`
- `frontend/src/components/ui/Hero.tsx`
- `frontend/src/components/ui/KpiCard.tsx`
- `frontend/src/components/ui/Progress.tsx`
- `frontend/src/components/ui/Table.tsx`
- `frontend/src/features/dashboard/DashboardPage.tsx`
- `frontend/src/features/cockpit/CockpitPage.tsx`
- `frontend/src/features/company/CompanyPage.tsx`
- `frontend/src/features/deliveries/DeliveriesPage.tsx`
- `frontend/src/features/evidences/EvidencesPage.tsx`
- `frontend/src/features/divergences/DivergencesPage.tsx`
- `frontend/src/features/installments/InstallmentsPage.tsx`
- `frontend/src/features/integrations/IntegrationsPage.tsx`
- `frontend/tests_e2e/smoke.spec.ts`
- `frontend/tests_e2e/shell.spec.ts`
- `frontend/tests_e2e/deliveries.spec.ts`

Validacao:
```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_lumen_read_endpoints.py -q
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py .\backend\tests\test_econtrole_mapper.py .\backend\tests\test_econtrole_sync.py .\backend\tests\test_econtrole_webhook.py -q
ruff check .\backend
cd .\frontend
npm run typecheck
npm run test:e2e
```

Aceite:
- `/login` permanece publico e `/lumen/*` permanece protegido.
- Sidebar, topbar, context strip e dropdowns funcionam sem `react-router-dom`.
- `external_companies` e `fiscal_periods` alimentam o portal.
- IE vazia continua sendo exibida como `ISENTO` apenas no frontend.
- KPIs zerados e listas vazias nao quebram a experiencia quando ainda nao existem dados fiscais operacionais.
- confirmacao explicita: o S6/Acessorias nao foi iniciado neste stage.
- pendencias visuais e de acabamento de UX ainda mantem o stage em fechamento parcial.

## S5.2 - Completion cadastral do eControle e backfill de reconciliacao

Status: concluido em 2026-08-20

Objetivo:
- completar automaticamente o cadastro da empresa apos webhook ou reconciliacao com o eControle
- permitir backfill operacional das empresas ja existentes, inclusive com diagnostico dos payloads invalidos de origem

Escopo:
- completion pos-webhook do eControle
- reprocessamento local de `company_cnaes`, regime Acessorias, CNAEs faltantes da Econet e `company_activity_types`
- inativacao automatica local quando o eControle informar `situacao = INATIVA`
- backfill de reconciliacao e completion para empresas ja persistidas

Entregues:
- `backend/app/services/integrations/econtrole/webhook_completion.py`
- `backend/scripts/backfill_econtrole_companies.py`
- `backend/tests/test_econtrole_webhook_completion.py`
- `backend/tests/test_backfill_econtrole_companies.py`
- ajuste em `backend/app/services/integrations/econtrole/sync.py` para disparar completion no upsert/delete e reconhecer `situacao = INATIVA`

Validacao executada:
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econtrole_sync.py .\backend\tests\test_econtrole_webhook.py .\backend\tests\test_econtrole_webhook_completion.py .\backend\tests\test_backfill_econtrole_companies.py -q`
- `.\.venv\Scripts\python.exe .\backend\scripts\backfill_econtrole_companies.py --org-slug neto-contabilidade --dry-run`
- `.\.venv\Scripts\python.exe -c "from backend.app.db.session import SessionLocal; from backend.scripts.backfill_econtrole_companies import run_backfill; import json; s=SessionLocal(); r=run_backfill(s, org_slug='neto-contabilidade', dry_run=True); print(json.dumps(r, ensure_ascii=False, indent=2)); s.close()"`

Resultados e validacoes reais registradas:
- reconciliacao dry-run validada em `2026-08-20` contra `http://localhost:8020/api/v1/companies`
- `228` empresas recebidas do eControle
- `2` criacoes potenciais e `223` updates potenciais no espelho local
- `3` payloads invalidos detectados por ausencia de `cnpj`, todos identificados nominalmente no resumo do backfill
- etapa local do mesmo dry-run processou `250` empresas sem erro
- `28` retries de Acessorias ficaram pendentes
- `4` CNAEs ainda estavam ausentes do cache da Econet no momento da validacao

Decisoes novas:
- `ECONTROLE_API_BASE_URL` deve apontar para a raiz que permita resolver `GET /companies`; no ambiente validado isso ficou em `http://localhost:8020/api/v1`
- payload do eControle sem `cnpj` e tratado como invalido; o caso nao deve ser “corrigido” no Lumen por inferencia
- o backfill pode reprocessar apenas o banco local com `--skip-econtrole-sync` quando a API do eControle nao estiver disponivel

Pendencias aceitas:
- os `3` registros sem `cnpj` permanecem como problema de origem do eControle e podem ser ignorados operacionalmente ate saneamento no sistema fonte

## S6 - Integração Acessórias: regime, obrigações e entregas

Status: concluido em 2026-07-15

Micro-stage preparatorio concluido em 2026-07-14:

- `docs/ACESSORIAS_CONTRACT.md`
- `docs/examples/sample_acessorias_company.json`
- `docs/examples/sample_acessorias_delivery.json`
- `schemas/acessorias_company.schema.json`
- `schemas/acessorias_delivery.schema.json`
- confirmacao formal de que o Acessorias possui API oficial documentada
- confirmacao formal de que o S6 usara somente operacoes de consulta

Premissas oficiais congeladas para o S6:

- documentacao oficial: `https://api.acessorias.com/documentation`
- base URL oficial: `https://api.acessorias.com`
- autenticacao: `Authorization: Bearer <token>`
- token gerado no proprio Sistema Acessorias pela opcao `API Token`
- rate limit documentado: `100` requisicoes por minuto
- nao e necessario usar DevTools, HAR ou engenharia reversa para o Acessorias
- Sittax e Econet continuam como integracoes que podem depender de requisicoes observadas em etapas futuras
- nenhuma inclusao, edicao, transmissao ou alteracao externa faz parte do S6

Objetivo:
- Trazer a fonte oficial de regime tributário e status formal das obrigações.

Escopo:
- Cliente Acessórias.
- Sync de empresas/entregas por competência.
- Snapshot de entregas.
- Upsert em `fiscal_obligation_statuses`.
- Runs rastreáveis.

Entregáveis:
- `acessorias_delivery_snapshots`.
- Cliente e mapper de Acessórias.
- Job `sync_acessorias_deliveries`.
- Endpoint manual `POST /api/v1/integrations/acessorias/sync` (`ADMIN|DEV`).
- Health de integração.

Regras:
- Regime oficial do Lumen = regime do Acessórias.
- Se regime divergir do eControle, usar Acessórias e gerar alerta cadastral.
- o S6 deve permanecer read-only para a fonte Acessorias
- o sync inicial deve priorizar seguranca e previsibilidade sobre paralelismo ou throughput

Validação:
```bash
pytest backend/tests/test_acessorias_mapper.py backend/tests/test_acessorias_sync.py backend/tests/test_regime_precedence.py
```

Aceite:
- Sync idempotente por empresa/competência.
- Status entregue/pendente refletido no domínio fiscal.
- Runs têm contadores, erros e resumo.

Entregues:
- configuracao `ACESSORIAS_API_BASE_URL`, `ACESSORIAS_API_TOKEN`, `ACESSORIAS_TIMEOUT_SECONDS` e `ACESSORIAS_REQUESTS_PER_MINUTE`
- migration `20260714_0004_create_acessorias_snapshots.py`
- tabelas `acessorias_company_snapshots` e `acessorias_delivery_snapshots`
- cliente oficial read-only com Bearer Token, rate limit serial, tratamento de `204`, `401`, `404`, `429`, JSON invalido e erro de negocio
- mapper puro para empresas, entregas, datas, identificadores e status
- mapping explicito de regime e aliases seguros de obrigacoes
- sync serial de empresas por `ListAll + registrationData`
- sync serial de entregas por empresa e intervalo mensal com `config`
- upsert restrito de `fiscal_obligation_statuses` apenas para empresa local + obrigacao mapeada + `Config.Tipo = O`
- alerta idempotente `REGIME_DIVERGENCE_ACESSORIAS_ECONTROLE`
- endpoint manual `POST /api/v1/integrations/acessorias/sync` com RBAC `ADMIN|DEV`
- script `backend/scripts/sync_acessorias_deliveries.py` com fixture mode
- health da integracao e precedencia do regime no read model do portal
- testes backend `test_acessorias_client.py`, `test_acessorias_mapper.py`, `test_acessorias_sync.py`, `test_acessorias_endpoint.py`, `test_regime_precedence.py`
- E2E `frontend/tests_e2e/integrations.spec.ts`

Validacao executada:
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_acessorias_client.py .\backend\tests\test_acessorias_mapper.py .\backend\tests\test_acessorias_sync.py .\backend\tests\test_acessorias_endpoint.py .\backend\tests\test_regime_precedence.py .\backend\tests\test_lumen_read_endpoints.py -q`
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py .\backend\tests\test_models.py .\backend\tests\test_econtrole_mapper.py .\backend\tests\test_econtrole_sync.py .\backend\tests\test_econtrole_webhook.py -q`
- `.\.venv\Scripts\python.exe -m ruff check .\backend`
- `.\.venv\Scripts\python.exe -m backend.scripts.sync_acessorias_deliveries --org-slug neto-contabilidade --period 2026-06 --companies-fixture .\backend\tests\fixtures\acessorias\companies_sample.json --deliveries-fixture .\backend\tests\fixtures\acessorias\deliveries_sample.json`
- `cd frontend && npm run typecheck && npm run test:e2e`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini downgrade -1`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
- `.\.venv\Scripts\python.exe -m backend.scripts.create_initial_admin`
- `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login ...`
- `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/integrations/acessorias/sync ...`
- `.\.venv\Scripts\python.exe -m backend.scripts.sync_acessorias_deliveries --org-slug neto-contabilidade --period 2026-06 --company-id 78 --dry-run`
- `.\.venv\Scripts\python.exe -m backend.scripts.sync_acessorias_deliveries --org-slug neto-contabilidade --period 2026-06 --skip-deliveries --dry-run`

Pendencias:
- a validacao com fixture na base principal confirmou snapshots e runs, mas nao criou `fiscal_obligation_statuses` porque os CNPJs anonimizados nao existem em `external_companies` da organizacao local usada na execucao manual
- a sincronizacao incremental global por `ListAll + DtLastDH` continua fora desta primeira entrega do S6
- o `dry_run` amplo por tenant pode demorar ou bloquear em handshake TLS externo; a validacao operacional recomendada no estado atual e por empresa (`--company-id`) ou apenas cadastro/regime (`--skip-deliveries`)

Decisoes novas:
- usar exclusivamente a API oficial documentada em `https://api.acessorias.com/documentation`
- restringir o S6 a `GET /companies/{identificador}` e `GET /deliveries/{identificador}`
- nao baixar anexos no sync padrao e nao persistir links temporarios
- manter tarefas `Config.Tipo = T` apenas em snapshot, sem criar `fiscal_obligation_statuses`
- nao mapear obrigacoes por aproximacao e nao mapear `GPS` automaticamente para `DCTFWEB`
- manter rollback de codigo e migration coordenados; durante downgrade controlado das tabelas `acessorias_*`, o read model deve ser revertido junto da migration em deploy real
- para validacao manual via endpoint HTTP, o usuario autenticado precisa pertencer a uma organizacao que possua `external_companies` correspondentes ao tenant consultado no Acessorias; no ambiente local isso significou diferenciar `lumen` de `neto-contabilidade`

## S6.2 - Backfill operacional retroativo do Acessorias

Status: concluido em 2026-08-03

Objetivo:
- materializar um backfill reproduzivel para preencher os dados do Acessorias usando apenas schema e servicos ja existentes

Entregues:
- `backend/app/services/integrations/acessorias/backfill.py`
- `backend/scripts/backfill_acessorias.py`
- `backend/tests/test_acessorias_backfill.py`
- `backend/tests/test_backfill_acessorias_script.py`
- reaproveitamento do sync Acessorias existente com `run_metadata` adicional para rastrear backfill por competencia
- ampliacao do mapeamento de regimes reais do Acessorias, incluindo filiais
- normalizacao segura de `EntGuiaLida` no snapshot de entregas
- filtro opcional `--fiscal-only` no sync mensal e no backfill

Decisoes novas:
- o regime tributario atual oficial da empresa no Lumen e o `regime_canonical` do `acessorias_company_snapshots` vinculado a empresa local
- `external_companies` continua sendo apenas espelho cadastral do eControle
- o schema atual nao possui historico legal de regime; o snapshot do Acessorias representa somente o estado atual observado
- o backfill foi dividido em duas fases: sincronizacao cadastral unica e processamento serial de entregas por intervalo
- a retomada do backfill e baseada em idempotencia de snapshots e `fiscal_obligation_statuses`, sem `--resume` heuristico
- `Filial - Regime Normal` deve herdar o regime canonico da mesma raiz de CNPJ quando houver um unico regime mapeado no grupo
- `--fiscal-only` limita o snapshot de entregas a itens operacionais pertinentes ao fiscal, sem alterar o comportamento padrao quando a flag nao e usada

Validacao esperada:
- `python -m backend.scripts.backfill_acessorias --org-slug <slug> --from-period YYYY-MM --to-period YYYY-MM`
- `pytest backend/tests/test_acessorias_backfill.py backend/tests/test_backfill_acessorias_script.py`

Validacao executada:
- `python -m backend.scripts.backfill_acessorias --org-slug neto-contabilidade --from-period 2026-01 --to-period 2026-07`
- conferencia SQL de `acessorias_company_snapshots`, `acessorias_delivery_snapshots` e `fiscal_obligation_statuses`
- consulta de duplicidades por `organization_id + external_company_id + external_delivery_id`
- `pytest backend/tests/test_acessorias_mapper.py backend/tests/test_acessorias_sync.py backend/tests/test_acessorias_backfill.py backend/tests/test_backfill_acessorias_script.py -q`

Resultados principais validados em 2026-08-03:
- backfill concluido com `status = SUCCESS`
- intervalo processado integralmente com `periods_success = 7` e `periods_failed = 0`
- fase cadastral executada com `companies_received = 221`, `companies_matched = 218` e `companies_unmatched = 3`
- regime atual oficial do Acessorias retroalimentado em snapshot; o resumo do run registrou `regimes_mapped = 3` e `regimes_unmapped = 218`
- conferencia SQL final de cadastro mostrou `223` snapshots de empresa, `218` vinculados a empresa local e `5` com `regime_mapping_status = 'MAPPED'`
- fase de entregas concluida com `deliveries_received = 10999`, `delivery_snapshots_created = 10999`, `statuses_created = 196` e `tasks_skipped = 328`
- nenhuma duplicidade encontrada em `acessorias_delivery_snapshots`

Complementos validados em 2026-08-04:

- labels reais de regime do Acessorias passaram a normalizar corretamente para `SIMPLES_NACIONAL`, `MEI`, `LUCRO_PRESUMIDO`, `LUCRO_REAL` e `IMUNE_ISENTA`
- `Filial - Simples Nacional` ficou mapeado diretamente para `SIMPLES_NACIONAL`
- `Filial - Regime Normal` ficou coberto por inferencia segura a partir da mesma raiz de CNPJ
- `EntGuiaLida` passou a ser normalizado para valores curtos compativeis com `guide_read_status`
- `--fiscal-only` ficou coberto em sync e backfill sem regressao do comportamento padrao
- regressao impactada do Acessorias executada com `29 passed`

Rerun real complementar executado em 2026-08-04:

- `python -m backend.scripts.backfill_acessorias --org-slug neto-contabilidade --from-period 2026-01 --to-period 2026-07 --only-active --fiscal-only`
- `run_id` reais por competencia de `116` a `122`, todos com `status = SUCCESS`
- rerun idempotente confirmado com `delivery_snapshots_created = 0` e apenas `delivery_snapshots_updated` no intervalo
- o filtro `--fiscal-only` removeu itens nao pertinentes do snapshot, registrando `deliveries_filtered_out` em todos os meses processados
- conferencia SQL final de regimes mostrou apenas linhas `MAPPED` nos canonicos `SIMPLES_NACIONAL`, `LUCRO_PRESUMIDO`, `LUCRO_REAL` e `IMUNE_ISENTA`
- filiais com `Filial - Regime Normal` e `Filial - Simples Nacional` ficaram validadas no banco real com o canonico esperado

Confirmacoes de escopo:
- nenhuma migration nova
- nenhuma tabela nova
- nenhuma alteracao em `external_companies`
- nenhuma alteracao de frontend
- somente endpoints `GET` do Acessorias
- nenhum download de anexo
- nenhuma transmissao fiscal

Observacao:
- o S6.2 e micro-stage complementar e nao reabre S7, S8 ou outros stages posteriores

## S6.3 - Retry automatico de regime da Acessorias por empresa

Status: concluido em 2026-08-20

Objetivo:
- automatizar o retry de sync pontual de regime da Acessorias para empresas que ainda nao existem na fonte no momento do webhook
- evitar loop infinito para empresas que realmente nunca estarao no Acessorias

Escopo:
- persistir pendencias de retry na base existente
- processar apenas retries vencidos
- fechar pendencias bem-sucedidas
- cancelar ou esgotar retries sem criar scheduler externo novo

Entregues:
- `backend/app/services/integrations/econtrole/webhook_completion.py` com processador de retries vencidos
- `backend/scripts/process_acessorias_retries.py`
- `backend/app/worker/runner.py` em modo `--once` processando retries da Acessorias
- ajuste do health do worker para refletir o processador real
- ampliacao de `backend/tests/test_econtrole_webhook_completion.py`
- atualizacao de `backend/tests/test_health.py`

Validacao executada:
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econtrole_webhook_completion.py .\backend\tests\test_backfill_econtrole_companies.py .\backend\tests\test_health.py -q`
- `.\.venv\Scripts\python.exe .\backend\scripts\process_acessorias_retries.py`
- `.\.venv\Scripts\python.exe .\backend\scripts\process_acessorias_retries.py --dry-run`
- `.\.venv\Scripts\python.exe -m backend.app.worker.runner --once`

Resultados e validacoes reais registradas:
- suite focada aprovada com `15 passed`
- processador manual e worker `--once` executaram com `selected = 0` no momento da conferencia final, confirmando que nao havia retries vencidos pendentes naquela janela
- o dry-run do backfill eControle de `2026-08-20` registrou `28` retries pendentes ainda nao vencidos na Acessorias

Decisoes novas:
- retries de Acessorias sao persistidos em `integration_sync_runs` com `provider = ACESSORIAS` e `job_name = sync_acessorias_company_webhook_retry`
- retries usam `retry_after = now + 24h`
- `SUCCESS` encerra a pendencia
- `EXHAUSTED` e atingido apos `5` tentativas
- `CANCELLED` e aplicado quando a empresa local estiver inativa ou ausente
- o worker atual continua simples e orientado a execucao `--once`; isto nao inaugura o macro-stage S16

Confirmacao de escopo:
- nenhuma migration nova
- nenhuma fila externa nova
- nenhum scheduler APScheduler/Celery/RQ dedicado
- nenhum write-back para o Acessorias alem do snapshot local do Lumen

## S7 - Sittax read-only: Simples, DAS, DIFAL e documentos fiscais

Status: pendente

Objetivo:
- Integrar dados do Sittax para enriquecer a operação do Simples Nacional, especialmente apuração, DAS, DIFAL, documentos fiscais importados e tarefas/transmissões.

Justificativa:
- O Sittax é uma das integrações centrais do Lumen.
- Depois do eControle e do Acessórias, é a fonte operacional mais importante para empresas do Simples Nacional.
- Essa integração deve vir antes de novos refinamentos visuais, porque ela alimentará o Cockpit, Envios, Evidências, Divergências e futuras regras de conciliação.

Premissas:
- A integração é somente leitura.
- Tratar Sittax como integração baseada em endpoints observados, até confirmação formal.
- Não acionar transmissão, envio, recálculo ou qualquer ação fiscal externa.
- Não usar endpoints com `recalcular=true`.
- Não chamar endpoints de transmissão.
- Não processar várias empresas em paralelo usando a mesma sessão quando o endpoint depender de contexto empresa/período.

Escopo:
- Login por endpoint com JWT Bearer.
- Sessão/controlador de autenticação.
- Listagem de empresas.
- Mapeamento de empresas Sittax com empresas espelhadas do eControle.
- Consulta de apuração por CNPJ e período.
- Consulta de DIFAL respeitando contexto de sessão.
- Consulta de documentos fiscais de entrada.
- Consulta de documentos fiscais de saída.
- Consulta de tarefas/transmissões.
- Snapshots locais.
- Health da integração.
- Fixture mode para testes sem token real.

Endpoints observados e candidatos:
- `POST https://autenticacao.sittax.com.br/api/auth/login`
- `GET /api/empresa/listar-todas-escritorio-empresas-selecao`
- `GET /api/apuracao/retornar-apuracao-sittax?empresaCnpj=...&periodo=...`
- `GET /api/difal/obter-valores-difal?recalcular=false`
- `GET /api/nota-fiscal/lista-nota-fiscal-entrada-paginacao`
- `GET /api/nota-fiscal/lista-nota-fiscal-saida-paginacao`
- `GET /api/tarefa/paginacao`

Regra técnica crítica:
- A chamada de apuração com `empresaCnpj` e `periodo` define o contexto da sessão.
- O endpoint de DIFAL usa esse contexto.
- O conector não deve consultar DIFAL de empresas diferentes em paralelo na mesma sessão.
- Usar fila sequencial, lock de contexto ou sessões isoladas.

Entregáveis de banco:
- `sittax_company_snapshots`
- `sittax_apuracao_snapshots`
- `sittax_difal_snapshots`
- `sittax_fiscal_document_snapshots`
- `sittax_task_snapshots`, se necessário

Entregáveis backend:
- `backend/app/models/sittax_company_snapshot.py`
- `backend/app/models/sittax_apuracao_snapshot.py`
- `backend/app/models/sittax_difal_snapshot.py`
- `backend/app/models/sittax_fiscal_document_snapshot.py`
- `backend/app/models/sittax_task_snapshot.py`
- migration para snapshots Sittax
- `backend/app/services/integrations/sittax/client.py`
- `backend/app/services/integrations/sittax/session.py`
- `backend/app/services/integrations/sittax/mapper.py`
- `backend/app/services/integrations/sittax/sync.py`
- `backend/app/services/integrations/sittax/context_lock.py`
- `backend/app/api/v1/endpoints/integrations/sittax.py`
- `backend/app/schemas/sittax.py`
- `backend/scripts/sync_sittax.py`

Jobs:
- `sync_sittax_companies`
- `sync_sittax_apuracao_period`
- `sync_sittax_difal_period`
- `sync_sittax_fiscal_documents`
- `sync_sittax_tasks`

Variáveis de ambiente:
```powershell
SITTAX_AUTH_BASE_URL=https://autenticacao.sittax.com.br
SITTAX_API_BASE_URL=https://api.sittax.com.br
SITTAX_APURACAO_BASE_URL=https://apuracao.sittax.com.br
SITTAX_EMAIL=
SITTAX_PASSWORD=
SITTAX_API_TOKEN=
SITTAX_TIMEOUT_SECONDS=20
````

Observação de segurança:

* Senha, token JWT, cookies e headers sensíveis nunca devem ser versionados.
* Logs devem mascarar `Authorization`, `password`, `token`, `apiKey`, cookies e qualquer JWT.

Campos úteis da apuração:

* CNPJ
* razão social
* período
* receita líquida
* receita de produtos
* receita de serviços
* RBT12
* RBA
* valor do DAS
* valor do DAS por XML
* anexos
* CFOPs
* se possui folha
* CNAEs/atividades
* alertas
* erros
* riscos

Campos úteis do DIFAL:

* possui guia
* número DARE
* valor total
* valor de revenda
* valor de uso/consumo/imobilizado
* data de fechamento
* data de transmissão
* total de compras
* mensagem
* notas sem tipo/referência

Campos úteis dos documentos fiscais:

* chave de acesso
* modelo
* número
* data de emissão
* data de entrada
* competência
* UF emitente/destinatário
* CFOP
* valor
* presença de XML
* tipo entrada/saída

Validação:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_sittax_client.py .\backend\tests\test_sittax_mapper.py .\backend\tests\test_sittax_context_lock.py .\backend\tests\test_sittax_sync.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend
```

Aceite:

* Login Sittax funciona em ambiente local autorizado.
* Empresas são salvas em snapshot de forma idempotente.
* Apuração por CNPJ/período é salva em snapshot.
* DIFAL é consultado sem mistura de contexto entre empresas.
* Documentos fiscais de entrada/saída são persistidos em snapshot.
* Tarefas/transmissões são persistidas quando disponíveis.
* Nenhuma transmissão, recálculo ou mutação externa é executada.
* Health da integração aparece em `/api/v1/lumen/integrations/health`.
* Fixture mode permite testar sem credenciais reais.

### Micro-stage S7.0 - Contrato observado, seguranca dos artefatos e fixtures anonimizadas

Status: concluido em 2026-07-15

Entregues:
- `docs/SITTAX_OBSERVED_CONTRACT.md`
- `docs/DECISOES.md`
- `docs/RISCOS.md`
- `docs/SECURITY.md`
- fixtures anonimizadas em `backend/tests/fixtures/sittax/`
- schemas observados em `schemas/sittax_*.schema.json`
- testes `backend/tests/test_sittax_fixture_safety.py` e `backend/tests/test_sittax_observed_schemas.py`
- isolamento do stack E2E dedicado contra `ACESSORIAS_API_TOKEN`, `SITTAX_EMAIL`, `SITTAX_PASSWORD` e `SITTAX_API_TOKEN` vindos do `.env` local

Validacao executada:
- `git check-ignore -v .\scripts\scan\logs\sittax-network-log.jsonl`
- `git ls-files | Select-String -Pattern "sittax-network-log|sittax-network"`
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_sittax_fixture_safety.py .\backend\tests\test_sittax_observed_schemas.py -q`

Pendencias:
- o macro-stage S7 continua pendente
- cliente HTTP real, models, migrations e sync real seguem fora de escopo

Decisoes novas:
- a regra de contexto por `empresaCnpj` e `periodo` fica registrada como confirmada
- nenhuma chamada externa nova foi autorizada neste micro-stage
- o log bruto do Sittax permanece fora do Git e nao gera fixture automatica

### Micro-stage S7.1 - Cliente base: autenticacao, sessao exclusiva e empresas

Status: concluido em 2026-07-16

Entregues:
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
- ajuste de `frontend/tests_e2e/integrations.spec.ts` para consolidar o card Sittax sem operacao externa

Validacao executada:
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_sittax_client.py .\backend\tests\test_sittax_session.py .\backend\tests\test_sittax_mapper.py .\backend\tests\test_sittax_connection_script.py -q`
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests -q`
- `.\.venv\Scripts\python.exe -m ruff check .\backend`
- `cd .\frontend && npm run typecheck && npm run test:e2e`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini heads`
- `.\.venv\Scripts\python.exe -m backend.scripts.check_sittax_connection --fixture`
- `.\.venv\Scripts\python.exe -m backend.scripts.check_sittax_connection`

Pendencias:
- o macro-stage S7 continua pendente
- apuracao, DIFAL, documentos fiscais, painel e tarefas seguem fora de escopo
- snapshots, sync, endpoint manual e health funcional seguem fora de escopo

Decisoes novas:
- a fundacao do Sittax nasce stateful e exclusiva por sessao, sem `httpx.Client` global
- o JWT permanece apenas em memoria dentro de `SittaxSession`
- o escritorio e resolvido deterministicamente a partir do login observado
- a listagem de empresas continua sem persistencia e sem reconciliacao neste micro-stage
- fixture mode e script de conectividade validam apenas login e empresas
- a validacao real confirmou `157` empresas retornadas no tenant autorizado
- o login real do portal foi homologado com sucesso por `codigo = 200`; o mapper passou a aceitar `0` e `200` como sucesso observado

### Micro-stage S7.2 - Snapshot de empresas e reconciliacao cadastral

Status: concluido em 2026-07-16

Objetivo:
- persistir localmente o snapshot read-only da listagem de empresas Sittax
- reconciliar cada empresa por `organization_id + cnpj`

Entregues:
- `backend/app/models/sittax_company_snapshot.py`
- migration `20260716_0005_create_sittax_company_snapshots.py`
- `backend/app/services/integrations/sittax/sync.py`
- `backend/scripts/sync_sittax_companies.py`
- `backend/tests/test_sittax_company_snapshot.py`
- `backend/tests/test_sittax_company_sync.py`
- `backend/tests/test_sync_sittax_companies_script.py`

Validacao executada:
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_sittax_company_snapshot.py .\backend\tests\test_sittax_company_sync.py .\backend\tests\test_sync_sittax_companies_script.py -q`
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests -q`
- `.\.venv\Scripts\python.exe -m ruff check .\backend`
- `cd .\frontend && npm run typecheck && npm run test:e2e`
- `.\.venv\Scripts\python.exe -m backend.scripts.check_sittax_connection --fixture`
- `.\.venv\Scripts\python.exe -m backend.scripts.check_sittax_connection`
- `.\.venv\Scripts\python.exe -m backend.scripts.sync_sittax_companies --org-slug neto-contabilidade --dry-run`
- `.\.venv\Scripts\python.exe -m backend.scripts.sync_sittax_companies --org-slug neto-contabilidade`
- `.\.venv\Scripts\python.exe -m backend.scripts.sync_sittax_companies --org-slug neto-contabilidade`
- `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select count(*) from sittax_company_snapshots;"`
- `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select match_status, count(*) from sittax_company_snapshots group by match_status order by match_status;"`
- `docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select organization_id, sittax_company_id, count(*) from sittax_company_snapshots group by organization_id, sittax_company_id having count(*) > 1;"`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini downgrade -1`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current`
- `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`

Decisoes novas:
- o snapshot e multi-tenant e idempotente por `organization_id + sittax_company_id`
- a reconciliacao local usa `organization_id + cnpj` e trata `MATCHED`, `UNMATCHED`, `AMBIGUOUS` e `INVALID_CNPJ`
- `state_registration` continua nullable
- `raw_payload` fica apenas no snapshot; `integration_sync_runs` recebem apenas resumo seguro
- `dry_run` nao escreve banco e fixture mode nao acessa rede
- o sync Sittax continua limitado a login e listagem de empresas, sem apuracao, sem contexto ativo e sem mutacao externa
- a validacao real final do S7.2 confirmou `157` snapshots, `155` `MATCHED`, `2` `UNMATCHED` e segunda execucao real com `snapshots_created = 0`

### Micro-stage S7.3 - Apuracao Sittax por empresa e competencia

Status: concluido em 2026-07-16

Entregues:
- `backend/app/models/sittax_apuracao_snapshot.py`
- `backend/alembic/versions/20260716_0006_create_sittax_apuracao_snapshots.py`
- `backend/scripts/sync_sittax_apuracoes.py`
- `backend/tests/test_sittax_apuracao_mapper.py`
- `backend/tests/test_sittax_apuracao_client.py`
- `backend/tests/test_sittax_apuracao_snapshot.py`
- `backend/tests/test_sittax_apuracao_sync.py`
- `backend/tests/test_sync_sittax_apuracoes_script.py`

Validacao executada:
- `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_sittax_apuracao_mapper.py .\backend\tests\test_sittax_apuracao_client.py .\backend\tests\test_sittax_apuracao_snapshot.py .\backend\tests\test_sittax_apuracao_sync.py .\backend\tests\test_sync_sittax_apuracoes_script.py -q`
- `.\.venv\Scripts\python.exe -m ruff check .\backend`

Pendencias:
- validacao real controlada de uma empresa e do lote pequeno ainda nao executadas neste fechamento
- suites completas de backend e frontend ainda precisam ser rodadas no fechamento operacional completo

Decisoes novas:
- a apuracao usa `empresaCnpj + periodo` como setter real do contexto
- o contexto e limpo antes de cada tentativa e so e confirmado apos resposta coerente
- a competencia e resolvida obrigatoriamente em `fiscal_periods`
- o sync de apuracoes permanece serial, read-only e sem chamadas de DIFAL, documentos, painel ou tarefas

### Micro-stage S7.4 - DIFAL, documentos fiscais e tarefas do Sittax

Status: concluido em 2026-07-17

Observacao de 2026-07-17:
- a validacao real confirmou que a apuracao funciona no host `apuracao.sittax.com.br`, mas o host `api.sittax.com.br` continua sem empresa ativa no replay HTTP hoje conhecido
- o conector ja foi corrigido para separar contexto por host, bloquear DIFAL/documentos sem contexto de API e falhar cedo com diagnostico sanitizado
- a conclusao do micro-stage depende da comprovacao do mecanismo real de handoff da empresa para o host API

Objetivo:
- completar o Sittax como fonte operacional read-only do Simples no Lumen, adicionando DIFAL, documentos fiscais e tarefas/transmissoes sobre o contexto ja definido pela apuracao

Escopo:
- consultar DIFAL somente apos apuracao valida da mesma empresa/competencia
- consultar documentos fiscais de entrada e saida com paginacao controlada
- consultar tarefas/transmissoes do Sittax em modo read-only
- persistir snapshots locais multi-tenant para DIFAL, documentos e tarefas
- manter execucao serial por sessao, sem paralelismo e sem mutacao externa
- enriquecer sinais operacionais para Cockpit, Envios, Evidencias e Divergencias sem expor o frontend ainda

Entregaveis de dados:
- `backend/app/models/sittax_difal_snapshot.py`
- `backend/app/models/sittax_fiscal_document_snapshot.py`
- `backend/app/models/sittax_task_snapshot.py`
- migration incremental apos o head vigente do S7.3

Entregaveis de integracao:
- expansao do cliente Sittax para:
  - `GET /api/difal/obter-valores-difal?recalcular=false`
  - `GET /api/nota-fiscal/lista-nota-fiscal-entrada-paginacao`
  - `GET /api/nota-fiscal/lista-nota-fiscal-saida-paginacao`
  - `GET /api/tarefa/paginacao`
- mappers read-only especificos para DIFAL, documentos e tarefas
- sync operacional serial reutilizando o contexto da apuracao dentro da mesma sessao exclusiva

Regras obrigatorias:
- toda consulta contextual comeca por apuracao valida da empresa/competencia solicitada
- `recalcular=true` e proibido
- nenhuma rota de transmissao, painel, upload, fechamento, exclusao ou escrita externa pode ser chamada
- documentos devem respeitar paginacao deterministica e sem loops infinitos
- tarefas nao devem ser tratadas como prova absoluta de entrega sem cruzamento futuro
- erros e logs continuam sanitizados, sem CNPJ completo, payload bruto, token ou credenciais em `integration_sync_runs`

Escopo detalhado por fonte:

1. DIFAL
- capturar possui guia, numeros DARE, valores por tipo, data de fechamento, data de transmissao, total de compras, mensagens e inconsistencias
- persistir um snapshot por empresa/competencia
- nao recalcular nem corrigir contexto automaticamente

2. Documentos fiscais
- capturar entrada e saida em snapshot unico com `document_direction = ENTRADA|SAIDA`
- persistir chave de acesso, numero, modelo, status, datas relevantes, competencia, UF, CFOPs, valor total, origem/importacao, presenca de XML e payload bruto
- iterar paginacao ate esgotar a lista, com limite defensivo de paginas por execucao

3. Tarefas/transmissoes
- capturar tipo/nome, descricao, empresa, periodo, datas de criacao/fim, usuario, status, arquivo e payload bruto
- tratar como evidencia operacional de processamento, nao como mutacao do Lumen

Contadores minimos:
- companies_selected
- companies_processed
- apuracoes_received
- difal_received
- fiscal_documents_received
- tasks_received
- difal_snapshots_created
- difal_snapshots_updated
- document_snapshots_created
- document_snapshots_updated
- task_snapshots_created
- task_snapshots_updated
- snapshots_unchanged
- context_mismatches
- not_found
- failures

Testes obrigatorios:
- cliente: contexto correto, `recalcular=false`, paginacao, nenhum endpoint proibido, limpeza de contexto em falhas
- DIFAL: fixture, not found, payload malformado, contexto divergente
- documentos: entrada, saida, varias paginas, lista vazia, XML presente/ausente
- tarefas: lista vazia, status variados, campos opcionais
- sync: uma empresa, lote pequeno, dry-run, fixture mode, idempotencia, `PARTIAL`, `FAILED`, erros sanitizados
- script: argumentos obrigatorios, saida segura, codigos de saida e fechamento de sessao

Validacao minima esperada:
- dry-run real de uma empresa com apuracao + DIFAL + documentos + tarefas
- persistencia real de uma empresa
- repeticao real com `unchanged`
- lote pequeno real serial
- consultas SQL sem duplicidade por chave logica de cada snapshot

Aceite:
- Sittax passa a cobrir apuracao, DAS, DIFAL, documentos e tarefas em modo read-only
- contexto de sessao continua seguro e serial
- snapshots multi-tenant e idempotentes
- nenhuma chamada proibida ocorre
- o Lumen fica com dados suficientes para alimentar conciliacao futura sem depender apenas da teoria do contrato

Fechamento tecnico S7.4 em 2026-07-21
Registro complementar de fechamento do stage S7.4:

- observacao documental: o S7.4 consolidou o fechamento tecnico da integracao operacional read-only com o Sittax, incluindo apuracao, handoff contextual do host `api`, DIFAL, documentos fiscais, tarefas, persistencia local, endpoint interno do Lumen e validacao manual controlada do comportamento real da sessao web
- status confirmado como concluido em 2026-07-21
- entregues: cliente stateful do Sittax em `backend/app/services/integrations/sittax/client.py`, sessao exclusiva e contextual em `backend/app/services/integrations/sittax/session.py`, mapeadores observados em `backend/app/services/integrations/sittax/mapper.py`, sync operacional em `backend/app/services/integrations/sittax/sync.py`, snapshots operacionais, endpoint `POST /api/v1/integrations/sittax/sync`, testes operacionais e documentacao tecnica consolidada em `docs/SITTAX_CONTEXT_HANDOFF.md` e `docs/SITTAX_OBSERVED_CONTRACT.md`
- validacoes registradas: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_sittax_session.py backend/tests/test_sittax_context_handoff.py backend/tests/test_sittax_operational_client.py backend/tests/test_sittax_operational_sync.py -q`, `.\.venv\Scripts\python.exe -m backend.scripts.check_sittax_connection`, `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/integrations/sittax/sync -Headers $headers -ContentType "application/json" -Body $body` com `dry_run = true`, `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/integrations/sittax/sync -Headers $headers -ContentType "application/json" -Body $body` com `dry_run = false`, replay manual controlado com `WebRequestSession` em `autenticacao.sittax.com.br`, `api.sittax.com.br` e `apuracao.sittax.com.br`, alem de consultas SQL de conferencia em snapshots e `integration_sync_runs`
- resultado real confirmado no Lumen: `dry_run = SUCCESS` e execucao com escrita `status = SUCCESS`, `run_id = 39`, `context_mismatches = 0`, `failures = 0`, `apuracoes_received = 1`, `difal_received = 1`, `document_snapshots_created = 39`, `task_snapshots_created = 16`
- confirmacao central do contrato real: o host `api.sittax.com.br` nao se comporta como API stateless pura; ele depende de sessao HTTP persistente, `cookie jar`, JWT Bearer reutilizado e afinidade de backend
- descoberta tecnica principal: apuracao valida no host `apuracao.sittax.com.br` nao basta, sozinha, para liberar DIFAL e documentos no host `api.sittax.com.br`
- sequencia funcional real validada em 2026-07-20: `POST /api/auth/login` -> `GET /api/empresa/listar-todas-escritorio-empresas-selecao?idEscritorio=...` -> `GET /api/apuracao/retornar-apuracao-sittax?empresaCnpj=...&periodo=MM/YYYY` -> materializacao de sessao com cookies de contexto -> `POST /api/v2/painel-contador/valor-auditoria` -> `GET /api/painelprincipal/retornar-dados-por-empresa` -> `GET /api/difal/obter-valores-difal?recalcular=false` -> `GET /api/nota-fiscal/lista-nota-fiscal-entrada-paginacao` -> `GET /api/nota-fiscal/lista-nota-fiscal-saida-paginacao` -> `GET /api/tarefa/paginacao`
- cookies minimos observados como relevantes no replay stateful funcional: `sittax-api-affinity`, `CnpjDaEmpresaSelecionada`, `DataInicialSelecionada`, `IdEscritorioSelecionado` e `IdGrupoDeEmpresaSelecionado`
- especificacao consolidada do handoff: o contexto de `apuracao.sittax.com.br` e o contexto de `api.sittax.com.br` continuam separados conceitualmente, mas o host `api` exige sessao persistente com cookies e afinidade; por isso o cliente do Lumen deve permanecer stateful por sessao e nao pode ser reescrito como cliente stateless por request
- confirmacao explicita: replay manual simplificado com `Authorization: Bearer ...` e header `Cookie` montado manualmente em chamada avulsa falhou e nao e equivalente ao portal real
- erros reais reproduzidos e agora documentados para evitar recorrencia futura: `Favor Selecionar a Empresa` em `painelprincipal` e documentos quando a sessao contextual do host `api` nao foi materializada corretamente; `Informe o período fiscal.` no DIFAL quando o periodo ativo do host `api` nao foi efetivamente confirmado; `Invalid isoformat string: '2026-07-20T20:20:01.53'` durante persistencia de tarefas por parser rigido de datetime
- correcao tecnica incorporada ao backend: o parser de datas do Sittax passou a aceitar fracoes curtas e longas de segundos, incluindo formatos como `.53` e `.1456358`, evitando nova quebra em `datetime.fromisoformat`
- campos e especificacoes observadas como estaveis o suficiente para o conector atual:
- empresas do escritorio: `id`, `cnpj`, `nome`, `fantasia`, `uf`, `inscricaoEstadual`, `homologada`, `usaRegimeDeCaixa`
- apuracao: `id`, `periodoFiscal`, `empresasApuracao`, `valorDas`, `valorDasXml`, `receitaLiquida`, `receitaProdutos`, `receitaServicos`, `receitaDevolucao`, `rbt12`, `rba`, `folhaDePagamentos`, `percentualFatorR`, `dataHoraTransmissao`, `mensagens`, `inconsistencias`, `resumosTributacaoSittax`, `resumosTributacaoXml`
- painel principal: `nome`, `email`, `alertas`, com alertas contendo `id`, `tipoDoAlerta`, `tipoStatusAlerta`, `mensagem`, `ciente`, `historicoDoAlerta`
- DIFAL: `id`, `possuiGuia`, `numeroDareGuiaRevenda`, `numeroDareGuiaUsoConsumoImobilizado`, `valorGuiaRevenda`, `valorGuiaRevendaUtilizandoCredito`, `valorGuiaUsoConsumoImobilizadoUtilizandoCredito`, `totalTodasCompras`, `totalReceitaRevendaInterestadual`, `totalReceitaUsoConsumoImobilizado`, `dataFechamento`, `dataTransmissao`, `creditos`, `temNotasComReferenciaSemTipo`
- documentos de entrada: `id`, `chave_acesso`, `numero`, `modelo`, `status`, `data_emissao`, `data_entrada`, `data_competencia`, `emitente_nome`, `emitente_uf`, `cfops`, `valor_total`, `tem_xml`, `tipo_importacao`, `importada`
- documentos de saida: `id`, `numero`, `modelo`, `status`, `data_emissao`, `data_competencia`, `destinatario_nome`, `destinatario_uf`, `emitente_cpf_cnpj`, `valor_total`, `valor_base_calculo`, `valor_deducoes`, `desconto_condicionado`, `desconto_incondicionado`, `tem_xml`
- tarefas: `id`, `guid`, `titulo`, `descricaoString`, `nomeEmpresa`, `periodo`, `status`, `usuarioId`, `usuarioNome`, `dataCriacao`, `dataFimProcessamento`, `tempoProcessamento`, `possuiArquivo`, `nomeArquivo`, `extensaoArquivo`
- confirmacao explicita do escopo operacional: o conector do S7.4 continua estritamente read-only, nao executa transmissao, nao recalcula apuracao, nao chama `recalcular=true`, nao usa endpoints ambiguos como `POST /api/v2/painel-contador/transmissao` e nao trata o portal como fonte oficial de mutacao fiscal
- confirmacao arquitetural: o processamento continua serial por sessao, com exclusao mutua local, sem alternancia de empresas ou competencias dentro da mesma sessao operacional
- persistencias locais confirmadas como parte do stage: `sittax_company_snapshots`, `sittax_apuracao_snapshots`, `sittax_difal_snapshots`, `sittax_fiscal_document_snapshots`, `sittax_task_snapshots` e `integration_sync_runs`
- pendencia futura registrada: se houver nova regressao no host `api`, o diagnostico deve sempre partir de replay stateful com sessao persistente e inspecao do `cookie jar`, nunca de request stateless isolado
- pendencia documental registrada: caso o portal exponha futuramente endpoint explicito de selecao de empresa no host `api`, o contrato deve ser revisado, mas ate nova evidencia o comportamento oficial do conector permanece baseado na sessao stateful validada em 2026-07-20
- confirmacao final: o S7.4 encerra com contrato tecnico suficientemente validado para operacao read-only do Lumen sobre a funcionalidade real da API observada do Sittax, com os erros historicos principais mapeados, reproduzidos, explicados e mitigados documentalmente

---

## S8 - Econet: CNAE, atividade, Fator R e cache assistido
### Micro-stage S8.0 - Contrato observado, seguranca e fixtures anonimizadas

Status: concluido em 2026-07-21

Objetivo:

* Formalizar o contrato HTML observado da consulta por CNAE da Econet sem iniciar integracao funcional.
* Proteger o repositorio contra versionamento de HAR, JSONL, storages, cookies e artefatos brutos reais.
* Preparar o terreno tecnico do S8.1 com fixtures offline seguras e reproduziveis.

Entregaveis:

* `docs/ECONET_OBSERVED_CONTRACT.md`
* `backend/tests/fixtures/econet/README.md`
* `backend/tests/fixtures/econet/manifest.json`
* fixtures HTML sinteticas para busca, detalhe, subabas tributarias e obrigacoes
* `backend/tests/econet_test_utils.py`
* `backend/tests/test_econet_fixture_safety.py`
* `backend/tests/test_econet_observed_contract.py`
* endurecimento do `.gitignore` para artefatos brutos da Econet

Validacoes:

* `git ls-files | Select-String -Pattern "econet-network|econet-storage|\\.har"` sem artefatos brutos rastreados da Econet
* `git check-ignore -v` confirmando cobertura dos padroes `econet-network*.har`, `econet-network-log*.jsonl` e `econet-storage-*.json`
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econet_fixture_safety.py .\backend\tests\test_econet_observed_contract.py -q`
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests -q`
* `.\.venv\Scripts\python.exe -m ruff check .\backend`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini heads`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current`
* `cd .\frontend && npm run typecheck`
* `cd .\frontend && npm run test:e2e`

Decisoes:

* Econet permanece como fonte indicativa e nao oficial.
* Login continua manual e CAPTCHA nao sera automatizado.
* Fixtures da Econet devem ser sempre sinteticas ou rigorosamente sanitizadas.
* O contrato observado do S8.0 distingue fatos confirmados, inferencias e lacunas.
* O S8.0 nao autoriza decisao fiscal automatica, persistencia de sessao ou parser produtivo.

Limitacoes:

* nao foi criada fixture dedicada de Fator R, porque o HTML especifico nao ficou comprovado o suficiente nos artefatos analisados para este micro-stage;
* nao houve cliente HTTP, parser produtivo, migration, model ou sync;
* o macro-stage S8 continua pendente;
* o S8.1 ainda nao foi iniciado.

### Micro-stage S8.1 - Model, migration, parser HTML puro e cache por CNAE

Status: concluido em 2026-07-21

Objetivo:

* Criar a fundacao persistente e offline da integracao Econet sem qualquer chamada externa.
* Materializar model, migration, parser HTML puro, payload normalizado e cache idempotente por CNAE.
* Preparar o repositorio para o S8.2 sem iniciar sessao assistida, cliente HTTP real, endpoint manual ou sync funcional.

Entregaveis:

* `backend/app/models/econet_cnae_cache.py`
* `backend/alembic/versions/20260721_0009_create_econet_cnae_cache.py`
* `backend/app/services/integrations/econet/__init__.py`
* `backend/app/services/integrations/econet/errors.py`
* `backend/app/services/integrations/econet/parser.py`
* `backend/app/services/integrations/econet/cache.py`
* export do model em `backend/app/models/__init__.py`
* enums `EconetSemanticStatus` e `EconetCacheWriteStatus` em `backend/app/core/enums.py`
* `backend/tests/test_econet_parser.py`
* `backend/tests/test_econet_cache.py`
* `backend/tests/test_econet_cnae_cache_model.py`
* reforco controlado das fixtures sinteticas de tributacao/MEI para explicitar cenarios de parser cobertos

Schema e contrato interno materializados:

* tabela `econet_cnae_cache` global por `cnae` normalizado
* `cnae` com 7 digitos e `cnae_formatted` em `0000-0/00`
* `econet_id_cnae` persistido como chave externa textual separada do CNAE
* percentuais tributarios em `Numeric(5,2)`
* blocos `simples`, `mei`, `presumed_profit`, `actual_profit` e `obligations_*` normalizados em JSONB
* `normalized_payload` sem HTML bruto, sem cookie, sem token e sem sessao
* `content_hash` SHA-256 deterministico sobre o payload canonicamente serializado

Decisoes:

* o cache da Econet no S8.1 e global por CNAE, nao multi-tenant por organizacao
* a Econet continua estritamente indicativa; o cache nao cria status fiscal, nao altera regime oficial e nao gera obrigacao automatica
* o parser do S8.1 e puro e offline; ele nao faz request, nao conhece cookie e nao conhece credencial
* `econet_id_cnae` nao e calculado localmente e precisa vir do HTML de busca/detalhe observado
* percentuais tributarios usam `Decimal`; `float` continua proibido
* Fator R continua `NOT_OBSERVED` quando o HTML nao comprova limiar ou regra textual
* obrigacoes desconhecidas continuam em `unmapped_obligations`; nao ha matching por aproximacao neste micro-stage
* mensagens negativas da Econet sao resultados de negocio validos, nao erro tecnico do parser
* TTL padrao do cache ficou em `180` dias como constante de dominio do servico
* persistencias com hash identico retornam `UNCHANGED`, mas renovam `retrieved_at` e `expires_at`

Validacoes:

* `docker compose -f .\infra\docker-compose.yml up -d postgres redis`
* `docker compose -f .\infra\docker-compose.yml ps`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini heads`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current`
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econet_fixture_safety.py .\backend\tests\test_econet_observed_contract.py .\backend\tests\test_econet_parser.py .\backend\tests\test_econet_cache.py .\backend\tests\test_econet_cnae_cache_model.py -q`
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests -q`
* `.\.venv\Scripts\python.exe -m ruff check .\backend`
* `docker compose -f .\infra\docker-compose.yml exec -T postgres psql -U lumen -d lumen -c "\d+ econet_cnae_cache"`
* `docker compose -f .\infra\docker-compose.yml exec -T postgres psql -U lumen -d lumen -c "select table_name from information_schema.tables where table_schema = 'public' and table_name = 'econet_cnae_cache';"`
* `docker compose -f .\infra\docker-compose.yml exec -T postgres psql -U lumen -d lumen -c "select indexname, indexdef from pg_indexes where schemaname = 'public' and tablename = 'econet_cnae_cache' order by indexname;"`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini downgrade -1`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current`
* `docker compose -f .\infra\docker-compose.yml exec -T postgres psql -U lumen -d lumen -c "select to_regclass('public.econet_cnae_cache');"`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current`
* `cd .\frontend && npm run typecheck`
* `cd .\frontend && npm run test:e2e`
* `git diff --check`
* `git diff --stat`
* `git status --short`

Rollback:

* downgrade isolado de `20260721_0009`
* remocao de `backend/app/models/econet_cnae_cache.py`
* remocao de `backend/app/services/integrations/econet/`
* remocao dos testes dedicados `test_econet_parser.py`, `test_econet_cache.py` e `test_econet_cnae_cache_model.py`
* restore dos documentos atualizados e do export em `backend/app/models/__init__.py`

Pendencias:

* o macro-stage S8 continua pendente
* o cruzamento entre `external_companies` e `econet_cnae_cache` segue para stage posterior
* `activity_types` permanece vazio ate evidencia HTML suficiente ou regra posterior segura

### Micro-stage S8.2 - Sessao manual assistida, cliente HTTP stateful e health seguro

Objetivo:

* materializar sessao assistida da Econet apenas em memoria, sem login automatizado e sem persistencia
* expor importacao controlada de cookies, probe explicito, status sanitizado e limpeza idempotente
* manter o health local da Econet sem chamadas externas e sem iniciar enriquecimento do S8.3

Arquivos materializados:

* `backend/app/services/integrations/econet/assisted_session.py`
* `backend/app/services/integrations/econet/client.py`
* `backend/app/schemas/econet.py`
* `backend/app/api/v1/endpoints/integrations/econet.py`
* `backend/tests/test_econet_assisted_session.py`
* `backend/tests/test_econet_client.py`
* `backend/tests/test_econet_endpoint.py`
* `backend/tests/test_econet_health.py`
* `backend/tests/test_econet_session_security.py`
* `scripts/scan/export_econet_session.js`

Limites:

* nenhuma migration nova
* nenhum login automatico
* nenhum CAPTCHA automatizado
* nenhuma persistencia de sessao em banco, Redis ou arquivo carregado no boot
* nenhum enriquecimento, worker, scheduler ou sync funcional da Econet

Validacao:

* validacao offline concluida com testes dedicados por `httpx.MockTransport`
* validacao real da sessao manual permanece opcional e separada do fechamento automatizado

### Micro-stage S8.3 - Catalogo relacional, enriquecimento por CNAE e potencial cadastral

Status: concluido em 2026-07-22

Entregues:

* `company_cnaes` como catalogo relacional canonico por empresa
* reconciliacao atomica do catalogo no webhook e no sync do eControle
* script de backfill de `external_companies` para `company_cnaes`
* enriquecimento serial da Econet por CNAE com cache e sem HTML bruto persistido
* parser com Fator R positivo, negativo e nao observado
* complemento corretivo com decode seguro a partir de bytes, sem `errors="replace"` e sem aceitar `U+FFFD`
* threshold de Fator R extraido apenas do contexto textual do proprio Fator R, com normalizacao em `Decimal("28.00")`
* normalizacao de anexo condicional repetido, por exemplo `IV / IV -> IV / NULL`
* `parser_version` centralizado e cache fresco dependente da versao atual do parser
* `econet_cnae_cache.mei_occupation` mantido como `Text` no model, sem truncamento silencioso
* limite administrativo de `50`, mantendo `5` como padrao e `25` como uso normal/futuro portal
* endpoints read-only de catalogo e potencial cadastral de Fator R
* contrato canonico inicial de NFS-e com fixtures sinteticas

## Retificacao auditada do Stage S8 em 2026-07-27

Esta secao substitui o rascunho anterior do macro-stage `S8`. O estado real do repositorio, do Git, das migrations, do OpenAPI e dos testes e:

* `S8.0`: concluido no commit `f862b84`
* `S8.1`: concluido no commit `6164f7e`
* `S8.2`: concluido no commit `02cb7e4`
* `S8.3`: concluido e validado
* `S8.3.1`: concluido em 2026-08-05 como micro-stage complementar de correção semantica do parser de Fator R, saneamento do cache e validacao real final
* `S8.4`: NAO INICIADO

### Macro-stage S8

Objetivo consolidado:

* usar a Econet como fonte indicativa para enriquecer CNAEs com anexos, obrigacoes, permissao indicativa de MEI, classificacao de atividade e potencial cadastral de Fator R;
* manter separacao explicita entre espelho cadastral do eControle, catalogo canonico interno de CNAEs, cache global da Econet, classificacao derivada e potencial de Fator R;
* preparar o contrato canonico de NFS-e para o futuro `S10`, sem afirmar parser XML, watcher ou uso por competencia ja implementados.

Arquitetura consolidada:

* `external_companies`: espelho do eControle
* `company_cnaes`: catalogo canonico interno por empresa
* `econet_cnae_cache`: enriquecimento global por CNAE
* `company_activity_types`: classificacao derivada com `source = ECONET`
* `factor_r_potential`: leitura cadastral derivada do cache fresco, sem prova de uso em competencia

Seguranca e limites:

* login da Econet continua manual e assistido
* CAPTCHA nao e automatizado
* sessao existe apenas em memoria do backend
* health da Econet e local e nao faz rede
* `decode_econet_html` opera sobre bytes, normaliza Unicode em NFC e rejeita decodificacao insegura com `U+FFFD`
* o stage nao calcula folha, nao le XML e nao determina uso real de Fator R por competencia

Contrato outbound efetivamente utilizado:

* `GET /ferramentas/regimes_cnae/buscaCnae.php?busca=...`
* `GET /ferramentas/regimes_cnae/index.php?idcnae=...&acao=abrir`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroPresumido&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroRealTrimestral&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroRealEstimativa&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=simplesNacionalTributacao&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=empreendedorIndividual&idCnae=...`
* `GET /ferramentas/regimes_cnae/abas.php?aba=obrigacoes&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=pjGeral&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=optanteSimplesNacional&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=optanteSimei&idCnae=...`

### S8.0

Objetivo:

* observar o contrato sem integrar login, sem cliente HTTP produtivo e sem persistencia de sessao

Entregas confirmadas:

* `docs/ECONET_OBSERVED_CONTRACT.md`
* `backend/tests/fixtures/econet/README.md`
* `backend/tests/fixtures/econet/manifest.json`
* fixtures HTML sanitizadas de busca, detalhe, abas tributarias e obrigacoes
* `backend/tests/econet_test_utils.py`
* `backend/tests/test_econet_fixture_safety.py`
* `backend/tests/test_econet_observed_contract.py`

Evidencias:

* contrato observado com host `www.econeteditora.com.br`
* artefatos brutos, cookies, HAR e storageState reais fora do Git
* fixtures adicionais de Fator R foram introduzidas apenas depois, no S8.3

Status:

* commitado em `f862b84`

### S8.1

Objetivo:

* criar parser HTML puro, offline e testavel
* criar cache global por CNAE

Migration:

* `20260721_0009_create_econet_cnae_cache.py`
* tabela `econet_cnae_cache`
* constraints: `uq_econet_cnae_cache_cnae`, `ck_econet_cnae_cache_cnae_digits`, `ck_econet_cnae_cache_parse_status`
* indices: `ix_econet_cnae_cache_econet_id_cnae`, `ix_econet_cnae_cache_expires_at`

Model e payload:

* identificacao: `cnae`, `cnae_formatted`, `description`, `econet_id_cnae`
* classificacao: `activity_types`
* Simples: `simples_status`, `simples_allowed`, `simples_annex_default`, `simples_annex_conditional`, `factor_r_applicable`, `factor_r_threshold`
* MEI: `mei_status`, `mei_allowed`, `mei_occupation`
* Lucro Presumido: `presumed_profit_status`, `presumed_profit_allowed`, `presumed_profit_irpj_rate`, `presumed_profit_csll_rate`
* Lucro Real: `actual_profit_status`, `actual_profit_mandatory`
* obrigacoes: `obligations_general`, `obligations_simples`, `obligations_simei`, `unmapped_obligations`
* controle: `normalized_payload`, `parse_status`, `parser_version`, `content_hash`, `retrieved_at`, `expires_at`

Politica de cache:

* global por CNAE
* TTL padrao de `180` dias
* sem HTML bruto
* `UNCHANGED` renova datas do cache
* sem endpoint publico proprio no S8.1

Testes:

* `test_econet_parser.py`
* `test_econet_cache.py`
* `test_econet_cnae_cache_model.py`

Status:

* commitado em `6164f7e`

### S8.2

Objetivo:

* sessao manual assistida, cliente HTTP stateful e health local sem rede

Sessao:

* `EconetAssistedSession` com estados `DISABLED`, `NOT_LOADED`, `LOADED_UNVALIDATED`, `VALID`, `EXPIRED`, `INVALID`, `ERROR`
* exportador manual `scripts/scan/export_econet_session.js`
* allowlist de dominios e cookies
* nenhuma senha, CAPTCHA, localStorage ou persistencia em banco

API efetiva do S8.2:

* `POST /api/v1/integrations/econet/session/import`
* `POST /api/v1/integrations/econet/session/probe`
* `GET /api/v1/integrations/econet/session/status`
* `DELETE /api/v1/integrations/econet/session`

Contrato:

* todas as rotas exigem bearer token
* RBAC de escrita: `ADMIN` e `DEV`
* RBAC de leitura do status: `VIEW`, `ADMIN`, `DEV`
* `probe` faz rede controlada
* `status` e `health` nao fazem rede

Validacao real:

* importacao sanitizada de seis cookies permitidos
* `probe` com retorno `VALID`
* sessao somente em memoria

Testes:

* `test_econet_assisted_session.py`
* `test_econet_client.py`
* `test_econet_endpoint.py`
* `test_econet_health.py`
* `test_econet_session_security.py`

Status:

* commitado em `02cb7e4`

### S8.3

Objetivo:

* catalogo relacional de CNAEs
* integracao obrigatoria com webhook e sync do eControle
* backfill operacional
* enrichment serial da Econet
* parser `econet-html-v2`
* encoding seguro por bytes
* classificacao de atividade
* potencial cadastral de Fator R
* contrato canonico de NFS-e

Migrations:

* `20260722_0010_create_company_cnaes.py`
* `20260724_0011_expand_econet_mei_occupation_to_text.py`

Tabela `company_cnaes`:

* campos: `id`, `company_id`, `cnae`, `cnae_formatted`, `is_primary`, `source`, `active`, `first_seen_at`, `last_seen_at`, `deactivated_at`, `created_at`, `updated_at`
* `FK external_companies.id`
* `uq_company_cnaes_company_cnae`
* `ck_company_cnaes_cnae_digits`
* indices: `ix_company_cnaes_company_id`, `ix_company_cnaes_cnae`, `ix_company_cnaes_company_active`, `ix_company_cnaes_cnae_active`
* indice unico parcial: `ux_company_cnaes_active_primary_per_company`

Politica do catalogo:

* `company_cnaes` e o catalogo canonico interno
* `0000000` e placeholder invalido
* principal prevalece sobre secundario duplicado
* operacoes reais: `CREATED`, `UPDATED`, `REACTIVATED`, `DEACTIVATED`, `UNCHANGED`

Explicacao da mudanca de sanitizacao:

* a contagem inicial `794 validos / 4 invalidos` refletia a regra anterior, que ainda nao barrava explicitamente todos os placeholders operacionais normalizados
* a contagem posterior `726 validos / 73 invalidos` reflete a regra final do S8.3, que rejeita `0000-0/00` e outros valores que convergiam para `0000000`
* a diferenca veio do endurecimento da higienizacao, nao de remocao de CNAEs validos reais

Enrichment:

* estados reais: `CREATED`, `UPDATED`, `UNCHANGED`, `SKIPPED_FRESH_CACHE`, `SKIPPED_CACHE_ONLY`, `STALE_PARSER_VERSION`, `INVALID_CNAE`, `CNAE_NOT_FOUND`, `AMBIGUOUS_CNAE_RESULT`, `SESSION_NOT_VALID`, `SESSION_EXPIRED`, `PARSE_ERROR`, `TRANSPORT_ERROR`, `MANUAL_REVIEW`
* cache fresco exige `parse_status = PARSED`, `expires_at > agora` e `parser_version = econet-html-v2`
* limites: `5` padrao, `25` operacional, `50` administrativo, `51` rejeitado
* `ECONET_ENRICH_REQUEST_DELAY_SECONDS` controla serializacao e espacamento das chamadas

Fator R:

* cenario equivalente a `4120400`: Anexo IV, sem anexo condicional, Fator R nao observado
* cenario equivalente a `7020400`: Anexo V, Anexo III condicional, Fator R aplicavel, threshold `28.00%`
* cenario equivalente a `8593700`: Anexo III, Fator R nao aplicavel
* estados do potencial: `APPLICABLE`, `NOT_APPLICABLE`, `PARTIAL`, `UNKNOWN`

Contrato canonico de NFS-e:

* `backend/app/schemas/nfse.py`
* layouts: `NFSE_ABRASF_204`, `NFSE_NACIONAL_101`
* o parser XML permanece futuro, para o S10

API efetiva do S8.3:

* `POST /api/v1/integrations/econet/enrich`
* `GET /api/v1/lumen/companies/{company_id}/cnaes`
* `GET /api/v1/lumen/companies/{company_id}/factor-r-potential`
* `GET /api/v1/lumen/integrations/health`

Resumo formal da API documentada:

* `POST /api/v1/integrations/econet/session/import`
  * request: `cookies`
  * response: snapshot de sessao
  * RBAC: `ADMIN`, `DEV`
  * rede: nao
  * persistencia: somente memoria
* `POST /api/v1/integrations/econet/session/probe`
  * request: sem body
  * response: snapshot de sessao
  * RBAC: `ADMIN`, `DEV`
  * rede: sim
  * persistencia: somente memoria
* `GET /api/v1/integrations/econet/session/status`
  * request: sem body
  * response: snapshot de sessao
  * RBAC: `VIEW`, `ADMIN`, `DEV`
  * rede: nao
  * persistencia: nenhuma
* `DELETE /api/v1/integrations/econet/session`
  * request: sem body
  * response: snapshot limpo
  * RBAC: `ADMIN`, `DEV`
  * rede: nao
  * persistencia: limpa somente memoria
* `POST /api/v1/integrations/econet/enrich`
  * request: `organization_slug`, `company_ids`, `cnaes`, `limit`, `dry_run`, `cache_only`, `force_refresh`, `sync_catalog`, `classify_companies`
  * response: `run_id`, `status`, `summary`, `items`, `catalog_summary`
  * RBAC: `ADMIN`, `DEV`
  * rede: sim
  * persistencia: `IntegrationSyncRun`, `econet_cnae_cache`, catalogo e classificacao quando nao e `dry_run`
* `GET /api/v1/lumen/companies/{company_id}/cnaes`
  * request: `company_id`
  * response: lista de CNAEs ativos da empresa
  * RBAC: `VIEW`, `ADMIN`, `DEV`
  * rede: nao
  * persistencia: nenhuma
* `GET /api/v1/lumen/companies/{company_id}/factor-r-potential`
  * request: `company_id`
  * response: potencial cadastral de Fator R
  * RBAC: `VIEW`, `ADMIN`, `DEV`
  * rede: nao
  * persistencia: nenhuma
* `GET /api/v1/lumen/integrations/health`
  * request: sem body
  * response: itens por provider, incluindo counters da Econet
  * RBAC: `VIEW`, `ADMIN`, `DEV`
  * rede: nao
  * persistencia: nenhuma

Scripts:

* `backend/scripts/backfill_company_cnaes.py`
* `backend/scripts/enrich_cnaes_econet.py`
* `scripts/scan/export_econet_session.js`

Validacao real do fechamento:

* `244` empresas ativas
* `229` empresas com catalogo valido
* `726` vinculos ativos
* `264` CNAEs unicos
* `264` caches na versao atual
* `261` atualizados
* `3` inalterados
* `0` erros
* `0` CNAEs pendentes
* `0` `U+FFFD`
* `0` mojibake detectado

Qualidade:

* `92` testes especificos de Econet
* `74` testes complementares de catalogo, eControle, config e health
* `385` testes backend
* `ruff` aprovado

Status:

* concluido e validado, aguardando commit

### S8.4

Status:

* NAO INICIADO

Escopo apenas planejado:

* card da Econet na tela de integracoes
* status de sessao
* contadores de catalogo e cache
* acoes administrativas de import, probe, clear e enrichment de pendentes
* tabela de CNAEs da empresa
* exibicao do potencial de Fator R

Validacao real complementar executada em 2026-08-05:

* `.\.venv\Scripts\python.exe .\backend\scripts\backfill_company_cnaes.py --org-slug neto-contabilidade --only-active`
* `node .\scripts\scan\export_econet_session.js`
* `POST /api/v1/integrations/econet/session/import`
* `POST /api/v1/integrations/econet/session/probe`
* `POST /api/v1/integrations/econet/enrich` com `16` CNAEs em `dry_run = true`, `force_refresh = true`
* `POST /api/v1/integrations/econet/enrich` com os mesmos `16` CNAEs em `dry_run = false`, `force_refresh = true`
* `docker compose -f .\infra\docker-compose.yml exec -T postgres psql -U lumen -d lumen -c "select count(*) as suspicious_true ..."`
* `docker compose -f .\infra\docker-compose.yml exec -T postgres psql -U lumen -d lumen -c "select count(*) as suspicious_false ..."`
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econet_parser.py .\backend\tests\test_factor_r_service.py .\backend\tests\test_econet_enrichment_service.py .\backend\tests\test_econet_enrichment_endpoint.py -q`

Resultado real consolidado em 2026-08-05:

* `16` CNAEs historicamente inconsistentes foram reenriquecidos com `updated = 16`
* `suspicious_true = 0`
* `suspicious_false = 0`
* `factor_r_null = 0`
* org `neto-contabilidade`: `244` empresas ativas, `missing_unique_cnaes = 0`, `APPLICABLE = 62`, `NOT_APPLICABLE = 169`, `UNKNOWN = 13`
* os `13` `UNKNOWN` remanescentes correspondem a empresas de teste sem CNAE ativo no catalogo local

### Micro-stage S8.3.1 - Correcao semantica do parser de Fator R e saneamento final do cache

Status: concluido em 2026-08-05

Objetivo:

* corrigir a interpretacao de Fator R no parser da Econet para alinhar o cache a regra oficial da LC 123
* eliminar falsos positivos e falsos negativos historicos do `econet_cnae_cache`
* fechar a validacao real do S8.3 com base confiavel para `factor_r_potential`

Entregues:

* canonicalizacao dos casos positivos de Fator R para `Anexo V -> Anexo III`
* deteccao estruturada do bloco tributario do Simples, ignorando mencoes incidentais em `Nota ECONET`
* correcao dos falsos positivos `4651601` e `4751201`
* correcao do falso negativo `7312200`
* reenriquecimento controlado de `16` CNAEs afetados
* novo teste de servico `backend/tests/test_factor_r_service.py`
* ampliacao da suite `backend/tests/test_econet_parser.py`

Decisoes novas:

* a regra oficial a considerar no parser e no cache e: `Fator R >= 28% => Anexo III` e `Fator R < 28% => Anexo V`
* a ordem textual observada no HTML da Econet nao define semantica; o armazenamento canonico para caso positivo passa a ser `default = V`, `conditional = III`
* mencoes laterais a eventual reenquadramento tributario, sem regra estruturada no bloco principal, nao provam Fator R aplicavel

Aceite:

* combinacoes incoerentes entre anexos e `factor_r_applicable` zeradas no cache
* `factor_r_potential` sem `missing_cnaes` para a org validada
* suites focadas do parser, enrichment e servico de Fator R aprovadas
* cobertura, revisao manual, RBAC e E2E dedicados

### Micro-stage S8.3.2 - Catalogo canonico de atividades, backfill e auditoria de anexos

Status: concluido em 2026-08-20

Objetivo:

* substituir a classificacao heuristica de `company_activity_types` por um catalogo canonico CONCLA/CNAE 2.3 versionado
* materializar backfill idempotente das classificacoes por empresa
* operacionalizar auditoria de anexos do Simples em planilha, sem persistir anexos no banco

Entregues:

* `backend/app/data/company_activity_types/company_activity_types_cnae23_concla_mapeamento.json`
* `backend/app/data/company_activity_types/company_activity_types_cnae23_concla_catalogo_completo.json`
* `docs/artifacts/company_activity_types/company_activity_types_cnae23_catalogo_completo_com_anexos.xlsx`
* `backend/app/services/integrations/econet/activity_classifier.py` endurecido para usar o catalogo canonico e consolidacao final da empresa
* `backend/scripts/backfill_company_activity_types.py`
* `backend/scripts/export_econet_simples_annex_audit.py`
* `backend/scripts/fetch_econet_simples_annexes_to_xlsx.py`
* `backend/tests/test_company_activity_classifier.py`
* `backend/tests/test_backfill_company_activity_types.py`
* `backend/tests/test_export_econet_simples_annex_audit_script.py`
* `backend/tests/test_fetch_econet_simples_annexes_to_xlsx.py`

Validacao executada:

* `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_company_activity_classifier.py .\backend\tests\test_backfill_company_activity_types.py .\backend\tests\test_export_econet_simples_annex_audit_script.py .\backend\tests\test_fetch_econet_simples_annexes_to_xlsx.py -q`
* `.\.venv\Scripts\python.exe .\backend\scripts\backfill_company_activity_types.py --org-slug neto-contabilidade --only-active`
* `.\.venv\Scripts\python.exe .\backend\scripts\export_econet_simples_annex_audit.py --input-xlsx "C:\Users\Maria.clara\Downloads\company_activity_types_cnae23_catalogo_completo.xlsx" --output-xlsx "C:\Users\Maria.clara\Downloads\company_activity_types_cnae23_catalogo_completo_com_anexos.xlsx"`

Resultados e validacoes reais registradas:

* o catalogo canonico passou a conter `1331` subclasses oficiais da CNAE 2.3
* o backfill real de `company_activity_types` executado em `2026-08-12` processou `242` empresas ativas, com `295` classificacoes criadas, `0` removidas e `0` CNAEs sem mapeamento
* a auditoria inicial de anexos em planilha mostrou `rows_total = 1331`, `ok = 255`, `prohibited = 9`, `missing_cache = 1067`
* a coleta posterior dos anexos faltantes foi planejada em lotes de `50` CNAEs, apenas para preencher planilha, sem gravar no banco
* divergencias de classificacao x anexo foram revisadas manualmente em planilha antes de consolidar os JSONs canonicos

Decisoes novas:

* `company_activity_types` da empresa passam a ser a uniao dos CNAEs ativos classificados no catalogo canonico
* `SERVICOS` deve ser removido quando coexistir com `TEMPLO_RELIGIOSO`, `SERVICOS_MEDICOS_ODONTOLOGICOS` ou `SERVICOS_IMOBILIARIOS`
* `COMERCIO` e `INDUSTRIA` podem coexistir com classes especificas
* anexos do Simples ficam fora do banco nesta etapa; a auditoria operacional acontece em planilha versionada/derivada

Confirmacao de escopo:

* nenhuma migration nova
* nenhuma coluna nova no banco
* nenhum anexo do Simples persistido em `econet_cnae_cache`
* o macro-stage S8 continua pendente; este micro-stage fecha apenas classificacao, backfill e auditoria operacional

---

## S9 - Domínio Folha: importador do Resumo Mensal e DCTFWeb DP

Status: em andamento

Objetivo:

```text
Importar o Resumo Mensal da Folha emitido pelo Domínio, identificar
movimentos de folha por empresa e relacioná-los à competência de apuração
do mês seguinte, produzindo evidência para DCTFWeb DP e análise de Fator R.
```

Decisões definitivas:

* Domínio é integração documental.
* O núcleo do Lumen não dependerá de automação de tela.
* O coletor Windows é opcional e desacoplado.
* Upload manual do PDF continuará suportado.
* OCR não faz parte do caminho principal.
* O PDF prova movimento, não entrega da DCTFWeb.
* A ausência da empresa no PDF não equivale a folha zerada.
* CNPJ será a chave futura de matching.
* SHA-256 será a chave de idempotência do arquivo.

Limites estruturais:

* Domínio não é fonte principal de cadastro.
* Domínio não é fonte principal de regime.
* Domínio não é fonte principal de CNAE.
* Domínio não será consultada por API.
* Domínio não provará sozinha a transmissão da DCTFWeb.
* Domínio será fonte documental de movimento de folha.

Regra de competência obrigatória:

* `source_payroll_competence` preserva exatamente a competência da folha.
* `assessment_competence` representa a apuração do mês seguinte.
* `source_payroll_competence != assessment_competence`.
* Exemplo: `05/2026 -> 2026-05 -> 2026-06`.
* Exemplo de rollover: `12/2026 -> 2026-12 -> 2027-01`.
* No futuro, `period_id` do movimento apontará para a apuração.

### S9.0 - Contrato, segurança, fixtures e coletor Windows

Status: concluído em 2026-07-29

Escopo:

* documentar o contrato real do Resumo Mensal;
* formalizar a regra folha `M -> M+1`;
* criar tipos puros e helper de competência;
* criar fixtures integralmente sintéticas;
* criar testes de contrato;
* incorporar o coletor Windows ao repositório;
* criar `.env.example` do coletor;
* criar manifest lateral;
* endurecer escrita, validação, retry, hash e lock do coletor;
* atualizar documentação central;
* nenhuma migration;
* nenhum banco;
* nenhum endpoint;
* nenhum frontend;
* nenhum parser completo.

Entregues no S9.0:

* `backend/app/services/integrations/dominio/contracts.py`
* `backend/app/services/integrations/dominio/competence.py`
* `backend/tests/fixtures/dominio/manifest.json`
* `backend/tests/fixtures/dominio/synthetic_contract_samples.json`
* `backend/tests/test_dominio_payroll_contract.py`
* `backend/tests/test_dominio_payroll_competence.py`
* `docs/integrations/DOMINIO_PAYROLL_CONTRACT.md`
* `scripts/collectors/dominio/gerar_resumo_mensal_dominio.py`
* `scripts/collectors/dominio/.env.example`
* `scripts/collectors/dominio/README.md`

Validação planejada do S9.0:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend\app\services\integrations\dominio .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py
.\.venv\Scripts\python.exe -m py_compile .\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py
```

## Addendum S9 Roadmap

- `S9.2` = Persistencia, importador, matching e cobertura documental.
- `S9.3` = Origem DCTFWeb, departamentos e alertas.
- `S9.4.0` = Enriquecimento monetario estruturado do historico Domínio.
- `S9.4` = FS12 estimado, RBT12 Sittax e reconciliacao de Fator R.
- `S9.5` = API, watcher, frontend e E2E.

Alertas planejados para `S9.4`:

- `FACTOR_R_HISTORY_REQUIRED`
- `FACTOR_R_MONTHLY_REPORT_MISSING`
- `DOMINIO_FACTOR_R_FILTER_UPDATE_REQUIRED`
- `FACTOR_R_ESTIMATE_INCOMPLETE`
- `FACTOR_R_THRESHOLD_DIVERGENCE`
- `FACTOR_R_PERCENTAGE_DIVERGENCE`
- `FACTOR_R_ANNEX_MISMATCH`
- `FACTOR_R_NOT_APPLIED`

Validação executada no fechamento do S9.0 em 2026-07-29:

```powershell
git branch --show-current
git log -1 --oneline
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini heads
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend\app\services\integrations\dominio .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py
.\.venv\Scripts\python.exe -m py_compile .\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py
.\.venv\Scripts\python.exe -c @"
import ast
from pathlib import Path
path = Path(r'.\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py')
ast.parse(path.read_text(encoding='utf-8'))
print('AST OK:', path)
"@
pip install -r requirements.txt
Get-ChildItem .\scripts\collectors\dominio,.\backend\tests\fixtures\dominio -Recurse -File |
    Select-String -Pattern 'DOMINIO_PASSWORD=.+','password\s*=\s*[''"]([^''"]+)[''"]' |
    ForEach-Object { $_.Path + ':' + $_.LineNumber + ':' + $_.Line.Trim() }
git status --short |
    Select-String -Pattern 'Resumo_Mensal_.*\.pdf|gerar_resumo_mensal_dominio\.log|\.env$'
.\.venv\Scripts\python.exe .\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py --competencia 05/2026
Get-ChildItem .\scripts\collectors\dominio\Relatorios_Dominio\Resumo_Mensal_05-2026*
Get-Content .\scripts\collectors\dominio\Relatorios_Dominio\Resumo_Mensal_05-2026.manifest.json
Get-FileHash .\scripts\collectors\dominio\Relatorios_Dominio\Resumo_Mensal_05-2026.pdf -Algorithm SHA256
git status --short .\scripts\collectors\dominio .\requirements.txt .\PLANO_DESENVOLVIMENTO.md .\ESTRUTURA_REPO.md
```

Resultados observados no fechamento do S9.0:

* `pytest`: `17 passed in 6.27s`.
* `ruff check`: sem achados.
* `py_compile`: sem erro.
* parse AST UTF-8 do coletor: `AST OK`.
* `alembic current` e `alembic heads`: `20260724_0011 (head)`.
* `pip install -r requirements.txt`: ambiente central confirmou `pywinauto`, `pywin32` e `comtypes`.
* varredura de segredos: apenas placeholders `DOMINIO_PASSWORD=ALTERE_LOCALMENTE` em `.env.example` e `README.md`.
* varredura de artefatos versionados: sem `.env`, PDF real ou log real entrando no `git status`.
* execucao real do coletor para `05/2026`: concluida com PDF final e manifest lateral.
* PDF final observado: `Resumo_Mensal_05-2026.pdf`, `149` paginas, `1440469` bytes.
* SHA-256 observado: `A7BDE8EBFCD1679F8C0D92386AC4EB3E252468E542ACB699ED06B3797EC9C59F`.
* manifest lateral observado: `status = SUCCESS`, `payroll_competence = 2026-05`, `assessment_competence = 2026-06`, `selection_scope = ATIVAS`.

Aceite do S9.0:

* contratos puros e sem banco;
* regra `05/2026 -> 06/2026` testada;
* regra `12/2026 -> 01/2027` testada;
* fixtures 100% sintéticas;
* coletor com `.partial.pdf`, validação mínima, SHA-256, manifest, retry limitado e lock local;
* nenhum artefato real versionado;
* nenhum endpoint, migration, parser completo ou frontend criado.

Fechamento tecnico do S9.0 em 2026-07-29:

* contrato documental do `Resumo Mensal` congelado em `docs/integrations/DOMINIO_PAYROLL_CONTRACT.md`;
* helper puro `folha M -> apuracao M+1` implantado no backend com testes de competencia mensal e rollover anual;
* fixtures sinteticas e manifest sintetico implantados para contrato e validacao offline;
* coletor Windows incorporado ao repo e adaptado ao Lumen para ler `.env` central com fallback local opcional;
* coletor endurecido com `lock` local, retry de exportacao, escrita em `.partial.pdf`, troca atomica com `os.replace`, validacao minima de PDF, hash SHA-256 e manifest lateral;
* compatibilidade implantada para variaveis centralizadas `DOMINIO_LOGIN_TIMEOUT`, `DOMINIO_REPORT_TIMEOUT`, `DOMINIO_SAVE_TIMEOUT`, `DOMINIO_OVERWRITE_PDF`, `DOMINIO_CLOSE_DOMINIO_AFTER` e `DOMINIO_EXPORT_RETRIES`, mantendo fallback para nomes legados;
* requirements do coletor incorporados ao `requirements.txt` central, sem arquivo separado de dependencias;
* homologacao funcional real concluida no Windows com geracao do PDF `Resumo_Mensal_05-2026.pdf` e manifest correspondente.

### S9.1 - Parser offline do PDF

Status: concluido em 2026-07-29

Planejamento:

* extração textual sem OCR no caminho principal;
* OCR somente como fallback futuro e explícito;
* separação por empresa;
* agrupamento de páginas;
* cabeçalhos repetidos;
* páginas `1/2`, `2/2`;
* páginas de continuação vazias;
* blocos `Folha Mensal`;
* alterações salariais;
* lançamentos complementares;
* rubricas;
* totais;
* valores brasileiros;
* detecção de sinais de folha, empregado, pró-labore, autônomo, INSS, FGTS, férias, rescisão e afastamento;
* produção de objetos Python;
* nenhum acesso ao banco.

Fechamento do S9.1 em 2026-07-29:

* parser offline materializado em `backend/app/services/integrations/dominio/parser.py`, `normalization.py` e `rubrics.py`;
* API publica materializada com `parse_dominio_payroll_pdf(path)` e `parse_dominio_payroll_pages(pages, source_file_name=...)`;
* `pypdf` adotado como extrator primario do PDF textual; `PyMuPDF` restrito ao teste sintetico de fronteira;
* agrupamento materializado por `codigo Dominio + CNPJ normalizado + competencia original da folha`;
* blocos `MONTHLY_PAYROLL`, `SALARY_ADJUSTMENT`, `PAYMENT_ENTRY`, `COMPLEMENTARY` e `UNKNOWN` materializados;
* parsing de rubricas da direita para a esquerda materializado, com preservacao de codigo, nome, contagem, valor informado, valor calculado e marcador `*`;
* normalizacao de dinheiro em `Decimal`, incluindo `,95`, e normalizacao de horas em minutos, incluindo `220:00` e `7:20`;
* totais declarados por secao e `Liquido Geral` preservados, com warning `SECTION_TOTAL_MISMATCH` para divergencia de reconciliacao;
* sinais de folha materializados com origem por rubrica em `signal_sources`;
* correcao incremental aplicada no fechamento para `has_employee`: `INSS EMPREGADOR` deixou de ser evidencia positiva de empregado e o sinal passou a depender apenas de rubricas inequivocamente trabalhistas;
* regressao materializada para perfis `somente pro-labore`, `somente autonomo`, `perfil misto com empregado + pro-labore` e validacao explicita de `signal_sources`;
* parser mantido offline, sem banco, sem rede, sem endpoint, sem watcher, sem OCR e sem frontend.

Validacao executada no S9.1:

* `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py .\backend\tests\test_dominio_payroll_parser.py .\backend\tests\test_dominio_payroll_normalization.py .\backend\tests\test_dominio_payroll_rubrics.py -q`
* `.\.venv\Scripts\python.exe -m ruff check .\backend\app\services\integrations\dominio .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py .\backend\tests\test_dominio_payroll_parser.py .\backend\tests\test_dominio_payroll_normalization.py .\backend\tests\test_dominio_payroll_rubrics.py`
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests -q`
* `.\.venv\Scripts\python.exe -m py_compile .\backend\app\services\integrations\dominio\contracts.py .\backend\app\services\integrations\dominio\normalization.py .\backend\app\services\integrations\dominio\rubrics.py .\backend\app\services\integrations\dominio\parser.py`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini current`
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini heads`
* `git status --short .\backend\alembic\versions`
* `git diff --check`
* validacao real agregada com `Resumo_Mensal_05-2026.pdf` e `Resumo_Mensal_06-2026.pdf`, incluindo auditoria de `employee_true`, `employee_false`, `pro_labore_without_employee`, `autonomous_without_employee` e `employee_only_supported_by_forbidden_codes`

Resultados observados no S9.1:

* suite especifica do Dominio: `62 passed in 9.10s`;
* `ruff check`: sem achados;
* suite completa do backend: `447 passed, 1 warning`;
* `py_compile`: sem erros;
* Alembic permaneceu em `20260724_0011 (head)` e sem alteracoes em `backend/alembic/versions`;
* `git diff --check`: sem erros de whitespace; apenas warnings de `LF -> CRLF` na copia de trabalho;
* `Resumo_Mensal_05-2026.pdf`: `149` paginas fisicas, `137` empresas, `employee_true = 90`, `employee_false = 47`, `pro_labore_without_employee = 47`, `autonomous_without_employee = 5`, `employee_only_supported_by_forbidden_codes = 0`, warnings agregados `CONTINUATION_PAGE_EMPTY = 1` e `SECTION_TOTAL_MISMATCH = 7`, tempo `3.423s`;
* `Resumo_Mensal_06-2026.pdf`: `145` paginas fisicas, `137` empresas, `employee_true = 90`, `employee_false = 47`, `pro_labore_without_employee = 47`, `autonomous_without_employee = 5`, `employee_only_supported_by_forbidden_codes = 0`, warnings agregados `CONTINUATION_PAGE_EMPTY = 1` e `SECTION_TOTAL_MISMATCH = 3`, tempo `3.840s`;
* nenhuma migration nova foi criada;
* fechamento semantico confirmado: `has_employee` nao e mais explicado por `843`, `858`, `100`, `9380`, `235` ou `856` isoladamente.

### S9.2 - Persistencia, importador, matching e cobertura documental

Status: concluido em 2026-08-06

Planejamento:

* tabelas `dominio_payroll_imports` e `dominio_payroll_company_movements`;
* migration incremental;
* idempotencia por SHA-256;
* matching por CNPJ;
* `source_payroll_competence`;
* `assessment_competence`;
* `period_id` apontando para a apuracao;
* CLI com `--dry-run`;
* integracao futura com `integration_sync_runs`, `audit_log` e `fiscal_evidences`;
* fonte `DOMINIO_FOLHA_PDF`;
* unmatched sem interromper o lote;
* PDF nao armazenado como blob no banco;
* `rubrics_summary` como JSONB em vez de tabela de rubricas no MVP.

Fechamento tecnico S9.2 em 2026-08-06:

Entregues:

* migration `20260730_0012_create_dominio_payroll_tables.py`;
* modelos `DominioPayrollImport` e `DominioPayrollCompanyMovement`;
* tabelas `dominio_payroll_imports` e `dominio_payroll_company_movements`;
* importador `backend/app/services/integrations/dominio/importer.py`;
* matching por CNPJ em `backend/app/services/integrations/dominio/matching.py`;
* CLI `backend/scripts/import_dominio_payroll.py`;
* testes `test_dominio_payroll_models.py`, `test_dominio_payroll_matching.py`, `test_dominio_payroll_importer.py` e `test_dominio_payroll_cli.py`;
* persistencia de `source_payroll_competence` e `assessment_competence`;
* resolucao de `fiscal_period_id` sempre pela competencia de apuracao `M+1`;
* `rubrics_summary` deterministico em JSONB;
* criacao de `fiscal_evidences` apenas para movimentos `MATCHED`;
* `integration_sync_runs` e auditoria para imports reais;
* `--dry-run` sem escrita;
* normalizacao deterministica de `selection_scope`;
* inferencia de `ACTIVE_COMPANIES` a partir de manifests legados com `source_filter_name = Ativas`;
* isolamento de `target_company_count` e `target_list_sha256` somente para `FACTOR_R`;
* warning estruturado `FACTOR_R_TARGET_SCOPE_MISMATCH` com finalizacao em `MANUAL_REVIEW` quando o escopo `FACTOR_R` ficar incoerente;
* backfill local reconstruido com 12 competencias mensais canonicamente classificadas como `ACTIVE_COMPANIES`.

Validacao executada:

* `.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_dominio_payroll_contract.py .\backend\tests\test_dominio_payroll_competence.py .\backend\tests\test_dominio_payroll_normalization.py .\backend\tests\test_dominio_payroll_rubrics.py .\backend\tests\test_dominio_payroll_parser.py .\backend\tests\test_dominio_payroll_models.py .\backend\tests\test_dominio_payroll_matching.py .\backend\tests\test_dominio_payroll_importer.py .\backend\tests\test_dominio_payroll_cli.py -q`;
* `.\.venv\Scripts\python.exe -m pytest .\backend\tests -q`;
* `.\.venv\Scripts\python.exe -m ruff check .\backend\app\models\dominio_payroll.py .\backend\app\services\integrations\dominio .\backend\scripts\import_dominio_payroll.py .\backend\scripts\export_dominio_factor_r_targets.py .\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py`;
* `.\.venv\Scripts\python.exe -m py_compile .\backend\app\models\dominio_payroll.py .\backend\app\services\integrations\dominio\contracts.py .\backend\app\services\integrations\dominio\selection_scope.py .\backend\app\services\integrations\dominio\matching.py .\backend\app\services\integrations\dominio\importer.py .\backend\app\services\integrations\dominio\coverage.py .\backend\app\services\integrations\dominio\factor_r_targets.py .\backend\scripts\import_dominio_payroll.py .\backend\scripts\export_dominio_factor_r_targets.py .\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py`;
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini downgrade 20260724_0011`;
* `.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head`;
* `git diff --check`;
* reimportacao das 12 competencias `07/2025` a `06/2026`;
* reimportacao adicional de `06/2026` para comprovar `duplicate = true`;
* conferencia SQL agregada de competencias, escopos e status.

Resultados:

* migration incremental criada, com upgrade, downgrade para `20260724_0011` e upgrade novamente;
* nenhuma tabela de rubricas criada;
* unique `organization_id + file_sha256` e unique `import_id + source_company_key` ativos;
* matching automatico restrito a `organization_id + cnpj`;
* `fiscal_period_id` dos movimentos e evidencias apontando para a apuracao `M+1`;
* duplicidade concluida como `no-op`;
* retry de `FAILED` coberto por teste sintetico;
* `--dry-run` sem escrita;
* nenhuma alteracao em `fiscal_obligation_statuses`;
* os 12 imports canonicos ficaram em `ACTIVE_COMPANIES | Ativas | target_* = null`;
* o backfill mensal validado cobriu `07/2025` a `06/2026`;
* a janela de 12 meses para Fator R passa a ser montada a partir dos movimentos persistidos;
* nao existe segundo relatorio mensal obrigatorio com filtro `Fator R`;
* a reimportacao de `06/2026` retornou `duplicate = true` sem crescimento em `dominio_payroll_imports`, `dominio_payroll_company_movements` ou `fiscal_evidences`.

Decisao operacional final:

* fonte canonica mensal: um PDF por competencia com filtro `Ativas`;
* o backfill inicial do S9.2 usa 12 PDFs mensais individuais;
* a rotina mensal gera somente a competencia recem-fechada;
* a folha `M` corresponde a apuracao `M+1`;
* o Lumen monta a janela historica de 12 meses usando movimentos persistidos;
* somente empresas potencialmente sujeitas entram na analise de Fator R;
* o filtro `Fator R` e o modo intervalo permanecem opcionais para auditoria, diagnostico ou contingencia;
* o relatorio Dominio comprova movimento de folha/eSocial e componente DP, mas nao comprova transmissao da DCTFWeb nem fato gerador da REINF.

Pendencias nao bloqueantes:

* movimentos `UNMATCHED` continuam em revisao manual;
* PDFs reais anteriores ainda existem no historico do Git no commit `6060711`;
* limpeza historica do Git sera tratada como acao de seguranca separada;
* calculo e reconciliacao do Fator R pertencem ao S9.4;
* alertas e origem DCTFWeb pertencem ao S9.3;
* a tentativa de reemissao assistida de `06/2026` em `2026-08-06` falhou por timeout do processamento e depois por erro de `SendInput()`, mas o PDF local permaneceu com agregado compativel com o backfill mensal e o manifest foi normalizado para o escopo canonico `Ativas`.

### S9.3 - Origem DCTFWeb, departamentos e alertas

Status: CONCLUIDO em 2026-08-21, aguardando revisao e commit

Entregues:

* migration `20260820_0013_create_dctfweb_origin_assessments.py` e tabela auditavel por organizacao, empresa e competencia;
* motor `backend/app/services/dctfweb_origins.py` e CLI `backend/scripts/reconcile_dctfweb_origins.py` com `--dry-run`;
* cobertura Domínio por competencia de apuracao: `CONFIRMED_MOVEMENT`, `CONFIRMED_NO_MOVEMENT` e `REPORT_MISSING`;
* avaliacao de todas as empresas atualmente ativas da organizacao, usando `ExternalCompany.active` como estado operacional corrente por ainda nao existir historico de ativacao;
* origem esperada `DP`, `FISCAL`, `COMPARTILHADO` ou `UNDETERMINED`, com fingerprint deterministico, reason codes e resumo sem PII;
* DCTFWeb modelada como composicao operacional de eSocial, EFD-Reinf e MIT: eSocial/Domínio para DP, REINF/MIT para Fiscal;
* `REINF` detectada apenas por obrigacao/evidencia canonica `REINF`;
* MIT detectado apenas a partir da PA `2025-01` por obrigacoes canonicas `PIS` e `COFINS`; DAS, regime tributario e `EFD_CONTRIBUICOES` nao inferem MIT;
* observacao de DCTFWeb por entrega Acessorias, evidencia ou status canonico, sem confundir observacao com entrega confirmada;
* empresa ativa sem DP, REINF, MIT ou DCTFWeb observados persiste `UNDETERMINED` com `NO_DCTFWEB_COMPONENT_OBSERVED`, sem alerta acionavel;
* alertas idempotentes e resolviveis para cobertura Domínio ausente agregada por organizacao/periodo, origem compartilhada, revisao mensal, componente DP ainda nao observado e origem indeterminada acionavel;
* auditoria agregada de execucao real, sem criar `integration_sync_runs` para um processamento derivado interno.
* auditoria final em `2026-08-21`: catalogo MIT atual com `PIS`/`COFINS`, sem status ou evidencias MIT em `2026-07`; fontes canonicas DCTFWeb (status, evidencia e Acessorias) tambem ausentes, justificando `MIT = 0` e `dctfweb_observed = 0` no snapshot;
* auditoria confirmou 242 assessments (`DP=127`, `FISCAL=5`, `COMPARTILHADO=8`, `UNDETERMINED=102`), invariante Fiscal = REINF ou MIT sem violacoes, reexecucao idempotente e nenhuma alteracao em `fiscal_obligation_statuses`.

Limites mantidos:

* o stage nao altera `fiscal_obligation_statuses`, nem marca DCTFWeb, REINF ou MIT como entregue;
* nao calcula Fator R, Anexo III/V, DAS ou divergencias com Sittax;
* nao cria endpoint HTTP, frontend, watcher, RQ ou scheduler;
* o PDF `FACTOR_R` nao substitui a cobertura mensal canonica `ACTIVE_COMPANIES`;
* a base ainda nao possui historico de empresas ativas por competencia; o S9.3 usa o `active` atual;
* a responsabilidade e origem persistidas sao operacionais esperadas, nao conclusao juridica nem confirmacao de transmissao.

### S9.4.0 - Enriquecimento monetario estruturado do historico Domínio

Status: concluido e validado em 2026-08-21

Entregues:

* `backend/app/services/integrations/dominio/monetary_summary.py` com `rubrics_summary` `schema_version = 2`;
* classificacao monetaria conservadora por codigo, secao e contrato observado para `employee_remuneration`, `pro_labore`, `autonomous`, `thirteenth_salary`, `employer_cpp_observed` e `fgts_observed`;
* preservacao obrigatoria de `unclassified_monetary` e `excluded_monetary`, sem usar `gross_total` como preenchimento;
* warning estruturado `UNCLASSIFIED_MONETARY_RUBRICS` quando houver valor monetario nao classificado;
* CLI `backend/scripts/enrich_dominio_payroll_monetary_summary.py` com `--organization-slug`, `--file`, `--directory`, `--dry-run` e `--json`;
* enrichment real do backfill `07/2025` a `06/2026` por reprocessamento dos PDFs locais originais, sem criar imports, evidencias ou novo periodo fiscal;
* testes sinteticos focados em Decimal, nao classificacao, separacao de categorias, enrichment e CLI.

Fechamento tecnico S9.4.0 em 2026-08-21:

* o parser ja preservava `calculated_value: Decimal` por rubrica; a limitacao real do `schema_version = 1` era perder esse detalhe ao persistir apenas sinais, codigos e totais agregados por bloco;
* `rubrics_summary` v2 permanece backward compatible com os campos de `codes`, `signals`, `blocks` e `rubric_count`, mas agora inclui resumo monetario estruturado, `monetary_summary_confidence`, `unclassified_monetary` e `excluded_monetary`;
* a serializacao monetaria permanece deterministica em string decimal com duas casas, sem `float`;
* `raw_text` persistido nao entra no enrichment; o backfill reprocessa novamente os PDFs originais;
* dry-run real dos `12` PDFs: `imports_found = 12`, `movements_parsed = 1624`, `movements_matched = 1624`, `movements_would_update = 1624`, `schema_v2 = 1624`, `complete = 505`, `partial = 1112`, `insufficient = 7`, `unclassified_monetary_movements = 1119`;
* persistencia real dos `12` PDFs: `movements_updated = 1624`, sem erro de correspondencia;
* segunda execucao real: `movements_updated = 0` e `already_enriched = 1624`, comprovando idempotencia material;
* query agregada posterior confirmou `schema_version = 2` em todos os `1624` movimentos da janela `07/2025` a `06/2026`;
* regressao Domínio completa: `99 passed`;
* regressao S9.3: `14 passed`;
* suite backend completa: `560 passed, 1 warning`;
* `ruff check` e `py_compile` aprovados;
* nenhum PDF real novo foi adicionado ao Git.

Limites mantidos:

* `monetary_summary` nao e `FS12` oficial e nao substitui apuracao fiscal;
* o stage nao cria `factor_r_assessments`, nao calcula `FS12`, `RBT12`, percentual de Fator R ou reconciliacao com Sittax;
* `employer_cpp_observed` e `fgts_observed` continuam sendo observacoes do relatorio, nao prova de recolhimento efetivo;
* rubricas monetarias desconhecidas permanecem em `unclassified_monetary` em vez de classificacao por aproximacao.

Proximo passo:

* retomar `S9.4` para `fs12_dominio_estimate`, `RBT12` via Sittax e reconciliacao historica de Fator R.

### S9.4 - FS12 estimado, RBT12 Sittax e reconciliacao de Fator R

Status: concluido e validado em 2026-08-26, aguardando revisao e commit

Planejamento:

* `fs12_dominio_estimate` a partir do `rubrics_summary` v2;
* `RBT12` historico observado via Sittax;
* reconciliacao `FS12/RBT12` e percentual de Fator R por empresa e competencia;
* classificacao de completude e divergencia do historico;
* possivel persistencia derivada para assessments de Fator R;
* alertas especificos de historico incompleto, threshold e anexo;
* sem redefinir o contrato de identidade do import Domínio ja estabilizado no S9.2/S9.4.0.

Implementacao atual:

* migration `20260824_0014` cria `factor_r_assessments` sem alterar imports, movimentos, snapshots Sittax, cache Econet, DAS ou status fiscal;
* a reconciliacao usa o resumo monetario v2 persistido, `RBT12` observado no Sittax e Decimal para formula/threshold;
* `fs12_dominio_estimate` preserva limites de caixa, CPP/FGTS observados, 13o e rubricas nao classificadas;
* CLI `reconcile_factor_r.py` suporta PA, empresa opcional, dry-run e saida somente agregada.
* a cobertura da folha consulta exclusivamente imports Domínio canônicos `ACTIVE_COMPANIES`: ausencia da empresa em relatório existente e `CONFIRMED_NO_MOVEMENT`, cobertura historica valida, e nao `REPORT_MISSING`.
* o modelo atual nao possui data canonica de abertura ou historico de atividade por competencia; o motor nao infere `SHORT_HISTORY` nem preenche meses anteriores com zero.
* novos imports Domínio ja persistem `rubrics_summary` v2; a folha `07/2026` integra a janela do PA `2026-08`, nunca o PA `2026-07`.
* Sittax somente promove uma empresa de `POTENTIAL` para `EFFECTIVE` quando tambem existe potencial CNAE canonico; snapshot isolado nao amplia o universo alvo.
* `factor_r_percent` Sittax e tratado como pontos percentuais observados e normalizado para ratio `Decimal`; anexos dependem de codigo explicito, sem inferencia por descricao livre.

Fechamento tecnico e operacional em 2026-08-26:

* import Domínio de `07/2026` validado e idempotente: `135` movimentos, todos `MATCHED` e com `rubrics_summary schema v2`; o contador de `97` warnings permaneceu coerente por camada (`1` de relatorio, `4` promovidos por empresa e `92` monetarios);
* PA `2026-06` comprovou a independencia das fontes: `58` targets, `43` snapshots Sittax com `RBT12` e fator observado, mesmo com `58` historicos de folha insuficientes pela ausencia de `06/2025`;
* o workflow S7 existente `backend/scripts/sync_sittax_apuracoes.py` foi usado em modo read-only para persistir `153` snapshots canonicos de `2026-07`; nao houve reutilizacao de snapshot de outro PA nem acao fiscal externa mutavel;
* PA `2026-07`: `58` targets (`42 EFFECTIVE`, `16 REVIEW`), `58` FS12 estimadas `LOW`, `43` RBT12/fatores Sittax observados e calculados, `14` fatores `>= 28%`, `29` `< 28%`, `29` matches e `14` divergencias de threshold;
* os `58` assessments permaneceram idempotentes nas reexecucoes finais, sem criacao ou atualizacao material; os alertas tambem permaneceram idempotentes, com `42` `FACTOR_R_ESTIMATE_INCOMPLETE` de severidade `LOW` e sem alerta falso de historico;
* fontes canonicas ficaram preservadas: `13` imports Domínio, `1759` movimentos, `1717` evidencias, `196` status de obrigacao e `264` entradas Econet; snapshots Sittax cresceram legitimamente de `154` para `307` pelo workflow S7;
* testes focados S9.4: `15 passed`; regressao integrada: `149 passed`; suite backend: `572 passed, 1 warning` preexistente; Ruff, `py_compile`, Alembic `20260824_0014 (head)` e `git diff --check` aprovados.

Limites mantidos:

* `fs12_dominio_estimate` continua sendo estimativa conservadora, nao FS12 oficial, e confidence `LOW` nao e promovida pela simples presenca de Sittax;
* CPP/FGTS observados nao provam recolhimento, caixa nao e presumido e a cobertura de 13o/rubricas nao classificadas continua como limitacao explicita;
* divergencia de threshold registra revisao tecnica, sem afirmar erro fiscal no Sittax; ausencia global de snapshot nao gera alertas empresariais em massa.

### S9.5-BE - API backend operacional/read-only

Status: concluido e validado em 2026-08-26, aguardando revisao e commit

Entregues:

* extensao da API publica existente `/api/v1/lumen`, sem segunda API paralela e sem migration;
* GETs sanitizados para resumo e detalhe Domínio, DCTFWeb origin, Factor R, dashboard, cockpit, resumo de empresa e health local;
* POSTs locais de reconcile DCTFWeb e Factor R, restritos a `ADMIN|DEV`, reutilizando os servicos S9.3/S9.4 e aceitando `dry_run`;
* queries multi-tenant por `organization_id`, paginação limitada e ordenação deterministica;
* cobertura Domínio com `MOVEMENT_FOUND`, `CONFIRMED_NO_MOVEMENT` e `REPORT_MISSING`, mantendo a semantica `sourcePeriod` separada do PA;
* health Domínio/Sittax baseado exclusivamente em banco local, sem chamadas externas em GET.

Limites mantidos:

* APIs nunca retornam `raw_text`, PDF, manifest, paths locais, hash de arquivo, payload Sittax bruto, fingerprint, cookie, token ou credencial;
* GETs nao recalculam assessments nem escrevem audit; o frontend continua compativel pelos campos existentes preservados;
* upload HTTP de PDF Domínio permanece fora do patch: o fluxo canonico continua collector local mais CLI de importacao;
* `S9.5-WATCHER`, `S9.5-FE` e `S9.5-E2E` foram validados no fechamento operacional abaixo; não há pendência de suíte para encerramento formal do macro-stage.

### S9.5 - fechamento operacional

Entregas implementadas para validação final:

* dashboard, cockpit e tela da empresa exibem apenas resumos sanitizados de DCTFWeb, Fator R e Domínio; a Company Page busca cada detalhe isoladamente e trata `404` como `Não avaliado`, sem quebrar os outros cards;
* a compatibilidade é mantida entre dashboard e resumos: `dctfweb.evaluated` deriva das mesmas assessments do summary e `factor_r.calculated` conta assessments com fator estimado;
* `factor_r.incomplete` identifica cálculo não `COMPUTED`, separado de alertas e divergências;
* watcher Domínio local observa somente `scripts/collectors/dominio/Relatorios_Dominio`, com `--once` para controle e `--watch` para processo supervisionado; valida manifesto/arquivo estável e encaminha arquivos novos ao importador canônico;
* o watcher trata duplicatas por `organization + file_sha256`, ignora parciais, não movimenta arquivos e só reconcilia DCTFWeb/Fator R para o PA M+1 do relatório novo;
* health apresenta o watcher com dados locais persistidos; não há chamada a UI Domínio, Sittax, Acessórias ou Econet durante GETs;
* o fluxo mantém `folha M -> PA M+1`: a folha `07/2026` participa do PA `2026-08`, nunca do PA `2026-07`.

Limites preservados:

* `fs12_dominio_estimate` continua estimativa derivada e não FS12 oficial;
* watcher e frontend não criam imports duplicados, fiscal evidence extra, payload bruto ou operação externa mutável;
* S10 não foi iniciado e o watcher de evidências fiscais genéricas permanece fora do escopo.

Status: concluído em 2026-08-28

* `S9.5-BE`, `S9.5-WATCHER`, `S9.5-FE` e `S9.5-E2E` concluídos.
* Macro-stage `S9` concluído: API sanitizada, watcher Domínio singleton, frontend operacional e E2E cobrem o fluxo sem alterar fontes canônicas.
* Validação final: backend `581 passed` com um warning conhecido de compatibilidade Starlette/httpx; frontend `typecheck`, `build`, spec S9 e `7` E2E aprovados; Ruff, `py_compile`, parser PowerShell, OpenAPI e Alembic `20260824_0014` aprovados.
* O watcher foi validado com uma única árvore gerenciada por `organization_slug + diretório canônico`; `Stop` encerrou a árvore e não restaram processos legados.


## S10 - Watcher local e motor de evidências por arquivo

Status: em andamento; S10.0 e S10.1 concluidos, S10.2 pendente.

Objetivo:

* Detectar guias, recibos, parcelamentos e evidências fiscais salvas nas pastas das empresas.

Justificativa:

* O watcher é uma fonte essencial de evidências reais.
* Ele não decide sozinho o status fiscal; ele gera sinais e evidências para o backend conciliar.
* Deve funcionar principalmente sobre PDFs digitais com texto extraível.

Escopo:

* S10.0: contrato, seguranca, auth do agent, path grammar e fixtures.
* S10.1: core offline do agent.
* S10.2: ingest backend + persistencia/idempotencia.
* S10.3: watcher Windows operacional.
* S10.4: worker/reprocessamento/observabilidade/piloto.

S10.1 materializou somente o core offline: config lazy da root, guardas lexical/fisico de path, extracao de sinais de pasta, filtro PDF/temporarios, SHA-256 streaming, hint por filename, probe estrutural/textual com `pypdf` e builder de payload v1. Nao ha observacao continua, HTTP, banco, endpoint, worker, OCR, parser fiscal ou frontend. Os testes cobrem somente arvores `tmp_path` e PDFs sinteticos gerados dinamicamente.

XMLs de NFS-e sao fonte fiscal distinta das guias/recibos PDF do watcher. S10.1 permanece exclusivamente PDF e offline: nao adiciona `.xml`, nao trata NFS-e como `fiscal_evidence` de guia e nao decide atividade, receita ou Fator R.

Pasta principal alvo:

```txt
G:\EMPRESAS\[empresa]\Escrita Fiscal\[MM-AAAA]\Guias - Impostos e Parcelamentos
```

Palavras-chave iniciais:

```txt
DAS, PIS, COFINS, ICMS, ISS, DIFAL, PROTEGE, PGFN, SISPAR, PARC,
DCTFWEB, DARF, REINF, MIT, IRPJ, CSLL
```

Regras congeladas no S10.0:

* A pasta `MM-AAAA` vira `AAAA-MM`, sem aplicar a regra Dominio Folha `M+1`.
* O primeiro watcher aceitara apenas PDF; XML e OCR ficam fora deste fluxo.
* S11 permanece reservado aos parsers fiscais e S12 ao motor de conciliacao.
* S10.2/S10.3 deverao adicionar E2E para evidencias `WATCHER_FILE` e health/estado do Watcher em Integracoes.

S10.0 nao materializa `agent/watcher/main.py`, endpoint, migration, persistencia, extracao/classificacao PDF, worker ou frontend. Esses itens continuam nos micro-stages posteriores.

---

## S11 - Parsers fiscais e classificação de guias/recibos

Status: pendente

Objetivo:

* Transformar PDFs e arquivos encontrados em evidências fiscais úteis para conciliação.

Justificativa:

* Os exemplos reais de guias demonstraram que o conteúdo dos PDFs traz dados suficientes para classificar e extrair campos relevantes.
* O nome do arquivo ajuda, mas a fonte principal deve ser o conteúdo do PDF.

Escopo:

* Parsers por tipo de documento.
* Campos normalizados.
* Confiança por evidência.
* Tratamento de guias estaduais sem CNPJ claro.
* Parcelamentos PGFN/SISPAR.
* Testes com fixtures anonimizadas.
* Micro-stage proprio de normalizacao/parser de XML NFS-e para identificar atividades efetivamente geradoras de receita por empresa e competencia, como insumo de Fator R.

Limite do micro-stage NFS-e futuro:

* Preservar os layouts de NFS-e ja conhecidos pelo projeto, sem implementar parser neste patch.
* Nao definir tabelas ou migrations antes de inspecao especifica do schema existente.
* XML NFS-e nao sera tratado simplesmente como evidencia de guia PDF.

Entregáveis:

* `backend/app/services/pdf/parse_das.py`
* `backend/app/services/pdf/parse_darf.py`
* `backend/app/services/pdf/parse_icms.py`
* `backend/app/services/pdf/parse_iss.py`
* `backend/app/services/pdf/parse_installment.py`
* `backend/app/services/pdf/parse_dctfweb_receipt.py`
* `backend/app/services/pdf/parse_reinf_receipt.py`
* `backend/app/services/pdf/normalize.py`

Prioridade de implementação:

1. DAS
2. DARF/PIS/COFINS
3. ICMS/PROTEGE
4. Parcelamento PGFN/SISPAR
5. DCTFWeb/REINF/MIT/recibos

Campos mínimos de evidência:

* `file_path`
* `file_hash`
* `file_name`
* `detected_tax`
* `detected_obligation`
* `cnpj_detected`
* `ie_detected`
* `razao_social_detected`
* `competencia_detected`
* `due_date`
* `amount_total`
* `amount_principal`
* `amount_multa`
* `amount_juros`
* `document_number`
* `receipt_number`
* `barcode`
* `installment_protocol`
* `installment_current`
* `installment_total`
* `confidence`
* `raw_text`

Regras:

* DAS deve identificar Documento de Arrecadação do Simples Nacional.
* DARF deve identificar Documento de Arrecadação de Receitas Federais.
* PIS/COFINS devem ser confirmados por código/denominação no PDF.
* ICMS/PROTEGE podem não ter CNPJ; vincular por pasta + IE + razão social.
* Parcelamento deve aproveitar também o nome do arquivo, especialmente padrões como `(13 de 18)`.
* Se nome e conteúdo concordam, confiança alta.
* Se nome e conteúdo divergem, enviar para conferência manual.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_pdf_parsers.py .\backend\tests\test_installment_parser.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend
```

Aceite:

* Guias comuns são classificadas com confiança adequada.
* Valores, vencimentos, competência e documento são extraídos quando presentes.
* Guias sem CNPJ podem ser vinculadas por pasta + IE + razão social.
* Parcelamento no padrão `Parc. PGFN-SISPAR 013021061 - 05-2026 (13 de 18)` extrai tipo, protocolo, competência, parcela atual e total.
* OCR não é usado no caminho padrão.

---

## S12 - Motor de conciliação fiscal

Status: pendente

Objetivo:

* Cruzar Acessórias, Sittax, Domínio, Econet, watcher e evidências para calcular o status fiscal real por empresa/competência.

Justificativa:

* O motor de conciliação deve vir depois das fontes principais, para que as regras sejam implementadas sobre dados reais ou snapshots já modelados.
* Ele é o coração lógico do Lumen.

Escopo:

* Serviço central de conciliação.
* Priorização de fontes.
* Cálculo de status.
* Divergências.
* Responsável por departamento.
* Reprocessamento idempotente por competência.
* Auditoria das decisões.

Fontes:

* Acessórias
* Sittax
* Domínio Folha
* Econet
* Watcher/PDF
* Histórico interno

Entregáveis:

* `backend/app/services/reconciliation.py`
* `backend/app/services/source_priority.py`
* `backend/app/services/dctfweb_origins.py`, complementos se necessário
* job `reconcile_fiscal_period`
* endpoint `POST /api/v1/lumen/reconciliation/run` com RBAC `ADMIN|DEV`
* atualização das APIs de Cockpit, Envios, Evidências e Divergências

Exemplos de regra:

* Guia DAS encontrada + Acessórias entregue = `CONFIRMADO_ARQUIVO_ACESSORIAS`.
* Acessórias entregue + arquivo não encontrado = `CONFIRMADO_API` com alerta leve se evidência física for obrigatória.
* Guia ICMS encontrada + Acessórias pendente = `DIVERGENTE`.
* Sittax informa DIFAL sem guia + Acessórias consta DIFAL pendente = revisar aplicabilidade/dispensa.
* Sittax informa DIFAL com guia + arquivo ausente + Acessórias pendente = pendência crítica.
* Folha com movimento + Acessórias sem DCTFWeb = alerta DP.
* Econet indica Fator R + empresa Simples + Sittax apurou DAS = alerta de revisão de anexo/fator R.
* DCTFWeb somente folha/eSocial = responsável `DP`.
* DCTFWeb com folha + REINF/MIT = responsável `COMPARTILHADO`.

Status de conciliação:

* `CONFIRMADO_ARQUIVO_ACESSORIAS`
* `CONFIRMADO_API`
* `CONFIRMADO_ARQUIVO`
* `PENDENTE`
* `PENDENTE_SEM_ARQUIVO`
* `DIVERGENTE`
* `DISPENSADO_AUTOMATICAMENTE`
* `NAO_APLICAVEL`
* `BAIXA_CONFIANCA`
* `CONFERENCIA_MANUAL`

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_reconciliation.py .\backend\tests\test_divergence_rules.py .\backend\tests\test_dctfweb_origins.py .\backend\tests\test_factor_r_rules.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend
```

Aceite:

* Reprocessar a mesma competência não duplica alertas/evidências.
* Status por obrigação é recalculável e auditável.
* Divergências aparecem nas APIs do Cockpit e tela Divergências.
* Responsável por departamento é calculado corretamente.
* DCTFWeb por folha é atribuída ao DP quando for único fator gerador.
* DCTFWeb mista é atribuída como `COMPARTILHADO`.

---

## S13 - Frontend operacional com dados reais

Status: pendente

Objetivo:

* Transformar o shell e as telas read-only já existentes em uma experiência operacional conectada aos dados reais das integrações e da conciliação.

Justificativa:

* O shell fiscal e as rotas principais já foram materializados no S5.1.
* A partir deste stage, o foco visual deve ser conectar e lapidar a experiência sobre dados reais, e não apenas montar layout vazio.
* Este stage deve consumir resultados de Acessórias, Sittax, Econet, Domínio, watcher e conciliação.

Escopo:

* Painel com KPIs reais.
* Cockpit com status por fonte/departamento.
* Tela Empresa com dossiê fiscal real.
* Tela Envios com origem, evidência, responsável e confiança.
* Tela Evidências com arquivos processados.
* Tela Divergências com fila real.
* Tela Integrações com health real.
* Ajustes visuais de fidelidade ao guia estético.

Entregáveis backend:

* Ajustes nos endpoints read-only já existentes:

  * `GET /api/v1/lumen/dashboard`
  * `GET /api/v1/lumen/cockpit`
  * `GET /api/v1/lumen/companies/{id}/summary`
  * `GET /api/v1/lumen/deliveries`
  * `GET /api/v1/lumen/evidences`
  * `GET /api/v1/lumen/divergences`
  * `GET /api/v1/lumen/installments`
  * `GET /api/v1/lumen/integrations/health`

Entregáveis frontend:

* refino de `DashboardPage.tsx`
* refino de `CockpitPage.tsx`
* refino de `CompanyPage.tsx`
* refino de `DeliveriesPage.tsx`
* refino de `EvidencesPage.tsx`
* refino de `DivergencesPage.tsx`
* refino de `IntegrationsPage.tsx`
* componentes:

  * `DctfwebOriginCard.tsx`
  * `FactorRCard.tsx`
  * `EvidenceTimeline.tsx`
  * `IntegrationHealthCard.tsx`
  * `JobsGrid.tsx`

Checklist visual:

* Sidebar, topbar, context strip e dropdowns preservados.
* Header sticky com blur.
* Empresa e competência no header.
* IE vazia aparece como `ISENTO`.
* Regime oficial vem do Acessórias.
* Fator R aparece no dossiê da empresa.
* DCTFWeb exibe origem e departamento responsável.
* Tela Envios suporta escopo "empresa" e "todas".
* Estados vazios continuam honestos.
* Divergências reais aparecem com severidade e ações.

Validação:

```powershell
cd .\frontend
npm run typecheck
npm run test:e2e
```

Validação backend:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_lumen_read_endpoints.py .\backend\tests\test_dashboard_endpoints.py .\backend\tests\test_cockpit_endpoints.py .\backend\tests\test_deliveries_endpoint.py -q
```

Aceite:

* Painel mostra KPIs reais por competência.
* Cockpit filtra por status, departamento, regime e fonte.
* Tela Empresa mostra dados cadastrais, regime oficial, atividades, Fator R, obrigações, evidências, DCTFWeb e divergências.
* Tela Envios mostra responsável, status, evidência, protocolo, valor e confiança.
* Tela Integrações mostra eControle, Acessórias, Sittax, Domínio, Econet e Watcher.
* Nenhuma ação fiscal externa é adicionada.

---

## S14 - Parcelamentos: controle ativo, evidência mensal e risco

Status: pendente

Objetivo:

* Controlar parcelamentos ativos, evidências mensais e risco de inadimplência.

Escopo:

* Persistência de parcelamentos.
* Atualização por PDF/nome do arquivo.
* Histórico por competência.
* Regras de risco.
* Tela Parcelamentos.

Entregáveis:

* Serviço `backend/app/services/installments.py`
* job `scan_installment_risks`
* endpoint `GET /api/v1/lumen/installments?period=YYYY-MM&companyId=`
* atualização de `InstallmentsPage.tsx`
* tabela com empresa, tipo, protocolo, parcela, valor, vencimento, última evidência e risco

Alertas:

* Parcelamento sem envio no mês.
* Parcelamento sem evidência por vários meses.
* Parcela atual não evolui.
* Parcelamento ativo sem protocolo.
* Parcelamento próximo do fim.
* Possível inadimplência.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_installments.py .\backend\tests\test_installment_risk_rules.py -q
cd .\frontend
npm run test:e2e -- installments.spec.ts
```

Aceite:

* Parcelamento PDF atualiza status sem duplicidade.
* Risco aparece no painel e na tela Parcelamentos.
* Histórico por competência fica rastreável.

---

## S15 - Divergências, alertas e centro operacional

Status: pendente

Objetivo:

* Transformar exceções fiscais em fila operacional clara para revisão humana.

Escopo:

* Serviço de alertas.
* Fila de divergências.
* Severidade.
* Ações humanas: confirmar evidência, justificar, abrir empresa.
* Centro de integrações/jobs.

Entregáveis:

* `backend/app/services/alerts.py`
* endpoint `GET /api/v1/lumen/divergences?period=YYYY-MM&companyId=`
* endpoint `POST /api/v1/lumen/divergences/{id}/resolve` com RBAC `ADMIN|DEV`
* tela `DivergencesPage.tsx`
* tela `IntegrationsPage.tsx` com saúde de:

  * eControle
  * Acessórias
  * Sittax
  * Domínio
  * Econet
  * Watcher G:
* `JobsGrid.tsx`

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_alerts.py .\backend\tests\test_divergences_endpoint.py .\backend\tests\test_integrations_health.py -q
cd .\frontend
npm run test:e2e -- divergences.spec.ts integrations.spec.ts
```

Aceite:

* Divergências são deduplicadas por empresa/competência/regra.
* Usuário consegue justificar ou confirmar evidência com auditoria.
* Saúde das integrações aparece de forma compreensível.
* Ações humanas não executam transmissão fiscal externa.

---

## S16 - Jobs, observabilidade e runbooks operacionais

Status: pendente

Objetivo:

* Tornar automações rastreáveis, reprocessáveis e operáveis pelo escritório.

Escopo:

* Worker real.
* Tracking de jobs.
* APIs de status.
* Scripts PowerShell.
* Runbooks.

Entregáveis:

* Worker runner real.
* endpoints:

  * `GET /api/v1/worker/health`
  * `GET /api/v1/worker/jobs/{job_id}`
  * `GET /api/v1/worker/snapshot`
* scripts:

  * `scripts/ops/run_acessorias_sync.ps1`
  * `scripts/ops/run_econtrole_reconcile.ps1`
  * `scripts/ops/run_sittax_sync.ps1`
  * `scripts/ops/run_econet_enrich.ps1`
  * `scripts/ops/run_dominio_payroll_import.ps1`
  * `scripts/ops/run_file_scan.ps1`
  * `scripts/ops/run_reconciliation_period.ps1`
* `docs/RUNBOOK_LOCAL.md`

Jobs principais:

* `sync_econtrole_companies`
* `sync_acessorias_deliveries`
* `sync_sittax_companies`
* `sync_sittax_apuracao_period`
* `sync_sittax_difal_period`
* `sync_sittax_fiscal_documents`
* `enrich_cnaes_econet`
* `import_dominio_payroll_pdf`
* `scan_fiscal_files`
* `process_pdf_evidences`
* `reconcile_fiscal_period`
* `scan_dctfweb_origins`
* `scan_installment_risks`
* `generate_fiscal_alerts`

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_worker.py .\backend\tests\test_job_runs.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend .\agent
```

Aceite:

* Cada job tem `run_id`, status, início, fim, contadores, erros e resumo.
* Job pode ser reprocessado sem duplicidade indevida.
* Operação por PowerShell funciona sem credenciais versionadas.
* Health de integrações e worker aparece no portal.

---

## S17 - Hardening de segurança e LGPD operacional

Status: pendente

Objetivo:

* Proteger dados fiscais, sessões e credenciais antes de uso real amplo.

Escopo:

* Revisão de segredos.
* Criptografia de credenciais/sessões quando persistidas.
* Sanitização de logs.
* RBAC refinado.
* Política de retenção.
* Export de dados sem arquivos sensíveis.

Entregáveis:

* `docs/SECURITY.md` atualizado.
* Serviço de criptografia para credenciais.
* Redaction de logs.
* Testes de permissão.
* Checklist de go-live seguro.
* Revisão de armazenamento de tokens no frontend.
* Revisão de sessões assistidas da Econet.
* Política para não versionar arquivos fiscais reais.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_security.py .\backend\tests\test_rbac.py .\backend\tests\test_log_redaction.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend .\agent
```

Aceite:

* Logs não exibem tokens, senhas, cookies, JWTs ou API keys.
* Arquivos fiscais reais seguem fora do Git.
* Sessões assistidas são protegidas e expiram de forma controlada.
* VIEW não executa jobs sensíveis.
* ADMIN/DEV têm permissões compatíveis com operação segura.

---

## S18 - Testes de regressão, performance e go-live MVP

Status: pendente

Objetivo:

* Validar o Lumen em cenário real controlado antes de uso operacional amplo.

Escopo:

* Testes ponta a ponta.
* Carga inicial com empresas reais controladas.
* Validação de watcher em pasta piloto.
* Validação de Acessórias, Sittax, Domínio e Econet com amostras reais/anonimizadas.
* Ajustes de UX.
* Runbooks finais.
* Plano de rollback.
* Plano de backup.

Entregáveis:

* suíte E2E completa
* `docs/GO_LIVE_CHECKLIST.md`
* `docs/KNOWN_LIMITATIONS.md`
* plano de rollback
* plano de backup
* checklist de operação mensal
* checklist de incidentes de integração

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests
.\.venv\Scripts\python.exe -m ruff check .\backend .\agent
cd .\frontend
npm run lint
npm run typecheck
npm run test:e2e
```

Aceite:

* Usuário consegue abrir Painel, Cockpit, Empresa, Envios, Evidências, Divergências, Parcelamentos e Integrações.
* Uma competência piloto pode ser reconciliada do início ao fim.
* Acessórias sincroniza regime e entregas.
* Sittax sincroniza Simples, DAS, DIFAL e documentos.
* Econet identifica Fator R e atividade por CNAE.
* Domínio Folha identifica DCTFWeb DP.
* Watcher identifica guias/recibos salvos.
* Divergências e baixa confiança ficam em fila humana, não escondidas.
* Nenhum fluxo transmite obrigação fiscal automaticamente.

---

## Ordem recomendada para execução com Codex

1. S0 a S4: fundação técnica e modelo fiscal.
2. S5 e S6: fontes estruturais eControle + Acessórias.
3. S7: Sittax read-only, por ser o motor operacional do Simples, DAS, DIFAL e documentos fiscais.
4. S8: Econet, para CNAE, atividade, Fator R, anexos e validação tributária.
5. S9: Domínio Folha, para fator gerador de DCTFWeb e responsabilidade DP.
6. S10 e S11: watcher e parsers de guias/recibos.
7. S12: motor de conciliação fiscal.
8. S13: frontend operacional com dados reais.
9. S14 e S15: parcelamentos, divergências, alertas e centro operacional.
10. S16 a S18: jobs, segurança, regressão e go-live.

## Modelo de fechamento de stage

Ao concluir cada stage, registrar no fim da seção:

```txt
Status: concluído em AAAA-MM-DD

Entregues:
- ...

Validação executada:
- comando 1
- comando 2

Pendências:
- ...

Decisões novas:
- ...
```

## Comando padrão para pedir implementação ao Codex

```txt
Implemente somente o Stage S<n> do PLANO_DESENVOLVIMENTO.md do projeto Lumen.
Respeite README.md e ESTRUTURA_REPO.md.
Não avance para stages seguintes.
Inclua testes automatizados.
Atualize documentação quando houver decisão técnica ou de domínio.
Não versionar segredos, cookies, PDFs/XMLs reais ou sessões assistidas.
Não criar automação de transmissão fiscal nem bypass de CAPTCHA.
Ao final, informe arquivos alterados, comandos de validação e pendências.
```

```
