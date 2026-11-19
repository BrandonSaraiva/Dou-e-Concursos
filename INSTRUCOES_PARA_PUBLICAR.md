# Comece aqui: publicar o Radar DOU como novo repositório público

## Passo 1: subir o código

1. Entre na **outra conta GitHub** e crie um repositório **público**, vazio (sem `README` automático).
2. Extraia o ZIP desta entrega. Envie o **conteúdo** da pasta extraída, incluindo os diretórios ocultos `.github/` e `.gitattributes`. Não envie um arquivo ZIP único.
3. Confirme que `main.py`, `README.md`, `radar_dou/` e `.github/workflows/build-windows.yml` aparecem na raiz do novo repositório.

## Passo 2: obter o EXE de verdade no repositório

1. Na aba **Actions**, selecione **Criar executável Windows**. O workflow dispara ao enviar os arquivos para a branch `main` ou `master`; se necessário, use **Run workflow**.
2. A automação cria uma máquina Windows, instala Python somente no ambiente de compilação, roda os testes, gera `RadarDOU.exe` com PyInstaller e **executa o `.exe --self-test`**.
3. Se tudo passar, ela **faz um commit automático de `downloads/RadarDOU.exe` e do manifesto `downloads/SOURCE_COMMIT.txt`**. Assim, o repositório passa a conter um EXE idêntico ao código daquele build. Há também o download em Artifacts.
4. Se falhar, abra a etapa vermelha nos logs de Actions e corrija o problema. O binário antigo não se atualiza sozinho; não o distribua como se fosse novo.

## Passo 3: quem vai usar no PC

Baixe `downloads/RadarDOU.exe` do novo repositório após uma compilação verde. Basta executar em **Windows 10/11 x64 compatível**, sem instalar Python nem VS Code. Preencha seus dados e toque em **Ativar radar**. O programa requer internet. Windows pode alertar sobre um EXE sem assinatura digital.

**O arquivo `.exe` não está dentro deste ZIP**, pois não é possível gerar um executável Windows nativo com PyInstaller no ambiente Linux usado para preparar a entrega. O Actions foi incluído justamente para produzir o binário verdadeiro antes de você divulgá-lo. A automação de APK está separada e também precisa ser executada para disponibilizar um instalador Android.

## Manutenção e colaboração

Conecte o novo repositório GitHub a esta conversa e me mande o endereço. Assim as próximas alterações podem ser feitas nos arquivos desse repositório (conforme permissões disponíveis). Se quiser compilar localmente em seu próprio Windows, dê dois cliques no `GERAR_EXE_WINDOWS.bat` na raiz e aguarde `downloads/RadarDOU.exe`. Esse modo local exige Python **somente para a pessoa que compila**, não para usuários finais.
