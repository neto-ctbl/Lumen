# Security do Lumen

Data de referencia: 2026-07-15

## Regras gerais

- Credenciais devem existir somente em `.env` local ou fonte segura equivalente fora do Git.
- Senha do Sittax nunca deve ser persistida em banco, snapshot, fixture ou log.
- JWT do Sittax deve existir somente em memoria durante a execucao futura; ele nao deve ser persistido em snapshots.
- Headers completos nao devem ser logados.
- Qualquer log de erro com dados externos deve usar `mask_value()` e `redact_mapping()`.
- Logs de rede brutos do navegador, como `sittax-network-log.jsonl`, sao proibidos no Git.

## Fixtures e testes

- Fixtures do Sittax devem usar apenas dados sinteticos e anonimizados.
- Fixtures nao podem conter tokens, JWTs, senhas, cookies, `Authorization`, `connectionToken` ou `apiKeyAcessorias`.
- Testes do Sittax devem rodar em fixture mode.
- E2E nao devem depender de credenciais reais nem de chamada externa nova.

## Escopo permitido

- Somente leitura no Sittax.
- Proibido chamar transmissao, recalculo, fechamento, upload, inclusao, exclusao ou edicao.
- `recalcular=true` e proibido.
- O health futuro do Sittax deve refletir apenas estado local, sem login ou consulta externa por request.
