#!/bin/bash
# Compila o llama-server para placas ARM64 no Ubuntu 22.04 (glibc 2.35): o binário oficial pede glibc 2.38 e deixaria de fora
# Raspberry Pi OS Bookworm, Debian 12 e Ubuntu 22.04. Sem OpenSSL, sem curl e sem OpenMP: só precisa da libc.
# Uso: bash tools/compilar_motor.sh PASTA_DO_LLAMA_CPP [aarch64|x86_64]
set -euo pipefail
FONTE=$(realpath "$1"); ALVO=${2:-aarch64}
RAIZ=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$RAIZ/dist"
docker --context default run --rm -v "$FONTE:/src:ro" -v "$RAIZ/dist:/saida" -e ALVO="$ALVO" -e DONO="$(id -u):$(id -g)" ubuntu:22.04 bash -euc '
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ca-certificates cmake make git gcc g++ g++-aarch64-linux-gnu binutils-aarch64-linux-gnu >/dev/null
cp -r /src /tmp/src && cd /tmp/src && rm -rf build
# o GCC 11 do Ubuntu 22.04 não conhece armv9.2+sme; placas com esse chip usam a variante armv8.6
sed -i "/armv9.2/d" ggml/src/CMakeLists.txt
OPCOES=(-DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF -DGGML_CPU_ALL_VARIANTS=ON -DGGML_OPENMP=OFF
        -DLLAMA_OPENSSL=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_WEBUI=OFF
        "-DCMAKE_INSTALL_RPATH=\$ORIGIN" -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON
        "-DCMAKE_EXE_LINKER_FLAGS=-static-libstdc++ -static-libgcc" "-DCMAKE_SHARED_LINKER_FLAGS=-static-libstdc++ -static-libgcc")
if [ "$ALVO" = aarch64 ]; then
  OPCOES+=(-DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=aarch64 -DCMAKE_C_COMPILER=aarch64-linux-gnu-gcc -DCMAKE_CXX_COMPILER=aarch64-linux-gnu-g++)
  STRIP=aarch64-linux-gnu-strip
else
  STRIP=strip
fi
cmake -B build "${OPCOES[@]}" > /tmp/cmake.log 2>&1 || { tail -40 /tmp/cmake.log; exit 1; }
cmake --build build -j8 --target llama-server > /tmp/build.log 2>&1 || { grep -nE "error|Error |undefined" /tmp/build.log | head -30; exit 1; }
mkdir -p /tmp/motor
cp -a build/bin/llama-server build/bin/*.so* /tmp/motor/
cp LICENSE /tmp/motor/LICENSE-llama.cpp
$STRIP /tmp/motor/llama-server /tmp/motor/*.so* 2>/dev/null || true
tar czf /saida/opentars-pi-motor-$ALVO.tar.gz -C /tmp/motor .
chown "$DONO" /saida/opentars-pi-motor-$ALVO.tar.gz
ls -la /tmp/motor /saida
'
