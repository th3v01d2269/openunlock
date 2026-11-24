#!/bin/bash
# Manual APK build for OpenUnlock — no Gradle required.
#
# WHY THIS EXISTS: the Gradle daemon protocol is broken in this build
# sandbox (proven on an empty project: every Gradle invocation fails
# with "Could not receive a message from the daemon"). The Gradle
# project in android/ is still the reference build for a normal machine;
# this script builds the same native Kotlin app with the SDK tools
# directly: kotlinc + aapt2 + d8 + zipalign + apksigner.
#
# Usage:  bash android/manual/build-manual.sh
# Output: android/app-debug.apk
# Requires: $ANDROID_SDK (default ~/workspace/android-sdk),
#           ~/workspace/kotlinc (Kotlin 2.0.0 compiler), network for the
#           one-time androidx.annotation download (cached in manual/).
set -euo pipefail

ANDROID_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MANUAL="$ANDROID_DIR/manual"
SDK="${ANDROID_SDK:-/home/hatch/workspace/android-sdk}"
KOTLINC_HOME="${KOTLINC_HOME:-/home/hatch/workspace/kotlinc}"
BUILD="$MANUAL/build"
BT="$SDK/build-tools/34.0.0"
PLATFORM="$SDK/platforms/android-34/android.jar"

rm -rf "$BUILD"
mkdir -p "$BUILD/gen" "$BUILD/classes" "$BUILD/dex" "$BUILD/shizuku"

# --- dependencies -------------------------------------------------------
# Shizuku API 12.1.0 (shizuku-api.aar, checked in here). 13.x removed
# Shizuku.newProcess, which this app uses for all live shell work.
unzip -q -o "$MANUAL/shizuku-api.aar" "classes.jar" -d "$BUILD/shizuku"

# --- 1. compile resources ----------------------------------------------
echo "== aapt2 compile =="
"$BT/aapt2" compile --dir "$ANDROID_DIR/app/src/main/res" \
    -o "$BUILD/compiled-res.zip"

# --- 2. link (produces an APK without dex, plus R.java) -----------------
echo "== aapt2 link =="
"$BT/aapt2" link -o "$BUILD/base.apk" \
    -I "$PLATFORM" \
    --manifest "$ANDROID_DIR/app/src/main/AndroidManifest.xml" \
    --min-sdk-version 26 --target-sdk-version 34 \
    --version-code 3 --version-name 0.2.1 \
    --auto-add-overlay \
    --java "$BUILD/gen" \
    -R "$BUILD/compiled-res.zip"

# --- 3. compile Kotlin (+ generated R.java) -----------------------------
echo "== kotlinc =="
"$KOTLINC_HOME/bin/kotlinc" "$ANDROID_DIR/app/src/main/java" \
    "$BUILD/gen/com/openunlock/R.java" \
    -cp "$PLATFORM:$BUILD/shizuku/classes.jar" \
    -d "$BUILD/classes" -jvm-target 17

# --- 4. dex --------------------------------------------------------------
# d8 does not accept a raw directory of .class files here, so jar the
# compiled classes first (d8 skips non-class entries like .kotlin_module).
echo "== d8 =="
jar cf "$BUILD/app.jar" -C "$BUILD/classes" .
"$BT/d8" --lib "$PLATFORM" --release --output "$BUILD/dex" \
    "$BUILD/app.jar" "$BUILD/shizuku/classes.jar" \
    "$KOTLINC_HOME/lib/kotlin-stdlib.jar"

# --- 5. add dex + assets, align, sign ------------------------------------
echo "== packaging =="
python3 - "$BUILD/base.apk" "$BUILD/dex/classes.dex" "$ANDROID_DIR/app/src/main/assets" <<'EOF'
import sys, zipfile
apk, dex, assets = sys.argv[1:4]
import os
with zipfile.ZipFile(apk, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, "classes.dex")
    for name in sorted(os.listdir(assets)):
        z.write(os.path.join(assets, name), f"assets/{name}")
print("added classes.dex + assets")
EOF

if [ ! -f "$MANUAL/debug.keystore" ]; then
    keytool -genkeypair -keystore "$MANUAL/debug.keystore" \
        -alias androiddebugkey -keypass android -storepass android \
        -dname "CN=Android Debug,O=Android,C=US" \
        -keyalg RSA -keysize 2048 -validity 10000 -noprompt
fi
"$BT/zipalign" -f 4 "$BUILD/base.apk" "$BUILD/app-debug-aligned.apk"
"$BT/apksigner" sign --ks "$MANUAL/debug.keystore" \
    --ks-key-alias androiddebugkey --ks-pass pass:android \
    --key-pass pass:android --out "$ANDROID_DIR/app-debug.apk" \
    "$BUILD/app-debug-aligned.apk"
"$BT/apksigner" verify --verbose "$ANDROID_DIR/app-debug.apk"
ls -la "$ANDROID_DIR/app-debug.apk"
echo "BUILD OK: $ANDROID_DIR/app-debug.apk"
