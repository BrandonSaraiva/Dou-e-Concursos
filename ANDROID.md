# Radar DOU no Android

O Android está em fase experimental. O projeto oferece o código-fonte e um workflow para gerar um APK de depuração. A instalação e o funcionamento em aparelho real ainda precisam ser validados. Para usar a versão distribuída para computador, consulte o [guia para Windows](docs/GUIA_WINDOWS.md).

## Se você já recebeu um APK

1. Confira se o arquivo veio de uma compilação que você reconhece. Se recebeu um ZIP do GitHub Actions, extraia o arquivo `.apk`.
2. Envie o APK para o aparelho e toque no arquivo. Se o sistema solicitar permissão para instalar apps dessa origem, confira a origem antes de confirmar.
3. Abra **Radar DOU** e permita as notificações quando o Android solicitar. A notificação indica que o serviço está em execução.
4. Siga os passos para [criar o bot](docs/GUIA_WINDOWS.md#2-crie-seu-bot-no-telegram) e [descobrir seu ID numérico](docs/GUIA_WINDOWS.md#3-descubra-seu-id-numérico). Envie `/start` ao seu próprio bot antes de testar o envio.

O perfil de compilação atual usa **ARM64**, com Android mínimo configurado na API 26 e alvo na API 35. Esses valores descrevem a configuração de compilação. A compatibilidade depende dos testes no aparelho. [Configuração do Buildozer](buildozer.spec)

## Configure e teste os alertas

1. Em **Seu ID numérico no Telegram**, digite o número da sua conta. Em **Token do bot fornecido pelo @BotFather**, cole o token completo.
2. Marque **Diário Oficial da União** se quiser acompanhar um nome e preencha **Nome ou expressão que o DOU deve acompanhar**. **Intervalo entre consultas** controla essa pesquisa.
3. Marque **Concursos públicos abertos** se quiser acompanhar concursos. Em **UF dos concursos (além dos nacionais)**, escolha uma UF ou deixe **Somente nacional**. O Radar consulta concursos a cada 60 minutos.
4. Toque em **SALVAR CONFIGURAÇÕES** e em **TESTAR ENVIO PARA O TELEGRAM**. Confirme que recebeu a mensagem no chat do seu bot.
5. Toque em **ATIVAR RADAR**. Na primeira consulta bem-sucedida, o Radar guarda os resultados existentes como referência. Depois, uma publicação ou oportunidade inédita pode gerar alerta.
6. Consulte o **Registro de atividades** ou toque em **CONFERIR AGORA**. No Telegram, envie `/status`, `/concursos` ou `/ultimas`, conforme os monitores ativos.

Você pode sair da tela e continuar recebendo alertas enquanto o serviço permanecer ativo e conectado. Se o Android encerrar o serviço por economia de bateria, verifique as opções em **Configurações → Aplicativos → Radar DOU → Bateria**. Os nomes dos menus variam por aparelho. Depois de reiniciar o celular, abra o app e toque em **ATIVAR RADAR**. Use **DESLIGAR** antes de alterar a configuração.

## Gere um APK para teste

Quem mantém o repositório ou tem acesso de escrita pode iniciar a compilação manual no GitHub. Quem só tem acesso de leitura pode baixar um artefato existente, desde que esteja conectado à conta e que o artefato ainda esteja disponível. [Execuções manuais no GitHub](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow) · [Download de artefatos](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

1. Abra **Actions** no repositório que contém o workflow e selecione **Criar APK Android** na barra lateral.
2. Clique em **Run workflow**, selecione `main` e confirme em **Run workflow**. O GitHub exige que o workflow já esteja disponível na branch padrão.
3. Quando o job terminar com sucesso, abra a execução e clique em **RadarDOU-Android-APK** na seção **Artifacts**.
4. Extraia o ZIP. O instalador é o arquivo `.apk` que estiver dentro dele. O workflow guarda o artefato por 30 dias. [Workflow Android](.github/workflows/build-android.yml)

Para compilar localmente em Linux ou WSL 2, siga a instalação do Buildozer para sua distribuição e ative o ambiente Python indicado na documentação. No WSL, mantenha o checkout no sistema de arquivos Linux. Na pasta que contém `buildozer.spec`, rode o comando abaixo. Se a compilação passar, procure o APK em `bin/`. [Instalação oficial do Buildozer](https://buildozer.readthedocs.io/en/stable/installation/)

```bash
buildozer android debug
```

## Validação em aparelho

Use um bot exclusivo para teste ou pare o Radar no outro dispositivo antes de ativá-lo no Android. Dois processos lendo os comandos do mesmo bot podem entrar em conflito.

1. Confirme o envio de teste no Telegram e a notificação do serviço após a ativação.
2. Consulte o DOU, quando ativo, e as listas de concursos nacionais e da UF selecionada. Confira os números no painel e os links recebidos.
3. Vá para a tela inicial do Android e deixe o telefone em espera. Teste `/status` novamente e reabra o Radar para confirmar a atividade registrada.
4. Toque em **DESLIGAR**, aguarde a parada e confirme que o serviço deixou de responder. Reinicie o aparelho e verifique a ativação manual.
5. Em caso de falha, consulte **Registro de atividades**. Para depuração com o aparelho conectado, use `adb logcat` e procure mensagens de `python`, `AndroidRuntime` ou `ServiceRadar`.

## Serviço e dados

A tela Kivy salva as preferências e envia pedidos ao serviço. `android_service.py` roda em processo separado, atualiza o sinal de atividade e usa o mesmo serviço de monitoramento do Windows. O serviço Android está configurado como `specialUse` e começa por ação do usuário. Uma eventual publicação na Google Play requer revisão da declaração do subtipo no manifesto e das condições de distribuição. [Serviços do python-for-android](https://python-for-android.readthedocs.io/en/latest/services.html) · [Tipos de serviço em primeiro plano](https://developer.android.com/develop/background-work/services/fgs/service-types)

No Android, o Radar consulta as fontes por requisições HTTPS. Se receber uma página bloqueada ou incompleta, registra a falha e mantém o histórico anterior. As configurações, o token e o banco ficam no armazenamento privado do app. O token usa a proteção dessa pasta, sem criptografia adicional pelo Android Keystore. Desinstalar o app remove esses dados locais.

[Voltar ao projeto](README.md) · [Guia de desenvolvimento](docs/DESENVOLVIMENTO.md)
