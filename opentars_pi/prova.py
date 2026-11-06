"""A prova do app inteiro com o modelo real: `opentars --test`. Roda numa pasta temporária; a memória e os arquivos da pessoa
não entram. O juiz olha o que aconteceu de fato: a resposta veio do sistema, o fato foi guardado, o arquivo existe."""
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from . import memoria, pastas
from .agente import Agente
from .motor import Motor

# (pedido, memória antes, como conferir). {d} é a pasta temporária da prova.
TAREFAS = [
    # estado da placa
    ("how much ram is left?", (), ("fala", r"\bMB\b")),
    ("qual o uso de memória agora?", (), ("fala", r"\bMB\b")),
    ("is there space left on the disk?", (), ("fala", r"\bGB\b")),
    ("quanto de armazenamento ainda tenho?", (), ("fala", r"\bGB\b")),
    ("what's the cpu temperature?", (), ("fala", r"°C|sensor")),
    ("a placa está muito quente?", (), ("fala", r"°C|sensor")),
    ("how long has this board been up?", (), ("fala", r"\d+ (min|h|d)")),
    ("qual é o meu ip?", (), ("fala", r"\d+\.\d+\.\d+\.\d+|rede")),
    # memória
    ("remember that the garage door is on pin PC9", (), ("guardou", "garage")),
    ("anota aí que a senha do wifi fica na gaveta", (), ("guardou", "gaveta")),
    ("note that my sister lives in Recife", (), ("guardou", "Recife")),
    ("guarda isso: o backup roda às 3 da manhã", (), ("guardou", "backup")),
    ("forget what I said about the garage", ("the garage door is on pin PC9",), ("esqueceu", "garage")),
    ("esquece a gaveta", ("a senha do wifi fica na gaveta",), ("esqueceu", "gaveta")),
    ("where does my sister live?", ("my sister lives in Recife",), ("fala", "Recife")),
    ("quando roda o backup?", ("o backup roda às 3 da manhã",), ("fala", r"\b3\b")),
    # comandos de verdade, conferidos no disco
    ("create a folder called fotos in {d}", (), ("existe", "fotos")),
    ("cria a pasta {d}/musicas", (), ("existe", "musicas")),
    ("make a new directory {d}/old/2024", (), ("existe", "old/2024")),
    ("write hello to the file {d}/oi.txt", (), ("contem", "oi.txt", "hello")),
    ("cria um arquivo {d}/nota.txt com o texto bom dia", (), ("contem", "nota.txt", "bom dia")),
    ("list the files in /etc/ssl", (), ("comando", r"\bls\b.*/etc/ssl")),
    ("lista o que tem em /usr/share/doc", (), ("comando", r"\bls\b.*/usr/share/doc")),
    ("show the contents of /etc/hostname", (), ("comando", r"(cat|head|less).*/etc/hostname")),
    # o que não existe aqui
    ("open the calculator", (), ("sem_ferramenta",)),
    ("clica no botão ok", (), ("sem_ferramenta",)),
    ("show me the window list", (), ("sem_ferramenta",)),
    ("faz um desenho de um gato", (), ("sem_ferramenta",)),
    # conversa
    ("good morning!", (), ("sem_ferramenta",)),
    ("obrigado pela ajuda", (), ("sem_ferramenta",)),
    ("who are you?", (), ("fala", r"Gargantua")),
    ("quem é você?", (), ("fala", r"Gargantua")),
    # pesquisa
    ("search the web for raspberry pi 5 price", (), ("pesquisou",)),
    ("pesquisa a previsão do tempo em Curitiba", (), ("pesquisou",)),
    ("look up the latest debian release", (), ("pesquisou",)),
    ("procura na internet como ligar um sensor dht22", (), ("pesquisou",)),
]


def _julgar(conferir, fala, comandos, pasta):
    tipo = conferir[0]
    if tipo == "fala":
        return bool(re.search(conferir[1], fala))
    if tipo == "guardou":
        return any(conferir[1].lower() in f.lower() for f in memoria.ler())
    if tipo == "esqueceu":
        return not any(conferir[1].lower() in f.lower() for f in memoria.ler())
    if tipo == "existe":
        return (pasta / conferir[1]).exists()
    if tipo == "contem":
        arquivo = pasta / conferir[1]
        return arquivo.exists() and conferir[2] in arquivo.read_text(errors="replace")
    if tipo == "comando":
        return any(re.search(conferir[1], c) for c in comandos)
    if tipo == "sem_ferramenta":
        return not comandos
    if tipo == "pesquisou":
        return bool(comandos) and bool(fala)
    raise ValueError(tipo)


def rodar(tarefas=TAREFAS, motor=None, mostrar=print):
    motor = motor or Motor()
    original = pastas.MEMORIA
    pasta = Path(tempfile.mkdtemp(prefix="opentars-pi-prova-"))
    pastas.MEMORIA = pasta / "memoria-da-prova.json"
    certas, tempos, erros = 0, [], []
    try:
        for pedido, fatos, conferir in tarefas:
            pastas.gravar_json(pastas.MEMORIA, list(fatos))
            pedido = pedido.format(d=pasta)
            comandos = []

            def so_na_pasta(comando, nivel):     # a prova nunca muda nada fora da pasta dela
                return nivel != "perigoso" and str(pasta) in comando and ".." not in comando

            agente = Agente(motor, so_na_pasta, lambda tipo, texto: comandos.append(texto) if tipo == "comando" else None)
            inicio = time.time()
            fala = agente.responder(pedido)
            tempos.append(time.time() - inicio)
            ok = _julgar(conferir, fala, comandos, pasta)
            certas += ok
            if not ok:
                erros.append((pedido.replace(str(pasta), "{d}"), comandos[:2], fala[:90]))
            mostrar(f"{'ok ' if ok else 'XX '} {tempos[-1]:5.1f}s  {pedido.replace(str(pasta), '{d}')}")
    finally:
        pastas.MEMORIA = original
        shutil.rmtree(pasta, ignore_errors=True)
        motor.desligar()
    tempos.sort()
    mostrar(f"\nopenTARS Pi test: {certas}/{len(tarefas)} (median {tempos[len(tempos) // 2]:.1f} s per task)")
    for erro in erros:
        mostrar(f"  failed: {erro}")
    return certas, len(tarefas), erros
