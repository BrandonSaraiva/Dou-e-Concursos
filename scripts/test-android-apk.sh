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
check_launch reabertura
