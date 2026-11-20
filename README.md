# Radar DOU + Concursos

O Radar acompanha um nome ou expressão no Diário Oficial da União (DOU) e consulta concursos públicos no Brasil e no estado que você escolher. Ele consulta as fontes automaticamente e avisa pelo Telegram quando encontra novidades. A primeira consulta guarda o que já existe como referência para os próximos avisos.

## 1. Baixe e abra o Radar

Escolha seu dispositivo. Os links baixam o arquivo pronto para usar, sem precisar de Git, terminal ou conta no GitHub.

### No celular ou tablet Android

1. Toque em **[Baixar RadarDOU.apk](https://github.com/BrandonSaraiva/Dou-e-Concursos/releases/download/android-v1.2.2/RadarDOU.apk)** no próprio aparelho. O APK requer Android 8.0 ou superior e processador ARM64.
2. Abra **Downloads**, toque em **RadarDOU.apk** e escolha **Instalar**. Se o Android pedir, permita que o navegador ou gerenciador de arquivos instale apps dessa origem.
3. Abra **Radar DOU** e permita as notificações quando solicitado.

Se já tiver a versão 1.2.0 ou 1.2.1, desinstale-a antes de instalar a 1.2.2. A assinatura mudou e a desinstalação apaga os dados locais. [Guia Android](ANDROID.md)

### No computador Windows

1. Clique em **[Baixar RadarDOU.exe](https://github.com/BrandonSaraiva/Dou-e-Concursos/releases/latest/download/RadarDOU.exe)**. O executável é para Windows de 64 bits (x64) e já vem com Python.
2. Abra a pasta **Downloads** e dê dois cliques em **RadarDOU.exe** para abrir o aplicativo. [Guia Windows](docs/GUIA_WINDOWS.md)

## 2. Prepare o Telegram

1. Abra o [@BotFather](https://t.me/BotFather) no Telegram, toque em **Iniciar** e envie `/newbot`. Siga as instruções para dar um nome ao bot e escolher um nome de usuário que termine em `bot`.
2. Copie o **token** que o BotFather enviar. É o código completo, com números, dois-pontos e letras. Guarde-o como senha.
3. Abra o link do **seu bot** que o BotFather enviou e toque em **Iniciar** ou envie `/start`. É nessa conversa que você receberá os avisos.
4. Abra o [@userinfobot](https://t.me/userinfobot), toque em **Iniciar** e copie o número que aparecer no campo **Id**. Esse é o ID da sua conta.

## 3. Configure e teste os avisos

1. No Radar, preencha o **ID numérico do Telegram** e o **token do bot**. No Android, copie cada dado separadamente e use **Colar** ao lado do ID e **Colar token** ao lado do token. No Windows, use **Ctrl+V**.
2. Escolha o que acompanhar. Para o **DOU**, digite o nome ou expressão e escolha o intervalo de consulta. Para **concursos**, escolha seu estado pela sigla ou deixe **Somente nacional**.
3. Clique ou toque em **Salvar configurações**. Em seguida, use **Testar conexão com Telegram** no Windows ou **Testar envio para o Telegram** no Android. Confira se a mensagem chegou no chat do seu bot.
4. Se a mensagem chegou, selecione **Ativar radar**. Para conferir se ele está respondendo, envie `/status` no chat do seu bot.

Se os botões estiverem mais abaixo, role a tela. No Android, a notificação do Radar indica que o serviço está ativo e pode continuar com a tela apagada. No Windows, o Radar pode continuar na bandeja, perto do relógio, depois que você fechar a janela.

## O que o Radar acompanha

| Monitor | Como funciona |
| --- | --- |
| **Diário Oficial da União** | Pesquisa um nome ou expressão e verifica as publicações em um intervalo configurável. |
| **Concursos públicos** | Consulta o catálogo nacional e, opcionalmente, o da UF escolhida a cada hora. A lista estadual omite oportunidades que também estão na lista nacional. |
| **Telegram** | Mostra notícias, publicações e links em um chat privado. Use `/status`, `/verificar` e `/concursos` para consultar ou atualizar os dados. |

No Windows, você pode configurar o Radar para iniciar ao entrar na sua conta.

As fontes são a [pesquisa pública do DOU](https://www.in.gov.br/consulta/-/buscar/dou) e o portal editorial [Concursos no Brasil](https://concursosnobrasil.com/concursos/). O Radar é um projeto pessoal independente. Confira prazos e requisitos no edital do órgão. A disponibilidade do monitoramento depende da conexão, do dispositivo ativo e das fontes.

## Veja as respostas no Telegram

A [demonstração com capturas reais](docs/DEMONSTRACAO.md) mostra o menu, o status, as publicações do DOU, as listas nacional e estadual e as consultas manuais.

![Menu real do Radar no Telegram com o nome monitorado ocultado](assets/telegram-real/menu.png)

Ao compartilhar capturas do Radar, oculte tokens, IDs e dados monitorados.

Projeto distribuído sob a [licença MIT](LICENSE).
