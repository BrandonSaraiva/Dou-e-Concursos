"""Regera ilustrações originais do README. Todos os tokens/IDs são fictícios."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap

HERE=Path(__file__).resolve().parent
W,H=1180,550
COLORS={"bg":"#101725","panel":"#1c283d","panel2":"#24324b","text":"#f0f5ff","muted":"#b3c0d3","mint":"#45d6c9","blue":"#437bf4","pink":"#ff9aad","amber":"#f5cc87"}
FONT="/usr/share/fonts/truetype/lato/Lato-Regular.ttf"
BOLD="/usr/share/fonts/truetype/lato/Lato-Bold.ttf"

def f(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)

def base(title,subtitle):
    image=Image.new("RGB",(W,H),COLORS["bg"]);d=ImageDraw.Draw(image)
    d.rounded_rectangle((22,22,W-22,H-22),radius=24,outline="#31455f",width=2)
    d.text((62,56),title,font=f(40,True),fill=COLORS["text"])
    d.text((62,108),subtitle,font=f(23),fill=COLORS["muted"])
    return image,d

def card(d,rect,title,sub,bg=None):
    x1,y1,x2,y2=rect;d.rounded_rectangle(rect,radius=22,fill=bg or COLORS["panel"])
    d.text((x1+20,y1+21),title,font=f(25,True),fill=COLORS["text"])
    d.text((x1+20,y1+58),sub,font=f(19),fill=COLORS["muted"])

def textlines(d,x,y,lines,size=22,step=34,color=None,bold=False):
    for i,line in enumerate(lines):
        d.text((x,y+step*i),line,font=f(size,bold),fill=color or COLORS["text"])

def pill(d,box,text,fill=None,color=None,size=19):
    d.rounded_rectangle(box,radius=15,fill=fill or COLORS["panel2"])
    d.text((box[0]+15,box[1]+11),text,font=f(size,True),fill=color or COLORS["text"])

def done(image,name): image.save(HERE/name,optimize=True)

im,d=base("1. Crie seu bot com o BotFather","Exemplo ilustrativo do processo oficial no Telegram")
card(d,(60,171,535,467),"Conversa no Telegram","@BotFather • conta verificada")
pill(d,(86,256,264,314),"/newbot",COLORS["blue"])
pill(d,(86,328,490,388),"Meu Radar de Publicações",COLORS["panel2"])
pill(d,(86,400,487,453),"meu_radar_dou_bot",COLORS["panel2"])
card(d,(555,171,1120,467),"O que você precisa fazer","Siga as mensagens do BotFather")
textlines(d,585,266,["1. Envie /newbot", "2. Escolha o nome do seu bot", "3. Crie um @usuario terminado em bot", "4. Copie o token para o Radar DOU"],23,40)
pill(d,(570,476,1107,524),"TOKEN É SENHA: não compartilhe com ninguém",COLORS["panel2"],COLORS["pink"],18)
done(im,"tutorial-botfather.png")

im,d=base("2. Descubra seu ID no Telegram","O ID é um número de sua conta, diferente do token do bot")
card(d,(60,175,556,482),"Conversa com @userinfobot","Abra, toque em Iniciar e veja o número")
pill(d,(90,259,285,313),"/start",COLORS["blue"])
pill(d,(90,331,495,400),"Id: 123456789   (EXEMPLO)",COLORS["panel2"],COLORS["mint"],24)
card(d,(576,175,1120,482),"Preenchendo o aplicativo","Use o número da sua conta pessoal")
textlines(d,605,258,["Campo: Seu ID numérico do Telegram", "Exemplo fictício: 123456789", "Não use seu @usuario ou telefone.", "Inicie também o SEU bot (/start)."],23,42)
done(im,"tutorial-seu-id.png")

im,d=base("3. Gere o executável no GitHub","O projeto já inclui uma automação para criar o aplicativo Windows")
for x,n,t,desc in [(55,"01","Novo repositório","Publicar como público"),(342,"02","Abra Actions","No repositório"),(629,"03","Executar workflow","Criar executável Windows"),(916,"04","Baixar ZIP","RadarDOU-Windows")]:
    d.rounded_rectangle((x,196,x+252,468),radius=20,fill=COLORS["panel"])
    d.ellipse((x+20,218,x+78,276),fill=COLORS["blue"])
    d.text((x+32,233),n,font=f(21,True),fill="white")
    d.text((x+18,299),t,font=f(23,True),fill=COLORS["text"])
    for i,line in enumerate(textwrap.wrap(desc,width=19)):
        d.text((x+18,351+i*28),line,font=f(19),fill=COLORS["muted"])
    if x<916:
        d.text((x+244,484),"›",font=f(42,True),fill=COLORS["mint"])
done(im,"tutorial-github-actions.png")

im,d=base("Como o Radar DOU funciona","Consultas verificadas, histórico persistente e alertas só de novidades")
boxes=[(55,"1. BUSCA NO DOU",["Consulta pública","Contagem e metadados","Validação de páginas"]),
       (438,"2. BASE LOCAL",["SQLite no computador","Referência da 1ª busca","URLs sem duplicatas"]),
       (821,"3. TELEGRAM",["Avisa só novidades","Mensagens com link","Fila de reenvio"])]
for x,t,ls in boxes:
    d.rounded_rectangle((x,188,x+306,465),radius=24,fill=COLORS["panel"])
    d.rounded_rectangle((x+16,207,x+290,260),radius=13,fill=COLORS["panel2"])
    d.text((x+27,220),t,font=f(22,True),fill=COLORS["mint"])
    textlines(d,x+23,310,ls,23,40)
for x in (366,749):
    d.text((x,290),"→",font=f(55,True),fill=COLORS["blue"])
done(im,"fluxo.png")

# Ilustração de referência, não captura de tela do APK compilado.
im=Image.new("RGB",(1180,730),COLORS["bg"]); d=ImageDraw.Draw(im)
d.text((50,41),"Radar DOU no Android",font=f(43,True),fill=COLORS["text"])
d.text((50,101),"Exemplo ilustrativo de como a interface mobile será organizada",font=f(23),fill=COLORS["muted"])
d.rounded_rectangle((62,169,502,700),radius=35,fill="#030c19",outline=COLORS["muted"],width=3)
d.rounded_rectangle((79,190,485,681),radius=18,fill=COLORS["panel"])
d.text((103,212),"RADAR DOU",font=f(30,True),fill=COLORS["mint"])
d.text((103,251),"● Monitoramento ativo",font=f(19),fill=COLORS["mint"])
for i,(caption,content) in enumerate([("NOME MONITORADO","Maria da Silva"),("SEU ID NO TELEGRAM","123456789"),("TOKEN DO BOT","•••••••••••••••••")]):
    y=297+i*77
    d.text((103,y),caption,font=f(17,True),fill=COLORS["muted"])
    d.rounded_rectangle((101,y+27,457,y+66),radius=8,fill=COLORS["panel2"])
    d.text((114,y+35),content,font=f(18),fill=COLORS["text"])
d.rounded_rectangle((103,539,455,593),radius=12,fill=COLORS["blue"])
d.text((148,554),"ATIVAR RADAR",font=f(23,True),fill=COLORS["text"])
d.text((105,621),"Verificar agora   •   Desligar",font=f(18),fill=COLORS["muted"])
card(d,(543,173,1122,355),"Monitoramento sem tela aberta","Serviço em primeiro plano no Android")
textlines(d,571,276,["Notificação de serviço ativo", "Bot recebe comandos via Telegram"],22,39,color=COLORS["mint"])
card(d,(543,375,1122,673),"O que aparece nos logs?","Mensagens guardadas no celular")
textlines(d,569,479,["11:00  Conectando ao Telegram...", "11:00  Bot autenticado", "11:01  Consultando DOU...", "11:02  7 resultados, 0 novos", "12:02  Próxima consulta programada"],20,33,color=COLORS["mint"])
done(im,"interface-android.png")

im,d=base("4. Gerar o APK com GitHub Actions","Sem Android Studio ou ferramentas de programação no seu computador")
steps=[("1", "Repositório", "Extraia o ZIP e envie os arquivos"),
       ("2", "Actions", "Abra Criar APK Android"),
       ("3", "Run workflow", "Execute a compilação"),
       ("4", "Artifacts", "Baixe RadarDOU-Android-APK")]
for i,(n,t,sub) in enumerate(steps):
    x=50+i*286
    d.rounded_rectangle((x,190,x+268,460),radius=20,fill=COLORS["panel"])
    d.ellipse((x+24,212,x+82,270),fill=COLORS["blue"])
    d.text((x+44,226),n,font=f(27,True),fill=COLORS["text"])
    d.text((x+22,298),t,font=f(24,True),fill=COLORS["text"])
    for j,line in enumerate(textwrap.wrap(sub,25)):
        d.text((x+22,360+j*28),line,font=f(18),fill=COLORS["muted"])
done(im,"tutorial-apk-github.png")
