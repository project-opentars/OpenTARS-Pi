"""As 4 ferramentas do Gargantua Pi. Os resultados têm o formato que o modelo viu no treino."""
import os
import re
import signal
import subprocess
import threading

from . import busca, memoria, seguranca

TEMPO_COMANDO = 30
LIMITE_SAIDA = 1500
NAO_APROVOU = "The user did not approve this command. It did not run."


def _coletar(fluxo, destino):
    """Lê até o fim guardando só a ponta: `yes` não pode encher a memória de uma placa de 1 GB."""
    for pedaco in iter(lambda: fluxo.read(4096), b""):
        destino += pedaco
        del destino[:-LIMITE_SAIDA * 4]


def rodar(comando, tempo=TEMPO_COMANDO):
    """{success, exit_code, stdout, stderr, message}."""
    processo = subprocess.Popen(["bash", "-c", comando], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=os.path.expanduser("~"), start_new_session=True, env={**os.environ, "DEBIAN_FRONTEND": "noninteractive"})
    saida, erro = bytearray(), bytearray()
    leitores = [threading.Thread(target=_coletar, args=a, daemon=True) for a in ((processo.stdout, saida), (processo.stderr, erro))]
    for leitor in leitores:
        leitor.start()
    try:
        codigo = processo.wait(timeout=tempo)
    except subprocess.TimeoutExpired:
        os.killpg(processo.pid, signal.SIGKILL)
        processo.wait()
        return {"success": False, "message": f"The command ran for more than {tempo}s and was stopped."}
    for leitor in leitores:
        leitor.join(1)      # um programa em segundo plano pode segurar a saída aberta
    processo.stdout.close()
    processo.stderr.close()
    texto = lambda b: bytes(b).decode("utf-8", "replace")[-LIMITE_SAIDA:]   # noqa: E731
    return {"success": codigo == 0, "exit_code": codigo, "stdout": texto(saida), "stderr": texto(erro),
            "message": "Command finished." if codigo == 0 else "Command finished with an error."}


class Ferramentas:
    def __init__(self, aprovar, auto=False, idioma="en", ao_rodar=None):
        """aprovar(comando, nivel) -> bool. auto: roda o que muda coisas sem perguntar, menos o perigoso. ao_rodar(comando): logo antes de rodar."""
        self.aprovar, self.auto, self.idioma, self.ao_rodar = aprovar, auto, idioma, ao_rodar

    def chamar(self, nome, argumentos):
        funcao = {"execute_terminal": self.terminal, "search_web": self.pesquisar, "remember": self.lembrar, "forget": self.esquecer}.get(nome)
        if not funcao:
            return {"success": False, "message": f"ERROR: unknown tool {nome}. Use execute_terminal, search_web, remember or forget."}
        return funcao(argumentos)

    def terminal(self, a):
        comando = re.sub(r'"~/', '"$HOME/', str(a.get("command") or "").strip())    # entre aspas o shell não expande o ~, e o modelo escreve assim
        if not comando:
            return {"success": False, "message": "ERROR: empty command."}
        nivel = seguranca.nivel(comando)
        if nivel == "perigoso" or (nivel == "perguntar" and not self.auto):
            if not self.aprovar(comando, nivel):
                return {"success": False, "message": NAO_APROVOU}
        if self.ao_rodar:
            self.ao_rodar(comando)
        return rodar(comando)

    def pesquisar(self, a):
        consulta = str(a.get("query") or "").strip()
        if not consulta:
            return {"success": False, "message": "ERROR: no search terms given (empty 'query')."}
        resultados, erro = busca.buscar(consulta, "pt" if self.idioma == "pt" else "en")
        if not resultados:
            return {"success": False, "action": "search_web", "query": consulta, "message": f"Web search failed ({erro}). Tell the user the search did not work."}
        return {"success": True, "resultados": resultados}

    def lembrar(self, a):
        if memoria.lembrar(a.get("fact")):
            return {"success": True, "message": "SUCCESS: saved. It will be in your instructions from now on."}
        return {"success": False, "message": "ERROR: nothing to save."}

    def esquecer(self, a):
        saiu = memoria.esquecer(a.get("fact"))
        if saiu:
            return {"success": True, "message": "SUCCESS: forgot: " + "; ".join(saiu)}
        return {"success": False, "message": "Nothing saved that matches that. The saved facts are in your instructions."}
