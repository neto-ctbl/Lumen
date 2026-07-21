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

- fixture dedicada de Fator R com HTML comprovado para este micro-stage;
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
