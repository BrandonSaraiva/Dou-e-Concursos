# Se o app nao abrir

1. Extraia o ZIP completo.
2. Clique duas vezes em `rodar_com_python.bat`.
3. Aguarde a instalacao inicial; a janela preta nao fecha sozinha.
4. Se houver erro, copie a mensagem exibida e informe qual e.

O `.bat` original iniciava `pythonw.exe` separadamente e ocultava os erros. A versao corrigida executa `python.exe` na propria janela para permitir diagnostico.

## Se a janela ainda fechar após as etapas 1/3, 2/3, 3/3

Execute `INICIAR_SEM_FECHAR.bat`, que abre uma janela persistente de diagnóstico e salva o erro em `diagnostico_inicio.txt`. **Não** dê dois cliques no antigo `rodar_com_python.bat` para diagnosticar uma falha, pois versões antigas ocultam a saída de erros.

Alternativa no VS Code: menu Terminal > Novo Terminal; digite `cmd /k INICIAR_SEM_FECHAR.bat` e pressione Enter. Envie as últimas linhas do arquivo `diagnostico_inicio.txt` após ocultar qualquer token.

## Novo: coleta de concursos

Se o Telegram conectar e o DOU funcionar mas o log mostrar “Tabela de concursos abertos ausente”, atualize `radar_dou/concursos.py` pelo arquivo de correção. Os dados continuam em `%APPDATA%\RadarDOU` e não precisam ser apagados. Reinicie o monitoramento e use `/conferirconcursos`.
