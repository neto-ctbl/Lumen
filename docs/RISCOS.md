# Riscos Tecnicos do Lumen

Data de referencia: 2026-07-20

## Sittax

- Os endpoints observados do portal podem mudar sem aviso.
- Payloads e envelopes podem mudar sem versionamento formal.
- Empresas com CNPJ invalido ou payload parcial devem degradar para `INVALID_CNPJ` sem derrubar a execucao inteira.
- Mistura de contexto entre empresas pode levar DIFAL, notas ou painel a apontarem para a empresa errada.
- Mistura de competencia pode produzir leitura incorreta do contexto.
- Uma sessao pode ser alterada por nova apuracao no meio do processamento.
- Paginacao incompleta pode esconder documentos e tarefas.
- Grandes volumes de documentos podem exigir iteracao de varias paginas e aumentar tempo de execucao.
- JWT, cookies e headers sensiveis podem vazar se houver logging inadequado.
- Dados fiscais reais podem vazar se fixtures ou logs forem versionados.
- O portal pode aplicar bloqueio, rate limit, timeout ou respostas parciais.
- Perda de contexto durante a execucao pode invalidar leituras contextuais.
- Uso sem autorizacao formal do portal pode trazer risco operacional e contratual.
- Endpoints com nome/metodo ambiguo, como `POST /api/v2/painel-contador/transmissao`, nao podem ser tratados como seguros sem revalidacao.
- Reutilizar a mesma sessao sem exclusao mutua local pode misturar autenticacao e contexto futuro entre threads.
- Assumir qualquer escritorio fora do payload de login pode listar empresas erradas.
- Ausencia de uma empresa na listagem Sittax nao pode ser tratada como delete local automatico.
- Persistir apuracao sem conferir `empresaCnpj` e `periodoFiscal` pode contaminar snapshots entre empresas ou competencias.
- Reaproveitar contexto de apuracao apos tentativa falha cria risco de chamadas contextuais com empresa ou competencia obsoletas.
- O host `api.sittax.com.br` exige sessao stateful; tratar as chamadas como requests stateless cria risco de falso negativo local e de conclusao arquitetural errada.
- Perder o cookie `sittax-api-affinity` no meio da cadeia contextual pode quebrar o handoff mesmo com JWT valido e cookies de contexto presentes.
- Reconstituir manualmente apenas o header `Cookie` sem preservar o `cookie jar` completo pode produzir comportamento diferente do portal e do cliente do Lumen.
- Reordenar o fluxo validado `login -> empresas -> apuracao -> valor-auditoria -> painelprincipal -> DIFAL/documentos` cria risco de contexto parcial no host `api`.
- Ausencia de endpoint explicito de selecao de empresa no host API continua sendo risco documental; o conector depende da sequencia observada e da sessao persistente, nao de um setter oficial documentado.
- Datas retornadas pelo Sittax podem vir com fracao de segundos curta ou longa; parser rigido cria falha operacional mesmo com payload semanticamente valido.

## Econet

- A sessao autenticada pode expirar no meio do uso futuro.
- O HTML observado pode mudar sem aviso.
- Os IDs internos da Econet podem mudar ou variar por busca.
- O conteudo pode variar conforme o CNAE consultado.
- Mensagens negativas de negocio podem ser confundidas com erro tecnico.
- Lista indicativa de obrigacoes pode ser confundida com obrigacao definitivamente exigivel.
- HAR, JSONL, cookies e storages podem vazar segredo se forem versionados.
- Fixtures excessivamente acopladas ao HTML podem quebrar com mudancas cosmeticas.
- Encoding incorreto pode deformar nomes de regimes e obrigacoes.
- Nao existe contrato oficial JSON confirmado para a funcionalidade observada.
- O uso futuro depende de sessao autenticada manualmente.
- O parser do S8.1 pode ficar excessivamente acoplado a texto ou estrutura localmente observada e precisar revalidacao quando a Econet alterar microcopys.
- Resultados parciais entre abas podem gerar cache semanticamente incompleto se o carregamento futuro do HTML nao entregar todas as secoes esperadas.
- Divergencias entre as abas de tributacao e obrigacoes podem produzir payload coerente tecnicamente, mas contraditorio do ponto de vista fiscal.
- TTL de `180` dias pode ficar longo ou curto demais para determinados CNAEs; isso pode gerar cache desatualizado ou revalidacoes desnecessarias.
- Novos nomes de obrigacao podem surgir sem alias seguro e aumentar `unmapped_obligations`.
- Mudanca no formato de `econet_id_cnae` pode quebrar lookup, mesmo mantendo o CNAE visivel.
- Falso positivo de pagina de login ou CAPTCHA pode bloquear parse de HTML valido que contenha termos parecidos.
- Cache global por CNAE pode divergir entre assinaturas ou ambientes da Econet se a plataforma passar a exibir conteudo contextual por perfil.
- Em ambiente com multiplos workers, a sessao assistida fica local a cada processo e pode existir em um worker e faltar em outro.
- Mudanca em nomes de cookies allowlisted pode invalidar a importacao ate novo diagnostico direcionado.
- Dependencia futura de `localStorage` ou header nao observado quebraria o probe mesmo com cookies validos.
- O operador pode esquecer o arquivo temporario de exportacao e precisar remove-lo manualmente apos o uso.

## S8.3

- CNAE removido da empresa pode permanecer ativo se a reconciliacao nao rodar.
- Cache vencido ou parcial pode degradar o potencial cadastral para `PARTIAL`.
- Cache com `parser_version` antigo pode aparentar cobertura completa e esconder necessidade de refresh.
- CNAE sem resultado exato na Econet exige revisao manual.
- Mudanca no HTML da Econet pode invalidar o parser de Fator R e anexos.
- Charset ausente ou incorreto pode gerar mojibake, `U+FFFD` ou threshold fiscal perdido se o decode confiar em `response.text`.
- Percentual fora do contexto de Fator R pode ser capturado incorretamente se o parser usar regex ampla demais.
- Downgrade de `TEXT` para `VARCHAR(255)` em `mei_occupation` pode falhar quando existirem ocupacoes maiores que 255 caracteres.
- Sessao manual pode expirar no meio do reprocessamento integral e deixar parte do cache em versao antiga.
- `cTribMun` pode nao representar CNAE em alguns municipios.
- XML real pode conter certificado, assinatura e dados pessoais e nao pode virar fixture.
- Mudanca de microcopy no bloco principal do Simples pode reintroduzir deteccao incorreta de Fator R mesmo com notas laterais ignoradas.
- Um mesmo CNAE pode trazer multiplas descricoes tributarias no HTML observado; o parser precisa continuar privilegiando a regra estruturada e nao a primeira ocorrencia de `Anexo`.

## S9.0

- A automacao UI do Dominio pode mudar sem aviso e quebrar atalhos ou controles mapeados.
- A exportacao do PDF pode falhar de forma intermitente e exigir retry controlado.
- O arquivo pode ser gravado parcialmente se a validacao nao ocorrer antes da troca atomica.
- O PDF pode perder camada textual e inviabilizar o parser offline principal.
- O relatorio pode ter empresas em varias paginas, paginas `1/2`, `2/2` ou continuacao vazia.
- Rubricas desconhecidas podem exigir ampliacao do parser no S9.1.
- A ausencia da empresa no PDF pode ser interpretada incorretamente como ausencia de movimento.
- Confundir competencia da folha com competencia de apuracao pode contaminar DCTFWeb, alertas e Fator R.
- Concorrencia entre duas execucoes do coletor pode sobrescrever artefatos sem lock local.
- Fixtures podem vazar dado real se nomes, CNPJs ou valores observados forem copiados sem sanitizacao.

## S9.2

- Concorrencia entre duas importacoes do mesmo arquivo depende da constraint `organization_id + file_sha256` e do tratamento correto de `IntegrityError`.
- CNPJ invalido, ausente ou sem match nao pode interromper o lote, mas aumenta fila de revisao manual.
- `raw_text` persistido em movimento exige cuidado para nao vazar em log, erro, auditoria ou `integration_sync_runs`.
- Retry de import `FAILED` precisa limpar movimentos e evidencias anteriores para nao produzir duplicidade.
- Arquivo com multiplas competencias de apuracao pode deixar `assessment_period_id` do import nulo e exigir leitura por movimento.
