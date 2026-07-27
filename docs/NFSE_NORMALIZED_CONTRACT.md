# Contrato canonico de NFS-e

O S8.3 congela um contrato normalizado de NFS-e para uso futuro no S10.

Layouts observados inicialmente:

- `NFSE_ABRASF_204`
- `NFSE_NACIONAL_101`

Campos canonicos minimos:

- `source_layout`
- `document_key`
- `issued_at`
- `service_period`
- `service_amount`
- `cnae`
- `municipal_tax_code`
- `municipal_tax_description`
- `provider`
- `taker`
- `cancellation`

Regras do S8.3:

- o contrato aceita CNAE vindo de `CodigoCnae` ou de `cTribMun`;
- o CNAE normalizado sempre tem 7 digitos;
- cancelamento e substituicao apenas congelam semantica minima para o S10;
- o contrato nao le XML real;
- o contrato nao persiste certificado, assinatura ou dados pessoais alem do resumo minimo das partes.
