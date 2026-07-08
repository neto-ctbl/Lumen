# Lumen - Fiscal Cockpit

Data de referencia: 2026-07-07

O repositorio concluiu os Stages S1, S2, S3, S3.1, S3.2, S4, o micro-stage S4.1 e o Stage S5. Nesta etapa, alem da base tecnica minima do S1, do core backend do S2, da autenticacao backend/frontend do S3/S3.1 e do nucleo fiscal persistido no S4/S4.1, o projeto passou a ter o espelho cadastral MVP do eControle por HTTP, webhook e sincronizacao rastreavel.

## Escopo real atual

S1 entrega:

- Docker Compose com PostgreSQL e Redis
- Backend FastAPI minimo
- Healthchecks da API e do worker
- Worker stub executavel
- Frontend React/Vite minimo
- Smoke E2E minimo
- Scripts PowerShell de desenvolvimento

S2 entrega:

- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/core/security.py` com utilitarios minimos
- `backend/app/db/base.py`
- `backend/app/db/session.py`
- `backend/alembic.ini` e `backend/alembic/`
- modelo `audit_log`
- servico `backend/app/services/audit.py`
- testes backend de config, health, DB e auditoria
- `pytest.ini` na raiz com `pythonpath = .`

S3 entrega:

- `backend/app/models/organization.py`
- `backend/app/models/user.py`
- `backend/app/models/user_organization.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/endpoints/auth.py`
- migration `20260706_0002_auth_rbac_multitenant.py`
- script `backend/scripts/create_initial_admin.py`
- testes backend de auth e RBAC

S3.1 entrega:

- `frontend/src/services/apiClient.ts`
- `frontend/src/services/authService.ts`
- `frontend/src/stores/authStore.tsx`
- `frontend/src/features/auth/LoginPage.tsx`
- `frontend/src/features/auth/ProtectedRoute.tsx`
- `frontend/scripts/run_e2e_stack.ps1`
- rota `/login`
- `/lumen/painel` protegido no frontend
- logout integrado ao backend
- smoke E2E atualizado para login e logout

S3.2 entrega:

- microajuste tecnico de compatibilidade para `passlib` + `bcrypt` no Windows
- `bcrypt` pinado em faixa compatível no `requirements.txt`
- shim minimo em `backend/app/core/security.py` para evitar o warning do `bcrypt.__about__`

S4 entrega:

- enum Python em `backend/app/core/enums.py` para status de conciliacao, departamentos e tipos de atividade
- models fiscais centrais e tabelas do nucleo fiscal
- migration `backend/alembic/versions/20260706_0003_create_fiscal_core.py`
- seed idempotente `backend/scripts/seed_obligations.py`
- testes `backend/tests/test_models.py` e `backend/tests/test_obligation_seed.py`

S4.1 entrega:

- seed idempotente `backend/scripts/seed_obligation_rules.py`
- seed idempotente `backend/scripts/seed_periods.py`
- testes `backend/tests/test_obligation_rules_seed.py` e `backend/tests/test_period_seed.py`
- catalogo logico inicial de regras-base e competencias 2026 para uso interno do portal
- regras separadas para `LUCRO_PRESUMIDO` e `LUCRO_REAL` em `PIS`, `COFINS` e `EFD_CONTRIBUICOES`
- regime fiscal tecnico `IMUNE_ISENTA` reconhecido para uso futuro, com label de interface `Imune/Isenta`

S5 entrega:

- `backend/app/services/integrations/econtrole/client.py`
- `backend/app/services/integrations/econtrole/mapper.py`
- `backend/app/services/integrations/econtrole/sync.py`
- `backend/app/api/v1/endpoints/webhooks/econtrole.py`
- `backend/scripts/sync_econtrole_companies.py`
- testes backend de mapper, sync e webhook do eControle
- espelho cadastral de empresas do eControle em `external_companies`
- webhooks protegidos por `X-Lumen-Webhook-Token`
- execucoes rastreadas em `integration_sync_runs`

Ainda nao existem:

- dominio fiscal de negocio
- integracao Acessorias do S6
- transmissao fiscal
- frontend fiscal novo

## Regimes fiscais reconhecidos

- `SIMPLES_NACIONAL`
- `MEI`
- `LUCRO_PRESUMIDO`
- `LUCRO_REAL`
- `IMUNE_ISENTA`

Label futuro de interface para `IMUNE_ISENTA`: `Imune/Isenta`.

## Portas locais do Lumen

- API FastAPI: `8000`
- Frontend Vite: `5175`
- PostgreSQL host: `5435`
- Redis host: `6382`

Essas portas foram ajustadas para nao conflitar com outros projetos locais.

O Docker Compose do Lumen usa project name fixo `lumen` para evitar ambiguidade com outros repositorios locais.

## Estrutura e plano

- Estrutura alvo do monorepo: `ESTRUTURA_REPO.md`
- Plano por stages: `PLANO_DESENVOLVIMENTO.md`

No S1, apenas o subconjunto minimo foi materializado em disco. A arvore completa continua sendo objetivo de stages futuros.
No S2, foram materializados os blocos tecnicos de core, DB, migration, auditoria e testes.
No S3, foram materializados autenticacao backend, RBAC global e multi-tenant inicial.
No S4, foram materializados os modelos fiscais core, sem avancar para S5, S6 ou integracoes externas reais.
No S4.1, foram materializados seeds logicos de regras-base e competencias, sem criar status por empresa/competencia e sem iniciar sincronizacao de empresas.
O S4.1 foi tratado como micro-stage complementar de fechamento tecnico e nao como stage originalmente enumerado no `PLANO_DESENVOLVIMENTO.md`.
No S5, foi materializada apenas a integracao cadastral MVP do eControle; o fluxo visual do frontend e o smoke E2E existente permanecem os mesmos.

## Setup local no Windows PowerShell

### 1. Ambiente Python

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt
```

### 2. Variaveis locais

```powershell
Copy-Item .\.env.example .\.env
```

`.env` real continua fora do Git.

Variaveis novas do S3:

```powershell
SECRET_KEY=change-me-only-local
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
INITIAL_ADMIN_EMAIL=admin@example.local
INITIAL_ADMIN_PASSWORD=
INITIAL_ADMIN_FULL_NAME=Initial Admin
INITIAL_ORG_NAME=Lumen
INITIAL_ORG_SLUG=lumen
VITE_API_BASE_URL=http://localhost:8000
```

Variaveis novas do S5:

```powershell
ECONTROLE_API_BASE_URL=http://localhost:8090/api
ECONTROLE_API_TOKEN=
ECONTROLE_WEBHOOK_TOKEN=
ECONTROLE_TIMEOUT_SECONDS=15
```

Observacoes do S5:

- `ECONTROLE_API_BASE_URL` e `ECONTROLE_API_TOKEN` so sao exigidos para o script de sync HTTP
- `ECONTROLE_WEBHOOK_TOKEN` e obrigatorio para aceitar qualquer webhook do eControle
- o endpoint de listagem usa path placeholder MVP isolada em codigo: `GET /companies`
- nenhum token, cookie, sessao assistida ou payload real deve ser versionado

Observacao S3.1:

- o frontend usa `VITE_API_BASE_URL`
- `VITE_LUMEN_API_BASE_URL` continua aceito como fallback de compatibilidade
- neste MVP o access token e o refresh token ficam em `localStorage`
- hardening futuro deve revisar armazenamento e refresh automatico

`pytest.ini` define `pythonpath = .` para os imports do backend nos testes.

### 3. Infra local

```powershell
docker compose -f .\infra\docker-compose.yml up -d
docker compose -f .\infra\docker-compose.yml ps
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select current_database(), current_user;"
docker compose -f .\infra\docker-compose.yml exec redis redis-cli ping
```

Resultado esperado:

- containers `lumen-postgres-1` e `lumen-redis-1`
- PostgreSQL ouvindo em `localhost:5435`
- Redis ouvindo em `localhost:6382`
- comando `redis-cli ping` retornando `PONG`
- banco principal padrao: `lumen`
- banco de teste padrao: `lumen_test`

### 4. Backend

```powershell
.\scripts\dev\run_backend.ps1
alembic -c .\backend\alembic.ini upgrade head
python -m backend.scripts.create_initial_admin
```

Em outro terminal:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
Invoke-RestMethod http://localhost:8000/api/v1/worker/health
```

Exemplo de fluxo auth S3:

```powershell
$loginBody = @{ email = "admin@example.local"; password = "trocar-localmente" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/login -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }

Invoke-RestMethod -Method Get -Uri http://localhost:8000/api/v1/auth/me -Headers $headers

$refreshBody = @{ refresh_token = $login.refresh_token } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/refresh -ContentType "application/json" -Body $refreshBody

$logoutBody = @{ refresh_token = $login.refresh_token } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/auth/logout -Headers $headers -ContentType "application/json" -Body $logoutBody
```

### 5. Worker stub

```powershell
.\scripts\dev\run_worker.ps1
```

Resultado esperado:

```txt
Lumen worker stub OK - Stage S1
```

### 6. Frontend

```powershell
.\scripts\dev\run_frontend.ps1
Invoke-WebRequest http://localhost:5175/login -UseBasicParsing | Select-Object StatusCode
```

Fluxo esperado do S3.1:

1. Abrir `http://localhost:5175/login`
2. Entrar com o admin criado por `python -m backend.scripts.create_initial_admin`
3. Confirmar redirecionamento para `http://localhost:5175/lumen/painel`
4. Confirmar usuario e organizacao ativa no shell
5. Clicar em `Sair`
6. Confirmar retorno para `/login`

### 7. Validacao do frontend

```powershell
cd .\frontend
npm run typecheck
npm run test:e2e
```

Variaveis opcionais de E2E:

```powershell
$env:E2E_ADMIN_EMAIL = "admin@example.local"
$env:E2E_ADMIN_PASSWORD = "ChangeMe123!"
```

Se essas variaveis nao forem definidas, o E2E usa o admin local padrao de desenvolvimento acima apenas para ambiente local.

Observacao S5 para o frontend:

- o smoke E2E existente deve continuar passando sem alteracao de fluxo visual
- S5 nao adiciona tela nova nem altera `/login` ou `/lumen/painel`

### 8. Validacao minima do backend S2

```powershell
$env:LUMEN_TEST_DATABASE_URL = "postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test"
pytest .\backend\tests\test_health.py .\backend\tests\test_config.py .\backend\tests\test_db.py .\backend\tests\test_audit.py
ruff check .\backend
```

Os testes backend usam `LUMEN_TEST_DATABASE_URL`. Na ausencia dela, o padrao de teste continua `postgresql+psycopg://lumen:lumen@localhost:5435/lumen_test`.

### 9. Validacao do backend S3

```powershell
alembic -c .\backend\alembic.ini upgrade head
alembic -c .\backend\alembic.ini downgrade -1
alembic -c .\backend\alembic.ini upgrade head
pytest .\backend\tests\test_config.py .\backend\tests\test_health.py .\backend\tests\test_db.py .\backend\tests\test_audit.py .\backend\tests\test_auth.py .\backend\tests\test_rbac.py
ruff check .\backend
cd .\frontend
npm run typecheck
npm run test:e2e
```

O smoke E2E atual do frontend continua publico em `/lumen/painel`. O login visual e a protecao de rotas do frontend continuam fora do escopo do S3.

No S3.1, o frontend deixa de ser totalmente publico:

- `/login` fica publico
- `/lumen/painel` exige autenticacao
- o E2E sobe um backend dedicado local em porta isolada e usa `VITE_API_BASE_URL` apontando para ele

### 10. Validacao do backend S4

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select * from alembic_version;"
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "\dt"
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select code, name, department_default, active from fiscal_obligations order by code;"
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_models.py .\backend\tests\test_obligation_seed.py -q
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_config.py .\backend\tests\test_health.py .\backend\tests\test_db.py .\backend\tests\test_audit.py .\backend\tests\test_auth.py .\backend\tests\test_rbac.py -q
ruff check .\backend
```

Rollback validado no S4:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini downgrade -1
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "\dt"
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations
```

Observacao de escopo do S4:

- nenhum endpoint fiscal operacional novo foi criado
- `/login` e `/lumen/painel` permanecem funcionando como no S3.1
- o frontend/E2E existente nao muda de fluxo e deve continuar passando

### Integracao eControle do S5

Sync manual MVP:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m backend.scripts.sync_econtrole_companies --org-slug neto-contabilidade
```

Fallback MVP sem `--org-slug`:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.sync_econtrole_companies
```

Esse fallback so e aceito quando existir exatamente uma organizacao ativa.

Exemplo PowerShell de webhook de upsert:

```powershell
$headers = @{
  "X-Lumen-Webhook-Token" = "trocar-localmente"
  "Content-Type" = "application/json"
}
$body = @{
  org_slug = "neto-contabilidade"
  id = "123"
  profile_id = "456"
  cnpj = "19.163.109/0001-78"
  razao_social = "AC SOARES LTDA"
  nome_fantasia = "AC Soares"
  updated_at = "2026-07-07T10:00:00-03:00"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/webhooks/econtrole/company-upsert -Headers $headers -Body $body
```

Exemplo PowerShell de webhook de delete:

```powershell
$headers = @{
  "X-Lumen-Webhook-Token" = "trocar-localmente"
  "Content-Type" = "application/json"
}
$body = @{
  org_slug = "neto-contabilidade"
  cnpj = "19.163.109/0001-78"
  deleted_at = "2026-07-07T11:00:00-03:00"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/webhooks/econtrole/company-delete -Headers $headers -Body $body
```

Exemplo `curl` de webhook de upsert:

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/econtrole/company-upsert \
  -H "Content-Type: application/json" \
  -H "X-Lumen-Webhook-Token: trocar-localmente" \
  -d '{"org_slug":"neto-contabilidade","id":"123","profile_id":"456","cnpj":"19.163.109/0001-78","razao_social":"AC SOARES LTDA","nome_fantasia":"AC Soares","updated_at":"2026-07-07T10:00:00-03:00"}'
```

Exemplo `curl` de webhook de delete:

```bash
curl -X POST http://localhost:8000/api/v1/webhooks/econtrole/company-delete \
  -H "Content-Type: application/json" \
  -H "X-Lumen-Webhook-Token: trocar-localmente" \
  -d '{"org_slug":"neto-contabilidade","cnpj":"19.163.109/0001-78","deleted_at":"2026-07-07T11:00:00-03:00"}'
```

Validacao backend do S5:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_econtrole_mapper.py .\backend\tests\test_econtrole_sync.py .\backend\tests\test_econtrole_webhook.py -q
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py .\backend\tests\test_models.py .\backend\tests\test_obligation_seed.py .\backend\tests\test_obligation_rules_seed.py .\backend\tests\test_period_seed.py -q
ruff check .\backend
cd .\frontend
npm run typecheck
npm run test:e2e
```

Observacao de escopo do S5:

- o sync cadastral nao usa banco direto do eControle
- o S5 nao cria `fiscal_obligation_statuses`
- o S5 nao inicia Acessorias nem transmissao fiscal
- o frontend visual e o fluxo E2E existente continuam inalterados e devem seguir passando

### 11. Seed logico do S4.1

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligation_rules
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligation_rules
.\.venv\Scripts\python.exe -m backend.scripts.seed_periods --year 2026
.\.venv\Scripts\python.exe -m backend.scripts.seed_periods --year 2026
```

Com `organization_id` obrigatorio em `fiscal_periods`, o seed aceita:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.seed_periods --year 2026 --org-slug neto-contabilidade
```

Se `--org-slug` nao for informado, o script usa a primeira organizacao ativa apenas em ambiente local/MVP.

Conferencia de banco para o S4.1:

```powershell
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select count(*) from fiscal_obligations;"
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select count(*) from fiscal_obligation_rules;"
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select competencia from fiscal_periods order by competencia;"
```

Observacao de escopo do S4.1:

- nenhuma integracao externa foi criada
- nenhum endpoint fiscal operacional novo foi criado
- nenhum `fiscal_obligation_statuses` por empresa/competencia foi gerado ainda
- a aplicabilidade real continua futura e dependera de Acessorias, watcher, Sittax, Dominio e motor de conciliacao
- pendencia futura registrada: avaliar inclusao de `DESTDA` no catalogo estadual para cenarios de Simples Nacional com ST, antecipacao ou DIFAL
- pendencia tecnica registrada: avaliar constraint unica futura em `fiscal_obligation_rules` considerando `organization_id`, `obligation_id`, `regime`, `activity_type` e `rule_type`; hoje o seed e idempotente por aplicacao, mas execucao paralela pode gerar duplicidade transitoria sem trava/constraint no banco

Complemento do S4.1 para regime fiscal:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligations
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligation_rules
.\.venv\Scripts\python.exe -m backend.scripts.seed_obligation_rules
docker compose -f .\infra\docker-compose.yml exec postgres psql -U lumen -d lumen -c "select distinct regime from fiscal_obligation_rules order by regime nulls first;"
```

Resultado esperado nas regras:

- `NULL`
- `LUCRO_PRESUMIDO`
- `LUCRO_REAL`
- `MEI`
- `SIMPLES_NACIONAL`

`IMUNE_ISENTA` passa a existir no catalogo tecnico de regimes, mas nao precisa aparecer em `fiscal_obligation_rules` neste momento.

## Healthchecks do S1

- `GET /healthz`
- `GET /api/v1/worker/health`

Respostas esperadas:

```json
{
  "status": "ok",
  "service": "lumen-api",
  "stage": "S1"
}
```

```json
{
  "status": "ok",
  "service": "lumen-worker",
  "mode": "stub",
  "stage": "S1"
}
```

## Arquivos-base do stage

- `.env.example`
- `infra/docker-compose.yml`
- `backend/app/main.py`
- `backend/app/api/v1/endpoints/health.py`
- `backend/app/api/v1/endpoints/worker.py`
- `backend/app/worker/runner.py`
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/src/main.tsx`
- `frontend/src/app/LumenShell.tsx`
- `frontend/tests_e2e/smoke.spec.ts`
- `scripts/dev/run_backend.ps1`
- `scripts/dev/run_frontend.ps1`
- `scripts/dev/run_worker.ps1`

## Arquivos-base adicionados no S2

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
- `pytest.ini`

## Arquivos-base adicionados no S3

- `backend/app/models/organization.py`
- `backend/app/models/user.py`
- `backend/app/models/user_organization.py`
- `backend/app/schemas/auth.py`
- `backend/app/services/auth.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/endpoints/auth.py`
- `backend/scripts/create_initial_admin.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_rbac.py`
- `backend/alembic/versions/20260706_0002_auth_rbac_multitenant.py`

## Arquivos-base adicionados no S3.1

- `frontend/src/services/apiClient.ts`
- `frontend/src/services/authService.ts`
- `frontend/src/stores/authStore.tsx`
- `frontend/src/features/auth/LoginPage.tsx`
- `frontend/src/features/auth/ProtectedRoute.tsx`
- `frontend/scripts/run_e2e_stack.ps1`

## Arquivos-base adicionados no S4

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

## Arquivos-base adicionados no S4.1

- `backend/scripts/seed_obligation_rules.py`
- `backend/scripts/seed_periods.py`
- `backend/tests/test_obligation_rules_seed.py`
- `backend/tests/test_period_seed.py`

## Arquivos-base adicionados no S5

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
