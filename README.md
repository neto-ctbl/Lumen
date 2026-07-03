# Lumen — Fiscal Cockpit

Data de referência: 2026-07-03

O **Lumen** é um portal fiscal independente da Neto Contabilidade, criado para ser uma central de visualização, conciliação, evidências e alertas fiscais por empresa e competência.

A proposta não é criar mais um sistema para ser alimentado manualmente. O Lumen deve cruzar fontes já usadas pelo escritório e exigir intervenção humana apenas quando houver divergência, baixa confiança, ausência de evidência, exceção fiscal ou risco de obrigação não observada.

## Objetivo do produto

Responder, de forma visual e confiável:

> Qual é a situação fiscal de cada empresa nesta competência?

O Lumen deve consolidar:

- obrigações exigíveis, entregues, pendentes, dispensadas ou não aplicáveis;
- guias, recibos, comprovantes e arquivos encontrados;
- divergências entre Acessórias, Sittax, pastas, Domínio, Econet e eControle;
- parcelamentos ativos e risco de inadimplência;
- fator gerador e responsabilidade da DCTFWeb;
- alertas por empresa, competência, obrigação, fonte e departamento.

## Princípios obrigatórios

1. **Não ser mais um sistema para alimentar.** Entrada manual deve ficar limitada a revisões, justificativas, confirmações e exceções.
2. **Trabalhar por evidências.** O status fiscal deve nascer do cruzamento entre APIs, arquivos, PDFs, relatórios e snapshots.
3. **Projeto separado do eControle.** O eControle é fonte cadastral; o Lumen tem banco próprio e integração por API, webhook e reconciliação periódica.
4. **Evitar robôs frágeis.** Priorizar API, endpoint autorizado, exportação, watcher, parser de PDF e OCR apenas como fallback. Não burlar CAPTCHA e não transmitir obrigação automaticamente.
5. **Segurança primeiro.** Tokens, cookies, sessões assistidas, senhas, certificados e arquivos fiscais reais nunca devem ser versionados.

## Stack inicial

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- RQ Worker
- Pytest

### Frontend

- React
- Vite
- TypeScript
- CSS Modules ou SCSS com tokens visuais próprios
- App shell SaaS com sidebar azul escuro, header sticky translúcido, dropdown global de empresa/competência e telas operacionais

### Agente local / automações

- Watcher de diretórios do `G:\EMPRESAS`
- Processamento de PDFs com texto extraível
- OCR somente como fallback
- Scripts PowerShell operacionais
- Jobs agendados externamente quando fizer sentido

### Infra

- Docker Compose para PostgreSQL e Redis
- `.env.example` para configuração local
- Healthchecks de API, worker e integrações
- Logs de auditoria e runs de sincronização

## Fontes e integrações

| Fonte | Papel no Lumen | Regra principal |
|---|---|---|
| eControle | Dados cadastrais gerais das empresas | Sincronizar para `external_companies`; exclusão vira soft delete |
| Acessórias | Regime tributário e status formal de obrigações | Fonte oficial para regime e entregas |
| Sittax | Simples Nacional, DAS, DIFAL, documentos fiscais e tarefas | Somente leitura; cuidado com contexto de sessão por empresa/período |
| Domínio | Folha/DP por relatórios e arquivos exportados | Sem robô de tela; importar PDF do Resumo Mensal da Folha |
| Econet | CNAE, atividade, Fator R, anexos e obrigações indicativas | Login assistido; cache por CNAE; não burlar CAPTCHA |
| Watcher G: | Guias, recibos, parcelamentos e evidências salvas em pasta | Parser de caminho, nome, texto do PDF e hash do arquivo |

## Regras críticas do domínio fiscal

### Regime tributário

O regime usado na lógica fiscal do Lumen deve vir do **Acessórias**. Se divergir do eControle, o Lumen usa Acessórias para regra fiscal e gera alerta cadastral.

### Inscrição Estadual

A Inscrição Estadual deve ser mantida no cadastro espelhado da empresa. Quando vazia, o frontend deve exibir:

```txt
ISENTO
```

### DCTFWeb

A DCTFWeb deve ser analisada por origem/fator gerador:

| Origem | Responsabilidade |
|---|---|
| eSocial/Folha | DP |
| REINF | Fiscal |
| MIT/tributos federais | Fiscal |
| Folha + REINF/MIT | Compartilhado |

Se houve DCTFWeb com movimento em uma competência, a competência seguinte deve gerar alerta para verificar envio, ainda que zerado/sem movimento.

### Fator R

A Econet será a fonte principal de enriquecimento por CNAE. O Lumen deve sinalizar empresas sujeitas ao Fator R e cruzar com folha/pró-labore, DAS, Sittax e regime Simples Nacional.

## Estrutura inicial do repositório

Consultar [`ESTRUTURA_REPO.md`](./ESTRUTURA_REPO.md).

## Plano de desenvolvimento

Consultar [`PLANO_DESENVOLVIMENTO.md`](./PLANO_DESENVOLVIMENTO.md).

O plano está dividido em stages com objetivo, escopo, entregáveis e critérios de validação. A recomendação para trabalhar com Codex é executar um stage por vez, sempre fechando testes e documentação antes de avançar.

## Setup local previsto

### 1. Clonar o repositório

```bash
git clone <repo-lumen>
cd lumen
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Nunca versionar `.env`, cookies, tokens, arquivos `.pfx`, sessões assistidas ou PDFs fiscais reais.

### 3. Subir infraestrutura local

```bash
docker compose -f infra/docker-compose.yml up -d
```

Serviços previstos:

- PostgreSQL
- Redis

### 4. Backend

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic -c backend/alembic.ini upgrade head
uvicorn backend.app.main:app --reload --port 8000
```

Healthcheck esperado:

```bash
curl http://localhost:8000/healthz
```

### 5. Worker

```bash
python -m backend.app.worker.runner
```

Healthcheck esperado:

```bash
curl http://localhost:8000/api/v1/worker/health
```

### 6. Frontend

```bash
cd frontend
npm install
npm run dev
```

URL esperada:

```txt
http://localhost:5173/lumen/painel
```

## Comandos de validação previstos

```bash
# backend
pytest backend/tests
ruff check backend agent
mypy backend/app

# migrations
alembic -c backend/alembic.ini upgrade head
alembic -c backend/alembic.ini downgrade -1
alembic -c backend/alembic.ini upgrade head

# frontend
cd frontend
npm run lint
npm run typecheck
npm run test
npm run test:e2e
```

## Convenções de API

Prefixo sugerido:

```txt
/api/v1
```

Rotas de produto sugeridas:

```txt
GET /api/v1/lumen/companies?search=
GET /api/v1/lumen/periods
GET /api/v1/lumen/dashboard?period=2026-06
GET /api/v1/lumen/cockpit?period=2026-06&companyId=&status=&department=&source=
GET /api/v1/lumen/companies/{id}/summary?period=2026-06
GET /api/v1/lumen/deliveries?period=2026-06&companyId=
GET /api/v1/lumen/evidences?period=2026-06&companyId=
GET /api/v1/lumen/divergences?period=2026-06&companyId=
GET /api/v1/lumen/installments?period=2026-06&companyId=
GET /api/v1/lumen/integrations/health
```

Formato interno de competência:

```txt
YYYY-MM
```

Formato exibido no frontend:

```txt
MM/YYYY
```

## Convenções visuais obrigatórias

- Tema azul escuro SaaS, com apoio azul vivo e roxo.
- Fonte Inter.
- Sidebar desktop com 288px.
- Header sticky translúcido com blur.
- Dropdown global de empresa e competência.
- Context strip com empresa, CNPJ/IE, competência e regime.
- Cards com raio grande, sombras suaves e badges por status.
- Tabelas limpas com cabeçalho uppercase e hover azul claro.
- Não usar Bootstrap/Material UI padrão nem Tailwind sem mapear tokens.

## Como trabalhar com Codex

Para cada stage:

1. Abrir o stage no `PLANO_DESENVOLVIMENTO.md`.
2. Pedir ao Codex para implementar apenas aquele escopo.
3. Exigir testes automatizados e documentação mínima junto com o código.
4. Rodar validações locais.
5. Corrigir falhas antes de avançar.
6. Atualizar status do stage e registrar decisões em `docs/DECISOES.md`.

Modelo de pedido recomendado ao Codex:

```txt
Implemente somente o Stage S<n> do PLANO_DESENVOLVIMENTO.md.
Não avance para stages seguintes.
Mantenha compatibilidade com ESTRUTURA_REPO.md.
Adicione ou atualize testes.
Não crie automação de transmissão fiscal, não burle CAPTCHA e não versionar segredos.
Ao final, liste arquivos alterados, comandos de validação executados e pendências.
```
