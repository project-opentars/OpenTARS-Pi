"""Aprovação na própria placa para pedidos que vêm pela rede: o token não pode virar chave do terminal.
Cada pendência é um arquivo; quem está na placa responde com `opentars-pi --aprovacoes`. Sem resposta, é não."""
import json
import os
import secrets
import time

from . import pastas

ESPERA = 120


def pedir(descricao, nivel, espera=ESPERA):
    pastas.APROVACOES.mkdir(parents=True, exist_ok=True)
    caminho = pastas.APROVACOES / (secrets.token_hex(4) + ".json")
    pastas.gravar_json(caminho, {"descricao": descricao, "nivel": nivel, "quando": time.time(), "resposta": None})
    limite = time.time() + espera
    try:
        while time.time() < limite:
            resposta = pastas.ler_json(caminho, {}).get("resposta")
            if resposta is not None:
                return bool(resposta)
            time.sleep(0.5)
        return False
    finally:
        caminho.unlink(missing_ok=True)


def pendentes():
    saida = []
    for caminho in sorted(pastas.APROVACOES.glob("*.json")) if pastas.APROVACOES.exists() else []:
        dados = pastas.ler_json(caminho, None)
        if dados and dados.get("resposta") is None:
            saida.append((caminho, dados))
    return saida


def responder(caminho, sim):
    dados = pastas.ler_json(caminho, None)
    if dados:
        pastas.gravar_json(caminho, {**dados, "resposta": bool(sim)})


def novo_token():
    pastas.DADOS.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    fd = os.open(pastas.TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(token)
    return token


def token():
    try:
        return pastas.TOKEN.read_text().strip() or novo_token()
    except OSError:
        return novo_token()


def resumo_json(dados):
    return json.dumps(dados, ensure_ascii=False)
