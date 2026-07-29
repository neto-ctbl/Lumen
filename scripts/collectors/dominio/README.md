# Coletor Domínio Folha

Coletor Windows-only para gerar o relatório `Resumo Mensal` do Domínio Folha em PDF e produzir um manifest lateral compatível com o fluxo documental do Lumen.

## O que este coletor faz

- abre o módulo Folha do Domínio no Windows;
- executa o fluxo operacional do relatório `Resumo Mensal`;
- prefere uma única competência por PDF;
- salva primeiro um arquivo temporário `.partial.pdf`;
- valida o PDF com `pypdf` antes da troca atômica;
- preserva o último PDF válido quando a nova execução falha;
- calcula SHA-256 do PDF definitivo;
- gera `Resumo_Mensal_MM-AAAA.manifest.json`;
- usa lock local para evitar duas execuções simultâneas;
- registra tentativas explícitas de exportação em PDF.

## O que este coletor não faz

- não executa parser completo do PDF;
- não grava nada no banco do Lumen;
- não chama FastAPI;
- não faz upload;
- não roda watcher do backend;
- não transmite DCTFWeb;
- não lê API do Domínio;
- não acessa banco interno do Domínio.

## Dependências

- Windows
- Python 3.10+
- Domínio instalado localmente
- `pywinauto`
- `pywin32`
- `python-dotenv`
- `python-dateutil`
- `pypdf`

## Instalação local

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\requirements.txt
```

O coletor passa a ler primeiro o `.env` central da raiz do Lumen. Um `.env` local ao lado do coletor continua opcional e só deve ser usado como fallback.

## Configuração

Variáveis relevantes no `.env` central do Lumen:

```dotenv
DOMINIO_PASSWORD=ALTERE_LOCALMENTE
DOMINIO_EXE=C:\Contabil\contabil.exe
OUTPUT_DIR=
LOG_PATH=
LOGIN_TIMEOUT=90
REPORT_TIMEOUT=1200
SAVE_TIMEOUT=180
OVERWRITE_PDF=True
CLOSE_DOMINIO_AFTER=False
EXPORT_RETRIES=3
```

`COMPETENCIA` pode continuar existindo como fallback opcional, mas não é a forma recomendada de operação porque a competência do relatório é dinâmica.

## Execução recomendada

Fluxo mensal preferencial:

```powershell
python .\scripts\collectors\dominio\gerar_resumo_mensal_dominio.py --competencia 05/2026
```

Modo legado por intervalo continua disponível, mas não é o caminho automático preferencial do Lumen.

Recomendação operacional:

- usar `--competencia MM/AAAA` na linha de comando para a execução mensal;
- usar `COMPETENCIA_DE` e `COMPETENCIA_ATE` no ambiente apenas se houver necessidade operacional fixa;
- evitar depender de `COMPETENCIA` no `.env` central.

## Regra de competência

Relatório da folha: `05/2026`  
Apuração no Lumen: `06/2026`

Outro caso obrigatório:

Relatório da folha: `12/2026`  
Apuração no Lumen: `01/2027`

No manifest:

- `payroll_competence` preserva a competência da folha
- `assessment_competence` representa a apuração do mês seguinte

## Arquivos gerados

- `Resumo_Mensal_MM-AAAA.partial.pdf`
- `Resumo_Mensal_MM-AAAA.pdf`
- `Resumo_Mensal_MM-AAAA.manifest.json`
- `logs/gerar_resumo_mensal_dominio.log`

## Validação mínima do PDF

Antes da troca atômica, o coletor valida:

- existência do arquivo;
- tamanho maior que zero;
- assinatura `%PDF-`;
- abertura por `pypdf`;
- pelo menos uma página;
- ausência de criptografia;
- camada textual extraível;
- presença de `RESUMO DA FOLHA`;
- presença de competência em formato reconhecível;
- presença de pelo menos um CNPJ em formato reconhecível.

## Manifest

Exemplo resumido:

```json
{
  "schema_version": 1,
  "source": "DOMINIO_FOLHA_RESUMO",
  "evidence_source": "DOMINIO_FOLHA_PDF",
  "selection_scope": "ATIVAS",
  "payroll_competence": "2026-05",
  "assessment_competence": "2026-06",
  "pdf_file_name": "Resumo_Mensal_05-2026.pdf",
  "status": "SUCCESS"
}
```

O manifest nunca grava senha, token, CNPJ, nome de empresa ou texto integral do PDF.

## Códigos de saída

- `0`: execução concluída com PDF validado e manifest gerado
- `1`: falha operacional
- `130`: interrupção manual

## Retry e lock

- a exportação em PDF usa retry explícito, limitado por `EXPORT_RETRIES`;
- cada tentativa tenta recuperar foco e relocalizar o preview;
- o lock local `gerar_resumo_mensal_dominio.lock` impede execução concorrente;
- o lock é removido em `finally`.

## Logs e diagnóstico

- logs ficam em `scripts/collectors/dominio/logs/`;
- falha na exportação não apaga o último PDF válido;
- falha de validação remove apenas o `.partial.pdf` quando seguro;
- o hash SHA-256 do PDF validado fica no log e no manifest.

## Segurança

- mantenha `.env` apenas localmente;
- não registre senha em script, log, teste ou documentação;
- não coloque PDFs reais nem logs reais no Git;
- não execute automação contra ambiente operacional fora do fluxo controlado.
