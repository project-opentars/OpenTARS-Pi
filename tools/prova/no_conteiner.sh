#!/bin/bash
# Roda a prova de capacidade num contêiner descartável.
#   bash tools/prova/no_conteiner.sh MODELO.gguf [dev|guardada|todas] [ids...]
# O motor é o x86_64 da Release (dist/). A rede fica ligada só para a busca na Wikipédia.
set -euo pipefail
cd "$(dirname "$0")/../.."
MODELO=$(realpath "$1"); shift
MOTOR=$(mktemp -d)
trap 'rm -rf "$MOTOR"' EXIT
tar xzf dist/opentars-pi-motor-x86_64.tar.gz -C "$MOTOR"
docker --context default build -q -t opentars-pi-prova tools/prova >/dev/null
docker --context default run --rm -v "$PWD":/app:ro -v "$MODELO":/m/modelo.gguf:ro -v "$MOTOR":/dados/motor:ro \
  -e OPENTARS_PI_MODELO=/m/modelo.gguf -e OPENTARS_PI_HOME=/dados -e OPENTARS_PI_URL_VERSAO=http://127.0.0.1:9/x \
  ${CEREBRO:+-e OPENTARS_PI_CEREBRO="$CEREBRO"} \
  -v "${SAIDA:-$PWD/tools/prova/resultados}":/saida opentars-pi-prova python3 /app/tools/prova/rodar.py "$@"
