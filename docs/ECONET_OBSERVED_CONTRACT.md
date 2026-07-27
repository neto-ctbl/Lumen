# Contrato Observado da Econet

Data de referencia: 2026-07-21

Este documento formaliza apenas o contrato HTML observado localmente na ferramenta de consulta por CNAE da Econet. Ele nao representa API oficial publicada pela Econet e nao autoriza automacao de login, CAPTCHA ou consulta externa fora das regras internas do projeto.

## Base observada

- Base observada: `https://www.econeteditora.com.br`
- Ferramenta: `/ferramentas/regimes_cnae/`
- Formato das respostas relevantes: `HTML`

## Confirmado pelos scans

### Busca de CNAE

Endpoint confirmado:

```text
GET /ferramentas/regimes_cnae/buscaCnae.php?busca={termo}
```

Fatos confirmados:

- o termo de busca pode ser parcial;
- a resposta relevante e HTML;
- a resposta inclui CNAE e descricao;
- a resposta expoe um identificador interno da Econet em `idcnae`;
- `econet_id_cnae` nao deve ser calculado a partir do CNAE;
- o cliente futuro precisara resolver e armazenar esse identificador retornado.

### Abertura do CNAE

Endpoint confirmado:

```text
GET /ferramentas/regimes_cnae/index.php?idcnae={econet_id_cnae}&acao=abrir
```

Fatos confirmados:

- o identificador interno e o CNAE normalizado sao identidades distintas;
- a abertura do detalhe leva a um HTML com contexto da consulta por CNAE;
- a tela aberta serve como ponto de partida para abas e subabas tributarias e de obrigacoes.

Exemplo sintetico:

```text
cnae_normalizado = 0000000
econet_id_cnae = 999999
```

### Abas tributarias observadas

Endpoints confirmados:

```text
GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroPresumido&idCnae={id}
GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroRealTrimestral&idCnae={id}
GET /ferramentas/regimes_cnae/subAbas.php?aba=lucroRealEstimativa&idCnae={id}
GET /ferramentas/regimes_cnae/subAbas.php?aba=simplesNacionalTributacao&idCnae={id}
GET /ferramentas/regimes_cnae/subAbas.php?aba=empreendedorIndividual&idCnae={id}
```

Tipos de informacao observados:

- possibilidade indicativa de Lucro Presumido;
- obrigatoriedade indicativa de Lucro Real;
- observacoes tributarias textuais;
- permissao ou impedimento ao Simples Nacional;
- anexo do Simples, quando exposto no HTML;
- permissao ou impedimento ao MEI;
- fundamentacao textual.

### Obrigacoes acessorias observadas

Endpoint confirmado:

```text
GET /ferramentas/regimes_cnae/abas.php?aba=obrigacoes&idCnae={id}
```

Grupos observados na resposta:

- `PJ em Geral`
- `Optante Simples Nacional`
- `Optante SIMEI`

Subabas confirmadas:

```text
GET /ferramentas/regimes_cnae/subAbas.php?aba=pjGeral&idCnae={id}
GET /ferramentas/regimes_cnae/subAbas.php?aba=optanteSimplesNacional&idCnae={id}
GET /ferramentas/regimes_cnae/subAbas.php?aba=optanteSimei&idCnae={id}
```

Tipos de resposta efetivamente observados:

1. lista HTML de obrigacoes indicativas;
2. mensagem de atividade impedida ao Simples;
3. mensagem de CNAE nao permitido ao SIMEI;
4. linhas com detalhe oculto ou vazio.

Regras documentais obrigatorias:

- obrigacoes da Econet sao indicativas;
- obrigatoriedade final depende de regime, atividade e outras condicoes;
- a Econet nao cria diretamente status `PENDENTE`;
- a Econet nao define obrigacao como definitivamente exigivel;
- a Econet nao substitui o Acessorias como fonte oficial de regime e entregas;
- hifen ou coluna vazia nao significa dispensa;
- mensagem de regime impedido e resultado de negocio valido, nao erro de parser.

### Sessao observada

Observacoes de alto nivel:

- as consultas ocorreram dentro de sessao web previamente autenticada;
- as chamadas observadas reutilizaram cookies;
- nao foi observado `Authorization: Bearer` nas chamadas da ferramenta;
- `localStorage` nao mudou durante as consultas analisadas;
- login continua manual;
- CAPTCHA nao pode ser automatizado;
- cookies e tokens nunca serao versionados;
- o MVP futuro deve preferir sessao apenas em memoria.

## Inferido

- a sequencia funcional do frontend usa `buscaCnae.php` para resolver o identificador interno e depois abre `index.php?idcnae=...&acao=abrir`;
- `abas.php` atua como carregador de grupos principais e `subAbas.php` como carregador de conteudo especifico por regime ou grupo;
- o contrato util para o Lumen e predominantemente de HTML parcial, nao de JSON.

## Ainda nao confirmado

- estabilidade do mesmo conjunto de abas para todos os CNAEs;
- existencia de contrato oficial, versionado e publico em JSON;
- comportamento completo de expiracao de sessao;
- mapeamento universal entre texto observado e decisao fiscal automatica.

## Fora do escopo

- automacao de login;
- automacao ou bypass de CAPTCHA;
- persistencia de sessao;
- parser produtivo;
- cache produtivo;
- sync funcional;
- endpoint funcional de integracao;
- qualquer mutacao fiscal ou decisao automatica por empresa.

## Contrato interno normalizado do S8.1

O S8.1 nao cria cliente HTTP nem consulta externa. Ele cria um contrato interno de normalizacao para persistir somente o resultado semantico derivado de HTML local:

```json
{
  "contract_version": "s8.1",
  "parser_version": "econet-html-v2",
  "cnae": {
    "normalized": "0000000",
    "formatted": "0000-0/00",
    "description": "ATIVIDADE SINTETICA PARA TESTE",
    "econet_id_cnae": "999999"
  },
  "activity_types": [],
  "simples": {
    "status": "ALLOWED",
    "allowed": true,
    "annex_default": "III",
    "annex_conditional": null,
    "factor_r_applicable": null,
    "factor_r_threshold": null,
    "factor_r_status": "NOT_OBSERVED"
  },
  "mei": {
    "status": "ALLOWED",
    "allowed": true,
    "occupation": "OCUPACAO SINTETICA"
  },
  "presumed_profit": {
    "status": "ALLOWED",
    "allowed": true,
    "irpj_rate": "8",
    "csll_rate": "12"
  },
  "actual_profit": {
    "status": "MANDATORY|NOT_MANDATORY|ALLOWED|UNKNOWN|NOT_OBSERVED",
    "mandatory": true
  },
  "obligations": {
    "general": {},
    "simples": {},
    "simei": {}
  },
  "unmapped_obligations": [
    "DIRBI",
    "DME",
    "ECD",
    "ECF",
    "e-Social"
  ]
}
```

Campos efetivamente persistidos no cache:

- `cnae`
- `cnae_formatted`
- `description`
- `econet_id_cnae`
- `activity_types`
- `simples_*`
- `mei_*`
- `presumed_profit_*`
- `actual_profit_*`
- `obligations_general`
- `obligations_simples`
- `obligations_simei`
- `unmapped_obligations`
- `normalized_payload`
- `parse_status`
- `parser_version`
- `content_hash`
- `retrieved_at`
- `expires_at`

## Estados semanticos do S8.1

Os estados semanticos centralizados em `backend/app/core/enums.py` e usados pelo parser/cache sao:

- `ALLOWED`
- `PROHIBITED`
- `NOT_ALLOWED`
- `NOT_MANDATORY`
- `MANDATORY`
- `PARSED`
- `NOT_OBSERVED`
- `UNKNOWN`
- `PARSE_ERROR`
- `REGIME_PROHIBITED`
- `REGIME_NOT_ALLOWED`
- `EMPTY`

Regras de interpretacao documentadas:

- mensagem negativa de Simples e resultado valido de negocio: `PROHIBITED`
- mensagem negativa de SIMEI e resultado valido de negocio: `NOT_ALLOWED` ou `REGIME_NOT_ALLOWED`
- ausencia de evidencia de Fator R continua `NOT_OBSERVED`
- tabela vazia de obrigacoes continua `EMPTY`, nao erro tecnico

## Hashes, parser version e limites

- `parser_version = "1"` no S8.1
- `parser_version = "econet-html-v2"` no complemento corretivo do S8.3
- `contract_version = "s8.1"` no payload normalizado
- `content_hash` usa `SHA-256` sobre JSON canonico com chaves ordenadas
- timestamps nao entram no hash
- espacos, ordem arbitraria de dicionarios e detalhes decorativos de HTML nao entram no hash

Limitacoes explicitas do payload normalizado:

- nao guarda HTML bruto
- nao guarda cookies
- nao guarda token
- nao guarda headers
- nao guarda URL completa com parametros sensiveis
- nao guarda sessao autenticada

## Diferenca entre HTML observado e payload normalizado

- o HTML observado e fonte local, parcial e estruturalmente fragil
- o payload normalizado e a traducao semantica minima que o Lumen consegue persistir com seguranca
- obrigacoes so recebem `mapped_code` quando o alias e explicitamente seguro
- nomes nao mapeados continuam preservados em `unmapped_obligations`
- `econet_id_cnae` permanece como chave externa textual observada, separada do CNAE canonico

## Sessao assistida do S8.2

- a importacao publica aceita somente `cookies` em formato compativel com `storageState`
- `origins`, `localStorage`, `sessionStorage`, `indexedDB` e `token` nao entram no contrato do backend
- os dominios permitidos no S8.2 sao `.econeteditora.com.br` e `www.econeteditora.com.br`
- o backend aceita apenas cookies allowlisted da ferramenta e exclui analytics
- o probe do S8.2 usa `GET /ferramentas/regimes_cnae/index.php`
- redirects nao sao seguidos automaticamente
- redirect para login, HTML de autenticacao ou CAPTCHA marcam a sessao como `EXPIRED`
- o health local da Econet no S8.2 consulta apenas estado em memoria e resumo do cache

## Atualizacao S8.3

- o parser passa a distinguir Fator R positivo, negativo e nao observado;
- a ausencia de texto de Fator R continua `NOT_OBSERVED`;
- respostas HTML da Econet podem declarar charset ausente, generico ou incorreto; o decode confiavel deve partir dos bytes;
- `response.text` isolado nao e fonte confiavel para a Econet; o client usa `response.content` com ordem deterministica de charsets permitidos;
- o decode seguro tenta `Content-Type`, `meta charset`, `meta http-equiv`, `UTF-8`, `windows-1252` e `iso-8859-1`, sem `errors="replace"` e sem aceitar `U+FFFD`;
- Fator R positivo observado pode trazer `Anexo V`, `Anexo III` condicional e limiar `28%` no mesmo contexto textual;
- anexo repetido, como `IV / IV`, nao representa condicao e deve ser normalizado para `annex_conditional = null`;
- o enriquecimento continua serial, por CNAE, e sem persistencia de HTML bruto;
- o catalogo `company_cnaes` vira a fonte interna para enriquecimento e cobertura cadastral;
- cache antigo com `parser_version` desatualizado nao deve ser tratado como fresco nem como cobertura completa em `cache_only`.
