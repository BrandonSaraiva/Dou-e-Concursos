#!/usr/bin/env bash
set -euo pipefail

apk=${1:?Informe o caminho do APK}
evidence=${2:?Informe o diretório para os registros}
package=org.radardou.monitor
mkdir -p "$evidence"

save_logs() {
    timeout 15s adb logcat -d -v threadtime > "$evidence/logcat.txt" || true
}
trap save_logs EXIT

adb wait-for-device
until [[ $(adb shell getprop sys.boot_completed | tr -d '\r') == 1 ]]; do
    sleep 2
done
abis=$(adb shell getprop ro.product.cpu.abilist | tr -d '\r')
if [[ ",$abis," != *,arm64-v8a,* ]]; then
    echo "O emulador não anuncia suporte a ARM64: $abis" >&2
    exit 1
fi

adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
# A interface Kivy é desenhada em uma superfície única. Fixe a geometria do
# emulador para que os toques do teste correspondam aos controles visíveis.
adb shell wm size 1080x1920
adb shell wm density 420
adb install -g "$apk"
activity=$(adb shell cmd package resolve-activity --brief "$package" | tail -n 1 | tr -d '\r')
[[ "$activity" == "$package/"* ]]

app_resumed() {
    adb shell dumpsys activity activities | grep -E '(topResumedActivity|mResumedActivity)' | grep -F "$activity" > /dev/null
}

check_launch() {
    local label=$1 pid='' ready=false
    adb logcat -c
    adb shell am start -W -n "$activity"
    for ((attempt = 0; attempt < 45; attempt++)); do
        pid=$(adb shell pidof -s "$package" | tr -d '\r') || pid=''
        if [[ "$pid" =~ ^[0-9]+$ ]] && app_resumed \
            && adb logcat -d --pid="$pid" -s python | grep -F 'Start application main loop' > /dev/null; then
            ready=true
            break
        fi
        sleep 2
    done
    if [[ "$ready" != true ]]; then
        echo "O Radar DOU não chegou à tela inicial na tentativa $label." >&2
        return 1
    fi

    sleep 10
    [[ $(adb shell pidof -s "$package" | tr -d '\r') == "$pid" ]]
    app_resumed
    adb logcat -d --pid="$pid" -v threadtime > "$evidence/$label.log"
    if grep -Eq 'FATAL EXCEPTION|Fatal signal|Traceback \(most recent call last\)|Python for android ended' "$evidence/$label.log"; then
        echo "O processo do Radar DOU registrou um erro na tentativa $label." >&2
        return 1
    fi
    adb exec-out screencap -p > "$evidence/$label.png"
    echo "Radar DOU abriu e permaneceu em primeiro plano: $label"
}

check_launch abertura
adb shell am force-stop "$package"

# Preencha os outros campos com dados fictícios para isolar o teste de colagem.
# O APK de depuração permite conferir o arquivo que o botão Salvar grava.
config_path=files/RadarDOU/config.json
printf '%s\n' '{"version":3,"name":"Pessoa de Teste","telegram_id":123456789,"token_method":"user-file","protected_token":"123456789:InitialFixtureOnly_000000"}' \
    | adb shell -T "run-as $package tee $config_path >/dev/null"
check_launch reabertura

clipboard_token=123456789:ClipboardFixtureOnly_123456
adb shell am start -W -a android.settings.SETTINGS --activity-clear-top
adb shell uiautomator dump /data/local/tmp/radar-settings.xml >/dev/null
adb exec-out cat /data/local/tmp/radar-settings.xml > "$evidence/busca-configuracoes.xml"
search_position=$(python3 - "$evidence/busca-configuracoes.xml" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET

for node in ET.parse(sys.argv[1]).iter("node"):
    resource_id = node.get("resource-id", "").rsplit("/", 1)[-1]
    if resource_id in {"search_action_bar_title", "search_action_bar", "search_bar"}:
        left, top, right, bottom = map(int, re.findall(r"\d+", node.attrib["bounds"]))
        if left < right and top < bottom:
            print((left + right) // 2, (top + bottom) // 2)
            break
else:
    sys.exit("A busca nas Configurações do Android não foi encontrada.")
PY
)
read -r search_x search_y <<< "$search_position"
adb shell input tap "$search_x" "$search_y"
sleep 2
adb shell input text "$clipboard_token"
adb exec-out screencap -p > "$evidence/busca-antes-de-copiar.png"
# Copie pelo campo de texto nativo das Configurações, usando o clipboard real
# do Android e sem expor credenciais reais nas entradas ou nos registros.
adb shell input keycombination -t 100 KEYCODE_CTRL_LEFT KEYCODE_A
adb shell input keycombination -t 100 KEYCODE_CTRL_LEFT KEYCODE_C
sleep 1
adb shell am start -W -n "$activity"
sleep 2
app_resumed
adb shell input tap 890 1280  # Colar token
adb exec-out screencap -p > "$evidence/token-colado.png"

adb shell input swipe 200 1660 200 330 1100
sleep 2
adb exec-out screencap > "$evidence/configuracao.raw"
# Localize o primeiro botão azul visível após a rolagem (Salvar configurações).
# A barra de rolagem pode alterar a posição final em alguns pixels.
save_y=$(python3 - "$evidence/configuracao.raw" <<'PY'
import struct
import sys
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()
width, height, pixel_format = struct.unpack_from("<III", data)
offset = len(data) - width * height * 4
if offset not in (12, 16) or pixel_format not in (1, 2):
    sys.exit("Formato de captura de tela inesperado.")
rows = []
for y in range(80, height - 80):
    pixel = offset + (y * width + width // 8) * 4
    red, green, blue = data[pixel:pixel + 3]
    if 40 <= red <= 85 and 95 <= green <= 140 and 212 <= blue <= 255:
        rows.append(y)
    elif len(rows) >= 36:
        print((rows[0] + rows[-1]) // 2)
        break
    else:
        rows.clear()
else:
    sys.exit("O botão Salvar configurações não ficou visível após a rolagem.")
PY
)
rm -- "$evidence/configuracao.raw"
adb shell input tap 540 "$save_y"
sleep 1
adb exec-out screencap -p > "$evidence/configuracao-depois-de-salvar.png"
adb shell run-as "$package" cat "$config_path" | python3 -c '
import json
import sys

config = json.load(sys.stdin)
if config["protected_token"] != sys.argv[1]:
    sys.exit("O token salvo não corresponde ao texto copiado no Android.")
' "$clipboard_token"
echo "Radar DOU colou o token do Android e salvou o valor completo."
