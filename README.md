# Lumen - Fiscal Cockpit

Data de referencia: 2026-07-06

O repositorio concluiu os Stages S1 e S2. Nesta etapa, alem da base tecnica minima do S1, foi entregue o core backend do S2 com configuracao por ambiente, logging estruturado basico, sessao DB SQLAlchemy, Alembic funcional, modelo `audit_log`, servico de auditoria e harness de testes com banco isolado.

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

Ainda nao existem:

- autenticacao ou RBAC real
- modelos fiscais do S4
- dominio fiscal de negocio
- integracoes reais

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
No S2, foram materializados apenas os blocos tecnicos de core, DB, migration, auditoria e testes, sem avancar para autenticacao, RBAC ou modelos fiscais.

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

### 4. Backend

```powershell
.\scripts\dev\run_backend.ps1
alembic -c .\backend\alembic.ini upgrade head
```

Em outro terminal:

```powershell
Invoke-RestMethod http://localhost:8000/healthz
Invoke-RestMethod http://localhost:8000/api/v1/worker/health
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
Invoke-WebRequest http://localhost:5175/lumen/painel -UseBasicParsing | Select-Object StatusCode
```

### 7. Validacao do frontend

```powershell
cd .\frontend
npm run typecheck
npm run test:e2e
```

### 8. Validacao minima do backend S2

```powershell
pytest .\backend\tests\test_health.py .\backend\tests\test_config.py .\backend\tests\test_db.py .\backend\tests\test_audit.py
ruff check .\backend
```

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
