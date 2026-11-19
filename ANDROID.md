# Android: notas técnicas e limitações

Este projeto possui uma versão nativa Android empacotada em APK com **Kivy** e **python-for-android**.

A interface (`radar_dou/android_ui.py`) apenas salva as configurações, mostra os logs e envia comandos. O processamento real acontece no Android Foreground Service (`android_service.py`), em outro processo. O serviço solicita ao Android uma notificação de execução contínua, roda o mesmo `RadarService` da versão Windows e atualiza um heartbeat para a interface.

O Buildozer declara `services = Radar:android_service.py:foreground:sticky:foregroundServiceType=specialUse`. O aplicativo pede permissões `INTERNET`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_SPECIAL_USE`, `POST_NOTIFICATIONS` e `WAKE_LOCK`. A declaração de serviço de uso especial se destina a monitoramento contínuo acionado explicitamente pelo usuário. Antes de publicar na Google Play, verifique as regras de elegibilidade e declaração de finalidade dos serviços, incluindo a propriedade de subtipo no manifesto, e faça os testes com a versão Android alvo.

## Testar em aparelho real

1. Execute `Criar APK Android` na aba Actions.
2. Se o APK for gerado, instale manualmente em um aparelho Android (preferencialmente Android 13–16).
3. Conceda notificações, defina bateria sem restrições e configure um bot de teste.
4. Clique em **Testar envio** e confirme a mensagem no Telegram.
5. Clique em **Ativar radar** e confirme a notificação persistente e os eventos no log.
6. Use `/status`, `/verificar` e `/ultimas` no bot e confira os resultados.
7. Feche a interface com Home, deixe o telefone em espera e teste os comandos novamente após algumas horas.
8. Reabra a interface para conferir o último heartbeat; use **Desligar** e confirme a parada.
9. Desligue e ligue o aparelho: o aplicativo **não** reinicia sozinho após reboot; ative manualmente.
10. Em caso de falhas na compilação, consulte o log de **Actions**; em falha de execução, use `adb logcat` (filtro `python`, `AndroidRuntime`, `ServiceRadar`) e os logs internos do app.

## Ressalvas

- Não foi fornecido APK pré-compilado: somente o código-fonte e o workflow para geração. É necessário compilar e validar em dispositivo real.
- O Android pode encerrar processos por restrições de bateria. O serviço não é garantia absoluta de disponibilidade 24/7.
- Não há Chromium/Playwright embutido no APK. O scraper móvel usa `requests`; se o DOU bloquear a resposta, verá o problema nos logs e o histórico será mantido.
- O Android armazena credenciais em pasta privada do app. **O arquivo de configuração não utiliza Android Keystore** nesta versão e não deve ser extraído/compartilhado.
- Em Android 15+, serviços classificados como `dataSync` têm limite de execução, por isso o projeto declara `specialUse`. Essa classificação exige revisão caso o aplicativo venha a ser distribuído em lojas.
- Não ative o mesmo bot em várias instalações ao mesmo tempo: a leitura de `getUpdates` do Telegram pode entrar em conflito.

Fontes: [serviços python-for-android](https://python-for-android.readthedocs.io/en/latest/services.html), [Android Foreground Services](https://developer.android.com/develop/background-work/services/fgs/declare), [tipos de serviço](https://developer.android.com/develop/background-work/services/fgs/service-types).

## Concursos nacionais e estaduais na versão Android

A partir da versão 1.2, a tela Android permite marcar **Monitorar concursos abertos**, escolher a **UF** (ou **Somente nacional**) e manter essa seleção no armazenamento privado do aplicativo. O serviço Android executa o mesmo coletor e banco SQLite que o Windows, com checagem de concursos a cada **60 minutos**. A interface mostra a última quantidade registrada de concursos nacionais e estaduais; os logs detalham sucessos e falhas por categoria.

No Telegram, use `/concursos` para abrir o menu de listas, `/nacionais` e `/estaduais` para consultar oportunidades já salvas, ou `/conferirconcursos` para pedir nova coleta. A primeira consulta de cada UF cria a referência, sem disparar avisos antigos. Os próximos concursos com URL inédita podem gerar alertas mesmo com a interface Kivy fechada, **desde que o serviço Android continue em execução**.

Se o site Concursos no Brasil alterar as tabelas ou bloquear o celular, o serviço registra o problema e preserva o histórico. O aplicativo **não confirma inscrições abertas no edital oficial**: ele lê a classificação do portal jornalístico e fornece o link da matéria.
