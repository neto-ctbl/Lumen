# Acessorias API Contract for Lumen S6

Data de referencia: 2026-07-14

Fonte oficial exclusiva deste contrato:

- https://api.acessorias.com/documentation

Escopo deste documento:

- formalizar o contrato tecnico oficial necessario para implementar o S6.1
- limitar o uso do Acessorias a operacoes de consulta
- registrar campos, filtros, limites, lacunas e riscos sem criar codigo de integracao

Fora de escopo neste micro-stage:

- sync de producao
- endpoint manual de sincronizacao
- migration
- escrita em `fiscal_obligation_statuses`
- alteracao do regime exibido no portal
- download padrao de anexos
- qualquer `POST` de inclusao ou edicao no Acessorias

## Autenticacao

- Header obrigatorio: `Authorization: Bearer <token>`
- Base URL oficial: `https://api.acessorias.com`
- O token deve ser gerado no Sistema Acessorias pela opcao `API Token`
- O token deve ser armazenado apenas por variavel de ambiente ou referencia segura
- O token nao deve ser logado
- Headers e payloads sensiveis devem usar `mask_value()` ou `redact_mapping()` antes de logging
- Rate limit oficial: `100` requisicoes por minuto
- Erros a tratar no cliente futuro:
  - `401`: token ausente, invalido ou expirado
  - `403`: acesso negado para o recurso solicitado
  - `429`: limite de taxa atingido; o cliente futuro deve respeitar backoff
  - erros de transporte: timeout, DNS, conexao, proxy e resposta truncada

## Empresas

Endpoint oficial:

- `GET /companies/{identificador}`

Identificadores confirmados:

- CNPJ ou CPF
- `ListAll`

Parametros relevantes confirmados:

- `obligations`
- `departments`
- `stateRegistrations`
- `contacts`
- `registrationData`
- `ativa`
- `Pagina`

Regras documentadas:

- `obligations`, `departments`, `stateRegistrations`, `contacts` e `registrationData` sao flags de presenca e devem ser enviados sem valor
- parametros sem uso devem ser omitidos da URL
- `Pagina` padrao e `1`
- a consulta lista `20` registros por pagina
- a paginacao termina quando a pagina seguinte retorna lista vazia
- `ativa` aceita `S` ou `N`; sem filtro, a documentacao informa retorno legado de ativas e inativas

Campos de interesse para o Lumen confirmados na documentacao:

- `ID`
- `Identificador`
- `Razao`
- `Fantasia`
- `Status`
- `UF`
- `Regime`
- `InscricoesEstaduais[].IE`
- `InscricoesEstaduais[].UF`
- `Departamentos[].ID`
- `Departamentos[].Nome`
- `Departamentos[].RespNome`
- `Departamentos[].RespEmail`
- `ContatosNaEmpresa[].Nome`
- `ContatosNaEmpresa[].E-mail`
- `ContatosNaEmpresa[].Celular`
- `Obrigacoes[].Nome`
- `Obrigacoes[].Status`
- `Obrigacoes[].Entregues`
- `Obrigacoes[].Atrasadas`
- `Obrigacoes[].Proximos30D`
- `Obrigacoes[].Futuras30+`

Observacoes de contrato:

- a consulta de empresas pode retornar `Regime` como label textual
- o mapper futuro deve aceitar somente aliases explicitamente documentados e testados
- a documentacao tambem mostra um `POST /companies`, mas o S6 nao deve usa-lo

## Entregas

Endpoint oficial:

- `GET /deliveries/{identificador}`

Identificadores confirmados:

- CNPJ ou CPF
- `ListAll`

Parametros relevantes confirmados:

- `DtInitial`
- `DtFinal`
- `DtLastDH`
- `situation`
- `department_id`
- `Pagina`
- `attachments`
- `attachmentsId`
- `config`

Regras documentadas:

- `DtInitial` e `DtFinal` sao obrigatorios e usam `YYYY-MM-DD`
- `DtLastDH` usa `YYYY-MM-DD HH:MM:SS`
- se a hora nao for informada em `DtLastDH`, a API considera `00:00:00`
- quando o identificador for `ListAll`, `DtLastDH` torna-se obrigatorio
- com `ListAll`, `DtLastDH` aceita apenas o dia atual e/ou o dia anterior
- `situation` aceita um ou mais valores separados por virgula:
  - `pending`
  - `read`
  - `delivered`
- `department_id` aceita um ou mais IDs separados por virgula
- a consulta lista `50` registros por pagina
- a paginacao termina quando a pagina seguinte retorna lista vazia
- `attachments` retorna links temporarios com expiracao padrao de `60` minutos
- `attachments=S` pode gerar links com mais tempo de expiracao
- `attachmentsId` so funciona se `attachments` estiver ativo
- `config` retorna identificadores e responsaveis tecnicos da entrega
- se `config` receber uma ID de entrega, a API retorna apenas aquela entrega especifica

Campos de interesse para o Lumen confirmados na documentacao:

- empresa: `ID`, `Identificador`, `Razao`, `Fantasia`
- entrega: `Nome`
- competencia, quando retornada: `EntCompetencia`
- prazo: `EntDtPrazo`
- atraso: `EntDtAtraso`
- entrega: `EntDtEntrega`
- finalizacao: `EntDtFinalizacao`
- status: `Status`
- ultima alteracao: `EntLastDH`
- responsavel textual: `RespEntrega`
- flags auxiliares: `EntMulta`, `EntGuiaLida`
- configuracao tecnica:
  - `Config.EntID`
  - `Config.Tipo`
  - `Config.ID`
  - `Config.DptoID`
  - `Config.DptoNome`
  - `Config.CriadorID`
  - `Config.RespPrazo`
  - `Config.RespPrazoID`
  - `Config.RespEntrega`
  - `Config.RespEntregaID`

Diretriz para anexos:

- o S6 nao deve baixar anexos por padrao
- o contrato deve priorizar IDs e metadados, nao links temporarios
- links temporarios nao devem ser armazenados como evidencia permanente

## Regimes

Catalogo documentado pela API:

- `0` = `Indefinido`
- `1` = `Simples Nacional com inscricao estadual`
- `2` = `Simples Nacional sem inscricao estadual`
- `3` = `Lucro Presumido com inscricao estadual - industria/comercio`
- `4` = `Lucro Presumido sem inscricao estadual - servico`
- `5` = `Lucro Real`
- `6` = `MEI`
- `7` = `Domesticas/Caseiro - eSocial`
- `8` = `Produtor Rural`
- `9` = `Pessoa Fisica`
- `10` = `Imune/Isenta`

Proposta de mapping interno para os regimes atuais do Lumen:

- `1`, `2` -> `SIMPLES_NACIONAL`
- `3`, `4` -> `LUCRO_PRESUMIDO`
- `5` -> `LUCRO_REAL`
- `6` -> `MEI`
- `10` -> `IMUNE_ISENTA`

Valores explicitamente nao mapeados neste momento:

- `0`
- `7`
- `8`
- `9`

Regra de seguranca para o mapper:

- nao classificar valores desconhecidos por aproximacao
- se a API retornar label textual de regime, aceitar somente aliases documentados e cobertos por teste

## Status das entregas

Filtros tecnicos confirmados:

- `pending`
- `read`
- `delivered`

Labels textuais confirmados apenas como exemplos da documentacao:

- `Pendente`
- `Ent. antecipada`
- `Atrasada!`

Regras propostas para o S6.1:

- entrega com data valida em `EntDtFinalizacao` ou `EntDtEntrega` diferente de `0000-00-00` -> estado externo de entrega concluida
- pendente sem conclusao -> `PENDENTE`
- atrasada sem conclusao -> `PENDENTE`
- status textual desconhecido -> `CONFERENCIA_MANUAL` ou estado externo nao mapeado, conforme arquitetura fechada no S6.1

Estados explicitamente proibidos neste ponto:

- `CONFIRMADO_ARQUIVO`
- `CONFIRMADO_ARQUIVO_ACESSORIAS`

Esses estados dependem do watcher e da conciliacao futura, fora do escopo do S6.

## Obrigacoes: exemplos oficiais versus catalogo local

Catalogo local atual em `backend/scripts/seed_obligations.py`:

- `DAS`
- `DIFAL`
- `ICMS`
- `ISS`
- `PIS`
- `COFINS`
- `PROTEGE`
- `DCTFWEB`
- `REINF`
- `EFD_CONTRIBUICOES`
- `DEFIS`
- `DASN_SIMEI`
- `PARCELAMENTO`

Tabela inicial de comparacao baseada apenas em exemplos da documentacao oficial:

| Nome externo documentado | Codigo interno sugerido | Tipo do mapping | Confianca | Observacao |
| --- | --- | --- | --- | --- |
| `GPS` | nenhum ainda | ambiguo | baixa | pode representar guia previdenciaria, mas o catalogo local nao tem `GPS` como obrigacao propria |
| `INSS / GPS` | nenhum ainda | ambiguo | baixa | pode se relacionar a contexto previdenciario ou folha; exige decisao funcional futura |
| `Guia da Previdencia Social` | nenhum ainda | ambiguo | baixa | exemplo oficial insuficiente para mapear com seguranca |
| `Consulta do e-Social!` | nenhum ainda | obrigacao local ausente | media | parece tarefa ou consulta operacional, nao obrigacao fiscal atual do catalogo |
| `Analisar fluxo de caixa` | nenhum ainda | nao mapeado | alta | nao corresponde a obrigacao fiscal do Lumen |

Regra para o S6.1:

- entregas ou obrigacoes externas nao mapeadas nao devem ser descartadas
- devem ir para snapshot bruto e erro estruturado para revisao posterior
- este micro-stage nao cria novas obrigacoes locais

## Estrategia de sincronizacao proposta

### Fase 1: sincronizacao cadastral e de regime

- consultar empresas com `ListAll`
- solicitar `registrationData`
- percorrer paginas de `20` registros
- normalizar CNPJ ou CPF
- localizar `ExternalCompany` por `organization_id + cnpj`
- salvar snapshot bruto cadastral
- atualizar futuramente a fonte oficial de regime
- gerar alerta quando o regime oficial divergir de outra fonte disponivel

### Fase 2: sincronizacao de entregas

Alternativas documentadas:

1. Carga por empresa e intervalo de competencia
2. Sincronizacao incremental por `ListAll + DtLastDH`

Restricao tecnica confirmada:

- `ListAll + DtLastDH` so aceita o dia atual e/ou o dia anterior

Diretriz inicial:

- a primeira implementacao deve privilegiar seguranca e previsibilidade
- e aceitavel comecar por empresa + janela de competencia antes de otimizar para incremental global

## Decisao canonica de regime no schema atual

- o regime tributario atual oficial da empresa no Lumen e o `regime_canonical` do `acessorias_company_snapshots` vinculado a empresa local
- `external_companies` continua sendo espelho cadastral do eControle e nao recebe o regime canonico
- o schema atual nao possui tabela separada de perfil fiscal, nem historico legal de mudancas de regime
- o snapshot do Acessorias representa apenas o regime atual observado na fonte externa
- esse snapshot nao deve ser aplicado retroativamente a competencias antigas sem evidencia adicional

## Backfill operacional S6.2

- o S6.2 materializa um backfill reproduzivel sem alterar schema, sem migration e sem endpoint novo
- a fase cadastral executa uma unica sincronizacao de empresas para reconciliar CNPJ, atualizar `acessorias_company_snapshots`, mapear regime atual, gerar alertas de divergencia e registrar casos nao mapeados ou sem match
- a fase de entregas recebe `--from-period YYYY-MM` e `--to-period YYYY-MM` e processa cada competencia serialmente
- opcionalmente, a fase de entregas pode usar `--fiscal-only` para persistir apenas entregas operacionais pertinentes ao fiscal
- cada competencia precisa existir previamente em `fiscal_periods`; o backfill nao cria periodos implicitamente
- o processamento de entregas reutiliza o sync existente, preserva `Config.Tipo = T` apenas em snapshot e atualiza `fiscal_obligation_statuses` somente para obrigacoes mapeadas
- a rastreabilidade reutiliza `integration_sync_runs`, marcando `run_metadata.backfill = true` e registrando `from_period`, `to_period`, `current_period`, `company_id` e `dry_run`
- a retomada operacional depende de idempotencia; reiniciar o backfill desde o inicio nao deve duplicar snapshots nem statuses
- o fluxo continua restrito aos endpoints `GET /companies/{identificador}` e `GET /deliveries/{identificador}`
- `DtLastDH`, anexos, `POST` externos, transmissao fiscal e download de anexos continuam fora de escopo

## Idempotencia proposta

Chave preferida:

- `organization_id`
- `external_company_id` ou CNPJ normalizado
- `Config.EntID`

Fallback quando `Config.EntID` nao vier:

- `organization_id`
- `cnpj`
- `obrigacao externa`
- `data de prazo`
- `tipo`

Diretrizes:

- solicitar `config` sempre que possivel para maximizar a estabilidade da chave
- correcoes posteriores da mesma entrega devem atualizar o snapshot existente
- preservar payload bruto, ultima alteracao externa e data de sincronizacao
- manter metadados suficientes para auditoria

## Configuracao prevista para o S6.1

Variaveis futuras documentadas, ainda nao implementadas:

```dotenv
ACESSORIAS_API_BASE_URL=https://api.acessorias.com
ACESSORIAS_API_TOKEN=
ACESSORIAS_TIMEOUT_SECONDS=15
ACESSORIAS_REQUESTS_PER_MINUTE=100
```

## Seguranca

- nao logar o header `Authorization`
- aplicar `mask_value()` ou `redact_mapping()` em headers, params e estruturas de erro sensiveis
- nao armazenar links temporarios de anexos como evidencia permanente
- preferir IDs de anexos e metadados
- nao baixar anexos no sync padrao
- nao chamar endpoints de inclusao ou edicao no S6
- nao utilizar `POST /companies` ou qualquer outra mutacao externa no S6

## Campos ainda incertos ou propositalmente nao assumidos

- catalogo completo de labels textuais de status retornados em `Status`
- conjunto completo de aliases textuais de `Regime`
- payload completo de anexos quando `attachments` estiver ativo
- representacao de tarefas (`Tipo = T`) alem do exemplo documentado
- estabilidade semantica de nomes de obrigacao usados pela conta real do escritorio
- se a API retorna identificadores adicionais para obrigacoes recorrentes alem de `Config.ID`

## Materializacao S6.1 no repositorio

Estado implementado em 2026-07-14:

- cliente read-only em `backend/app/services/integrations/acessorias/client.py`
- mapper puro em `backend/app/services/integrations/acessorias/mapper.py`
- mapping de regime em `backend/app/services/integrations/acessorias/regime.py`
- mapping explicito de obrigacoes em `backend/app/services/integrations/acessorias/obligation_mapping.py`
- sync serial em `backend/app/services/integrations/acessorias/sync.py`
- endpoint manual `POST /api/v1/integrations/acessorias/sync`
- script `python -m backend.scripts.sync_acessorias_deliveries`
- snapshots `acessorias_company_snapshots` e `acessorias_delivery_snapshots`

Escolhas implementadas:

- o sync de empresas usa `ListAll + registrationData + ativa=S + Pagina`
- o sync inicial de entregas consulta por empresa local ativa e janela mensal, com `DtInitial`, `DtFinal`, `Pagina` e `config`
- `attachments`, `attachmentsId` e `DtLastDH` nao sao usados na primeira implementacao
- o status interno usa evidencia estrutural antes do label textual:
  - `EntDtFinalizacao` ou `EntDtEntrega` valida -> `CONFIRMADO_API`
  - sem conclusao/entrega -> `PENDENTE`
  - contradicao ou incerteza -> `CONFERENCIA_MANUAL`
- tarefas `Config.Tipo = T` ficam apenas em snapshot, sem criar `fiscal_obligation_statuses`
- obrigacoes desconhecidas permanecem em snapshot com `UNMAPPED` ou `AMBIGUOUS`, sem erro tecnico fatal do run
- o sync nao apaga `fiscal_obligation_statuses` quando uma entrega deixa de aparecer na API
- anexos continuam fora do escopo do S6.1

Complemento S6.2 em 2026-07-30:

- backfill retroativo operacional em `backend/app/services/integrations/acessorias/backfill.py`
- CLI dedicada em `python -m backend.scripts.backfill_acessorias`
- execucao em duas fases: cadastro/regime atual uma vez e entregas por intervalo de competencias
- nenhum schema novo, nenhuma migration nova, nenhuma alteracao de frontend

Complemento S6.2 em 2026-08-04:

- ampliacao dos aliases seguros de regime para labels reais do Acessorias como `Simples Nacional - Servicos`, `Lucro Presumido - Servicos`, `Lucro Real - Comercio e Industria` e `Filial - Simples Nacional`
- `Filial - Regime Normal` passa a herdar o regime canonico da mesma raiz de CNPJ quando houver um unico regime mapeado para a matriz ou empresa irma no mesmo grupo
- `EntGuiaLida` deixa de ser persistido cru; o sync normaliza labels longos como `Guia ja acessada/lida` para codigos curtos compativeis com o schema atual
- o backfill e o sync mensal passam a aceitar `--fiscal-only`, preservando o comportamento anterior por padrao
- com `--fiscal-only`, o snapshot de entregas persiste apenas itens `Tipo = O` que sejam obrigacoes mapeadas ou pertencam ao departamento fiscal; tarefas e itens nao pertinentes ficam fora do snapshot

Validacao operacional S6.2 concluida em 2026-08-03:

- backfill real executado com `status = SUCCESS` no intervalo `2026-01` a `2026-07`
- fase cadastral executada com `companies_received = 221`, `companies_matched = 218` e `companies_unmatched = 3`
- o backfill de regime atual tambem foi executado; o resumo do run registrou `regimes_mapped = 3` e `regimes_unmapped = 218`
- a conferencia SQL final de `acessorias_company_snapshots` mostrou `223` snapshots, `218` empresas vinculadas e `5` linhas com `regime_mapping_status = 'MAPPED'`
- fase de entregas executada com `deliveries_received = 10999`, `delivery_snapshots_created = 10999`, `statuses_created = 196` e `tasks_skipped = 328`
- a cobertura por competencia foi confirmada via SQL para `2026-01` a `2026-07`
- a consulta de duplicidades em `acessorias_delivery_snapshots` retornou `0` linhas

Validacao complementar S6.2 concluida em 2026-08-04:

- suite impactada do Acessorias executada com sucesso apos os refinamentos de regime filial, `EntGuiaLida` e `--fiscal-only`
- os cenarios de `Filial - Simples Nacional` e `Filial - Regime Normal` ficaram cobertos por teste automatizado
- o modo `--fiscal-only` ficou coberto em sync e backfill sem alterar o comportamento padrao quando a flag nao e informada

Aliases seguros de obrigacoes implementados no S6.1:

- `DAS` -> `DAS`
- `DIFAL` -> `DIFAL`
- `ICMS` -> `ICMS`
- `ISS` -> `ISS`
- `PIS` -> `PIS`
- `COFINS` -> `COFINS`
- `PROTEGE` -> `PROTEGE`
- `DCTFWEB` -> `DCTFWEB`
- `REINF`, `EFD REINF`, `EFD-REINF` -> `REINF`
- `EFD CONTRIBUICOES`, `EFD CONTRIBUIÇÕES` -> `EFD_CONTRIBUICOES`
- `DEFIS` -> `DEFIS`
- `DASN-SIMEI`, `DASN SIMEI` -> `DASN_SIMEI`
- `PARCELAMENTO` -> `PARCELAMENTO`

Mapeamentos explicitamente nao implementados:

- `GPS` -> nenhum mapping automatico
- qualquer obrigacao por fuzzy match
- qualquer `POST /companies` ou endpoint de mutacao
- download padrao de anexos
- sincronizacao incremental global por `ListAll + DtLastDH`
