#!/bin/bash
# Monta os arquivos da Release em dist/: o app, os motores já compilados e o install.sh com os hashes.
set -euo pipefail
cd "$(dirname "$0")/.."
var() { sed -n "s/^$1 = \"\(.*\)\"/\1/p" opentars_pi/__init__.py; }
VERSAO=$(var VERSAO); MODELO=$(var MODELO); SHA_MODELO=$(var SHA_MODELO); URL_MODELO=$(var URL_MODELO)
REVISAO=$(date -u +%Y%m%d%H%M)
tar czf dist/opentars-pi.tar.gz --exclude='__pycache__' --owner=0 --group=0 opentars-pi opentars_pi LICENSE
sha() { sha256sum "$1" | cut -d' ' -f1; }
sed -e "s/@VERSAO@/$VERSAO/" -e "s/@REVISAO@/$REVISAO/" -e "s/@SHA_APP@/$(sha dist/opentars-pi.tar.gz)/" \
    -e "s/@MODELO@/$MODELO/" -e "s/@SHA_MODELO@/$SHA_MODELO/" -e "s|@URL_MODELO@|$URL_MODELO|" \
    -e "s/@SHA_MOTOR_AARCH64@/$(sha dist/opentars-pi-motor-aarch64.tar.gz)/" \
    -e "s/@SHA_MOTOR_X86_64@/$(sha dist/opentars-pi-motor-x86_64.tar.gz)/" install.sh > dist/install.sh
# versao.json: o que `opentars update` compara com o instalado (as notas são o assunto do último commit)
python3 - "$VERSAO" "$REVISAO" "$MODELO" "$SHA_MODELO" "$URL_MODELO" "$(git log -1 --format=%s)" <<'PY'
import hashlib, json, os, sys
versao, revisao, modelo, sha_modelo, url_modelo, notas = sys.argv[1:]
def parte(nome):
    caminho = os.path.join("dist", nome)
    return {"arquivo": nome, "sha256": hashlib.sha256(open(caminho, "rb").read()).hexdigest(), "mb": max(1, round(os.path.getsize(caminho) / 2**20))}
manifesto = {"versao": versao, "revisao": int(revisao), "notas": notas,
             "url": f"https://github.com/project-opentars/OpenTARS-Pi/releases/download/{versao}",
             "app": parte("opentars-pi.tar.gz"),
             "motor": {a: parte(f"opentars-pi-motor-{a}.tar.gz") for a in ("aarch64", "x86_64")},
             "modelo": {"arquivo": modelo, "sha256": sha_modelo, "url": f"{url_modelo}/{modelo}", "mb": 286}}  # shortcut: tamanho fixo do modelo, trocar junto com o SHA_MODELO
json.dump(manifesto, open("dist/versao.json", "w"), indent=1)
PY
(cd dist && sha256sum install.sh versao.json opentars-pi.tar.gz opentars-pi-motor-*.tar.gz > SHA256SUMS)
ls -la dist
