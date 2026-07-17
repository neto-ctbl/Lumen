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

## Escopo permitido

- Somente leitura no Sittax.
- Proibido chamar transmissao, recalculo, fechamento, upload, inclusao, exclusao ou edicao.
- `recalcular=true` e proibido.
- O health futuro do Sittax deve refletir apenas estado local, sem login ou consulta externa por request.
- O S7.2 cria snapshot e script operacional, mas continua sem apuracao, sem contexto ativo, sem endpoint de frontend e sem integracao operacional no health.
- O S7.3 cria snapshot read-only de apuracao e script operacional proprio, preservando `raw_payload` apenas em `sittax_apuracao_snapshots` e mantendo `integration_sync_runs` livres de payload bruto e valores fiscais.
