"""Atualização por partes: o app (com a Murph), o motor e o modelo, cada um só quando mudou.

A Release publica um `versao.json` com o hash de cada parte. A instalação guarda em `instalado.json` o que tem.
Tudo é baixado e conferido antes de trocar qualquer coisa; a versão anterior fica em `anterior/` para desfazer.
"""
import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request

from . import pastas

URL_VERSAO = os.environ.get("OPENTARS_PI_URL_VERSAO") or \
    "https://github.com/project-opentars/OpenTARS-Pi/releases/latest/download/versao.json"
INSTALADO = pastas.BASE / "instalado.json"
ANTERIOR = pastas.BASE / "anterior"
DIA = 86400


def arquitetura():
    return "x86_64" if os.uname().machine == "x86_64" else "aarch64"


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def instalado():
    return pastas.ler_json(INSTALADO, {})


def publicado(tempo=10):
    pedido = urllib.request.Request(f"{URL_VERSAO}?t={int(time.time())}", headers={"User-Agent": "opentars-pi", "Cache-Control": "no-cache"})   # logo depois de publicar, o cache servia o velho
    with urllib.request.urlopen(pedido, timeout=tempo) as r:
        return json.loads(r.read().decode("utf-8"))


def _partes(manifesto):
    """{nome: (url, arquivo, sha, mb)} do que a Release oferece para esta placa."""
    motor = manifesto["motor"][arquitetura()]
    m = manifesto["modelo"]
    return {"app": (manifesto["url"] + "/" + manifesto["app"]["arquivo"], manifesto["app"]["arquivo"], manifesto["app"]["sha256"], manifesto["app"]["mb"]),
            "motor": (manifesto["url"] + "/" + motor["arquivo"], motor["arquivo"], motor["sha256"], motor["mb"]),
            "modelo": (m["url"], m["arquivo"], m["sha256"], m["mb"])}


def _sha_do_modelo_local(arquivo):
    """Instalação de antes do `instalado.json`: o modelo se confere pelo arquivo, para não baixar 300 MB à toa."""
    caminho = pastas.MODELOS / arquivo
    return sha256(caminho) if caminho.exists() else None


def o_que_mudou(manifesto, local=None):
    local = instalado() if local is None else local
    mudou = []
    for nome, (_url, arquivo, sha, _mb) in _partes(manifesto).items():
        atual = local.get(nome)
        if nome == "modelo":
            atual = (atual or {}).get("sha256") if isinstance(atual, dict) else None
            if atual is None:
                atual = _sha_do_modelo_local(arquivo)
        if atual != sha:
            mudou.append(nome)
    return mudou


def _baixar(url, destino, sha, mostrar):
    pedido = urllib.request.Request(url, headers={"User-Agent": "opentars-pi"})
    with urllib.request.urlopen(pedido, timeout=60) as r, open(destino, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        feito, visto = 0, -1
        for bloco in iter(lambda: r.read(1 << 16), b""):
            f.write(bloco)
            feito += len(bloco)
            if total and mostrar and feito * 10 // total != visto:
                visto = feito * 10 // total
                mostrar(f"  {os.path.basename(destino)}: {feito * 100 // total}%")
    if sha256(destino) != sha:
        raise ValueError(f"{os.path.basename(destino)} failed the SHA-256 check.")


def _extrair(arquivo, destino):
    with tarfile.open(arquivo) as t:
        if hasattr(tarfile, "data_filter"):
            t.extractall(destino, filter="data")
        else:
            t.extractall(destino)


def estado_do_manifesto(manifesto):
    """O que fica instalado quando tudo bate com a Release (o que não mudou já batia)."""
    p = _partes(manifesto)
    return {"versao": manifesto["versao"], "revisao": manifesto["revisao"], "app": p["app"][2], "motor": p["motor"][2],
            "modelo": {"arquivo": p["modelo"][1], "sha256": p["modelo"][2]}}


def aplicar(manifesto, mudou, mostrar=print):
    """Baixa e confere tudo antes; só então troca. Devolve a lista do que foi trocado."""
    partes = _partes(manifesto)
    precisa = sum(partes[n][3] for n in mudou) * 2 + 50
    livre = shutil.disk_usage(pastas.BASE).free // 2**20
    if livre < precisa:
        raise OSError(f"not enough disk space: {livre} MB free, about {precisa} MB needed.")
    pastas.BASE.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=pastas.BASE, prefix=".atualizando-")
    try:
        novos = {}
        for nome in mudou:
            url, arquivo, sha, _mb = partes[nome]
            baixado = os.path.join(tmp, arquivo)
            _baixar(url, baixado, sha, mostrar)
            if nome == "modelo":
                novos[nome] = baixado
            else:
                pasta = os.path.join(tmp, nome)
                os.mkdir(pasta)
                _extrair(baixado, pasta)
                novos[nome] = pasta
        # daqui para baixo só troca de lugar, sem rede: rápido e sem meio-termo
        shutil.rmtree(ANTERIOR, ignore_errors=True)
        ANTERIOR.mkdir(parents=True)
        antes = instalado()
        for nome, novo in novos.items():
            if nome == "modelo":
                arquivo = partes["modelo"][1]
                velho = pastas.MODELOS / (antes.get("modelo", {}).get("arquivo") or arquivo)
                pastas.MODELOS.mkdir(parents=True, exist_ok=True)
                if velho.exists():
                    sobra = shutil.disk_usage(pastas.BASE).free // 2**20 - partes["modelo"][3]
                    if sobra > 500:                 # guardar o modelo velho só se o cartão aguenta
                        os.replace(velho, ANTERIOR / velho.name)
                    else:
                        velho.unlink()
                os.replace(novo, pastas.MODELOS / arquivo)
            else:
                atual = pastas.BASE / nome
                if atual.exists():
                    os.replace(atual, ANTERIOR / nome)
                os.replace(novo, atual)
        pastas.gravar_json(ANTERIOR / "instalado.json", antes)
        pastas.gravar_json(INSTALADO, estado_do_manifesto(manifesto))
        if "modelo" in novos:
            shutil.rmtree(pastas.CACHE, ignore_errors=True)   # o prompt guardado é do modelo velho
        return list(novos)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def desfazer():
    """Volta para o que estava antes da última atualização (e desfazer de novo refaz)."""
    if not (ANTERIOR / "instalado.json").exists():
        return []
    antes = pastas.ler_json(ANTERIOR / "instalado.json", {})
    agora = instalado()
    trocou = []
    troca = tempfile.mkdtemp(dir=pastas.BASE, prefix=".desfazendo-")
    for nome in ("app", "motor"):
        if (ANTERIOR / nome).exists():
            if (pastas.BASE / nome).exists():
                os.replace(pastas.BASE / nome, os.path.join(troca, nome))
            os.replace(ANTERIOR / nome, pastas.BASE / nome)
            trocou.append(nome)
    velho = antes.get("modelo", {}).get("arquivo")
    if velho and (ANTERIOR / velho).exists():
        atual = pastas.MODELOS / (agora.get("modelo", {}).get("arquivo") or velho)
        if atual.exists():
            os.replace(atual, os.path.join(troca, atual.name))
        os.replace(ANTERIOR / velho, pastas.MODELOS / velho)
        shutil.rmtree(pastas.CACHE, ignore_errors=True)
        trocou.append("modelo")
    for nome in os.listdir(troca):
        os.replace(os.path.join(troca, nome), ANTERIOR / nome)
    os.rmdir(troca)
    voltou = dict(antes)
    if "modelo" not in trocou:            # o modelo velho não foi guardado: continua o novo
        voltou["modelo"] = agora.get("modelo", antes.get("modelo"))
    pastas.gravar_json(ANTERIOR / "instalado.json", agora)
    pastas.gravar_json(INSTALADO, voltou)
    return trocou


def aviso():
    """Linha para o começo da conversa, se a última consulta achou algo novo. Não usa a rede."""
    c = pastas.config()
    if c.get("atualizar_auto") is False:
        return None
    novo = c.get("atualizacao_disponivel")
    return novo if novo and novo != instalado().get("revisao") else None


def consultar_em_segundo_plano():
    """No máximo uma vez por dia, sem segurar a conversa: placa sem internet não espera nada."""
    c = pastas.config()
    if c.get("atualizar_auto") is False or time.time() - c.get("ultima_consulta", 0) < DIA:
        return None

    def consultar():
        try:
            m = publicado()
            novo = m["revisao"] if o_que_mudou(m) else None
            pastas.salvar_config(ultima_consulta=time.time(), atualizacao_disponivel=novo)
        except Exception:                 # sem rede ou GitHub fora: tenta de novo amanhã
            pastas.salvar_config(ultima_consulta=time.time())
    fio = threading.Thread(target=consultar, daemon=True)
    fio.start()
    return fio

