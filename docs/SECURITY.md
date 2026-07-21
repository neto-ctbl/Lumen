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
