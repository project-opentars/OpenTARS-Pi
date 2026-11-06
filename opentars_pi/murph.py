"""Murph: a classificadora de pedidos do openTARS, a mesma do app grande (regressão logística em Python puro, sem GPU)."""

import json
import math
import os
import re
import unicodedata

VERSAO_FORMATO = 1
VERSAO = "1.0"          # helper Murph 1.0 (3.0.5): mostrado na janela e no terminal
N_GRAMAS = (2, 3, 4, 5)
_RE_PALAVRA = re.compile(r"\w+", re.UNICODE)


def normalizar(texto):
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s.lower().replace("ß", "ss")).strip()


def contagens(texto):
    """{característica: contagem} (antes do TF-IDF)."""
    t = normalizar(texto)
    palavras = _RE_PALAVRA.findall(t)
    feats = {}
    for w in palavras:
        feats["w:" + w] = feats.get("w:" + w, 0) + 1
        marcada = f" {w} "
        for n in N_GRAMAS:
            for i in range(max(0, len(marcada) - n + 1)):
                k = "c:" + marcada[i:i + n]
                feats[k] = feats.get(k, 0) + 1
    for a, b in zip(palavras, palavras[1:]):
        k = f"b:{a}_{b}"
        feats[k] = feats.get(k, 0) + 1
    n = len(palavras)
    feats["#n" + ("1" if n <= 1 else "2" if n <= 3 else "6" if n <= 6 else "+")] = 1
    return feats


def cobertura(texto, idf):
    """Quanto do texto (pedaços de palavra e palavras) o modelo já viu no
    treino, de 0 a 1. "asdfgh" ou uma língua que ela não conhece: baixo."""
    c = contagens(texto)
    total = sum(n for k, n in c.items() if not k.startswith("#"))
    if not total:
        return 0.0
    return sum(n for k, n in c.items() if not k.startswith("#") and k in idf) / total


def vetor(texto, idf):
    """Características com TF sublinear x IDF, normalizadas (L2).
    Só entra o que o modelo conhece (idf)."""
    v = {}
    for k, c in contagens(texto).items():
        peso = idf.get(k)
        if peso is not None:
            v[k] = (1.0 + math.log(c)) * peso
    norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
    return {k: x / norma for k, x in v.items()}


class Murph:
    def __init__(self, dados):
        self.tarefas = dados["tarefas"]
        self.idf = dados["idf"]
        self.vies = dados["vies"]
        # pesos: {característica: [peso por tarefa]}
        self.pesos = dados["pesos"]
        self.limite = float(dados.get("limite", 0.1))
        self.cobertura_minima = float(dados.get("cobertura_minima", 0.0))
        self.versao = str(dados.get("versao") or VERSAO)

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        if dados.get("formato") != VERSAO_FORMATO:
            raise ValueError("formato de modelo desconhecido")
        return cls(dados)

    def probabilidades(self, texto):
        """[(probabilidade, tarefa)] da mais provável pra menos."""
        notas = list(self.vies)
        for k, x in vetor(texto, self.idf).items():
            linha = self.pesos.get(k)
            if linha:
                for i, w in enumerate(linha):
                    notas[i] += x * w
        topo = max(notas)
        exps = [math.exp(n - topo) for n in notas]
        soma = sum(exps)
        return sorted(((e / soma, t) for e, t in zip(exps, self.tarefas)), reverse=True)

    def classificar(self, texto):
        """(tarefa, confiança 0..1)."""
        p = self.probabilidades(texto)
        return p[0][1], p[0][0]

_modelo = {}


def classificar(texto):
    """(tarefa, confiança) ou (None, 0) se o arquivo do modelo não abrir. Carrega na primeira vez."""
    if "m" not in _modelo:
        try:
            _modelo["m"] = Murph.carregar(os.path.join(os.path.dirname(os.path.abspath(__file__)), "murph.json"))
        except (OSError, ValueError):
            _modelo["m"] = None
    return _modelo["m"].classificar(texto) if _modelo["m"] and normalizar(texto) else (None, 0.0)
