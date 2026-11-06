#!/bin/bash
# Monta os arquivos da Release em dist/: o app, os motores já compilados e o install.sh com os hashes.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSAO=$(sed -n 's/^VERSAO = "\(.*\)"/\1/p' opentars_pi/__init__.py)
tar czf dist/opentars-pi.tar.gz --exclude='__pycache__' --owner=0 --group=0 opentars-pi opentars_pi LICENSE
sha() { sha256sum "$1" | cut -d' ' -f1; }
sed -e "s/@VERSAO@/$VERSAO/" -e "s/@SHA_APP@/$(sha dist/opentars-pi.tar.gz)/" \
    -e "s/@SHA_MOTOR_AARCH64@/$(sha dist/opentars-pi-motor-aarch64.tar.gz)/" \
    -e "s/@SHA_MOTOR_X86_64@/$(sha dist/opentars-pi-motor-x86_64.tar.gz)/" install.sh > dist/install.sh
(cd dist && sha256sum install.sh opentars-pi.tar.gz opentars-pi-motor-*.tar.gz > SHA256SUMS)
ls -la dist
