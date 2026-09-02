# Security do Lumen

Data de referencia: 2026-07-15

## Regras gerais

- Credenciais devem existir somente em `.env` local ou fonte segura equivalente fora do Git.
- Senha do Sittax nunca deve ser persistida em banco, snapshot, fixture ou log.
- JWT do Sittax deve existir somente em memoria durante a execucao futura; ele nao deve ser persistido em snapshots.
- No S7.1, o JWT do Sittax existe somente na instancia de `SittaxSession` e so durante a execucao do processo.
- No S7.2, `raw_payload` da empresa Sittax fica somente em `sittax_company_snapshots`; `integration_sync_runs` nao devem armazenar payload bruto, lista de empresas ou CNPJs completos.
- Headers completos nao devem ser logados.
- Qualquer log de erro com dados externos deve usar `mask_value()` e `redact_mapping()`.
- Logs de rede brutos do navegador, como `sittax-network-log.jsonl`, sao proibidos no Git.
- O body de login do Sittax nao pode ser logado nem reaproveitado em excecoes.

## Fixtures e testes

- Fixtures do Sittax devem usar apenas dados sinteticos e anonimizados.
- Fixtures nao podem conter tokens, JWTs, senhas, cookies, `Authorization`, `connectionToken` ou `apiKeyAcessorias`.
- Testes do Sittax devem rodar em fixture mode.
- E2E nao devem depender de credenciais reais nem de chamada externa nova.
- O script de conectividade do Sittax so pode exibir contagem de empresas e identificador mascarado do escritorio.
- O script `sync_sittax_companies` deve emitir apenas JSON seguro com contadores e erros sanitizados.
- O script `sync_sittax_apuracoes` deve emitir apenas JSON seguro com contadores e erros sanitizados.
- O modo `--diagnostic-contract` do Sittax so pode exibir host, status HTTP, tipo do JSON, nomes de chaves, flags de sucesso, mensagem sanitizada, nomes de cookies e estado booleano de contexto.
- O diagnostico do handoff entre hosts nao pode imprimir body bruto, token, `Authorization`, cookie values, CNPJ completo, documento fiscal, valor fiscal ou payload integral.

## Escopo permitido

- Somente leitura no Sittax.
- Proibido chamar transmissao, recalculo, fechamento, upload, inclusao, exclusao ou edicao.
- `recalcular=true` e proibido.
- O health futuro do Sittax deve refletir apenas estado local, sem login ou consulta externa por request.
- O S7.2 cria snapshot e script operacional, mas continua sem apuracao, sem contexto ativo, sem endpoint de frontend e sem integracao operacional no health.
- O S7.3 cria snapshot read-only de apuracao e script operacional proprio, preservando `raw_payload` apenas em `sittax_apuracao_snapshots` e mantendo `integration_sync_runs` livres de payload bruto e valores fiscais.
- O S7.4 mantem o health estritamente local e trata o handoff de contexto entre hosts como validacao operacional, nunca como consulta disparada pelo frontend.

## Regras adicionais da Econet

- HAR, JSONL e snapshots de storage da Econet sao proibidos no Git.
- Cookies da Econet nao podem ser logados.
- CAPTCHA da Econet nao pode ser automatizado.
- A sessao futura da Econet deve preferir armazenamento apenas em memoria.
- Cookies da Econet nao podem ser persistidos em `integration_sync_runs`.
- Nenhum token da Econet deve ser salvo no banco no MVP.
- Redaction e obrigatoria em qualquer diagnostico da Econet.
- Fixtures da Econet nao podem conter PII, CNPJ real ou dado operacional.
- O parser da Econet no S8.1 nunca recebe cookie, token ou sessao como entrada.
- O cache `econet_cnae_cache` nao guarda HTML bruto, cookie, token, header nem URL com parametro sensivel.
- O `normalized_payload` da Econet contem apenas campos semanticos normalizados e hashes.
- Erros do parser da Econet nao devem incluir HTML integral nem trechos suficientes para reconstruir credencial ou sessao.
- Futuras sessoes assistidas da Econet continuam fora do S8.1 e devem permanecer isoladas da persistencia do cache.
- No S8.2, o body de importacao da sessao da Econet nao deve ser logado.
- Os cookies de importacao da Econet usam `repr=False` nos schemas publicos.
- O arquivo `backend/storage/sessions/econet/manual-storage-state.json` e sensivel, temporario e ignorado pelo Git.
- A exclusao do arquivo temporario da Econet continua manual e operacional, nunca automatica pelo backend.
- O probe da Econet nao retorna HTML e nao deve expor cookies, headers completos ou valores de sessao.

## S8.3

- XML fiscal real continua fora de fixtures e fora do endpoint.
- Scans brutos da Econet continuam fora do Git.
- Tokens de storage, cookies e HTML bruto nao sao copiados para codigo, fixture ou resposta.
- Endpoints read-only de catalogo e Fator R potencial nao chamam rede.
- Erros de decoding da Econet nao retornam HTML, bytes, cookies, headers completos nem payload bruto.
- O client da Econet usa `response.content` e decode centralizado; `errors="replace"` permanece proibido.
- Cookies e arquivo temporario de sessao continuam apenas em memoria ou em artefato operacional ignorado pelo Git.

## S9.0

- O coletor Dominio deve ler primeiro o `.env` central da raiz do Lumen; `scripts/collectors/dominio/.env` permanece apenas como fallback local opcional.
- `DOMINIO_PASSWORD` nunca pode ser persistida em log, manifest, fixture ou documentacao.
- O manifest do Dominio nao pode conter senha, token, CNPJ, nome de empresa ou texto integral do PDF.
- PDFs reais do Dominio e logs reais do coletor permanecem fora do Git.
- O coletor deve validar o PDF antes da troca atomica e remover apenas o `.partial.pdf` em caso de falha.
- O lock local do coletor nao pode matar automaticamente outro processo; ele apenas bloqueia a nova execucao com mensagem clara.
- Fixtures do Dominio devem ser 100% sinteticas e sem nomes empresariais reais.

## S9.2

- O importador do Dominio nao deve abrir nem imprimir `.env`.
- A CLI do Dominio nao deve imprimir CNPJ, nome de empresa, `raw_text` ou rubricas individuais.
- `fiscal_evidences`, `integration_sync_runs` e `audit_log` do Dominio devem conter apenas agregados seguros.
- O banco nao deve receber PDF bruto, base64 ou blob do arquivo de folha.
- O `raw_text` persistido fica restrito a `dominio_payroll_company_movements` e nao pode aparecer em logs ou erros serializados.
- O `source_file_path` persistido deve ser opcional e interno; a CLI publica so exibe hash e contadores.
- `--dry-run` nao grava import, movimento, periodo, evidencia, sync run nem auditoria.
- Relatorios reais do Dominio devem permanecer fora do indice do Git, com `scripts/collectors/dominio/Relatorios_Dominio/` protegido por `.gitignore`.
- O fechamento do S9.2 registra separadamente o risco de historico antigo com PDFs reais no commit `6060711`; a limpeza historica do Git fica fora deste stage.
- O universo `FACTOR_R` pode gerar apenas CSV e resumo JSON sem nomes, CNPJs ou lista identificavel no manifest lateral.

## S9.3

- `dctfweb_origin_assessments`, alertas e auditoria do S9.3 armazenam apenas agregados, codigos estruturados e IDs tecnicos; nao armazenam CNPJ, nome, raw payroll text ou rubricas completas.
- A CLI de reconciliacao imprime apenas contadores agregados, inclusive contagens de sinais REINF/MIT e em `--dry-run`.
- O alerta de relatorio mensal Dominio ausente e agregado por organizacao/periodo com `company_id = null`, evitando multiplicar dados operacionais por empresa quando a falha e da fonte mensal.
- O S9.3 nao abre PDF, `.env`, manifest lateral ou portal externo.
- A auditoria de S9.3 consulta apenas agregados por codigo e competencia; nao imprime payload fiscal, CNPJ, nome ou identificador de empresa.

## S9.4

- A CLI `reconcile_factor_r.py` emite somente agregados; nao imprime empresa, CNPJ, valores monetarios, rubricas, raw payroll ou payload Sittax.
- O assessment guarda breakdowns sem identificadores pessoais e snapshots sanitizados de presenca/origem, nunca payload Sittax bruto adicional.
- `--dry-run` nao escreve assessments, alertas, auditoria, periodos ou fontes Domínio/Sittax/Econet.

## S9.5-BE

- As respostas de Domínio nao retornam `raw_text`, descricao de rubrica, PDF, manifest, caminho local ou hash do arquivo.
- As respostas de Fator R nao retornam `source_summary`, `fingerprint`, payload Sittax bruto, cookies, tokens, headers ou credenciais.
- Toda consulta aplica `organization_id` do contexto autenticado; recurso de outro tenant retorna 404.
- `VIEW` pode apenas consultar; POSTs de reconcile exigem `ADMIN` ou `DEV` e continuam estritamente locais.

## S9.5 Watcher Domínio

- O lock/PID contém somente PID, slug da organização, diretório canônico e instante de início; não contém PII, credenciais, hashes ou dados de folha.
- O watcher usa dados agregados, não move ou apaga PDFs e mantém relatórios reais fora do Git.
- A Company Page mostra somente cobertura, competências, sinais agregados, status e confidence; não mostra `raw_text`, rubricas individuais, identificadores pessoais, paths ou arquivos de folha.
- Os fixtures E2E de DCTFWeb, Fator R e Domínio são integralmente sintéticos.

## S10.0 Watcher fiscal: contrato de segurança

- A root allowlisted inicial é `G:\EMPRESAS`; somente descendentes podem ser elegíveis. Traversal, UNC fora da allowlist e reparse points/symlinks que escapem dela serão rejeitados.
- Paths Windows são normalizados e comparados case-insensitivamente. Arquivos `.partial`, `.tmp`, `.crdownload` e nomes `~$*` serão ignorados como não finalizados.
- O futuro token dedicado de agent nunca é versionado ou logado; deve ser redigido, comparado em constant-time e falhar fechado quando ausente.
- O payload não pode carregar PDF bruto, base64, XML, texto integral, cookie, senha, `Authorization` ou token. Arquivos fiscais reais permanecem fora do Git.
- S10.0 não fez transmissão externa, não abriu `G:\EMPRESAS` em testes e não criou endpoint ou agente operacional.
- S10.1 valida primeiro a gramatica lexical e, para arquivo existente explicitamente fornecido, rejeita symlink/reparse point e confirma o destino resolvido sob a root. Hash/probe sao cercados por checagem de tamanho/mtime para nao aceitar arquivo alterado durante processamento.
- S10.2 recebe apenas metadata pelo header `X-Lumen-Agent-Token`; token e org slug ausentes deixam o endpoint indisponivel, token ausente/invalido recebe resposta generica e a comparacao usa constant-time. Nenhum token, PDF, raw text ou campo de tenant e persistido/retornado.
- O backend revalida path puramente em memoria e nao abre `G:\EMPRESAS`, PDF, XML ou qualquer arquivo durante ingest. O payload e fechado contra campos extras e a evidencia inicial nao confirma obrigacao fiscal.
- S10.3 mantem token apenas em env/memoria e nunca escreve token, headers, payload, paths, nomes de empresa, hashes completos, PDF ou texto em state, health ou logs padrao. `agent/.state/`, `agent/logs/` e env local do agent ficam fora do Git.
- O agent rejeita URL HTTP remota; HTTP e permitido somente para `localhost`/loopback em desenvolvimento. Ele envia exclusivamente metadata v1 por `X-Lumen-Agent-Token`, sem JWT humano, org slug ou IDs de tenant.
- Polling opera somente sob a root allowlisted e reutiliza validacao fisica contra traversal/reparse point. O primeiro boot nao transmite historico e S10.3 nao executa piloto em `G:\EMPRESAS`, OCR, XML/NFS-e ou parser fiscal.
