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

Cenarios ainda nao cobertos:

- qualquer fluxo autenticado;
- CAPTCHA;
- comportamento de sessao;
- Fator R em fixture dedicada, porque esse HTML especifico nao foi comprovado de forma suficiente nos artefatos analisados para este micro-stage;
- parser de negocio;
- integracao funcional.
