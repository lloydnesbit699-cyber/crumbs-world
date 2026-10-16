#!/bin/bash
# Rebuild the Crumbs World Android launcher APK.
# Usage: ./rebuild-apk.sh [SERVER_URL]
#   SERVER_URL defaults to the placeholder — pass Harley's Funnel URL to bake it in.
# Needs: JDK 17 at ~/workspace/.jdk, Android SDK at ~/workspace/.android-sdk
set -e
SERVER_URL="${1:-https://HARLEY_URL_HERE}"
cd "$(dirname "$0")/android"

export JAVA_HOME=~/workspace/.jdk
export ANDROID_HOME=~/workspace/.android-sdk
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/build-tools/34.0.0:$PATH"
AAPT2="$ANDROID_HOME/build-tools/34.0.0/aapt2"
PLATFORM="$ANDROID_HOME/platforms/android-34/android.jar"

# bake the server URL into Config.java (idempotent: replaces whatever is there)
CFG=app/src/main/java/com/crumbsworld/launcher/Config.java
[ -f "$CFG.bak" ] || cp "$CFG" "$CFG.bak"
sed -i "s|public static final String SERVER_URL = \"[^\"]*\"|public static final String SERVER_URL = \"$SERVER_URL\"|" "$CFG"
grep -n "SERVER_URL =" "$CFG" | head -1

rm -rf build && mkdir -p build/classes build/dex
$AAPT2 compile --dir app/src/main/res -o build/res.zip
$AAPT2 link -o build/base.apk -I "$PLATFORM" \
  --manifest app/src/main/AndroidManifest.xml -R build/res.zip --java build/gen
javac -encoding UTF-8 -source 8 -target 8 -cp "$PLATFORM" -d build/classes \
  $(find app/src/main/java build/gen -name "*.java") 2>/dev/null
"$ANDROID_HOME/build-tools/34.0.0/d8" --lib "$PLATFORM" --output build/dex/ \
  $(find build/classes -name "*.class")
cp build/base.apk build/unsigned.apk
(cd build && zip -q unsigned.apk dex/classes.dex)
"$ANDROID_HOME/build-tools/34.0.0/zipalign" -f 4 build/unsigned.apk build/aligned.apk
# signing key lives OUTSIDE build/ so it survives clean rebuilds.
# BACK THIS FILE UP: losing it means players must uninstall/reinstall to update.
KEYSTORE="$(dirname "$0")/android/crumbs-release.keystore"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -keystore "$KEYSTORE" -alias crumbs -keyalg RSA \
    -keysize 2048 -validity 10000 -storepass crumbsworld -keypass crumbsworld \
    -dname "CN=Crumbs World, OU=Nesbits Fixit, O=Nesbits Fixit, L=Moultrie, ST=GA, C=US"
fi
"$ANDROID_HOME/build-tools/34.0.0/apksigner" sign --ks "$KEYSTORE" \
  --ks-pass pass:crumbsworld --key-pass pass:crumbsworld \
  --out build/crumbs-world-launcher.apk build/aligned.apk
"$ANDROID_HOME/build-tools/34.0.0/apksigner" verify build/crumbs-world-launcher.apk \
  && echo "OK: build/crumbs-world-launcher.apk"
