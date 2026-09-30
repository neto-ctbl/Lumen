# S11.2-A — Parser documental do MIT JSON

## Escopo e amostra real

`lumen.mit-json` versão `1` registra somente o fato documental observado no arquivo de
importação/apuração do MIT. Não transmite MIT, acessa e-CAC/DCTFWeb, compara DARF,
reconcilia tributos, altera obrigação ou promove campos canônicos/evidence.

A amostra inicial e outras duas empresas foram auditadas em modo somente leitura, sem copiar os arquivos para
o repositório e sem imprimir path, CPF, códigos, valores ou JSON bruto. O SHA-256 foi
comparado antes/depois. A estrutura observada é:

```text
PeriodoApuracao
  MesApuracao
  AnoApuracao
DadosIniciais
  SemMovimento
  QualificacaoPj
  TributacaoLucro
  VariacoesMonetarias
  RegimePisCofins
  ResponsavelApuracao
    CpfResponsavel
    TelResponsavel (Ddd, NumTelefone)
    EmailResponsavel
    RegistroCrc (UfRegistro, NumRegistro)
ListaEventosEspeciais[] (opcional)
  IdEvento | DiaEvento | TipoEvento
Debitos (opcional no esquema e ausente na variante real SemMovimento=true)
  BalancoLucroReal
  Irpj | Csll | Irrf | Ipi | Iof | PisPasep | Cofins
  ContribuicoesDiversas | Cpss | RetPagamentoUnificado
    ListaDebitos[] | ListaDebitosAposEvento[]
      IdDebito
      IdEventoDebito (na lista padrão)
      CodigoDebito
      AnoPostergado | TrimPostergado | AnoDebito | PaDebito
      CnpjScp | CnpjEstabelecimento | CodigoMunicipioOuro | CnpjIncorporacao
      ValorDebito
ListaSuspensoes[] (opcional)
  TipoSuspensao | MotivoSuspensao | ComDeposito | NumeroProcesso
  ProcessoTerceiro | DataDecisao | VaraJudiciaria | CodigoMunicipioSj
  ListaDebitosSuspensos[] (IdDebitoSuspenso, ValorSuspenso)
```

`ResponsavelApuracao` identifica o profissional responsável, não o contribuinte. O
parser não extrai CNPJ do nome do arquivo. As três amostras confirmaram IRPJ, CSLL, PIS,
COFINS, arquivo sem movimento, multiplicidade e `BalancoLucroReal=false`; hashes e
snapshot operacional permaneceram inalterados.

O esquema oficial 1.0 confirmou os campos opcionais acima. `BalancoLucroReal` é o
indicador de balanço/balancete de suspensão ou redução do IRPJ/CSLL no mês e, portanto,
é booleano tipado, não grupo desconhecido.

## Pipeline, assinatura e classificação

O layout registrado é `DOMINIO_MIT_JSON`. O fluxo reutiliza sem alteração do runtime:

```text
JSON / estrutura documental
  -> MitJsonLayoutExtractor (detecta e extrai)
  -> MitDocumentClassifier
  -> ComposableDocumentParser
  -> ParserExtraction / ParserRunResult
```

A assinatura exige objetos `PeriodoApuracao` e `DadosIniciais`, com `SemMovimento`
combinado a ao menos um campo inicial característico. `Debitos` deve ser objeto e,
quando há grupos, conter `ListaDebitos` ou `ListaDebitosAposEvento`. A exceção comprovada é a
variante real `SemMovimento=true`, que pode omitir completamente `Debitos` e produz zero
débitos com `MIT_NO_DEBITS`. Documento ativo sem `Debitos` continua desconhecido.
`PeriodoApuracao` isolado e filename/path nunca identificam MIT. JSON válido incompatível
resulta `UNKNOWN`/`UNSUPPORTED`; JSON sintaticamente inválido resulta `INVALID`.

O classifier confirma `family=MIT`, sem subtipo por tributo. Os sinais de estrutura e
conteúdo usam `FILE_STRUCTURE` e `CONTENT`. `period_from_content` não é sobrescrito por
`period_from_filename` ou `period_from_path`; divergências permanecem disponíveis para
reconciliação futura. Confidence mede apenas identificação/extração documental.

## Contrato tipado e débitos

`MitDocument` contém `MitInitialData`, `MitAssessmentPeriod`, `MitSpecialEvent[]`,
`MitDebit[]`, `MitSuspension[]`, `BalancoLucroReal`, `MitValidation`, nomes de campos
extras controlados e warning codes. Cada `MitDebit` preserva grupo, lista de origem,
código, periodicidade catalogada, atributos específicos, período explícito, principal e
identificadores. Não há `raw_payload`.

Mappings comprovados:

| Grupo JSON | Tax normalizado |
|---|---|
| `Irpj` | `IRPJ` |
| `Csll` | `CSLL` |
| `Irrf` | `IRRF` |
| `Ipi` | `IPI` |
| `Iof` | `IOF` |
| `PisPasep` | `PIS` |
| `Cofins` | `COFINS` |
| `ContribuicoesDiversas` | `CONTRIBUICOES_DIVERSAS` |
| `Cpss` | `CPSS` |
| `RetPagamentoUnificado` | `RET_PAGAMENTO_UNIFICADO` |

Grupo novo com `ListaDebitos` mantém `raw_group`, recebe `tax=UNKNOWN` e
`MIT_UNKNOWN_DEBIT_GROUP`; o documento continua `MATCHED`. Se uma seção desconhecida
for um objeto vazio, seu nome fica em `empty_debit_sections`, o mesmo warning é emitido
e nenhum débito fictício é criado. Se houver conteúdo não compreendido sem
`ListaDebitos`, o resultado é conservadoramente `INCONCLUSIVE`. Um arquivo pode produzir
N débitos e vários tributos.

`BalancoLucroReal` é campo conhecido e tipado. Campos escalares ainda não compreendidos dentro de `Debitos` não são grupos. Somente o
nome fica em `unknown_debits_fields`, com `MIT_UNKNOWN_DEBITS_FIELD`; seu valor não é
interpretado nem persistido. Estruturas complexas desconhecidas continuam
`INCONCLUSIVE`.

Números decimais são carregados com `json.loads(parse_float=Decimal)` e serializados
sem passagem por `float`. Zeros e casas adicionais são preservados. Identificadores e
códigos vêm somente de campos explícitos, nunca da posição do item.

O período mensal do MIT usa `MesApuracao`/`AnoApuracao`. Débitos preservam
`AnoPostergado`/`TrimPostergado`, `AnoDebito` e `PaDebito`; trimestre e ano só são
materializados quando esses campos oficiais existem. IRPJ/CSLL não são convertidos de
mês para trimestre por heurística. Período do arquivo e período do débito permanecem
separados. Divergência com hints de filename/path gera warning técnico, não fiscal.

## Catálogo de códigos

`mit_revenue_codes.py` contém os 240 códigos da tabela do Manual MIT 1.0, com grupo e
periodicidade `AN`, `TR`, `ME`, `DC` ou `DI`. O catálogo é referência versionada de
enriquecimento, não critério de reconhecimento nem enum fechado. Código novo de formato
válido é preservado e gera `MIT_REVENUE_CODE_UNKNOWN`; conflito entre código catalogado
e grupo estrutural gera `MIT_REVENUE_CODE_GROUP_CONFLICT`. As descrições não foram
copiadas porque o texto embutido no PDF oficial corrompe acentos; nenhum significado foi
inventado. Uma futura fonte oficial estruturada poderá adicioná-las.

## Evolução e warnings

Chaves extras não críticas não quebram a leitura: somente seus nomes são registrados em
allowlists tipadas (`unknown_fields`), nunca os valores. Uma quebra em envelope,
`ListaDebitos` ou item essencial reconhecível resulta `INCONCLUSIVE`; estrutura não MIT
resulta `UNSUPPORTED`. Não se usa `extra="allow"` nem armazenamento indiscriminado.

Warnings sanitizados aplicáveis:

- `MIT_ASSESSMENT_PERIOD_MISSING`;
- `MIT_UNKNOWN_DEBIT_GROUP`;
- `MIT_UNKNOWN_DEBITS_FIELD`;
- `MIT_DEBIT_PERIOD_MISSING`, quando o par ano/trimestre postergado está incompleto;
- `MIT_NO_DEBITS`;
- `MIT_PERIOD_CONFLICT`;
- `MIT_REVENUE_CODE_INVALID`, `MIT_REVENUE_CODE_UNKNOWN` e
  `MIT_REVENUE_CODE_GROUP_CONFLICT`;
- `UNKNOWN_JSON_LAYOUT`;
- `MIT_JSON_INVALID` e `MIT_STRUCTURE_INCONCLUSIVE`.

`MIT_TAXPAYER_ID_INVALID` não é emitido para o CPF do responsável, porque ele não é
identificação do contribuinte. Poderá ser implementado quando um campo documental de
contribuinte for comprovado no formato.

## Probe e segurança

`sanitized_mit_json_probe()` retorna somente family, layout, match/status, contagem de
débitos, taxes, presença de taxpayer/período, contagem de grupos desconhecidos e warning
codes. O harness `python -m agent.parsers.mit_json_validation <amostra>` ainda compara
hash e fingerprint/contagens do banco antes/depois, usa transação read-only e não cria
evidence/parser run. A saída não contém path, identidade, razão social, valores, códigos
ou JSON bruto.

Para matrizes manuais, `--expect-debits`, `--expect-tax`, `--expect-warning` e
`--expect-no-warnings` permitem validar cada perfil real sem codificar empresa ou path no
repositório.

Fixtures são exclusivamente sintéticas. O arquivo real permanece externo ao Git. O
watcher, polling, state, baseline e backfill não foram alterados.

## Ausência histórica

> A preservação regular de MIT JSON iniciou apenas no período operacional recente. A ausência de arquivo em competências históricas é ausência de fonte, não evidência de ausência de declaração/apuração.

O parser interpreta somente arquivos existentes. Não recebe data de adoção e não decide
se um MIT deveria existir. Ausência de JSON não significa MIT não entregue, apuração
ausente ou obrigação descumprida.
