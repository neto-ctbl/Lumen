# S11.1-C.1 — Extensao de parsers documentais

## Reuso por JSON no S11.2-A

`DOMINIO_MIT_JSON` comprovou que os contratos são documentais, não PDF-específicos.
`MitJsonLayoutExtractor` usa o mesmo `DocumentLayoutDetector`/
`DocumentLayoutExtractor`; `MitDocumentClassifier` usa `DocumentClassifier`; e
`MitJsonParser` delega a `ComposableDocumentParser`. `technical_format=JSON` percorre
layout, extração, classificação e resultado sem mudança em `DocumentParserRuntime`.

Para conteúdo estruturado, `FILE_STRUCTURE` representa schema/envelope e tem autoridade
acima de filename/path. Erro sintático é `INVALID`; JSON válido com schema desconhecido é
`UNKNOWN`/`UNSUPPORTED`. Campos extras irrelevantes são tratados pelo modelo da família,
não por `extra="allow"` no framework. O único ajuste mínimo tornou o warning de layout
desconhecido configurável no `ComposableDocumentParser`: o padrão retrocompatível
continua `UNKNOWN_GUIDE_LAYOUT`, enquanto o MIT usa `UNKNOWN_JSON_LAYOUT`. Protocolos e
runtime não mudaram.

## Regra confirmada pelo S11.1-E

Parcelamento demonstrou o caso central de reutilização: classificações documentais novas
consomem `DAS_FORM`, `FEDERAL_REVENUE_FORM` e `DARE_GO_5_1` sem criar extratores por
programa. O DAS expõe agora `extract_das_form()` como extração física compartilhada;
`DasPdfParser` mantém sua assinatura semântica, payload e versão. Somente o formulário
clássico numerado observado no Parcelamento Simplificado justificou
`DARF_LEGACY_FORM`.

O registry atual, em ordem, é `DAS_FORM`, `FEDERAL_REVENUE_FORM`, `DARE_GO_5_1`,
`DARF_LEGACY_FORM`, `ANAPOLIS_DUAM`, `NEROPOLIS_DUAM` e `DOMINIO_MIT_JSON`. O parser
installment consulta o registry antes de selecionar o pipeline composto. A family é
`INSTALLMENT`; programa, administrador, dívida e tributos não alteram a identidade do
layout.

## Regra confirmada pelo S11.1-D

O ISS inaugurou um parser novo integralmente composto sobre este contrato. Quando um
arquivo contém N documentos e a classificação pertence a cada documento, use o callback
opcional `serialize_result(extracted, classification)` do `ComposableDocumentParser`.
Ele permite montar o schema final sem reler o arquivo e sem misturar decisão fiscal no
extractor. `serialize_extracted` continua sendo o padrão retrocompatível.

Dois municípios só compartilham extractor quando a estrutura física foi comprovadamente
igual. O S11.1-D cadastrou `ANAPOLIS_DUAM` e `NEROPOLIS_DUAM` separadamente e normalizou
ambos para `IssGuideFile`; `ISS_OWN`/`ISS_WITHHELD` permanecem classificações, não layouts.

Status: framework concluido em 2026-09-21. Este contrato e local ao Agent,
deterministico e desacoplado do polling. Nao cria plugin dinamico, tabela,
migration, endpoint, backfill ou reconciliacao.

## Pipeline obrigatorio

```text
arquivo
  -> identificar layout fisico
  -> extrair estrutura
  -> classificar o documento/receita
  -> produzir ParserExtraction/ParserRunResult
```

Layout e classificacao fiscal sao identidades distintas. A precedencia de
sinais continua `CONTENT > FILE_STRUCTURE > FILENAME > PATH`; filename e path
nunca transformam um layout desconhecido em tributo conhecido.

Os contratos ficam em `agent/parsers/layout_framework.py`:

- `DocumentLayoutDetector`: possui `layout_id` e responde somente se reconhece
  a estrutura;
- `DocumentLayoutExtractor[T]`: reconhece a estrutura e devolve dados fisicos
  extraidos;
- `DocumentClassifier[T, ClassificationResult]`: classifica os dados ja
  extraidos e nao reabre o arquivo;
- `ClassificationResult`: carrega apenas identidade/classificacao, familia,
  subtipo, confianca, sinais e warnings; nao duplica o resultado do runtime;
- `ComposableDocumentParser`: adapta as tres etapas para a interface publica
  `DocumentParser`;
- `LayoutRegistry`: registro ordenado e explicito, sem reflection, scanning,
  YAML, banco, entry points ou hot reload.

O registry padrao de layouts e deliberadamente escrito em codigo e registra,
nesta ordem, `DAS_FORM`, `FEDERAL_REVENUE_FORM`, `DARE_GO_5_1`,
`DARF_LEGACY_FORM`, `ANAPOLIS_DUAM`, `NEROPOLIS_DUAM` e `DOMINIO_MIT_JSON`. O registry
de parsers continua separado e explicito. Um parser novo e registrado no
`ParserRegistry`; o `DocumentParserRuntime` nao precisa ser alterado.

## Dois resultados que nao podem ser confundidos

### Layout conhecido e classificacao desconhecida

O extractor concluiu a leitura estrutural. O resultado permanece `MATCHED`, a
estrutura extraida e preservada, `classification_known=false`, a classificacao
e `UNKNOWN` e um warning especifico e emitido. No DARE atual, por exemplo, um
codigo nao mapeado permanece no payload e gera `STATE_REVENUE_CODE_UNKNOWN` e,
quando nao houver semantica conclusiva, `STATE_GUIDE_KIND_INCONCLUSIVE`.

### Layout desconhecido

Nenhum detector reconheceu a estrutura. O resultado de identificacao usa
`layout_id=UNKNOWN`, `matched=false`; o parser composto devolve `UNSUPPORTED`,
familia/classificacao `UNKNOWN` e `UNKNOWN_GUIDE_LAYOUT`. Um nome enganoso como
`DARF ICMS.pdf` nao muda esse resultado.

`sanitized_layout_diagnostic()` permite levantar esse caso sem expor o arquivo.
Sua saida e allowlisted: formato tecnico, quantidade de paginas, disponibilidade
de texto, layout conhecido, `layout_id`, classificacao tecnica/conhecida e warnings. Nao
inclui path, texto, CNPJ/CPF, razao social, IE, valores, numero de guia, codigo
de barras ou identificador fiscal.

## Como estender um layout existente

Quando a estrutura ja e reconhecida, nao se cria outro extractor.

1. Confirmar por fixture sintetica que o detector/extractor atual aceita o
   documento.
2. Adicionar ou ampliar o mapping/classifier sem usar filename/path como
   autoridade.
3. Preservar codigo, descricao e demais campos observados quando a classificacao
   continuar desconhecida.
4. Adicionar casos positivo, conflitante e desconhecido aos testes da familia.
5. Alterar a versao do parser somente se o resultado publico mudar.

Exemplo: um novo codigo sintetico no `DARE_GO_5_1` requer mapping/testes do
classifier estadual, nao um novo parser nem um novo extractor.

## Como adicionar um layout novo

1. Criar um detector ou um extractor que tambem implemente
   `supports_layout(context)` e declarar um `layout_id` estavel.
2. Extrair somente estrutura documental; manter decisao fiscal no classifier.
3. Criar um classifier que consuma exclusivamente o objeto extraido.
4. Compor um `DocumentParser`, diretamente ou com
   `ComposableDocumentParser`.
5. Registrar detector/extractor em `default_layout_registry()` e parser em
   `default_parser_registry()`; ambos os registros sao explicitos.
6. Cobrir layout conhecido, classificacao conhecida/desconhecida, layout
   desconhecido, falhas sanitizadas, limites e regressao cruzada.

Exemplo exclusivamente sintetico:

```python
extractor = SyntheticLayoutExtractor()  # layout_id = "SYNTHETIC_FORM"
classifier = SyntheticClassifier()
parser = ComposableDocumentParser(
    name="synthetic.form",
    version="1",
    supported_formats=frozenset({TechnicalFormat.JSON}),
    extractor=extractor,
    classifier=classifier,
    serialize_extracted=lambda value: {"document": value},
)
registry = ParserRegistry((parser,))
result = DocumentParserRuntime(registry).run_file(synthetic_path)
```

O teste dedicado prova esse fluxo sem editar o runtime.

## Quando nao criar extractor novo

Nao criar outro extractor apenas porque mudou tributo, codigo de receita,
programa, nome do arquivo, pasta ou competencia. Tambem nao criar por simetria
se a separacao exigir reescrever um parser estavel sem consumidor real.

O DAS ganhou detector `DAS_FORM` no S11.1-C.1 e passou a expor a menor parte
estrutural necessária como `extract_das_form()` no S11.1-E. O `DasPdfParser`
continua proprietário de sua assinatura semântica e do payload DAS, sem bump ou
refatoração agressiva. O federal e o DARE possuem adaptadores formais sobre
`FederalRevenueGuideExtractor` e `StateRevenueGuideExtractor`. As exclusoes de
DARF, DAS normal e guia estadual normal continuam nos respectivos parsers,
nao nos detectores fisicos.

## Versao, testes e seguranca

- Refatoracao interna com payload, classificacao e comportamento identicos nao
  altera versao. S11.1-C.1 preserva DAS `2`, DARF `1` e estadual `1`.
- Mudanca semantica futura incrementa somente o parser afetado.
- Fixtures sao sinteticas; corpus real nao e versionado nem transcrito.
- Exceptions viram warnings sanitizados; nenhum texto bruto entra no resultado.
- O arquivo permanece local ao Agent e nenhum detector/extractor escreve nele.
- O framework nao conecta os parsers ao polling e nao promove campos canonicos.

Cobertura central: `backend/tests/test_document_layout_framework.py`, alem das
regressoes DAS, DARF, estadual, runtime e parser runs. Fechamento sequencial:
foco `190 passed`, backend `929 passed`, Ruff/diff/typecheck/build aprovados,
Playwright isolado `14 passed` e Alembic `20260911_0019 (head)`; houve somente o
warning conhecido Starlette/httpx. Como payloads, versoes e classificacoes
existentes permaneceram identicos, a revalidacao do corpus real para esta
refatoracao e `REAL_CORPUS_REVALIDATION_REQUIRED = NO`.
