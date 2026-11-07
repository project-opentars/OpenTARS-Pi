"""Onde tudo mora: uma pasta só, na pasta pessoal, para instalar sem sudo e remover com um comando."""
import json
import os
import tempfile
from pathlib import Path

from . import MODELO as ARQUIVO_MODELO

BASE = Path(os.environ.get("OPENTARS_PI_HOME") or Path.home() / ".local" / "share" / "opentars-pi")
MOTOR = BASE / "motor"
MODELOS = BASE / "modelos"
DADOS = BASE / "dados"
CONFIG = DADOS / "config.json"
MEMORIA = DADOS / "memoria.json"
TOKEN = DADOS / "token"
APROVACOES = DADOS / "aprovacoes"
CACHE = DADOS / "cache-do-prompt"


def ler_json(caminho, padrao):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return padrao


def gravar_json(caminho, dados):
    """Grava por inteiro ou não grava: uma queda de energia na placa não pode deixar o arquivo pela metade."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fd, temporario = tempfile.mkstemp(dir=caminho.parent, prefix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
    os.replace(temporario, caminho)


def config():
    return ler_json(CONFIG, {})


def salvar_config(**novos):
    gravar_json(CONFIG, {**config(), **novos})
