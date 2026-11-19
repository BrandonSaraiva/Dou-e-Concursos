# Executável pronto do Windows

O workflow **Criar executável Windows** gera automaticamente `RadarDOU.exe` no Windows a partir do código da própria revisão do repositório, roda um autoteste no executável e coloca o arquivo aqui, em `downloads/RadarDOU.exe`. Ele também publica um artefato para download na execução do Actions.

**O arquivo `.exe` não faz parte do ZIP de origem desta entrega**, pois a compilação tem que ocorrer em um ambiente Windows. Na primeira publicação no seu repositório, aguarde a execução do workflow em **Actions**. Após a compilação bem-sucedida, um commit automático adicionará o executável nesta pasta. Esse executável funciona sem Python instalado em PCs Windows 10/11 x64 compatíveis. Se o workflow falhar, não haverá um executável novo: consulte os logs e não distribua uma versão antiga.

- `SOURCE_COMMIT.txt`: commit de código-fonte exato usado na compilação.
- `SHA256SUMS.txt`: hash SHA-256 do executável, para verificar a integridade.

**Atenção:** o binário precisa ser compilado de novo após qualquer modificação do código; o workflow faz isso automaticamente quando há um push relevante. Binários com mais de 100 MB não podem ser versionados diretamente no GitHub e, nesse caso, o artefato do workflow será a alternativa.
