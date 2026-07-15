# Decisoes Tecnicas do Lumen

Data de referencia: 2026-07-15

## S7.0 - Sittax observado

- Sittax sera tratado como integracao baseada em endpoints observados do portal web, nao como API publica oficial documentada.
- A integracao Sittax permanecera estritamente read-only.
- A chamada `GET /api/apuracao/retornar-apuracao-sittax?empresaCnpj=...&periodo=...` e o setter oficial do contexto ativo da sessao.
- O contexto ativo da sessao persiste por `empresaCnpj` e `periodo` ate nova chamada de apuracao substituir um ou ambos.
- Endpoints contextuais como DIFAL, painel da empresa e notas fiscais devem ser consultados somente depois da apuracao definir o contexto.
- A primeira versao do conector Sittax deve executar em modo serial por sessao, com sessao exclusiva por empresa/competencia.
- Nao e permitido compartilhar a mesma sessao simultaneamente entre empresas ou competencias diferentes.
- `recalcular=true` e proibido.
- Endpoints de transmissao, fechamento, upload, inclusao, exclusao ou qualquer mutacao externa ficam fora de escopo.
- O health futuro do Sittax deve usar apenas estado local, sem login externo por request do frontend.
- Fixtures de teste do Sittax devem ser integralmente anonimizadas e sinteticas.
- O log bruto `sittax-network-log.jsonl` e somente fonte temporaria de analise e deve permanecer fora do Git.
- O endpoint `POST /api/v2/painel-contador/transmissao` foi classificado como ambiguo e adiado.
- O micro-stage S7.0 e documental e de seguranca; ele nao cria cliente HTTP real, login real, models, migrations ou sync.

## S7.1 - Fundacao tecnica do cliente Sittax

- O cliente Sittax do S7.1 permanece estritamente read-only e limitado a login e listagem de empresas.
- A sessao Sittax nasce stateful e exclusiva, com um unico `httpx.Client` por instancia.
- O JWT do Sittax existe somente em memoria na sessao ativa.
- A senha do Sittax so e usada para montar o body de login no momento da chamada.
- O cliente Sittax nao usa `httpx.Client` global, singleton global ou token global.
- A sessao local usa exclusao mutua por instancia via `session.exclusive()`.
- A mesma sessao nao pode ser usada simultaneamente por threads diferentes.
- `active_company_cnpj` e `active_period` existem apenas como placeholders nulos para compatibilidade com o contexto futuro.
- O S7.1 nao define contexto por apuracao e nao simula contexto ativo.
- O escritorio ativo deve ser resolvido deterministicamente a partir do payload observado de login.
- O fixture mode do Sittax reutiliza os mesmos mappers do cliente real e nao acessa rede.
- O script `check_sittax_connection` valida apenas login e listagem de empresas, sem persistencia e sem PII.
