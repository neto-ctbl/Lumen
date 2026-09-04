# Contrato do Watcher Fiscal

Status: S10.0 a S10.3 concluidos; S10.4 concluiu a fase 1 do piloto real e o macro-stage S10 permanece em andamento. O agent operacional usa polling e o endpoint de ingest/persistencia e o contrato S10.2; nao existe parser fiscal ou worker generico neste stage.

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

## Rollback do S10.1

Nao executar rollback sobre a sujeira preexistente. Para reverter somente S10.1 e preservar S10.0, restaure apenas os documentos e `agent/watcher/path_contract.py` alterados neste stage; remova somente `agent/parsers/`, os seis novos modulos do watcher e os testes S10.1. Nao usar `git reset --hard`, `git clean`, stash ou restauracao do repositorio inteiro.

## S10.1 Core offline

S10.1 materializa o core para um arquivo explicitamente fornecido: configuracao lazy, validacao lexical antes de acessar o arquivo, validacao fisica com rejeicao de symlink/reparse point, confirmacao do destino sob a root, SHA-256 streaming e comparacao de tamanho/mtime antes e depois do hash/probe. Alteracao durante processamento falha com `FILE_CHANGED_DURING_PROCESSING`; nao ha retry automatico.

O hint por filename nao le conteudo fiscal: uma keyword conhecida gera o hint, ausencia gera `UNKNOWN` e keywords independentes multiplas geram `AMBIGUOUS`. `PGFN + SISPAR` resulta em `PGFN_SISPAR`. O probe usa `pypdf`, retorna somente metadados e falha com seguranca para PDF invalido, vazio ou protegido; nao executa OCR.

DARF e uma familia documental. Classificacao de tributo e qualquer distincao entre periodo da pasta, referencia documental e periodo tributario ficam para S11; S10.1 usa somente `MM-AAAA -> AAAA-MM` da pasta.

## S10.2 Ingest backend

O agent futuro envia o payload v1 para `POST /api/v1/lumen/evidences/watcher-event` com `X-Lumen-Agent-Token`. O servidor exige token e org slug configurados, compara o token em constant-time e deriva a organizacao apenas do slug; JWT humano e campos de tenant no payload nao substituem esta autenticacao.

O backend revalida a gramatica relativa sem acessar filesystem, recalcula `normalized_relative_path` e fingerprint, persiste `watcher_file_event` por chave unica e cria no maximo uma evidence `WATCHER_FILE` vinculada quando empresa e periodo forem resolvidos. Eventos unmatched, ambiguous ou sem periodo continuam persistidos, sem evidence. O backend nao abre PDF, nao recebe binario, nao processa XML e nao executa parser/worker.

`classifier_hint` e sinal auxiliar originado do filename e permanece somente no payload/metadado seguro do watcher event. Ele nunca e classificacao fiscal canonica: a evidence `WATCHER_FILE` nova inicia com `detected_tax = NULL` e `detected_obligation = NULL`. A regra para S11 e `PARSER DE CONTEUDO > NOME DO ARQUIVO > CONTEXTO AUXILIAR`: parser conclusivo prevalece sobre filename conflitante; filename conclusivo sem parser e somente candidato de baixa confianca; ausencia de ambos exige conferencia manual. S10.2 nao implementa essa reconciliacao.

Exemplo local seguro (nao versionar payload real ou segredo):

```bash
curl -X POST http://localhost:8000/api/v1/lumen/evidences/watcher-event \
  -H "Content-Type: application/json" \
  -H "X-Lumen-Agent-Token: <LOCAL_SECRET>" \
  --data @watcher-event-local.json
```

## Rollback do S10.2

Nao executar automaticamente. Para preservar S10.0/S10.1 e reverter somente este stage, primeiro execute `python -m alembic -c backend/alembic.ini downgrade -1`; depois restaure somente os arquivos versionados do S10.2 e remova somente `backend/app/schemas/watcher.py`, `backend/app/services/watcher_ingest.py`, `backend/alembic/versions/20260831_0015_add_watcher_ingest_idempotency.py` e `backend/tests/test_watcher_ingest.py`. Nao usar reset hard, clean, stash ou restauracao global.

## S10.3 Agent Windows por polling

O mecanismo operacional primario e polling incremental, sem dependencia de notificacoes SMB. O scanner aceita somente PDFs sob a gramatica fiscal allowlisted, ignora temporarios, XML/ZIP e areas fora de `Escrita Fiscal`. O primeiro boot faz inventario/baseline local e nunca envia o historico encontrado; state ausente ou corrompido tambem resulta em baseline sem flood.

O state JSON local e atomico e guarda somente path relativo normalizado, tamanho, mtime, hash, entrega e retry. Nao guarda token, headers, PDF, texto, CNPJ ou resultado de parser. A estabilidade exige tamanho e mtime inalterados pelo intervalo configurado; o builder S10.1 ainda confirma a imutabilidade antes/depois do hash/probe. `FILE_CHANGED_DURING_PROCESSING` retorna o arquivo a observacao.

O client usa somente `X-Lumen-Agent-Token` e metadata v1. `2xx` confirma a entrega local; `400/422` marca a versao do arquivo como rejeitada ate mudanca material; autenticacao, indisponibilidade, `5xx` e rede usam backoff persistente limitado a cinco minutos. `--once` nao ignora baseline ou estabilidade e `--status` le apenas health sanitizado. Nao ha piloto real em `G:\EMPRESAS`, service/task automatico, parser fiscal, OCR ou XML neste stage.

`health.status` representa exclusivamente o lifecycle do processo: `STARTING` antes do primeiro ciclo, `RUNNING` ou `DEGRADED` enquanto o processo continuo esta vivo e `STOPPED` depois de `--once`, Ctrl+C ou encerramento limpo. `STOPPED` preserva diagnostico e timestamps da ultima execucao, inclusive `last_error_code`; resultado historico nao muda de significado ao encerrar o processo. Excecao fatal nao e mascarada como `STOPPED` saudavel: o health fica `DEGRADED` com codigo sanitizado.

No encerramento normal, o agent primeiro persiste health local `STOPPED` e depois tenta uma unica transmissao M2M do heartbeat `STOPPED`. A transmissao e best-effort: falha de rede ou backend nao bloqueia a saida, nao cria retry de shutdown e deixa o backend elegivel a `STALE` ate o proximo heartbeat.

## Piloto real fase 1

Em 2026-09-04, um baseline controlado na root oficial encontrou `1385` candidatos e gravou somente state local. Nenhum `watcher_file_event` ou `fiscal_evidence` foi criado. Em um segundo `--once`, sem arquivos novos, o backend recebeu o heartbeat final `STOPPED`. Token, nomes de arquivos e caminhos individuais nao foram registrados nesta documentacao.
