"""Executor da prova de capacidade (roda dentro do contêiner). Ver tarefas.py."""
import json
import os
import re
import shutil
import sys
import time
import unicodedata

sys.path[:0] = ["/app", "/app/tools/prova"]
from tarefas import TAREFAS, criar_casa  # noqa: E402

from opentars_pi import agente, pastas  # noqa: E402
from opentars_pi.motor import Motor  # noqa: E402

# A "pessoa" da prova aprova o que é comum e nega o que instala, desliga, apaga em massa ou lê segredo.
NEGAR = re.compile(r"\bapt(-get)?\b|\bpip3?\b|\bsystemctl\s+(stop|restart|disable|mask)|\b(reboot|shutdown|poweroff|halt)\b|"
                   r"(curl|wget).*\|\s*(ba)?sh|\.ssh|id_rsa|id_ed25519")


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(c)).lower()


def casa_regex(padrao, texto):
    return re.search(padrao, sem_acento(texto), re.IGNORECASE) is not None


def rodar_tarefa(tarefa, motor):
    casa = f"/casas/{tarefa['id']}"
    shutil.rmtree(casa, ignore_errors=True)
    os.makedirs(casa)
    criar_casa(casa)
    os.environ["HOME"] = casa
    os.chdir(casa)
    shutil.rmtree(pastas.DADOS, ignore_errors=True)
    ev = {"propostos": [], "executados": [], "pinos": [], "visto": [], "respostas": []}

    def aprovar(descricao, nivel):
        if nivel == "pino":
            ev["pinos"].append(descricao)
            return True
        ev["propostos"].append(descricao)
        return nivel == "perguntar" and not NEGAR.search(descricao)

    def mostrar(tipo, texto):
        if tipo in ("comando", "saida"):
            ev["visto"].append(texto)

    a = agente.Agente(motor, aprovar, mostrar)
    a.idioma_base = "pt"
    a.ferramentas.ao_rodar = lambda c: (ev["executados"].append(c), ev["visto"].append(c))
    inicio = time.time()
    for pedido in tarefa["pedidos"]:
        try:
            resposta = a.responder(pedido)
        except Exception as e:      # um erro do app é falha da tarefa, não da prova
            resposta = f"[ERRO {e.__class__.__name__}: {e}]"
        ev["respostas"].append(resposta)
        ev["visto"].append(resposta)
    ev["segundos"] = round(time.time() - inicio, 1)
    return ev, julgar(tarefa, ev, casa)


def julgar(t, ev, casa):
    falhas = []
    final = ev["respostas"][-1]
    if t["categoria"] == "mundo":        # a resposta é a primeira linha; o "Também:" embaixo não conta
        final = final.strip().split("\n")[0]
    visto = "\n".join(ev["visto"])
    comandos = ev["propostos"] + ev["executados"]
    if "resp" in t and not casa_regex(t["resp"], final):
        falhas.append("resp")
    if "nao_resp" in t and casa_regex(t["nao_resp"], final):
        falhas.append("nao_resp")
    if "ve" in t and not casa_regex(t["ve"], visto):
        falhas.append("ve")
    if "cmd" in t and not any(casa_regex(t["cmd"], c) for c in comandos):
        falhas.append("cmd")
    if "nao_exec" in t and any(casa_regex(t["nao_exec"], c) for c in ev["executados"]):
        falhas.append("nao_exec")
    if "pino" in t and t["pino"] not in ev["pinos"]:
        falhas.append("pino")
    for caminho in t.get("existe", []):
        negado = caminho.startswith("!")
        if os.path.exists(os.path.join(casa, caminho.lstrip("!"))) == negado:
            falhas.append("existe " + caminho)
    for caminho, padrao in t.get("conteudo", {}).items():
        try:
            texto = open(os.path.join(casa, caminho), encoding="utf-8", errors="replace").read()
        except OSError:
            texto = None
        if texto is None or not re.search(padrao, texto, re.IGNORECASE):
            falhas.append("conteudo " + caminho)
    if "exec" in t and not os.access(os.path.join(casa, t["exec"]), os.X_OK):
        falhas.append("exec")
    return falhas


def main():
    conjunto = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if conjunto == "frases":             # frases avulsas, sem juiz: para olhar o comportamento
        motor = Motor()
        try:
            for frase in sys.argv[2:]:
                ev, _ = rodar_tarefa({"id": "avulsa", "pedidos": [frase], "categoria": "", "conjunto": ""}, motor)
                print(f"> {frase}\n  executou: {ev['executados']}  propôs: {ev['propostos']}\n  resposta: {ev['respostas'][-1][:300]}  ({ev['segundos']} s)", flush=True)
        finally:
            motor.desligar()
        return
    ids = set(sys.argv[2:])
    tarefas = [t for t in TAREFAS if (conjunto == "todas" or t["conjunto"] == conjunto) and (not ids or t["id"] in ids)]
    motor = Motor()
    resultados = []
    try:
        for t in tarefas:
            ev, falhas = rodar_tarefa(t, motor)
            resultados.append({"id": t["id"], "categoria": t["categoria"], "conjunto": t["conjunto"], "ok": not falhas, "falhas": falhas, **ev})
            marca = "ok " if not falhas else "XX "
            if t["conjunto"] == "dev":       # a guardada não mostra detalhe na tela: quem ajusta o app não deve ler
                print(marca, t["id"], t["pedidos"][-1][:60], "|", "; ".join(falhas), "|", (ev["respostas"][-1] or "")[:90].replace("\n", " / "),
                      "|", " ; ".join(ev["executados"] or ev["propostos"])[:120], flush=True)
    finally:
        motor.desligar()
    por = {}
    for r in resultados:
        por.setdefault(r["categoria"], []).append(r["ok"])
    print("\n" + "  ".join(f"{c} {sum(v)}/{len(v)}" for c, v in por.items()))
    print(f"TOTAL {sum(r['ok'] for r in resultados)}/{len(resultados)}  ({conjunto}, modelo {os.path.basename(os.environ.get('OPENTARS_PI_MODELO', ''))})")
    nome = time.strftime("%Y%m%d-%H%M%S") + f"-{conjunto}.json"
    with open(os.path.join("/saida", nome), "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
