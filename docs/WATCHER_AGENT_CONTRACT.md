# Contrato do Watcher Fiscal

Status: S10.0 concluído como contrato offline. Não existe watcher operacional, endpoint de ingest, persistência ou worker genérico neste stage.

## Identidade e autenticação futura

O watcher é um processo de máquina, não um usuário humano. O futuro ingest usará somente `X-Lumen-Agent-Token: <secret>` com credencial dedicada, configurada localmente por `LUMEN_WATCHER_AGENT_TOKEN`, `LUMEN_WATCHER_AGENT_ORG_SLUG` e `LUMEN_WATCHER_ROOT`.

O token nunca é versionado ou logado, será comparado em constant-time, falhará fechado se não estiver configurado e será associado no servidor a uma única organização. O payload não escolhe `organization_id`; a rotação troca apenas a configuração local. Não usar JWT, email ou senha de `ADMIN`, `DEV` ou `VIEW`.

## Path grammar e segurança

A única root inicial é `G:\EMPRESAS`. O caminho aceito deve ser descendente dela e seguir o padrão predominante `G:\EMPRESAS\[empresa]\Escrita Fiscal\[MM-AAAA]\Guias - Impostos e Parcelamentos`.

O agente normalizará separadores, removerá segmentos redundantes, comparará case-insensitivamente, obterá o path relativo à root e rejeitará qualquer escape. A identidade usa o relative path normalizado, por exemplo `empresa exemplo\escrita fiscal\07-2026\guias - impostos e parcelamentos\das 07-2026.pdf`; a letra do drive não integra a identidade principal. UNC fora da allowlist, traversal e reparse points/symlinks que escapem da root serão rejeitados. `.partial`, `.tmp`, `.crdownload` e nomes iniciados por `~$` são temporários e serão ignorados.

Inicialmente, somente `.pdf` é elegível. Extensões futuras exigem contrato e testes explícitos. A pasta usa `MM-AAAA`, convertido diretamente para `AAAA-MM`: `07-2026 -> 2026-07`. A conversão Domínio Folha `M -> M+1` não se aplica ao watcher fiscal.

## Empresa, evento e payload

A resolução futura de empresa é estrita, sempre na organização autenticada: `apelido_pasta`, `nome_fantasia`, depois `razao_social`, todos por igualdade normalizada e apenas com um único ativo. Sem resultado é `UNMATCHED`; mais de um é `AMBIGUOUS`. Não usar contains, prefixo, similaridade, Levenshtein, primeiro resultado ou CNPJ ausente do path.

A fingerprint lógica é `sha256(organization_id + "\n" + normalized_relative_path + "\n" + file_sha256)`. `event_type` fica fora dela: mesmo path e hash é o mesmo evento lógico; hash novo ou path novo cria evento novo.

O payload v1 é definido em `schemas/watcher_event.schema.json`. Ele contém somente metadados e `pdf_probe` diagnóstico (`is_pdf`, páginas, texto extraível e tamanho aproximado). Não contém PDF, base64, XML, texto integral, token, cookie, senha, `Authorization`, `organization_id`, `company_id` ou `period_id`. `folder_company` e `folder_period` são sinais; o backend decide organização, empresa, período, status, evidência e confiança final.

## Direção para S10.2

S10.2 proporá `watcher_file_event 1 -> 0..1 fiscal_evidence`, provavelmente por `fiscal_evidences.watcher_event_id` nullable, FK e unicidade adequada. Evidências Domínio existentes permanecem inalteradas; não haverá constraint genérica por `file_hash` em `fiscal_evidences`.

## Rollback do S10.0

Não executar rollback sobre a sujeira preexistente. Para reverter somente este micro-stage, use `git restore --` nos arquivos versionados alterados e remova somente os arquivos novos: `agent/`, `docs/WATCHER_AGENT_CONTRACT.md`, `schemas/watcher_event.schema.json`, `backend/tests/test_watcher_contract.py` e `backend/tests/fixtures/watcher/`. Não usar `git reset --hard`, `git clean`, stash ou restauração do repositório inteiro.
