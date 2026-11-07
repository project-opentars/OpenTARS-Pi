"""Treina a Murph do Pi e grava opentars_pi/murph.json. Precisa de scikit-learn só aqui; a placa roda em Python puro.

    ~/opentars-lab/venv/bin/python3 tools/murph/treinar.py

Classes: placa, sobre, comando, mundo, papo, codigo, tela, conta. A Murph do app grande escolhe modelo; esta escolhe o caminho do pedido.
treino.jsonl veio de um professor (beam) e prova.jsonl de outro (gpt-oss:20b), para a nota não medir o estilo de quem escreveu.
"""
import json
import math
import os
import sys

import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
sys.path.insert(0, RAIZ)
from opentars_pi import murph as mm  # noqa: E402
sys.path.insert(0, AQUI)
from frases import DA_SESSAO  # noqa: E402

CLASSES = ["placa", "sobre", "comando", "mundo", "papo", "codigo", "tela", "conta"]
C = float(os.environ.get("MURPH_C", 10))
CORTE = float(os.environ.get("MURPH_CORTE", 0.03))


def ler(nome):
    with open(os.path.join(AQUI, nome), encoding="utf-8") as f:
        return [(d["frase"], d["classe"]) for d in map(json.loads, f)]


def treinar(dados):
    y = np.array([CLASSES.index(c) for _, c in dados])
    cont = [mm.contagens(f) for f, _ in dados]
    df = {}
    for feats in cont:
        for k in feats:
            df[k] = df.get(k, 0) + 1
    n = len(cont)
    idf = {k: math.log((1 + n) / (1 + d)) + 1.0 for k, d in df.items() if d >= 2}
    dv = DictVectorizer()
    X = dv.fit_transform([mm.vetor(f, idf) for f, _ in dados])
    clf = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
    clf.fit(X, y)
    pesos = {k: [round(float(x), 3) for x in linha] for k, linha in zip(dv.get_feature_names_out(), clf.coef_.T) if np.abs(linha).max() >= CORTE}
    return {"formato": mm.VERSAO_FORMATO, "versao": "pi-1", "tarefas": CLASSES, "idf": {k: round(v, 3) for k, v in idf.items() if k in pesos},
            "vies": [round(float(b), 4) for b in clf.intercept_], "pesos": pesos}


def nota(dados, modelo):
    m = mm.Murph(modelo)
    por = {}
    for frase, classe in dados:
        certo = m.classificar(frase)[0] == classe
        a, b = por.get(classe, (0, 0))
        por[classe] = (a + certo, b + 1)
    return por


if __name__ == "__main__":
    prova = ler("prova.jsonl")
    fora = {mm.normalizar(f) for f, _ in prova}
    treino = [(f, c) for f, c in ler("treino.jsonl") + DA_SESSAO * 3 if mm.normalizar(f) not in fora]
    modelo = treinar(treino)
    por = nota(prova, modelo)
    certas, total = sum(a for a, _ in por.values()), sum(b for _, b in por.values())
    print(f"{len(treino)} frases de treino, {len(modelo['pesos'])} características")
    print(f"prova: {certas}/{total} ({100 * certas / total:.1f}%)", {k: f"{a}/{b}" for k, (a, b) in por.items()})
    if "--gravar" in sys.argv:
        with open(os.path.join(RAIZ, "opentars_pi", "murph.json"), "w", encoding="utf-8") as f:
            json.dump(modelo, f, ensure_ascii=False, separators=(",", ":"))
        print(f"{os.path.getsize(os.path.join(RAIZ, 'opentars_pi', 'murph.json')) / 1e6:.1f} MB")
    if "--erros" in sys.argv:
        m = mm.Murph(modelo)
        for frase, classe in prova:
            achou, conf = m.classificar(frase)
            if achou != classe:
                print(f"{classe:>8} -> {achou:<8} {conf:.2f}  {frase}")
