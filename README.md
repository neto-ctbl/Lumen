# Lumen - Fiscal Cockpit

Data de referencia: 2026-07-14

O repositorio concluiu os Stages S1, S2, S3, S3.1, S3.2, S4, o micro-stage S4.1, o Stage S5, o microajuste S5.1.1, o Stage S5.1, o micro-stage S6.0, o Stage S6, o micro-stage S7.0, o micro-stage S7.1, o micro-stage S7.2 e o micro-stage S7.3. Nesta etapa, alem da base tecnica minima do S1, do core backend do S2, da autenticacao backend/frontend do S3/S3.1, do nucleo fiscal persistido no S4/S4.1, do espelho cadastral MVP do eControle no S5, do frontend fiscal read-only do S5.1, da integracao oficial read-only com o Sistema Acessorias no S6 e do snapshot cadastral do Sittax no S7.2, o projeto passou a persistir snapshot local read-only da apuracao Sittax por empresa e competencia, com contexto ativo validado por `empresaCnpj + periodo`, execucao serial, dry-run, fixture mode e sem chamar DIFAL, documentos, painel, tarefas ou qualquer mutacao externa.

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

S5.1 entregue:

- endpoints read-only em `backend/app/api/v1/endpoints/lumen.py`
- read model fiscal em `backend/app/services/lumen_read_model.py`
- schemas do portal em `backend/app/schemas/company.py`, `period.py`, `dashboard.py`, `cockpit.py`, `delivery.py`, `evidence.py`, `divergence.py`, `installment.py` e `integration.py`
- testes backend `backend/tests/test_lumen_read_endpoints.py`
- frontend fiscal read-only com shell, layout, componentes e rotas protegidas em `/lumen/*`
- E2E atualizados em `frontend/tests_e2e/smoke.spec.ts`, `shell.spec.ts` e `deliveries.spec.ts`
- frontend read-only validado como baseline funcional do portal fiscal

S6.0 entregue:

- `docs/ACESSORIAS_CONTRACT.md`
- `docs/examples/sample_acessorias_company.json`
- `docs/examples/sample_acessorias_delivery.json`
- `schemas/acessorias_company.schema.json`
- `schemas/acessorias_delivery.schema.json`
- documentacao do projeto atualizada para registrar a API oficial do Acessorias
- contrato limitado a operacoes de consulta para empresas e entregas
- preparacao documental de autenticacao Bearer Token, rate limit, regimes, payloads, idempotencia e estrategia de sync

S6 entregue:

- `backend/app/models/acessorias_company_snapshot.py`
- `backend/app/models/acessorias_delivery_snapshot.py`
- migration `backend/alembic/versions/20260714_0004_create_acessorias_snapshots.py`
- `backend/app/services/integrations/acessorias/client.py`
- `backend/app/services/integrations/acessorias/mapper.py`
- `backend/app/services/integrations/acessorias/regime.py`
- `backend/app/services/integrations/acessorias/obligation_mapping.py`
- `backend/app/services/integrations/acessorias/sync.py`
- `backend/app/api/v1/endpoints/integrations/acessorias.py`
- `backend/app/schemas/acessorias.py`
- `backend/scripts/sync_acessorias_deliveries.py`
- testes backend do Acessorias e E2E da tela Integracoes
- health read-only da integracao e precedencia de regime no read model

Ainda nao existem:

- dominio fiscal de negocio
- transmissao fiscal
- mutacoes fiscais no portal
- watcher, parser PDF, Dominio, Econet ou transmissao fiscal

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
No S5, foi materializada apenas a integracao cadastral MVP do eControle.
No S5.1, foram materializados os endpoints read-only `/api/v1/lumen/*`, o frontend fiscal funcional e os estados vazios honestos quando tabelas operacionais ainda estiverem vazias.

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

Variaveis do S6:

```powershell
ACESSORIAS_API_BASE_URL=https://api.acessorias.com
ACESSORIAS_API_TOKEN=
ACESSORIAS_TIMEOUT_SECONDS=15
ACESSORIAS_REQUESTS_PER_MINUTE=100
```

Variaveis preparatorias do S7:

```powershell
SITTAX_AUTH_BASE_URL=https://autenticacao.sittax.com.br
SITTAX_API_BASE_URL=https://api.sittax.com.br
SITTAX_APURACAO_BASE_URL=https://apuracao.sittax.com.br
SITTAX_EMAIL=
SITTAX_PASSWORD=
SITTAX_API_TOKEN=
SITTAX_TIMEOUT_SECONDS=20
```

Observacoes do S7.1:

- o cliente real do Sittax usa `SITTAX_EMAIL` e `SITTAX_PASSWORD`; `SITTAX_API_TOKEN` permanece apenas reservado
- o JWT do Sittax fica somente em memoria dentro de `SittaxSession`
- o S7.1 implementa apenas login e listagem de empresas
- apuracao, DIFAL, documentos, tarefas, snapshots, sync e health funcional continuam fora de escopo

Observacoes do S7.2:

- o S7.2 cria apenas `sittax_company_snapshots`
- o sync Sittax continua estritamente read-only e chama somente login e listagem de empresas
- a reconciliacao local usa `organization_id + cnpj` contra `external_companies`
- `state_registration` permanece nullable; `ISENTO` segue sendo apenas representacao futura de frontend
- `raw_payload` fica somente no snapshot da empresa; `integration_sync_runs` recebe apenas contadores, erros sanitizados e metadata segura
- `--dry-run` autentica e reconcilia em memoria sem escrever snapshots nem `integration_sync_runs`
- fixture mode reutiliza o mesmo mapper e o mesmo servico sem acessar rede

Observacoes do S7.3:

- o S7.3 cria `sittax_apuracao_snapshots`
- a apuracao Sittax usa `empresaCnpj + periodo` como setter real do contexto de sessao
- o contexto e limpo antes de cada consulta e so e confirmado apos resposta valida com CNPJ e competencia coerentes
- a CLI operacional usa `--period YYYY-MM`, resolve a competencia em `fiscal_periods` e nao a cria implicitamente
- o sync de apuracoes e serial por sessao, processa apenas snapshots `MATCHED` no lote e aceita `--company-id`, `--limit`, `--dry-run` e `--apuracao-fixture`
- `integration_sync_runs` do S7.3 guardam apenas contadores, erros sanitizados e metadata segura

Observacoes do S5:

- `ECONTROLE_API_BASE_URL` e `ECONTROLE_API_TOKEN` so sao exigidos para o script de sync HTTP
- `ECONTROLE_WEBHOOK_TOKEN` e obrigatorio para aceitar qualquer webhook do eControle
- o endpoint de listagem usa path placeholder MVP isolada em codigo: `GET /companies`
- nenhum token, cookie, sessao assistida ou payload real deve ser versionado

Observacoes do S5.1:

- todos os endpoints novos usam o prefixo `/api/v1/lumen`
- o escopo e estritamente read-only neste stage
- `VIEW`, `ADMIN` e `DEV` podem consultar; nao existem mutacoes nem execucao manual de jobs
- `external_companies` e a fonte de empresas; `fiscal_periods` e a fonte de competencias
- `fiscal_obligation_statuses`, `fiscal_evidences`, `fiscal_alerts`, `fiscal_installments` e `integration_sync_runs` podem retornar vazio sem erro
- IE vazia continua persistida como `NULL`/vazio e so aparece como `ISENTO` no frontend
- regime exibido permanece honesto como `Aguardando Acessorias` enquanto a fonte oficial do S6 nao existe

Observacoes do S6:

- o Acessorias possui API oficial documentada em `https://api.acessorias.com/documentation`
- a base URL oficial e `https://api.acessorias.com`
- a autenticacao oficial usa `Authorization: Bearer <token>`
- o token deve ser gerado no proprio Sistema Acessorias pela opcao `API Token`
- o limite oficial documentado e `100` requisicoes por minuto
- nao e necessario usar DevTools, HAR ou engenharia reversa
- Sittax e Econet permanecem como integracoes que podem depender de requisicoes observadas em etapas futuras
- o S6 utilizara somente operacoes de consulta
- nenhuma inclusao, edicao, transmissao ou alteracao externa faz parte do S6
- o token e opcional no boot geral da aplicacao e obrigatorio apenas para sync real
- o endpoint manual do S6 e `POST /api/v1/integrations/acessorias/sync` com RBAC `ADMIN|DEV`
- o script operacional do S6 e `python -m backend.scripts.sync_acessorias_deliveries`
- o modo fixture nao exige token real e reutiliza os mesmos mappers e servicos

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

Fluxo complementar do S5.1:

1. Validar sidebar com `Painel`, `Cockpit`, `Envios`, `Evidencias`, `Divergencias`, `Parcelamentos` e `Integracoes`
2. Abrir o dropdown de empresa no header e pesquisar por razao social, apelido ou CNPJ
3. Abrir o dropdown de competencia e confirmar exibicao em `MM/YYYY`
4. Navegar para `/lumen/envios` e alternar os modos `Empresa` e `Todas`
5. Confirmar que listas vazias e KPIs zerados aparecem sem erro quando nao houver dados fiscais operacionais

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

Observacao S5.1 para o frontend:

- `/login` permanece publico
- `/lumen/*` permanece protegido pelo fluxo atual de `ProtectedRoute`, `authStore`, `authService` e `apiClient`
- o roteamento continua manual, sem `react-router-dom`
- o smoke E2E continua passando e agora cobre shell e envios tambem
- estados vazios do portal sao esperados enquanto nao existirem dados fiscais operacionais

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

O smoke E2E publico em `/lumen/painel` ficou superado pelo S3.1. No estado atual, `/login` e publico e `/lumen/*` exige autenticacao.

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

Validacao do S5.1:

```powershell
.\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_lumen_read_endpoints.py -q
.\.venv\Scripts\python.exe -m pytest .\backend\tests\test_auth.py .\backend\tests\test_rbac.py .\backend\tests\test_econtrole_mapper.py .\backend\tests\test_econtrole_sync.py .\backend\tests\test_econtrole_webhook.py -q
ruff check .\backend
cd .\frontend
npm run typecheck
npm run test:e2e
```

Validacao manual do S5.1:

```powershell
.\scripts\dev\run_backend.ps1
.\scripts\dev\run_frontend.ps1
```

Observacao de escopo do S5.1:

- todos os endpoints novos sao `GET /api/v1/lumen/*`
- o portal fiscal continua estritamente read-only
- KPIs zerados e listas vazias sao respostas validas quando ainda nao houver dados fiscais operacionais
- nenhuma migration nova foi necessaria
- S6/Acessorias nao foi iniciado

Fechamento tecnico do S6:

- `docs/ACESSORIAS_CONTRACT.md` formaliza autenticacao, endpoints `GET /companies/{identificador}` e `GET /deliveries/{identificador}`, campos de interesse, limites, riscos, aliases seguros e estrategia de sync
- `docs/examples/` e `schemas/` contem exemplos anonimizados e contratos JSON derivados apenas da documentacao oficial
- a migration `20260714_0004_create_acessorias_snapshots.py` cria `acessorias_company_snapshots` e `acessorias_delivery_snapshots`
- o sync inicial permanece serial, read-only e previsivel: empresas por `ListAll + registrationData`, entregas por empresa e intervalo mensal com `config`
- o portal continua sem consultar a API externa em request do frontend; ele le apenas o read model local e os `fiscal_obligation_statuses` atualizados pelo sync
- o S6 nao baixa anexos, nao usa endpoints `POST`, nao transmite obrigacoes e nao inicia watcher nem conciliacao do S11

Fechamento tecnico do S7.0:

- `docs/SITTAX_OBSERVED_CONTRACT.md` materializa o contrato observado do portal Sittax sem versionar o log bruto
- `docs/DECISOES.md`, `docs/RISCOS.md` e `docs/SECURITY.md` passam a existir com as decisoes e restricoes do Sittax
- `backend/tests/fixtures/sittax/` contem fixtures sinteticas e anonimizadas para login, empresas, apuracao, DIFAL, painel, tarefas e notas fiscais
- `schemas/sittax_*.schema.json` registram envelopes observados e expansibilidade do contrato
- o stack E2E dedicado sobrescreve `ACESSORIAS_API_TOKEN`, `SITTAX_EMAIL`, `SITTAX_PASSWORD` e `SITTAX_API_TOKEN` para nao herdar integracoes do `.env` local
- nenhuma migration, nenhum model Sittax, nenhum cliente real, nenhum sync real e nenhuma chamada externa nova foram adicionados
- o macro-stage S7 continua pendente; apenas o micro-stage documental e de seguranca foi fechado

Fechamento tecnico do S7.1:

- `backend/app/services/integrations/sittax/` passou a existir com `errors.py`, `session.py`, `client.py`, `mapper.py` e `__init__.py`
- `backend/app/schemas/sittax.py` define DTOs read-only para escritorio e empresas
- `backend/scripts/check_sittax_connection.py` valida login e listagem de empresas sem persistir dados nem imprimir PII
- `backend/tests/test_sittax_client.py`, `test_sittax_session.py`, `test_sittax_mapper.py` e `test_sittax_connection_script.py` cobrem contrato, seguranca e fixture mode
- a sessao Sittax usa um unico `httpx.Client` por instancia, lock local por `session.exclusive()` e JWT somente em memoria
- o card Sittax do E2E continua `Nao iniciada` / `Nao configurada`, sem botao de sync e sem chamada externa
- nenhuma migration, nenhum model Sittax, nenhum sync e nenhum endpoint manual foram adicionados
- o macro-stage S7 continua pendente
- validacao real controlada do Sittax executada em `2026-07-16`: login real aprovado, escritorio resolvido e `157` empresas retornadas em modo read-only
- a homologacao real confirmou os endpoints do S7.1 sem chamar apuracao, DIFAL, documentos, tarefas ou qualquer mutacao externa
- o login real do portal retornou sucesso com `codigo = 200`, e o mapper do cliente foi ajustado para aceitar `0` e `200` como codigos de sucesso observados

Fechamento tecnico do S7.2:

- `backend/app/models/sittax_company_snapshot.py` materializa o snapshot multi-tenant de empresas Sittax
- a migration `20260716_0005_create_sittax_company_snapshots.py` cria apenas `sittax_company_snapshots`
- `backend/app/services/integrations/sittax/sync.py` implementa autenticacao, listagem, reconciliacao por CNPJ, upsert idempotente, dry-run, fixture mode e rastreio por `integration_sync_runs`
- `backend/scripts/sync_sittax_companies.py` executa o sync operacional seguro por `--org-slug`, `--dry-run` e `--companies-fixture`
- `MATCHED`, `UNMATCHED`, `AMBIGUOUS` e `INVALID_CNPJ` passam a ser tratados explicitamente no snapshot
- ausencia na listagem Sittax nao gera soft delete nem inativacao automatica de `external_companies`
- o sync continua serial por sessao, sem apuracao, sem contexto ativo, sem DIFAL, sem documentos, sem tarefas e sem qualquer mutacao externa
- o card Sittax do frontend e o fluxo E2E continuam sem sync operacional exposto
- validacao automatizada concluida em `2026-07-16` com `15 passed` na suite nova, `154 passed` na regressao backend, `ruff` limpo, `typecheck` ok e `4 passed` no E2E
- validacao real controlada concluida em `2026-07-16` com `157` empresas recebidas, `157` validas, `155` reconciliadas como `MATCHED` e `2` como `UNMATCHED`
- a primeira execucao real persistiu `157` snapshots; a segunda execucao serial confirmou idempotencia com `snapshots_created = 0` e `snapshots_unchanged = 157`
- a consulta SQL final confirmou `157` linhas em `sittax_company_snapshots`, distribuicao `MATCHED = 155` e `UNMATCHED = 2`, e zero duplicidades por `organization_id + sittax_company_id`

Fechamento tecnico do S7.3:

- `backend/app/models/sittax_apuracao_snapshot.py` materializa o snapshot multi-tenant de apuracao Sittax por empresa e competencia
- a migration `20260716_0006_create_sittax_apuracao_snapshots.py` cria apenas `sittax_apuracao_snapshots`
- `backend/app/services/integrations/sittax/client.py` passa a consultar `GET /api/apuracao/retornar-apuracao-sittax` com validacao de contexto e limpeza obrigatoria de sessao antes de cada tentativa
- `backend/app/services/integrations/sittax/sync.py` implementa resolucao de competencia em `fiscal_periods`, execucao serial, upsert idempotente e dry-run sem escrita para apuracao
- `backend/scripts/sync_sittax_apuracoes.py` executa o sync operacional seguro por `--org-slug`, `--period`, `--company-id`, `--limit`, `--dry-run` e `--apuracao-fixture`
- o sync continua read-only contra o Sittax, sem DIFAL, sem documentos fiscais, sem painel, sem tarefas e sem qualquer mutacao externa

Fechamento final validado em 2026-07-15:

- login manual com `ADMIN` confirmado no backend local
- endpoint manual `POST /api/v1/integrations/acessorias/sync` validado em `dry_run`
- leitura real da API oficial do Acessorias confirmada com token local fora do Git
- validacao real mais util no estado atual: `--org-slug neto-contabilidade --period 2026-06 --company-id 78 --dry-run`
- o `dry_run` amplo no tenant `lumen` confirmou conectividade e contrato, mas nao gerou match de empresas locais porque o usuario autenticado estava na organizacao `lumen` e o espelho real de empresas usado na validacao pertence a `neto-contabilidade`

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
