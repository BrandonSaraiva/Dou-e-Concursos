# Radar DOU no Android

O instalador Android está em compilação. [Acompanhar no GitHub Actions](https://github.com/BrandonSaraiva/Dou-e-Concursos/actions/workflows/build-android.yml)

## Baixe e instale

1. Quando **RadarDOU.apk** aparecer em [Releases](https://github.com/BrandonSaraiva/Dou-e-Concursos/releases), baixe o arquivo no celular. O pacote é para Android 8.0 ou superior em aparelhos ARM64.
2. Abra o APK em **Downloads**. Se o Android pedir autorização para instalar apps dessa origem, confirme que o arquivo veio deste GitHub antes de autorizar.
3. Abra **Radar DOU** e permita as notificações quando solicitado. A notificação do monitoramento aparece depois que você ativa o Radar.
4. Siga os passos para [criar o bot](docs/GUIA_WINDOWS.md#2-crie-seu-bot-no-telegram) e [descobrir seu ID](docs/GUIA_WINDOWS.md#3-descubra-seu-id-numérico). Envie `/start` no chat do seu próprio bot antes de testar o envio.

## Configure e teste os alertas

1. Em **Seu ID numérico no Telegram**, digite o número da sua conta. Em **Token do bot fornecido pelo @BotFather**, cole o token completo.
2. Marque **Diário Oficial da União** se quiser acompanhar um nome e preencha **Nome ou expressão que o DOU deve acompanhar**. **Intervalo entre consultas** controla essa pesquisa.
3. Marque **Concursos públicos abertos** se quiser acompanhar concursos. Em **UF dos concursos (além dos nacionais)**, escolha uma UF ou deixe **Somente nacional**. O Radar consulta concursos a cada 60 minutos.
4. Toque em **SALVAR CONFIGURAÇÕES** e em **TESTAR ENVIO PARA O TELEGRAM**. Confirme que recebeu a mensagem no chat do seu bot.
5. Toque em **ATIVAR RADAR**. Na primeira consulta bem-sucedida, o Radar guarda os resultados existentes como referência. Depois, uma publicação ou oportunidade inédita pode gerar alerta.
6. Consulte o **Registro de atividades** ou toque em **CONFERIR AGORA**. No Telegram, envie `/status`, `/concursos` ou `/ultimas`, conforme os monitores ativos.

Você pode sair da tela e continuar recebendo alertas enquanto o serviço permanecer ativo e conectado. Se o Android encerrar o serviço por economia de bateria, verifique as opções em **Configurações → Aplicativos → Radar DOU → Bateria**. Os nomes dos menus variam por aparelho. Depois de reiniciar o celular, abra o app e toque em **ATIVAR RADAR**. Use **DESLIGAR** antes de alterar a configuração.

## Confira seu primeiro teste

- Depois de ativar o Radar, abra o Telegram e envie `/status` e `/concursos` no chat do seu bot.
- Volte à tela inicial do celular e verifique se a notificação do Radar continua visível. Use um bot por instalação ativa para evitar conflito com o Radar do Windows.
- Se algo falhar, abra o **Registro de atividades** e informe o erro sem compartilhar seu token ou ID.

[Voltar ao projeto](README.md) · [Ver capturas reais do Telegram](https://github.com/BrandonSaraiva/Dou-e-Concursos/blob/main/docs/DEMONSTRACAO.md)
