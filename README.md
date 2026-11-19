# Radar DOU + Concursos

Acompanhe um nome no Diário Oficial da União e concursos nacionais ou da sua UF. O Radar guarda o histórico no dispositivo e avisa pelo Telegram quando encontra novidades.

**[Baixar para Windows](https://github.com/BrandonSaraiva/Dou-e-Concursos/releases/latest)** · **[Guia ilustrado](docs/GUIA_WINDOWS.md)** · [Android experimental](ANDROID.md) · [Desenvolvimento](docs/DESENVOLVIMENTO.md)

![Diagrama do download Windows pelo GitHub Releases e da versão de teste pelo GitHub Actions](assets/tutorial-download-windows.png)

## Comece pelo Windows

1. Em **Releases → Assets**, baixe **RadarDOU.exe**. O executável é para Windows x64 e já inclui Python.
2. Abra o aplicativo, preencha seu ID numérico do Telegram e o token do bot criado no BotFather.
3. Escolha os monitores, clique em **Salvar configurações**, teste a conexão e selecione **Ativar radar**.

Se a primeira release ainda estiver em preparação, [baixe uma compilação de teste pelo Actions](docs/GUIA_WINDOWS.md#versão-de-teste-pelo-actions). O [guia ilustrado](docs/GUIA_WINDOWS.md) mostra como criar o bot, localizar seu ID, configurar o Radar e atualizar sem perder os dados.

## O que o Radar acompanha

| Monitor | Como funciona |
| --- | --- |
| **Diário Oficial da União** | Pesquisa um nome ou expressão e verifica as publicações em um intervalo configurável. |
| **Concursos públicos** | Consulta o catálogo nacional e, opcionalmente, o da UF escolhida a cada hora. A lista estadual omite oportunidades que também estão na lista nacional. |
| **Telegram** | Mostra notícias, publicações e links em um chat privado. Use `/status`, `/verificar` e `/concursos` para consultar ou atualizar os dados. |

A primeira consulta bem-sucedida de cada monitor ou região cria uma referência. Os avisos começam quando aparecem novidades. No Windows, o Radar pode continuar na bandeja após fechar a janela e iniciar ao entrar na sua conta.

As fontes são a [pesquisa pública do DOU](https://www.in.gov.br/consulta/-/buscar/dou) e o portal editorial [Concursos no Brasil](https://concursosnobrasil.com/concursos/). O Radar é um projeto pessoal independente. Confira prazos e requisitos no edital do órgão. A disponibilidade do monitoramento depende da conexão, do dispositivo ativo e das fontes.

## Por dentro do projeto

- **Interface e execução.** Tkinter no Windows e Kivy na versão experimental Android. O serviço agenda consultas e conversa com o Telegram.
- **Dados locais.** SQLite mantém o catálogo, o histórico de publicações e a fila de alertas. No Windows, o token é protegido pelo DPAPI da conta que o salvou.
- **Entrega.** O GitHub Actions testa o projeto e empacota o Windows com PyInstaller. Depois de validar um build da `main`, publica o executável, o SHA-256 e o commit de origem em Releases.

O [guia de desenvolvimento](docs/DESENVOLVIMENTO.md) detalha a arquitetura, os testes, a compilação e o processo de publicação. Para reportar um problema, use a [página de Issues](https://github.com/BrandonSaraiva/Dou-e-Concursos/issues) e omita tokens, IDs e dados monitorados.

Projeto distribuído sob a [licença MIT](LICENSE).
