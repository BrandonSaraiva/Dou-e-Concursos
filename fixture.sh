#!/usr/bin/env bash
set -euo pipefail
evidence=android-smoke
mkdir -p "$evidence"
adb shell wm size 1080x1920
adb shell wm density 420
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
adb shell input keycombination -t 100 KEYCODE_CTRL_LEFT KEYCODE_A
adb shell input text Replacement
adb shell input keycombination -t 100 KEYCODE_CTRL_LEFT KEYCODE_A
adb shell input keycombination -t 100 KEYCODE_CTRL_LEFT KEYCODE_V
sleep 1
adb exec-out screencap -p > "$evidence/busca-depois-de-colar.png"
adb shell uiautomator dump /data/local/tmp/radar-settings.xml >/dev/null
adb exec-out cat /data/local/tmp/radar-settings.xml > "$evidence/busca-depois-de-colar.xml"
python3 - "$evidence/busca-depois-de-colar.xml" "$clipboard_token" <<'CHECK'
import sys
import xml.etree.ElementTree as ET

if not any(node.get("text") == sys.argv[2] for node in ET.parse(sys.argv[1]).iter("node")):
    sys.exit("A área de transferência não retornou o texto selecionado no campo de busca.")
print("As Configurações do Android copiaram e colaram o texto sintético de teste.")
CHECK
