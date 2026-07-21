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

Status: pendente

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

Status: pendente

Objetivo:

* Enriquecer empresas por CNAE com dados da Econet, identificando tipo de atividade, Fator R, anexos do Simples, possibilidade de Simples/MEI e obrigações indicativas por regime.

Justificativa:

* A Econet é fonte usada manualmente pelo escritório para classificação tributária.
* O Lumen deve aproveitar essa fonte para reduzir consulta manual repetitiva.
* A informação de Fator R é crítica para empresas do Simples Nacional e deve ser cruzada futuramente com Sittax e Domínio Folha.

Premissas:

* Econet possui CAPTCHA de clique no login.
* Não burlar CAPTCHA.
* Não automatizar login de forma indevida.
* Usar login manual assistido.
* Usar sessão persistente enquanto válida.
* Consultar apenas CNAEs novos ou com cache vencido.
* Não consultar Econet em tempo real a cada abertura de tela.

Tipos de atividade oficiais do Lumen:

* `COMERCIO`
* `INDUSTRIA`
* `SERVICOS`
* `SERVICOS_MEDICOS_ODONTOLOGICOS`
* `SERVICOS_IMOBILIARIOS`
* `TEMPLO_RELIGIOSO`

Regra:

* Uma empresa pode ter mais de um tipo de atividade, conforme seus CNAEs.

Endpoints observados e candidatos:

* `GET /ferramentas/regimes_cnae/buscaCnae.php?busca=...`
* `GET /ferramentas/regimes_cnae/index.php?idcnae=...&acao=abrir`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroPresumido&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroRealTrimestral&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroRealEstimativa&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=simplesNacionalTributacao&idCnae=...`
* `GET /ferramentas/regimes_cnae/subAbas.php?aba=empreendedorIndividual&idCnae=...`
* `GET /ferramentas/regimes_cnae/abas.php?aba=obrigacoes&idCnae=...`

Entregáveis de banco:

* `econet_cnae_cache`
* eventual ajuste em `company_activity_types`, se necessário para registrar fonte/confiança/revisão

Campos do cache:

* `cnae`
* `descricao`
* `econet_id_cnae`
* `simples_permitido`
* `mei_permitido`
* `tem_fator_r`
* `anexo_simples_padrao`
* `anexo_simples_condicional`
* `lucro_presumido_possivel`
* `lucro_real_obrigatorio`
* `atividade_detectada`
* `obrigacoes_pj_geral`
* `obrigacoes_simples`
* `raw_html_index`
* `raw_html_simples`
* `raw_html_lucro_presumido`
* `raw_html_obrigacoes`
* `retrieved_at`
* `expires_at`
* `parse_status`

Entregáveis backend:

* `backend/app/services/integrations/econet/assisted_session.py`
* `backend/app/services/integrations/econet/client.py`
* `backend/app/services/integrations/econet/parser.py`
* `backend/app/services/integrations/econet/cache.py`
* `backend/app/services/factor_r.py`
* `backend/app/api/v1/endpoints/integrations/econet.py`
* `backend/app/schemas/econet.py`
* `backend/scripts/enrich_cnaes_econet.py`

Jobs:

* `enrich_cnaes_econet`
* `revalidate_econet_cnae_cache`

Regras:

* Se `tem_fator_r = true`, criar sinal/alerta para empresas do Simples.
* Se Econet indicar Anexo V sujeito ao Fator R e possibilidade de Anexo III quando Fator R >= 28%, registrar essa condição.
* Se Econet indicar impossibilidade de Simples e Acessórias indicar Simples, gerar alerta cadastral/fiscal.
* Se sessão Econet expirar, não quebrar o portal; apenas exibir status de sessão expirada.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econet_parser.py .\backend\tests\test_econet_cache.py .\backend\tests\test_factor_r_rules.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend
```

Aceite:

* CNAE novo entra em fila de enriquecimento.
* Consulta assistida salva HTML bruto e campos interpretados no cache.
* Empresa recebe atividade padronizada quando a confiança for suficiente.
* Empresa com CNAE sujeito ao Fator R recebe flag `tem_fator_r`.
* Sessão expirada aparece no health da integração sem quebrar telas.
* Nenhuma tentativa de bypass de CAPTCHA é implementada.

---

## S9 - Domínio Folha: importador do Resumo Mensal e DCTFWeb DP

Status: pendente

Objetivo:

* Usar o relatório da Domínio Folha para identificar fator gerador de DCTFWeb pela folha/eSocial e atribuir a responsabilidade ao DP quando esse for o único fator gerador.

Justificativa:

* A Domínio não possui API útil para consulta.
* O relatório PDF do Resumo Mensal da Folha se mostrou mais útil que o Excel para automação.
* A DCTFWeb gerada exclusivamente por folha/eSocial deve ser responsabilidade do DP, não do Fiscal.

Premissas:

* Não criar robô de tela da Domínio.
* Não depender do Excel da Domínio para esse relatório.
* Usar PDF com texto extraível.
* OCR somente se o PDF vier como imagem ou a extração de texto falhar.

Escopo:

* Upload/importação assistida do PDF Resumo Mensal da Folha.
* Parser por blocos de empresa.
* Extração de CNPJ, empresa, competência e rubricas.
* Persistência de movimentos por empresa/competência.
* Regra de origem DCTFWeb.
* Alerta para mês seguinte quando houver movimento anterior.

Entregáveis de banco:

* `dominio_payroll_imports`
* `dominio_payroll_company_movements`

Entregáveis backend:

* `backend/app/models/dominio_payroll.py`
* migration para tabelas da Domínio Folha, se ainda não existirem fisicamente
* `backend/app/services/pdf/parse_dominio_payroll.py`
* `backend/app/services/integrations/dominio/payroll_importer.py`
* `backend/app/services/integrations/dominio/mapper.py`
* `backend/app/services/dctfweb_origins.py`
* `backend/app/api/v1/endpoints/integrations/dominio.py`
* `backend/app/schemas/dominio.py`
* `backend/scripts/import_dominio_payroll.py`

Campos extraídos:

* `company_cnpj`
* `company_name`
* `competencia`
* `tem_folha`
* `tem_empregado`
* `tem_pro_labore`
* `tem_autonomo`
* `tem_inss`
* `tem_fgts`
* `tem_rescisao`
* `tem_ferias`
* `valor_proventos`
* `valor_descontos`
* `valor_informativas`
* `valor_liquido`
* `raw_text`
* `arquivo_origem`

Regras de DCTFWeb:

* Movimento de folha, pró-labore, autônomo, INSS, FGTS ou rescisão indica fator gerador de DCTFWeb origem DP.
* Se o único fator gerador da DCTFWeb for folha/eSocial, `responsible_department = DP`.
* Se houver folha + REINF/MIT/tributos federais, `responsible_department = COMPARTILHADO`.
* Se houver somente REINF/MIT/tributos federais, `responsible_department = FISCAL`.
* Se houve DCTFWeb com movimento em uma competência, gerar alerta para a competência seguinte verificar envio, ainda que zerado/sem movimento, quando aplicável.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_dominio_payroll_parser.py .\backend\tests\test_dctfweb_origins.py .\backend\tests\test_dctfweb_next_month_alert.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend
```

Aceite:

* PDF importado cria movimento por empresa sem duplicidade.
* Empresas não encontradas no espelho local ficam em fila de conferência.
* DCTFWeb por folha aparece como responsabilidade do DP.
* DCTFWeb com múltiplas origens aparece como `COMPARTILHADO`.
* Alerta do mês posterior é gerado corretamente.
* Nenhum robô de tela da Domínio é criado.

---

## S10 - Watcher local e motor de evidências por arquivo

Status: pendente

Objetivo:

* Detectar guias, recibos, parcelamentos e evidências fiscais salvas nas pastas das empresas.

Justificativa:

* O watcher é uma fonte essencial de evidências reais.
* Ele não decide sozinho o status fiscal; ele gera sinais e evidências para o backend conciliar.
* Deve funcionar principalmente sobre PDFs digitais com texto extraível.

Escopo:

* Agente local.
* Parser de caminho, empresa e competência.
* Hash de arquivo.
* Classificação inicial por nome/caminho.
* Extração inicial de texto de PDF.
* Registro de evidências.
* Idempotência por hash/caminho.

Pasta principal alvo:

```txt
G:\EMPRESAS\[empresa]\Escrita Fiscal\[competência]\Guias - Impostos e Parcelamentos
```

Palavras-chave iniciais:

```txt
DAS, PIS, COFINS, ICMS, ISS, DIFAL, PROTEGE, PGFN, SISPAR, PARC,
DCTFWEB, DARF, REINF, MIT, IRPJ, CSLL
```

Entregáveis agent:

* `agent/watcher/main.py`
* `agent/watcher/config.py`
* `agent/watcher/file_detector.py`
* `agent/watcher/company_resolver.py`
* `agent/watcher/period_resolver.py`
* `agent/watcher/hash.py`
* `agent/watcher/client.py`
* `agent/parsers/file_name_classifier.py`
* `agent/parsers/pdf_text_probe.py`

Entregáveis backend:

* `backend/app/services/pdf/text_extract.py`
* `backend/app/services/pdf/classify_tax.py`
* `backend/app/api/v1/endpoints/watcher.py`
* endpoint `POST /api/v1/lumen/evidences/watcher-event`
* job `process_pdf_evidences`

Regras:

* O agente local gera evento e envia para o backend.
* O backend decide conciliação final.
* PDF com texto extraível não deve usar OCR.
* OCR é fallback futuro, não obrigatório neste stage.
* Arquivo duplicado por hash/caminho não deve gerar evidência duplicada.

Validação:

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_watcher_events.py .\backend\tests\test_pdf_text_extract.py .\backend\tests\test_file_classifier.py -q
.\.venv\Scripts\python.exe -m ruff check .\backend .\agent
```

Aceite:

* Arquivo novo gera `watcher_file_event`.
* Arquivo novo gera ou atualiza `fiscal_evidence`.
* Reprocessar o mesmo arquivo não duplica evidência.
* Empresa é resolvida por pasta quando possível.
* Competência é resolvida por pasta quando possível.
* Baixa confiança fica como `BAIXA_CONFIANCA` ou `CONFERENCIA_MANUAL`.

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
* Tela Envios suporta escopo “empresa” e “todas”.
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
```
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
* o S8.2 ainda nao foi iniciado
* nao existe sessao assistida, cliente HTTP stateful, endpoint manual, sync funcional ou health operacional da Econet
* o cruzamento entre `external_companies` e `econet_cnae_cache` segue para stage posterior
* `activity_types` permanece vazio ate evidencia HTML suficiente ou regra posterior segura
