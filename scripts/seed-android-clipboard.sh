#!/usr/bin/env bash
set -euo pipefail

fixture_text=${1:?Informe o texto sintético para a área de transferência}
[[ "$fixture_text" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]

sdk=${ANDROID_HOME:-${ANDROID_SDK_ROOT:?SDK Android indisponível}}
platform="$sdk/platforms/android-35/android.jar"
tools="$sdk/build-tools/35.0.0"
if [[ ! -x "$tools/d8" ]]; then
    "$sdk/cmdline-tools/latest/bin/sdkmanager" --install 'build-tools;35.0.0'
fi

fixture_package=org.radardou.clipboardfixture
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
mkdir -p "$work/classes" "$work/dex"
cat > "$work/AndroidManifest.xml" <<'XML'
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
          package="org.radardou.clipboardfixture">
    <application android:label="Teste de clipboard Radar DOU"
                 android:theme="@android:style/Theme.Material.Light.NoActionBar">
        <activity android:name=".ClipboardFixture" android:exported="true" />
    </application>
</manifest>
XML
cat > "$work/ClipboardFixture.java" <<'JAVA'
package org.radardou.clipboardfixture;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.os.Bundle;
import android.util.Log;
import android.widget.TextView;

public final class ClipboardFixture extends Activity {
    private boolean copied;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("Teste da área de transferência do Android");
        setContentView(view);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (!hasFocus || copied) {
            return;
        }
        String text = getIntent().getStringExtra("text");
        ClipboardManager clipboard = getSystemService(ClipboardManager.class);
        clipboard.setPrimaryClip(ClipData.newPlainText("Teste Radar DOU", text));
        copied = true;
        Log.i("RadarClipboardFixture", "Clipboard de teste preenchido.");
    }
}
JAVA

javac --release 8 -cp "$platform" -d "$work/classes" "$work/ClipboardFixture.java"
"$tools/d8" --lib "$platform" --min-api 23 --output "$work/dex" \
    "$work/classes/org/radardou/clipboardfixture/ClipboardFixture.class"
"$tools/aapt" package -f -M "$work/AndroidManifest.xml" -I "$platform" \
    --min-sdk-version 23 --target-sdk-version 35 -F "$work/unsigned.apk"
zip -q -j "$work/unsigned.apk" "$work/dex/classes.dex"
"$tools/zipalign" -f 4 "$work/unsigned.apk" "$work/aligned.apk"
keytool -genkeypair -keystore "$work/test.jks" -storepass android -keypass android \
    -alias fixture -keyalg RSA -validity 1 -dname 'CN=Radar DOU Android Test' >/dev/null 2>&1
"$tools/apksigner" sign --ks "$work/test.jks" --ks-pass pass:android \
    --out "$work/fixture.apk" "$work/aligned.apk"

adb uninstall "$fixture_package" >/dev/null 2>&1 || true
adb install "$work/fixture.apk"
adb shell am start -W -n "$fixture_package/.ClipboardFixture" --es text "$fixture_text"
for ((attempt = 0; attempt < 15; attempt++)); do
    pid=$(adb shell pidof -s "$fixture_package" | tr -d '\r') || pid=''
    if [[ "$pid" =~ ^[0-9]+$ ]] \
        && adb logcat -d --pid="$pid" -s RadarClipboardFixture | grep -F 'Clipboard de teste preenchido.'; then
        exit 0
    fi
    sleep 1
done
echo 'A atividade de teste não conseguiu preencher a área de transferência.' >&2
exit 1
