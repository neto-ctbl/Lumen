# Riscos Tecnicos do Lumen

Data de referencia: 2026-07-15

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
