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

Status: pendente

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

## S6 - Integração Acessórias: regime, obrigações e entregas

Status: pendente

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

Validação:
```bash
pytest backend/tests/test_acessorias_mapper.py backend/tests/test_acessorias_sync.py backend/tests/test_regime_precedence.py
```

Aceite:
- Sync idempotente por empresa/competência.
- Status entregue/pendente refletido no domínio fiscal.
- Runs têm contadores, erros e resumo.

---

## S7 - Frontend shell e fidelidade visual base

Status: pendente

Objetivo:
- Implementar o app shell visual do Lumen, preservando o protótipo e preparando navegação real.

Escopo:
- Layout global.
- Sidebar.
- Topbar.
- Dropdown de empresa.
- Dropdown de competência.
- Context strip.
- Tokens visuais.
- Rotas principais.
- Estado global.

Entregáveis:
- `frontend/src/app/LumenShell.tsx`
- `frontend/src/app/lumenRoutes.tsx`
- `frontend/src/components/layout/Sidebar.tsx`
- `Topbar.tsx`
- `ContextStrip.tsx`
- `CompanyDropdown.tsx`
- `PeriodDropdown.tsx`
- `frontend/src/styles/tokens.css`
- `global.css`
- `components.css`
- Store `lumenUiStore.ts`.

Rotas:
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

Validação:
```bash
cd frontend
npm run lint
npm run typecheck
npm run test:e2e -- shell.spec.ts
```

Checklist visual:
- Sidebar 288px desktop.
- Sidebar colapsada em telas médias.
- Header sticky com blur.
- Empresa e competência no header.
- Context strip com empresa, CNPJ/IE, competência e regime.
- IE vazia aparece como `ISENTO`.
- Inter, gradientes azul/roxo, cards arredondados e badges corretos.

Aceite:
- Navegação principal funcional.
- Estado de empresa/competência preservado entre telas.
- Layout responsivo abaixo de 760px.

---

## S8 - APIs e telas MVP: Painel, Cockpit, Empresa e Envios

Status: pendente

Objetivo:
- Entregar a primeira experiência operacional do Lumen com dados reais do backend.

Escopo:
- Endpoints agregados.
- Tela Painel.
- Tela Cockpit Fiscal.
- Tela Empresa.
- Tela Envios.

Entregáveis backend:
- `GET /api/v1/lumen/companies?search=`
- `GET /api/v1/lumen/periods`
- `GET /api/v1/lumen/dashboard?period=YYYY-MM`
- `GET /api/v1/lumen/cockpit?period=YYYY-MM&companyId=&status=&department=&source=`
- `GET /api/v1/lumen/companies/{id}/summary?period=YYYY-MM`
- `GET /api/v1/lumen/deliveries?period=YYYY-MM&companyId=`

Entregáveis frontend:
- `DashboardPage.tsx`
- `CockpitPage.tsx`
- `CompanyPage.tsx`
- `DeliveriesPage.tsx`
- Componentes de KPI, tabelas, filtros e badges.

Validação:
```bash
pytest backend/tests/test_dashboard_endpoints.py backend/tests/test_cockpit_endpoints.py backend/tests/test_deliveries_endpoint.py
cd frontend && npm run test:e2e -- dashboard.spec.ts cockpit.spec.ts deliveries.spec.ts company.spec.ts
```

Aceite:
- Painel mostra KPIs por competência.
- Cockpit filtra por status, departamento, regime e fonte.
- Tela Empresa mostra dados cadastrais, regime oficial, atividade, Fator R, obrigações, evidências e divergências.
- Tela Envios suporta escopo “empresa” e “todas”.

---

## S9 - Watcher local e motor de evidências por arquivo

Status: pendente

Objetivo:
- Detectar guias, recibos, parcelamentos e evidências fiscais salvas nas pastas das empresas.

Escopo:
- Agente local.
- Parser de caminho, empresa e competência.
- Hash de arquivo.
- Classificação inicial por nome/caminho.
- Extração de texto de PDF.
- Registro de evidências.
- Idempotência por hash/caminho.

Entregáveis:
- `agent/watcher/main.py`
- `file_detector.py`
- `company_resolver.py`
- `period_resolver.py`
- `backend/app/services/pdf/text_extract.py`
- `backend/app/services/pdf/classify_tax.py`
- Endpoint `POST /api/v1/lumen/evidences/watcher-event`.
- Job `process_pdf_evidences`.
- Tabela/eventos `watcher_file_events`.

Pasta principal alvo:
```txt
G:\EMPRESAS\[empresa]\Escrita Fiscal\[competência]\Guias - Impostos e Parcelamentos
```

Palavras-chave iniciais:
```txt
DAS, PIS, COFINS, ICMS, ISS, DIFAL, PROTEGE, PGFN, SISPAR, PARC,
DCTFWEB, DARF, REINF, MIT, IRPJ, CSLL
```

Validação:
```bash
pytest backend/tests/test_watcher_events.py backend/tests/test_pdf_text_extract.py backend/tests/test_file_classifier.py
```

Aceite:
- Arquivo novo gera evidência sem duplicidade.
- PDF com texto extraível não usa OCR.
- CNPJ/IE/competência/valor/vencimento são extraídos quando disponíveis.
- Baixa confiança fica como `CONFERENCIA_MANUAL` ou `BAIXA_CONFIANCA`.

---

## S10 - Parsers fiscais e classificação de guias/recibos

Status: pendente

Objetivo:
- Transformar PDFs e arquivos encontrados em evidências fiscais úteis para conciliação.

Escopo:
- Parsers por tipo de documento.
- Campos normalizados.
- Confiança por evidência.
- Tratamento de guias estaduais sem CNPJ claro.
- Parcelamentos PGFN/SISPAR.

Entregáveis:
- Parsers:
  - `parse_das.py`
  - `parse_darf.py`
  - `parse_icms.py`
  - `parse_iss.py`
  - `parse_installment.py`
  - `parse_dctfweb_receipt.py`
  - `parse_reinf_receipt.py`
- Normalizador de valores, datas, CNPJ, IE e competência.
- Test fixtures anonimizadas em `docs/examples` ou `data/examples`.

Campos mínimos de evidência:
- `file_path`
- `file_hash`
- `file_name`
- `detected_tax`
- `detected_obligation`
- `cnpj_detected`
- `ie_detected`
- `razao_social_detected`
- `competencia_detected`
- `due_date`
- `amount_total`
- `document_number`
- `receipt_number`
- `barcode`
- `installment_protocol`
- `installment_current`
- `installment_total`
- `confidence`
- `raw_text`

Validação:
```bash
pytest backend/tests/test_pdf_parsers.py backend/tests/test_installment_parser.py
```

Aceite:
- Guias comuns são classificadas com confiança adequada.
- Guias sem CNPJ podem ser vinculadas por pasta + IE + razão social.
- Parcelamento no padrão `Parc. PGFN-SISPAR 013021061 - 05-2026 (13 de 18)` extrai tipo, protocolo, competência, parcela atual e total.

---

## S11 - Motor de conciliação fiscal

Status: pendente

Objetivo:
- Cruzar Acessórias, watcher, Sittax, Domínio e evidências para calcular status fiscal real por empresa/competência.

Escopo:
- Serviço central de conciliação.
- Priorização de fontes.
- Cálculo de status.
- Divergências.
- Reprocessamento idempotente por competência.

Entregáveis:
- `backend/app/services/reconciliation.py`
- Job `reconcile_fiscal_period`.
- Endpoint `POST /api/v1/lumen/reconciliation/run` (`ADMIN|DEV`).
- Registro de divergências em `fiscal_alerts` ou tabela dedicada, conforme decisão S0.

Exemplos de regra:
- Guia DAS encontrada + Acessórias entregue = `CONFIRMADO_ARQUIVO_ACESSORIAS`.
- Guia ICMS encontrada + Acessórias pendente = `DIVERGENTE`.
- Acessórias entregue + arquivo não encontrado = `CONFIRMADO_API` com alerta leve se evidência física for obrigatória.
- Sittax com DIFAL com guia + arquivo ausente = pendência crítica.
- Folha com movimento + Acessórias sem DCTFWeb = alerta de obrigação possivelmente não controlada.

Validação:
```bash
pytest backend/tests/test_reconciliation.py backend/tests/test_divergence_rules.py
```

Aceite:
- Reprocessar a mesma competência não duplica alertas/evidências.
- Status por obrigação é recalculável e auditável.
- Divergências aparecem nas APIs do Cockpit e tela Divergências.

---

## S12 - Sittax read-only: Simples, DAS, DIFAL e documentos fiscais

Status: pendente

Objetivo:
- Integrar dados do Sittax para enriquecer apuração do Simples Nacional, DAS, DIFAL, documentos fiscais e tarefas/transmissões.

Escopo:
- Login por endpoint com JWT Bearer.
- Listagem de empresas.
- Consulta de apuração por CNPJ/período.
- Consulta de DIFAL respeitando contexto de sessão.
- Consulta de documentos fiscais.
- Consulta de tarefas/transmissões.
- Snapshots locais.

Entregáveis:
- `sittax_company_snapshots`
- `sittax_apuracao_snapshots`
- `sittax_difal_snapshots`
- `sittax_task_snapshots` se necessário.
- Cliente Sittax com fila sequencial ou sessão isolada.
- Job `sync_sittax_apuracao_period`.
- Job `sync_sittax_difal_period`.
- Health de integração.

Regra técnica crítica:
- Não processar várias empresas em paralelo usando a mesma sessão quando endpoint depender de contexto empresa/período.

Validação:
```bash
pytest backend/tests/test_sittax_client.py backend/tests/test_sittax_mapper.py backend/tests/test_sittax_context_lock.py backend/tests/test_sittax_sync.py
```

Aceite:
- Snapshots são idempotentes por empresa/período.
- DIFAL não mistura contexto entre empresas.
- Nenhum endpoint aciona transmissão ou recálculo sem autorização explícita.
- Dados alimentam Cockpit, Envios e Divergências.

---

## S13 - Domínio Folha: importador do Resumo Mensal e DCTFWeb DP

Status: pendente

Objetivo:
- Usar relatório da Domínio para identificar fator gerador de DCTFWeb pela folha/eSocial e atribuir responsabilidade ao DP quando aplicável.

Escopo:
- Upload/importação assistida de PDF do Resumo Mensal da Folha.
- Parser por blocos de empresa.
- Persistência dos movimentos.
- Regra de origem DCTFWeb.
- Alerta para mês seguinte após movimento.

Entregáveis:
- `dominio_payroll_imports`
- `dominio_payroll_company_movements`
- Parser `parse_dominio_payroll.py`.
- Endpoint `POST /api/v1/lumen/dominio/payroll/import` (`ADMIN|DEV`).
- Serviço `dctfweb_origins.py`.
- Job `scan_dctfweb_origins`.

Campos extraídos:
- `company_cnpj`
- `company_name`
- `competencia`
- `tem_folha`
- `tem_empregado`
- `tem_pro_labore`
- `tem_autonomo`
- `tem_inss`
- `tem_fgts`
- `tem_rescisao`
- `tem_ferias`
- `valor_proventos`
- `valor_descontos`
- `valor_informativas`
- `valor_liquido`
- `raw_text`
- `arquivo_origem`

Regras:
- Movimento, pró-labore, autônomo, INSS, FGTS ou rescisão indicam fator gerador DCTFWeb origem DP.
- Se único fator gerador for folha/eSocial, responsável = `DP`.
- Se houver folha + REINF/MIT, responsável = `COMPARTILHADO`.
- Se houve DCTFWeb com movimento em `05/2026`, gerar alerta para `06/2026` verificar envio zerado/sem movimento quando aplicável.

Validação:
```bash
pytest backend/tests/test_dominio_payroll_parser.py backend/tests/test_dctfweb_origins.py backend/tests/test_dctfweb_next_month_alert.py
```

Aceite:
- PDF importado cria movimentos por empresa sem duplicidade.
- DCTFWeb DP aparece no Cockpit/Envios.
- Alerta do mês posterior é gerado corretamente.

---

## S14 - Econet: cache por CNAE, atividade e Fator R

Status: pendente

Objetivo:
- Enriquecer empresas por CNAE com dados da Econet, preservando login assistido e cache local.

Escopo:
- Sessão assistida.
- Consulta de CNAEs novos/vencidos.
- Parser HTML.
- Cache por CNAE.
- Fator R.
- Classificação de atividades.
- Alertas por CNAE.

Entregáveis:
- `econet_cnae_cache`.
- `backend/app/services/integrations/econet/assisted_session.py`.
- `client.py`, `parser.py`, `cache.py`.
- Job `enrich_cnaes_econet`.
- Tela/endpoint de status da sessão Econet.
- Alerta de Fator R.

Campos do cache:
- `cnae`
- `descricao`
- `econet_id_cnae`
- `simples_permitido`
- `mei_permitido`
- `tem_fator_r`
- `anexo_simples_padrao`
- `anexo_simples_condicional`
- `lucro_presumido_possivel`
- `lucro_real_obrigatorio`
- `atividade_detectada`
- `obrigacoes_pj_geral`
- `obrigacoes_simples`
- `raw_html_index`
- `raw_html_simples`
- `raw_html_lucro_presumido`
- `raw_html_obrigacoes`
- `retrieved_at`
- `expires_at`
- `parse_status`

Regras:
- Não consultar Econet em tempo real a cada tela.
- Consultar CNAEs novos ou cache vencido.
- Permitir revisão manual de baixa confiança.
- Se `tem_fator_r = true`, alertar empresa do Simples para verificar folha/pró-labore antes de confirmar DAS.

Validação:
```bash
pytest backend/tests/test_econet_parser.py backend/tests/test_econet_cache.py backend/tests/test_factor_r_rules.py
```

Aceite:
- CNAE cacheado alimenta atividade e Fator R.
- Sessão expirada não quebra portal; gera status “Sessão assistida expirada”.
- Nenhuma tentativa de bypass de CAPTCHA.

---

## S15 - Parcelamentos: controle ativo, evidência mensal e risco

Status: pendente

Objetivo:
- Controlar parcelamentos ativos, evidências mensais e risco de inadimplência.

Escopo:
- Persistência de parcelamentos.
- Atualização por PDF/nome do arquivo.
- Histórico por competência.
- Regras de risco.
- Tela Parcelamentos.

Entregáveis:
- Serviço `installments.py`.
- Job `scan_installment_risks`.
- Endpoint `GET /api/v1/lumen/installments?period=YYYY-MM&companyId=`.
- Tela `InstallmentsPage.tsx`.
- Tabela com empresa, tipo, protocolo, parcela, valor, vencimento, última evidência e risco.

Alertas:
- Parcelamento sem envio no mês.
- Parcelamento sem evidência por vários meses.
- Parcela atual não evolui.
- Parcelamento ativo sem protocolo.
- Parcelamento próximo do fim.
- Possível inadimplência.

Validação:
```bash
pytest backend/tests/test_installments.py backend/tests/test_installment_risk_rules.py
cd frontend && npm run test:e2e -- installments.spec.ts
```

Aceite:
- Parcelamento PDF atualiza status sem duplicidade.
- Risco aparece no painel e na tela Parcelamentos.
- Histórico por competência fica rastreável.

---

## S16 - Divergências, alertas e centro operacional

Status: pendente

Objetivo:
- Transformar exceções fiscais em fila operacional clara para revisão humana.

Escopo:
- Serviço de alertas.
- Fila de divergências.
- Severidade.
- Ações humanas: confirmar evidência, justificar, abrir empresa.
- Centro de integrações/jobs.

Entregáveis:
- `backend/app/services/alerts.py`.
- Endpoint `GET /api/v1/lumen/divergences?period=YYYY-MM&companyId=`.
- Endpoint `POST /api/v1/lumen/divergences/{id}/resolve` (`ADMIN|DEV`).
- Tela `DivergencesPage.tsx`.
- Tela `IntegrationsPage.tsx` com saúde de eControle, Acessórias, Sittax, Domínio, Econet e Watcher G:.
- `JobsGrid.tsx`.

Validação:
```bash
pytest backend/tests/test_alerts.py backend/tests/test_divergences_endpoint.py backend/tests/test_integrations_health.py
cd frontend && npm run test:e2e -- divergences.spec.ts integrations.spec.ts
```

Aceite:
- Divergências são deduplicadas por empresa/competência/regra.
- Usuário consegue justificar ou confirmar evidência com auditoria.
- Saúde das integrações aparece de forma compreensível.

---

## S17 - Jobs, observabilidade e runbooks operacionais

Status: pendente

Objetivo:
- Tornar automações rastreáveis, reprocessáveis e operáveis pelo escritório.

Escopo:
- Worker RQ.
- Tracking de jobs.
- APIs de status.
- Scripts PowerShell.
- Runbooks.

Entregáveis:
- Worker runner.
- Endpoints:
  - `GET /api/v1/worker/health`
  - `GET /api/v1/worker/jobs/{job_id}`
  - `GET /api/v1/worker/snapshot`
- Scripts:
  - `scripts/ops/run_acessorias_sync.ps1`
  - `scripts/ops/run_econtrole_reconcile.ps1`
  - `scripts/ops/run_file_scan.ps1`
  - `scripts/ops/run_reconciliation_period.ps1`
- `docs/RUNBOOK_LOCAL.md`.

Jobs principais:
- `sync_econtrole_companies`
- `sync_acessorias_deliveries`
- `sync_sittax_companies`
- `sync_sittax_apuracao_period`
- `sync_sittax_difal_period`
- `scan_fiscal_files`
- `process_pdf_evidences`
- `import_dominio_payroll_pdf`
- `enrich_cnaes_econet`
- `reconcile_fiscal_period`
- `scan_dctfweb_origins`
- `scan_installment_risks`
- `generate_fiscal_alerts`

Validação:
```bash
pytest backend/tests/test_worker.py backend/tests/test_job_runs.py
```

Aceite:
- Cada job tem `run_id`, status, início, fim, contadores, erros e resumo.
- Job pode ser reprocessado sem duplicidade indevida.
- Operação por PowerShell funciona sem credenciais versionadas.

---

## S18 - Hardening de segurança e LGPD operacional

Status: pendente

Objetivo:
- Proteger dados fiscais, sessões e credenciais antes de uso real.

Escopo:
- Revisão de segredos.
- Criptografia de credenciais/sessões quando persistidas.
- Sanitização de logs.
- RBAC refinado.
- Política de retenção.
- Export de dados sem arquivos sensíveis.

Entregáveis:
- `docs/SECURITY.md` atualizado.
- Serviço de criptografia para credenciais.
- Redaction de logs.
- Testes de permissão.
- Checklist de go-live seguro.

Validação:
```bash
pytest backend/tests/test_security.py backend/tests/test_rbac.py backend/tests/test_log_redaction.py
```

Aceite:
- Logs não exibem tokens/senhas/cookies.
- Arquivos fiscais reais seguem fora do Git.
- Sessões assistidas são protegidas e expiram de forma controlada.

---

## S19 - Testes de regressão, performance e go-live MVP

Status: pendente

Objetivo:
- Validar o Lumen em cenário real controlado antes de uso operacional amplo.

Escopo:
- Testes ponta a ponta.
- Carga inicial com empresas reais controladas.
- Validação de watcher em pasta piloto.
- Validação de Acessórias, Sittax, Domínio e Econet com amostras reais/anonimizadas.
- Ajustes de UX.
- Runbooks finais.

Entregáveis:
- Suíte E2E completa.
- Checklist de go-live.
- `docs/GO_LIVE_CHECKLIST.md`.
- `docs/KNOWN_LIMITATIONS.md`.
- Plano de rollback.
- Plano de backup.

Validação:
```bash
pytest backend/tests
ruff check backend agent
mypy backend/app
cd frontend && npm run lint && npm run typecheck && npm run test && npm run test:e2e
```

Aceite:
- Usuário consegue abrir Painel, Cockpit, Empresa, Envios, Evidências, Divergências, Parcelamentos e Integrações.
- Uma competência piloto pode ser reconciliada do início ao fim.
- Divergências e baixa confiança ficam em fila humana, não escondidas.
- Nenhum fluxo transmite obrigação fiscal automaticamente.

---

## Ordem recomendada para execução com Codex

1. S0 a S4: fundação técnica e modelo fiscal.
2. S5 e S6: fontes essenciais eControle + Acessórias.
3. S7 e S8: portal operacional MVP.
4. S9 a S11: watcher, parsers e conciliação.
5. S12 a S14: Sittax, Domínio e Econet.
6. S15 e S16: parcelamentos, divergências e integrações visuais.
7. S17 a S19: operação, segurança, regressão e go-live.

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
