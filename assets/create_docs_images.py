"""Gera as ilustrações do guia sem capturas ou dados de contas reais."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ASSETS = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1200, 610
BACKGROUND = "#101725"
PANEL = "#192335"
CHIP = "#253650"
BORDER = "#354a64"
TEXT = "#edf4ff"
MUTED = "#b6c7df"
TEAL = "#66e1d3"


def font(size, bold=False):
    windows = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(windows, size)
    except OSError:
        linux = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(linux, size)


def label(draw, position, content, size, color=TEXT, bold=False):
    draw.text(position, content, fill=color, font=font(size, bold), anchor="lt")


def panel(draw, rect, fill=PANEL):
    draw.rounded_rectangle(rect, radius=18, fill=fill, outline=BORDER, width=1)


def canvas(kicker, title):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    label(draw, (48, 31), kicker, 24, TEAL, bold=True)
    label(draw, (48, 65), title, 51, bold=True)
    label(draw, (48, 565), "RADAR DOU + CONCURSOS   /   GUIA ILUSTRADO", 21, MUTED, bold=True)
    return image, draw


def path(draw, x, y, steps):
    for index, (content, width) in enumerate(steps):
        panel(draw, (x, y, x + width, y + 56), CHIP)
        label(draw, (x + 16, y + 15), content, 24, bold=True)
        x += width + 14
        if index < len(steps) - 1:
            label(draw, (x, y + 13), "→", 27, TEAL)
            x += 43


def download():
    image, draw = canvas("WINDOWS X64", "Baixe o Radar DOU no GitHub")
    panel(draw, (48, 144, 1152, 335))
    label(draw, (74, 166), "Versão publicada", 32, bold=True)
    path(draw, 74, 219, [("Releases", 166), ("Assets", 140), ("RadarDOU.exe", 223)])
    label(draw, (74, 290), "Baixe e abra o arquivo .exe.", 25, MUTED)
    panel(draw, (48, 350, 1152, 542))
    label(draw, (74, 372), "Prévia para teste", 32, bold=True)
    path(draw, 74, 425, [
        ("Actions", 115), ("Artifacts", 136), ("RadarDOU-Windows-x64", 320),
        ("Extrair Tudo…", 198),
    ])
    label(draw, (74, 496), "Entre no GitHub para baixar o ZIP. Abra RadarDOU.exe na pasta extraída.", 25, MUTED)
    image.save(ASSETS / "tutorial-download-windows.png", optimize=True)


def botfather():
    image, draw = canvas("TELEGRAM", "Crie seu bot com o BotFather")
    panel(draw, (48, 144, 592, 448))
    label(draw, (74, 170), "1   Abra o @BotFather", 32, bold=True)
    label(draw, (74, 221), "Confira o selo da conta oficial.", 26, MUTED)
    path(draw, 74, 267, [("Iniciar", 124), ("/newbot", 151)])
    label(draw, (74, 347), "Escolha um nome para o bot.", 26)
    label(draw, (74, 388), "O nome de usuário termina em bot.", 26)

    panel(draw, (608, 144, 1152, 448))
    label(draw, (635, 170), "2   Copie o token recebido", 32, bold=True)
    label(draw, (635, 221), "Copie a sequência completa.", 26, MUTED)
    panel(draw, (634, 267, 1125, 323), CHIP)
    label(draw, (656, 283), "••••••••••••••••••••", 24, TEAL, bold=True)
    label(draw, (635, 347), "Cole no Radar DOU, no campo", 26)
    label(draw, (635, 388), "Token do seu bot (BotFather).", 26, bold=True)

    panel(draw, (48, 463, 1152, 542))
    label(draw, (74, 486), "3   Abra o bot que você criou e toque em Iniciar ou envie /start.", 27, TEAL, bold=True)
    image.save(ASSETS / "tutorial-botfather.png", optimize=True)


def telegram_id():
    image, draw = canvas("TELEGRAM", "Encontre o ID da sua conta")
    panel(draw, (48, 144, 592, 542))
    label(draw, (74, 170), "1   Abra @userinfobot", 32, bold=True)
    label(draw, (74, 226), "Toque em Iniciar para ver seu ID.", 26, MUTED)
    panel(draw, (74, 286, 564, 362), CHIP)
    label(draw, (96, 308), "Id   123456789", 30, TEAL, bold=True)
    label(draw, (74, 396), "Copie apenas os dígitos.", 26)
    label(draw, (74, 442), "O número acima é fictício.", 26, MUTED)

    panel(draw, (608, 144, 1152, 542))
    label(draw, (635, 170), "2   Preencha no Radar DOU", 32, bold=True)
    label(draw, (635, 226), "Seu ID numérico do Telegram", 26, MUTED)
    panel(draw, (634, 286, 1125, 362), CHIP)
    label(draw, (656, 308), "123456789", 30, bold=True)
    label(draw, (635, 396), "Use o ID da sua conta pessoal.", 26)
    label(draw, (635, 442), "Digite o token no campo seguinte.", 26, MUTED)
    image.save(ASSETS / "tutorial-seu-id.png", optimize=True)


def windows_interface():
    image, draw = canvas("WINDOWS X64  /  MAPA DA INTERFACE", "Configure e ative o Radar")
    panel(draw, (48, 144, 592, 542))
    label(draw, (74, 168), "Configurar monitoramento", 32, bold=True)
    for y, field in [
        (222, "Nome ou expressão para acompanhar"),
        (258, "Seu ID numérico do Telegram"),
        (294, "Token do seu bot (BotFather)"),
        (330, "Intervalo entre consultas"),
        (366, "UF para os concursos estaduais"),
    ]:
        label(draw, (74, y), field, 25, MUTED)
    label(draw, (74, 421), "Role o painel até o fim se precisar.", 24, TEAL)
    label(draw, (74, 463), "Salvar configurações", 26, bold=True)
    label(draw, (74, 502), "Testar conexão com Telegram", 26, bold=True)

    panel(draw, (608, 144, 1152, 542))
    label(draw, (634, 168), "Central de monitoramento", 32, bold=True)
    label(draw, (634, 222), "Resultados DOU • Concursos abertos", 25, MUTED)
    panel(draw, (634, 273, 1125, 327), CHIP)
    label(draw, (656, 288), "Ativar radar", 28, TEAL, bold=True)
    label(draw, (634, 358), "Desligar  ·  Conferir agora", 26)
    label(draw, (634, 423), "Registro de atividades", 26, bold=True)
    label(draw, (634, 465), "Acompanhe o estado das consultas", 25, MUTED)
    label(draw, (634, 499), "e a entrega dos alertas.", 25, MUTED)
    image.save(ASSETS / "mapa-interface-windows.png", optimize=True)


if __name__ == "__main__":
    download()
    botfather()
    telegram_id()
    windows_interface()
