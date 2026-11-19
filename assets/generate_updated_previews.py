"""Ilustrações autorais, NÃO capturas de aplicativo instalado."""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ROOT = Path(__file__).parent
REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

def font(size,bold=False): return ImageFont.truetype(BOLD if bold else REG,size)
def box(d,rect,color,r=14,stroke=None):
    d.rounded_rectangle(rect,radius=r, fill=color, outline=stroke, width=2 if stroke else 1)
def txt(d,xy,text,color='#edf4ff',size=20,bold=False):
    d.text(xy,text,font=font(size,bold), fill=color)
def line(d,xy,text,maxlen=42,size=18,color='#a9b9d1'):
    words=text.split();cur='';y=xy[1]
    for w in words:
        draft=(cur+' '+w).strip()
        if len(draft)>maxlen and cur:
            txt(d,(xy[0],y),cur,color,size);y+=size+7;cur=w
        else:cur=draft
    if cur:txt(d,(xy[0],y),cur,color,size)
    return y

im=Image.new('RGB',(1460,850),'#0e1421'); d=ImageDraw.Draw(im)
# window chrome
box(d,(35,35,1425,815),'#182336',24,'#34445f')
box(d,(35,35,1425,107),'#202f49',23)
for k,c in enumerate(['#f98f91','#facb82','#70d6be']):
    d.ellipse((64+k*29,64,78+k*29,78),fill=c)
txt(d,(182,57),'RADAR DOU  +  CONCURSOS',size=25,bold=True)
box(d,(1126,52,1388,91),'#164d44',15)
txt(d,(1155,61),'●  Radar ligado',size=18,color='#88f4d5',bold=True)
# left
box(d,(60,128,568,788),'#1f2b40',22)
txt(d,(84,151),'01  SEUS MONITORAMENTOS',size=21,bold=True,color='#60ded1')
txt(d,(84,204),'Nome para acompanhar no DOU',size=19)
box(d,(84,236,544,284),'#101725',8,'#364b61')
txt(d,(100,249),'Maria da Silva',size=19)
txt(d,(84,305),'ID do Telegram',size=18)
box(d,(84,332,544,381),'#101725',8,'#364b61')
txt(d,(100,345),'123456789 (fictício)',size=17)
txt(d,(84,400),'Token do bot',size=18)
box(d,(84,428,544,477),'#101725',8,'#364b61')
txt(d,(100,440),'••••••••••••••••••••••••',size=21)
txt(d,(84,492),'MONITORAMENTOS',size=18,color='#5ce3d4',bold=True)
for y,word in [(523,'Acompanhar nome no DOU'),(563,'Acompanhar concursos abertos')]:
    box(d,(84,y,110,y+25),'#4b85ef',5)
    txt(d,(90,y),'✓','#ffffff',size=18,bold=True)
    txt(d,(122,y-1),word,size=17)
txt(d,(84,608),'Estado para concursos',size=18)
box(d,(84,636,544,685),'#101725',8,'#364b61')
txt(d,(102,650),'DF  ·  Distrito Federal',size=19)
box(d,(84,715,544,765),'#3e77ee',12)
txt(d,(179,729),'SALVAR CONFIGURAÇÕES',size=18,bold=True)
# right
box(d,(587,128,1398,788),'#1f2b40',22)
txt(d,(619,153),'02  CENTRAL DE MONITORAMENTO',size=21,bold=True,color='#60ded1')
for i,(cap,value) in enumerate([('RESULTADOS DOU','7'),('NACIONAIS','1'),('ESTADUAIS DF','5')]):
    x=619+i*255
    box(d,(x,196,x+232,302),'#293b55',15)
    txt(d,(x+15,213),cap,size=16,color='#bccbe0')
    txt(d,(x+15,240),value,size=37,bold=True)
box(d,(619,329,899,385),'#3d79ea',11)
txt(d,(678,344),'▶  ATIVAR RADAR',size=20,bold=True)
box(d,(913,329,1127,385),'#30415b',11)
txt(d,(964,346),'■  DESLIGAR',size=19)
box(d,(1140,329,1365,385),'#30415b',11)
txt(d,(1166,346),'↻  CONFERIR',size=19)
txt(d,(620,418),'REGISTRO DE ATIVIDADES',size=18,bold=True)
box(d,(619,451,1366,759),'#0f1726',12)
logs=[
 ('11:01:10','✓','Telegram autenticado com sucesso'),
 ('11:01:13','✓','DOU: 7 publicações encontradas'),
 ('11:01:18','✓','Concursos BR: 1 oportunidade aberta'),
 ('11:01:22','✓','Concursos DF: 5 oportunidades abertas'),
 ('11:01:23','✓','Referência inicial salva, sem alertas antigos'),
 ('12:01:20','+','Concursos DF: 1 nova oportunidade'),
 ('12:01:21','✓','Alerta entregue ao Telegram'),
]
for i,(clock,marker,msg) in enumerate(logs):
    y=476+i*38
    txt(d,(641,y),clock,size=17,color='#8291ab')
    txt(d,(747,y),marker,size=18,color='#51dec4' if marker=='✓' else '#ffcb77',bold=True)
    txt(d,(785,y),msg,size=17,color='#d9e7f9')
im.save(ROOT/'interface.png')

# Android preview
im=Image.new('RGB',(880,1120),'#0e1421');d=ImageDraw.Draw(im)
box(d,(175,29,704,1090),'#111a2a',42,'#42526a')
box(d,(194,62,685,1060),'#1b2940',33)
box(d,(332,41,550,61),'#32435b',11)
txt(d,(232,100),'RADAR DOU + CONCURSOS',size=25,bold=True)
txt(d,(233,143),'Alertas nacionais e por estado',size=17,color='#afc4dc')
box(d,(231,186,651,232),'#1c4a45',12)
txt(d,(250,199),'●  Monitoramento ativado',size=17,color='#78eccd',bold=True)
txt(d,(231,265),'01  CONFIGURAÇÕES',size=21,bold=True)
for y,label,content in [(308,'Nome monitorado no DOU','Maria da Silva'),
                        (416,'ID do Telegram','123456789'),
                        (524,'Token do BotFather','••••••••••••••••')]:
    txt(d,(231,y),label,size=16)
    box(d,(231,y+31,651,y+82),'#101725',11,'#38516b')
    txt(d,(246,y+47),content,size=17)
txt(d,(231,630),'Monitoramentos',size=19,bold=True)
for y,title in [(671,'✓  DOU'),(709,'✓  Concursos abertos')]:
    txt(d,(236,y),title,size=19,color='#8deed6')
txt(d,(231,753),'UF adicional',size=16)
box(d,(231,781,651,834),'#101725',11,'#38516b')
txt(d,(248,795),'DF  ·  Distrito Federal',size=18)
box(d,(231,861,651,914),'#3e79ed',11)
txt(d,(337,875),'ATIVAR RADAR',size=19,bold=True)
txt(d,(231,933),'Nacionais: 1    |    DF: 5',size=18,color='#7ad7c7')
txt(d,(231,969),'✓  Consultas e logs separados',size=16,color='#b7c9df')
txt(d,(233,1012),'Prévia ilustrativa  •  Android',size=13,color='#8196ae')
im.save(ROOT/'interface-android.png')

# Telegram example, two panel screens
im=Image.new('RGB',(1300,810),'#0f1725');d=ImageDraw.Draw(im)
txt(d,(52,35),'TELEGRAM   ·   MENU INTERATIVO DE CONCURSOS',size=29,bold=True)
txt(d,(53,80),'Exemplo ilustrativo com dados fictícios. Links e contadores reais variam por consulta.',size=17,color='#a9bacf')
for a,b in [(64,622),(681,1239)]:
    box(d,(a,128,b,769),'#19273a',22,'#435773')
    box(d,(a+17,151,b-17,210),'#23415b',15)
    txt(d,(a+39,166),'◉  Radar DOU',size=22,bold=True)
    txt(d,(b-154,169),'online',size=16,color='#9bdacb')
# left menu
box(d,(95,248,588,573),'#243950',17)
for y,s,size,bold in [(270,'CENTRAL DE CONCURSOS',21,True),
                      (323,'Nacionais: 12 disponíveis',19,False),
                      (363,'Distrito Federal: 8 disponíveis',19,False),
                      (410,'1 aviso pendente',18,False),
                      (456,'Atualização a cada 60 minutos',17,False),
                      (509,'Escolha uma lista abaixo:',18,False)]:
    txt(d,(118,y),s,size=size,bold=bold)
for x1,x2,t in [(95,332,'Ver nacionais'),(345,588,'Ver DF')]:
    box(d,(x1,598,x2,658),'#31516e',12)
    txt(d,(x1+15,615),t,size=18)
box(d,(95,678,588,732),'#31516e',12)
txt(d,(193,693),'↻ Conferir concursos',size=19)
# right list
box(d,(710,245,1209,610),'#243950',17)
txt(d,(738,265),'CONCURSOS · DF',size=22,bold=True)
txt(d,(738,307),'8 oportunidades  •  página 1 de 2',size=17,color='#d4e4f5')
txt(d,(738,345),'01.  DPDF',size=19,bold=True,color='#95d9ff')
txt(d,(740,376),'707 vagas',size=17)
txt(d,(740,409),'02.  ANCINE',size=19,bold=True,color='#95d9ff')
txt(d,(740,440),'Várias vagas',size=17)
txt(d,(740,473),'03.  IGESDF',size=19,bold=True,color='#95d9ff')
txt(d,(740,504),'Cadastro reserva',size=17)
txt(d,(738,556),'Toque no órgão para abrir a notícia.',size=16,color='#b7c7d9')
box(d,(710,632,949,691),'#31516e',10)
txt(d,(770,650),'◀  Anterior',size=18)
box(d,(966,632,1209,691),'#31516e',10)
txt(d,(1039,650),'Próxima  ▶',size=18)
box(d,(710,708,1209,750),'#31516e',9)
txt(d,(798,716),'Nacional       ·       Início',size=17)
im.save(ROOT/'telegram-concursos.png')
print('created:',*[p.name for p in [ROOT/'interface.png', ROOT/'interface-android.png', ROOT/'telegram-concursos.png']])

# Arquitetura com duas fontes independentes
im=Image.new('RGB',(1460,570),'#0f1725'); d=ImageDraw.Draw(im)
box(d,(25,20,1435,545),'#111e32',25,'#33516c')
txt(d,(65,51),'Como o Radar DOU + Concursos funciona',size=37,bold=True)
txt(d,(65,110),'Duas consultas independentes  •  Uma base local  •  Alertas pelo Telegram',size=20,color='#a8bed3')
for y,title,subtitle in [(179,'01 · DIÁRIO OFICIAL','Nome ou expressão  |  busca exata'),
                          (313,'02 · CONCURSOS','Nacionais  +  UF selecionada')]:
    box(d,(70,y,455,y+113),'#253851',19)
    txt(d,(95,y+21),title,size=22,bold=True,color='#65e0d0')
    txt(d,(95,y+65),subtitle,size=16,color='#e4effa')
box(d,(544,225,917,375),'#253851',19)
txt(d,(583,248),'SQLite · histórico',size=24,bold=True,color='#65e0d0')
txt(d,(583,294),'Primeira consulta é referência',size=17)
txt(d,(583,327),'URLs inéditas viram novidades',size=17)
box(d,(1000,225,1387,375),'#253851',19)
txt(d,(1030,246),'Telegram · alertas',size=24,bold=True,color='#65e0d0')
txt(d,(1030,291),'Botões Nacional / UF',size=18)
txt(d,(1030,328),'Detalhes, vagas e links',size=18)
# connections
for y in (235,366):
    d.line((456,y,508,y,508,280,544,280),fill='#628ff0',width=5)
d.line((919,298,995,298),fill='#628ff0',width=6)
d.polygon([(997,298),(978,286),(978,310)],fill='#628ff0')
txt(d,(72,475),'Falha de site não apaga dados nem impede a consulta da outra fonte.',size=19,color='#b5cadc')
im.save(ROOT/'fluxo.png')
