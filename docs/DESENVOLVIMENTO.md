# Desenvolvimento e publicação

Este guia cobre o código-fonte, os testes, a compilação do executável e o processo de distribuição. Para instalar e configurar o Radar, consulte o [guia Windows](GUIA_WINDOWS.md).

## Execute o projeto no Windows

Use Git, Python 3.12 de 64 bits e PowerShell. Os comandos abaixo criam um ambiente virtual e executam os testes a partir do clone.

```powershell
git clone https://github.com/BrandonSaraiva/Dou-e-Concursos.git
cd Dou-e-Concursos
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py
```

Ao revisar um PR localmente, faça checkout da branch dele antes de rodar os testes. O atalho [`rodar_com_python.bat`](../rodar_com_python.bat) também abre a interface pelo código-fonte.

## Compile e teste o executável

Na raiz do projeto, execute o script de compilação depois de instalar as dependências acima. O script exige Python Windows x64 e gera `dist/RadarDOU.exe` com PyInstaller. [Script de compilação](../scripts/build-windows.ps1)

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\build-windows.ps1 -Python .\.venv\Scripts\python.exe
```

Também é possível usar [`GERAR_EXE_WINDOWS.bat`](../GERAR_EXE_WINDOWS.bat). Use `-SmokeOnly` para repetir o teste de um binário existente em `dist/`.

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\build-windows.ps1 -SmokeOnly
```

O teste do executável retira o Python do `PATH` temporariamente, abre a interface e verifica a reabertura após enviar a janela para a bandeja. Também grava e relê em processos separados uma configuração fictícia protegida por DPAPI e um histórico no SQLite. A pasta de dados usada nesses testes é temporária. [Script do teste do executável](../scripts/test-windows-exe.ps1)

## Valide e publique pelo GitHub Actions

| Evento | Resultado |
| --- | --- |
| PR com destino à `main` | **Verificar projeto** roda os testes no Linux. **Compilar RadarDOU para Windows** testa o código, compila o EXE e testa a interface e a persistência em Windows x64. |
| Push ou integração na `main` | O workflow Windows testa o binário e, se a compilação passar e o commit ainda for o topo da `main`, publica uma Release. |
| Execução manual | Quem tem acesso de escrita pode abrir **Actions → Compilar RadarDOU para Windows → Run workflow**, escolher `main` e confirmar em **Run workflow**. Uma execução manual em outra branch produz somente o artefato se passar. |

Ao revisar um PR, abra **Checks** e confirme o resultado das duas execuções. Para testar o pacote antes da publicação, abra o resumo da execução Windows e selecione **RadarDOU-Windows-x64** em **Artifacts**. É necessário estar conectado ao GitHub e ter acesso de leitura. O ZIP contém `RadarDOU.exe`, `SHA256SUMS.txt` e `SOURCE_COMMIT.txt`. O artefato fica disponível por 30 dias conforme a configuração do workflow. [Workflow Windows](../.github/workflows/build-windows.yml) · [Download de artefatos](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

Depois de integrar, confira o job **Publicar executável em Releases** da execução na `main`. Abra a [última Release](https://github.com/BrandonSaraiva/Dou-e-Concursos/releases/latest) e confirme que os três arquivos aparecem em **Assets**.

### Conferir o executável baixado

Baixe o EXE e os manifestos para a mesma pasta. O valor em `SOURCE_COMMIT.txt` identifica o commit compilado. Abra o PowerShell nessa pasta e compare o hash calculado com o publicado.

```powershell
(Get-FileHash .\RadarDOU.exe -Algorithm SHA256).Hash
Get-Content .\SHA256SUMS.txt
Get-Content .\SOURCE_COMMIT.txt
```

O hash deve coincidir, ignorando diferenças entre maiúsculas e minúsculas. O EXE distribuído é autocontido. Python e o ambiente virtual são necessários para trabalhar com o código e gerar o pacote.

## Mapa do repositório

| Caminho | Responsabilidade |
| --- | --- |
| [`main.py`](../main.py), [`gui.py`](../radar_dou/gui.py) e [`windows.py`](../radar_dou/windows.py) | Entrada do aplicativo, painel Tkinter, instância única, bandeja e início com o Windows. |
| [`service.py`](../radar_dou/service.py) | Agendamento, consultas manuais, comandos para o ID autorizado, envio e nova tentativa de alertas. |
| [`scraper.py`](../radar_dou/scraper.py) e [`concursos.py`](../radar_dou/concursos.py) | Leitura da pesquisa do DOU e dos catálogos nacional e estadual de concursos. |
| [`database.py`](../radar_dou/database.py) e [`settings.py`](../radar_dou/settings.py) | Histórico, filas, preferências e armazenamento de credenciais. |
| [`android_ui.py`](../radar_dou/android_ui.py), [`android_runtime.py`](../radar_dou/android_runtime.py) e [`android_service.py`](../android_service.py) | Interface móvel, comunicação local e serviço em primeiro plano. |
| [`tests/`](../tests), [`scripts/`](../scripts) e [`.github/workflows/`](../.github/workflows) | Testes do código, compilação e validação do pacote, automação de CI e publicação. |
| [`assets/`](../assets) | Ilustrações do guia, regeneradas com `python assets/create_docs_images.py` em um ambiente com Pillow e Segoe UI ou DejaVu Sans. |

### Coleta e emissão de alertas

- O coletor do DOU tenta ler o JSON incorporado na página e tem um parser de cartões HTML para respostas sem esse JSON. Valida total e paginação até 30 páginas. Uma coleta incompleta ou bloqueada preserva o último histórico íntegro.
- O coletor de concursos lê a seção de abertos do Concursos no Brasil, com suporte a tabelas, listas e cartões. Consulta `/concursos/br/` e a página da UF escolhida. Resultados nacionais repetidos no catálogo estadual aparecem apenas na lista nacional.
- O SQLite identifica as publicações do DOU pelo hash da URL e os concursos pela URL normalizada. A primeira coleta bem-sucedida cria a referência sem disparar os alertas antigos. A fila conserva alertas ainda pendentes e tenta o envio novamente. Se o Telegram aceitar uma mensagem e a confirmação se perder antes de gravar o envio, uma nova tentativa pode gerar um aviso repetido.
- Os dois monitores registram seus próprios sucessos e falhas. No Windows, uma consulta HTTP malsucedida pode recorrer a um navegador compatível disponível. No Android, a coleta fica restrita às requisições HTTP. O estado exibido pelo portal de concursos deve ser confirmado junto ao órgão ou no edital.

### Dados locais e privacidade

No Windows, o Radar guarda os dados em `%APPDATA%\RadarDOU` e protege o token com DPAPI da conta logada. No Android, o token fica na pasta privada do app. As configurações permanecem no dispositivo. O nome monitorado integra a consulta ao DOU e o token é usado nas chamadas da API do Telegram.

As preferências ficam em `config.json`, o histórico e as filas em `radar.sqlite3` e o registro de atividades em `radar.log`. Falhas de inicialização podem deixar `falha_inicializacao.txt`. Ao depurar, use dados fictícios e uma pasta isolada definida por `RADAR_DOU_HOME`. Antes de anexar diagnósticos a uma issue pública, remova dados pessoais e mantenha o token, a configuração e o banco fora do Git.

## Android e referências

A compilação de depuração e a validação em aparelho estão descritas no [guia Android](../ANDROID.md). O workflow específico é manual.

- [Busca pública do DOU](https://www.in.gov.br/consulta/-/buscar/dou)
- [Catálogo nacional de concursos](https://concursosnobrasil.com/concursos/br/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Licença MIT](../LICENSE)
