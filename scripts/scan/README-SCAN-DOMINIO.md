# Scanner local do aplicativo Domínio

Este pacote serve para descobrir como o aplicativo desktop do Domínio se comporta no Windows antes de criar qualquer integração do Lumen.

## O que ele captura

No modo padrão:

- processos candidatos e processos filhos;
- executáveis e versões;
- janelas abertas;
- árvore de controles do Windows UI Automation;
- `AutomationId`;
- nome acessível;
- classe da janela/controle;
- framework visual detectado;
- tipo de controle;
- posição e tamanho;
- controles focados;
- elementos clicados;
- conexões TCP e UDP vinculadas aos processos;
- mudanças da interface ao longo da navegação.

Modo opcional:

- trace de rede ETL pelo Windows;
- tráfego HTTP/HTTPS por mitmproxy, quando tecnicamente possível.

## Limites importantes

1. Conexão TCP não é o mesmo que request HTTP.
2. Para ler corpo, URL e resposta HTTPS, o aplicativo precisa:
   - respeitar o proxy WinINET configurado;
   - aceitar o certificado do mitmproxy já instalado e confiável.
3. O pacote não instala certificados.
4. O pacote não contorna certificate pinning.
5. Se o aplicativo rejeitar o proxy ou usar pinning, não tente patch, DLL injection ou bypass.
6. O aplicativo pode ser Win32, WPF, WinForms, Java, Chromium/CEF ou outro framework. Alguns frameworks expõem poucos `AutomationId`.
7. O scanner não lê `ValuePattern` de campos de edição e não captura deliberadamente o conteúdo de senhas.

## Arquivos do pacote

- `Scan-DominioDesktop.ps1`: scanner principal.
- `dominio_mitm_addon.py`: addon sanitizado do mitmproxy.
- `README-SCAN-DOMINIO.md`: este guia.

## Uso recomendado — primeira rodada

Abra o PowerShell na pasta do pacote.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\Scan-DominioDesktop.ps1 -DurationMinutes 20
```

Depois:

1. Abra o Domínio.
2. Entre normalmente.
3. Navegue apenas nas telas que precisamos mapear.
4. Clique nos botões relevantes.
5. Gere ou abra o relatório **Resumo Mensal da Folha**.
6. Abra telas de exportação, impressão e seleção de competência.
7. Não transmita, exclua nem grave alterações fiscais durante o scan.
8. Encerre com `Ctrl+C` ou aguarde o tempo configurado.

Os resultados ficarão em:

```text
scan_logs\dominio-AAAAmmdd-HHMMSS\
```

## Caso o processo não seja encontrado

Primeiro descubra o nome do processo:

```powershell
Get-Process |
    Where-Object {
        $_.MainWindowTitle -match 'Dom[ií]nio|Thomson'
    } |
    Select-Object Id, ProcessName, MainWindowTitle, Path
```

Depois execute com um padrão específico:

```powershell
.\Scan-DominioDesktop.ps1 `
    -DurationMinutes 20 `
    -ProcessNamePattern 'nome_real_do_processo' `
    -WindowTitlePattern 'Dom[ií]nio|nome da janela'
```

## Trace de rede do Windows

Abra o PowerShell como Administrador:

```powershell
.\Scan-DominioDesktop.ps1 `
    -DurationMinutes 20 `
    -StartNetshTrace
```

Isso gera um arquivo `.etl`. Ele registra atividade de rede, mas não descriptografa HTTPS.

## Captura HTTP opcional com mitmproxy

Instale em ambiente isolado:

```powershell
py -3.10 -m venv .venv-scan
.\.venv-scan\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install mitmproxy
```

Primeiro teste sem alterar o proxy automaticamente:

```powershell
.\Scan-DominioDesktop.ps1 `
    -DurationMinutes 20 `
    -EnableMitmProxy
```

O mitmproxy ficará em:

```text
127.0.0.1:8877
```

Para configurar temporariamente o proxy WinINET do usuário e restaurá-lo ao encerrar:

```powershell
.\Scan-DominioDesktop.ps1 `
    -DurationMinutes 20 `
    -EnableMitmProxy `
    -ConfigureWinInetProxy
```

Atenção:

- esse modo pode afetar temporariamente outros programas do usuário;
- o script restaura o proxy no bloco `finally`;
- mesmo assim, confirme o proxy após a execução.

Verificação:

```powershell
Get-ItemProperty `
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' `
    ProxyEnable, ProxyServer, ProxyOverride
```

Para desligar manualmente em caso de interrupção abrupta:

```powershell
Set-ItemProperty `
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' `
    -Name ProxyEnable `
    -Type DWord `
    -Value 0
```

O scanner não altera o proxy WinHTTP.

## Instalação do certificado do mitmproxy

O pacote não instala certificados automaticamente.

Faça isso somente em máquina autorizada e apenas para diagnóstico controlado. Não instale certificado em servidor de produção. Não mantenha o proxy ativo após o scan.

Se o Domínio não aceitar a conexão, interrompa a captura HTTP. Não tente contornar pinning.

## Logs gerados

### `processes.jsonl`

Processos e versões detectadas.

### `windows.jsonl`

Janelas de primeiro nível.

### `uia_snapshots.jsonl`

Árvore dos controles quando a interface muda.

Campos mais úteis:

- `automation_id`;
- `name`;
- `class_name`;
- `framework_id`;
- `control_type`;
- `localized_control_type`;
- `bounding_rectangle`.

### `clicks.jsonl`

Elemento existente sob o cursor em cada clique esquerdo.

### `focused_controls.jsonl`

Mudanças de foco de teclado.

### `network_connections.jsonl`

Conexões por PID:

- endereço local;
- porta local;
- endereço remoto;
- porta remota;
- estado TCP.

### `http_flows_sanitized.jsonl`

Somente no modo mitmproxy. O addon mascara:

- `Authorization`;
- cookies;
- `Set-Cookie`;
- senhas;
- tokens;
- API keys;
- JWTs.

Corpos binários não são gravados. Corpos textuais são limitados.

### `windows_network_trace.etl`

Somente com `-StartNetshTrace`.

## Busca rápida nos resultados

Localizar botões:

```powershell
Get-Content .\scan_logs\dominio-*\clicks.jsonl |
    Select-String -Pattern '"control_type":"ControlType.Button"|"localized_control_type":"botão"'
```

Localizar AutomationId:

```powershell
Get-Content .\scan_logs\dominio-*\uia_snapshots.jsonl |
    Select-String -Pattern '"automation_id":"[^"]+"'
```

Localizar hosts e portas:

```powershell
Get-Content .\scan_logs\dominio-*\network_connections.jsonl |
    Select-String -Pattern '"remote_address"|"remote_port"'
```

Localizar requests HTTP:

```powershell
Get-Content .\scan_logs\dominio-*\http_flows_sanitized.jsonl |
    Select-String -Pattern '"method"|"pretty_url"|"status_code"'
```

## Fluxo de scan recomendado para o S9

Mapear, sem executar transmissão ou alteração externa:

1. tela inicial;
2. seleção de empresa;
3. seleção de competência;
4. módulo Folha;
5. relatórios;
6. Resumo Mensal;
7. filtros;
8. visualizar;
9. imprimir;
10. exportar PDF;
11. caminho e nome padrão do arquivo;
12. mensagens de erro e estados vazios;
13. navegação entre empresas;
14. fechamento da janela.

## O que não fazer

- não versionar os logs;
- não enviar logs brutos antes de revisar;
- não capturar produção sem autorização;
- não navegar em cadastros com dados desnecessários;
- não registrar senhas;
- não tentar transmissão fiscal;
- não usar DLL injection;
- não usar API hooking;
- não desabilitar TLS;
- não contornar certificate pinning;
- não automatizar cliques de produção nesta fase.

## Sugestão de `.gitignore`

```gitignore
scan_logs/
dominio-scan-*/
*.etl
*.pcap
*.pcapng
http_flows_sanitized.jsonl
```
