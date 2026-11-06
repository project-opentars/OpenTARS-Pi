#!/usr/bin/env bash
# openTARS Pi installer. No sudo: everything goes to ~/.local/share/opentars-pi and one command removes it.
#   curl -fsSL https://github.com/project-opentars/OpenTARS-Pi/releases/latest/download/install.sh | bash
set -euo pipefail

VERSAO="@VERSAO@"
URL="${OPENTARS_PI_URL:-https://github.com/project-opentars/OpenTARS-Pi/releases/download/$VERSAO}"
URL_MODELO="${OPENTARS_PI_URL_MODELO:-https://huggingface.co/OpenTARS/Gargantua-Pi/resolve/main}"
MODELO="gargantua-1.2-pi-functiongemma-270m-Q8_0.gguf"
SHA_MODELO="f921e2370833585eda692d4878f9ba50899bdce18b57dc10d0300f8a66f5ac60"
SHA_APP="@SHA_APP@"
SHA_MOTOR_AARCH64="@SHA_MOTOR_AARCH64@"
SHA_MOTOR_X86_64="@SHA_MOTOR_X86_64@"
BASE="${OPENTARS_PI_HOME:-$HOME/.local/share/opentars-pi}"
BIN="$HOME/.local/bin"
MARCA="# openTARS Pi"

falhar() { printf 'openTARS Pi: %s\n' "$1" >&2; exit 1; }
passo() { printf '\033[32m>\033[0m %s\n' "$1"; }

case "$(uname -m)" in
  aarch64|arm64) MOTOR=aarch64; SHA_MOTOR=$SHA_MOTOR_AARCH64 ;;
  x86_64) MOTOR=x86_64; SHA_MOTOR=$SHA_MOTOR_X86_64 ;;
  *) falhar "this board runs a $(uname -m) system. openTARS Pi needs a 64-bit system (aarch64): install the 64-bit version of your OS." ;;
esac
[ "$(uname -s)" = Linux ] || falhar "openTARS Pi runs on Linux."
command -v curl >/dev/null || falhar "curl is missing. Install it with: sudo apt install curl"
command -v sha256sum >/dev/null || falhar "sha256sum is missing (package coreutils)."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null || falhar "Python 3.9 or newer is needed. Install it with: sudo apt install python3"
GLIBC=$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')
python3 -c "import sys; v = '$GLIBC'; sys.exit(not v or tuple(map(int, v.split('.'))) < (2, 35))" || falhar "this system is too old or has no glibc (${GLIBC:-none}). openTARS Pi needs glibc 2.35: Debian 12, Ubuntu 22.04, Raspberry Pi OS Bookworm or newer."
LIVRE=$(df -Pk "$HOME" | awk 'NR==2 {print int($4 / 1024)}')
[ "$LIVRE" -ge 600 ] || falhar "not enough disk space: $LIVRE MB free, 600 MB needed."

TMP=$(mktemp -d "$HOME/.opentars-pi-install.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

baixar() {   # url arquivo sha
  curl -fL --retry 3 --progress-bar -o "$2" "$1" || falhar "could not download $1"
  [ "$(sha256sum "$2" | cut -d' ' -f1)" = "$3" ] || falhar "$(basename "$2") failed the SHA-256 check. Nothing was installed."
}

printf 'Installing openTARS Pi %s in %s\n' "$VERSAO" "$BASE"
passo "App"
baixar "$URL/opentars-pi.tar.gz" "$TMP/app.tar.gz" "$SHA_APP"
passo "Engine (llama.cpp, $MOTOR)"
baixar "$URL/opentars-pi-motor-$MOTOR.tar.gz" "$TMP/motor.tar.gz" "$SHA_MOTOR"
mkdir -p "$BASE/modelos" "$BASE/dados" "$BIN"
if [ -f "$BASE/modelos/$MODELO" ] && [ "$(sha256sum "$BASE/modelos/$MODELO" | cut -d' ' -f1)" = "$SHA_MODELO" ]; then
  passo "Model already here"
else
  passo "Model (Gargantua Pi, 300 MB)"
  baixar "$URL_MODELO/$MODELO" "$TMP/$MODELO" "$SHA_MODELO"
  mv "$TMP/$MODELO" "$BASE/modelos/$MODELO"
fi
mkdir -p "$TMP/app" "$TMP/motor"
tar xzf "$TMP/app.tar.gz" -C "$TMP/app"
tar xzf "$TMP/motor.tar.gz" -C "$TMP/motor"
rm -rf "$BASE/app" "$BASE/motor"
mv "$TMP/app" "$BASE/app"
mv "$TMP/motor" "$BASE/motor"
ln -sf "$BASE/app/opentars-pi" "$BIN/opentars-pi"

# O comando é `opentars`. Se o openTARS completo já usa esse nome aqui, ele continua dono e este fica em opentars-pi.
COMANDO=opentars
ATUAL=$(PATH="$BIN:$PATH" command -v opentars || true)
if [ -z "$ATUAL" ] || [ "$(readlink -f "$ATUAL")" = "$(readlink -f "$BASE/app/opentars-pi")" ]; then
  ln -sf "$BASE/app/opentars-pi" "$BIN/opentars"
else
  COMANDO=opentars-pi
  printf 'The full openTARS already uses the opentars command here, so this one is opentars-pi.\n'
fi

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) for perfil in "$HOME/.profile" "$HOME/.bashrc"; do
       grep -qs "$MARCA" "$perfil" || printf 'export PATH="$HOME/.local/bin:$PATH" %s\n' "$MARCA" >> "$perfil"
     done
     NOVO_PATH=1 ;;
esac

if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] || [ -d /usr/share/xsessions ]; then
  mkdir -p "$HOME/.local/share/applications"
  printf '[Desktop Entry]\nType=Application\nName=openTARS Pi\nExec=%s --window\nTerminal=false\nCategories=Utility;\n' "$BIN/opentars-pi" > "$HOME/.local/share/applications/opentars-pi.desktop"
  python3 -c 'import tkinter' 2>/dev/null || printf 'For the window: sudo apt install python3-tk\n'
fi

printf '\n\033[32mopenTARS Pi is installed.\033[0m\n'
[ -z "${NOVO_PATH:-}" ] || printf 'Open a new terminal first, or run: export PATH="$HOME/.local/bin:$PATH"\n'
printf 'Start it with: %s\n' "$COMANDO"
printf 'The Gargantua Pi model is provided under the Gemma Terms of Use: https://ai.google.dev/gemma/terms\n'
