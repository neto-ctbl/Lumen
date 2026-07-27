# Fixtures observadas da Econet

Estas fixtures sao sinteticas ou rigorosamente sanitizadas. Elas preservam apenas a estrutura HTML minima observada nos scans locais da ferramenta `/ferramentas/regimes_cnae/`.

Regras:

- nao contem cookies, credenciais, headers, tokens ou storages;
- nao podem ser substituidas por HAR, JSONL ou HTML bruto real;
- nao representam resposta oficial versionada da Econet;
- existem apenas para sustentar testes locais de contrato observado e seguranca.

Cenarios cobertos:

- busca de CNAE com identificador interno observado;
- abertura de detalhe do CNAE;
- subabas tributarias observadas;
- abas e subabas de obrigacoes acessorias;
- mensagens negativas validas para Simples Nacional e SIMEI.

Cenarios cobertos no S8.3:

- Fator R positivo com Anexo V e migracao condicional para Anexo III em 28%;
- Fator R negativo com Anexo III;
- Anexo IV sem inferencia de Anexo III/V;
- obrigacoes positivas do Simples Nacional com preservacao de nomes nao mapeados.

Cenarios ainda nao cobertos:

- qualquer fluxo autenticado de navegador;
- CAPTCHA;
- XML real de NFS-e;
- watcher;
- parser XML produtivo.
