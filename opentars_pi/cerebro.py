"""Quem pensa quando as regras não bastam.

- Gargantua Pi (270M): o padrão, cabe em qualquer placa. Contrato próprio, texto cru no llama.cpp (contrato.py).
- Gargantua Lite (0,8B): na própria placa, quando ela tem memória; muito melhor nos comandos que as regras não cobrem,
  mais lento. Usa o contrato do app completo: o prompt e as 19 ferramentas do treino, byte a byte (contrato_gargantua.json).
- Um Gargantua de outro computador da rede (Ollama ou servidor compatível com OpenAI): a pessoa escolhe com
  `opentars brain URL`, e o pedido sai da placa só para esse endereço.

As ferramentas de tela das 19 não existem numa placa: o agente responde que não há tela, sem rodar nada.
"""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

from . import contrato, pastas

_CONTRATO = json.loads((Path(__file__).parent / "contrato_gargantua.json").read_text(encoding="utf-8"))
IDIOMA_APP = {"pt": "IDIOMA: responda sempre em português do Brasil, de forma natural e curta. Se o usuário escrever em outro idioma, responda no idioma dele.",
              "en": "LANGUAGE: always reply in English, naturally and briefly. If the user writes in another language, reply in that language."}
FERRAMENTAS_DA_PLACA = {"execute_terminal", "search_web", "remember", "forget"}


class CerebroPi:
    """O Gargantua Pi de 270M, pelo contrato próprio."""
    nome = "Gargantua Pi"

    def __init__(self, motor):
        self.motor = motor

    def sistema(self, memoria, idioma):
        return contrato.sistema("", memoria, idioma)

    def preparar(self, sistema):
        self.motor.ligar()
        self.motor.preparar_prefixo(contrato.prefixo(sistema))

    def jogada(self, mensagens, ao_pedaco=None):
        estado = {"chamada": False}

        def pedaco(texto):
            if texto.startswith("<start_function_call>"):
                estado["chamada"] = True
            if not estado["chamada"] and not texto.startswith("<") and ao_pedaco:
                ao_pedaco(texto)
        return contrato.ler_resposta(self.motor.completar(contrato.renderizar(mensagens), pedaco))

    def conversar(self, voltas, pedido, ao_pedaco=None):
        self.motor.ligar()
        fala = self.motor.completar(contrato.renderizar_conversa(voltas, pedido), ao_pedaco, maximo=120, temperatura=0.4)
        return contrato.ler_resposta(fala)[1]


def _bloco_da_placa():
    """O bloco THIS COMPUTER do app, com o que vale numa placa (sem tela)."""
    sistema = "Linux"
    try:
        for linha in Path("/etc/os-release").read_text().splitlines():
            if linha.startswith("PRETTY_NAME="):
                sistema = linha.split("=", 1)[1].strip('"')
    except OSError:
        pass
    casa = str(Path.home())
    return ("\nTHIS COMPUTER\n"
            f"- System: {sistema}; desktop: unknown; session: no graphical session\n"
            "- Screen: no access to the screen\n"
            "- NO graphical session: terminal only. Don't try to open apps, click, type keys or take screenshots; "
            "use execute_terminal and the files the user attached, and give links to the user.\n"
            f"- User: {Path.home().name} (home folder {casa})\n"
            f"- Today: {time.strftime('%Y-%m-%d (%A)')}\n")


class CerebroGargantua:
    """Um Gargantua 2 (Lite ou 2B) pelo contrato do app, local ou na rede."""

    def __init__(self, url, modelo="", motor=None, nome="Gargantua"):
        self.url, self.modelo, self.motor, self.nome = url.rstrip("/"), modelo, motor, nome
        self.ollama = None
        self._arquivo = self._pronto = None

    def sistema(self, memoria, idioma):
        texto = _CONTRATO["sistema"] + _bloco_da_placa()
        if memoria:
            texto += "\nWHAT THE USER ASKED YOU TO REMEMBER (use it: e.g. their browser, folders, names; don't ask again what is here):\n" + "".join(f"- {f}\n" for f in memoria)
        return texto + "\n" + IDIOMA_APP[idioma] + "\n"

    def preparar(self, sistema):
        if self.motor:
            self.motor.ligar()
            # o prompt com as 19 ferramentas leva minutos numa placa lenta: lido uma vez, fica guardado em disco (como o do Pi)
            self._arquivo = self.motor._arquivo_do_prefixo((sistema or "") + json.dumps(_CONTRATO["ferramentas"]))
            if self._pronto != self._arquivo and (pastas.CACHE / self._arquivo).exists():
                try:
                    self.motor._pedir("/slots/0?action=restore", {"filename": self._arquivo}).close()
                    self._pronto = self._arquivo
                except (OSError, ValueError):
                    pass
        if self.ollama is None:
            try:
                urllib.request.urlopen(self.url + "/api/tags", timeout=3).close()
                self.ollama = True
            except OSError:
                self.ollama = False

    def _pedir(self, caminho, corpo, tempo=900):
        pedido = urllib.request.Request(self.url + caminho, json.dumps(corpo).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(pedido, timeout=tempo) as r:
                return json.loads(r.read())
        except (OSError, ValueError) as e:
            from .motor import MotorForaDoAr
            raise MotorForaDoAr(f"{self.nome} did not answer ({e.__class__.__name__}).") from e

    def _converter(self, mensagens):
        """Do formato interno do agente para o da API: chamadas com tool_calls e resultados com role tool."""
        saida = []
        for i, m in enumerate(mensagens):
            if m["role"] == "assistant" and m.get("chamada"):
                nome, argumentos = m["chamada"]
                chamada = {"id": f"c{i}", "type": "function", "function": {"name": nome, "arguments": argumentos if self.ollama else json.dumps(argumentos, ensure_ascii=False)}}
                saida.append({"role": "assistant", "content": "", "tool_calls": [chamada]})
            elif m["role"] == "tool":
                saida.append({"role": "tool", "content": m["content"], "tool_call_id": f"c{i - 1}", "name": m.get("name", "")})
            else:
                saida.append({"role": m["role"], "content": m["content"]})
        return saida

    def jogada(self, mensagens, ao_pedaco=None):
        """(chamada, fala): chamada = (nome, argumentos) ou None."""
        conversa = self._converter(mensagens)
        if self.ollama:
            r = self._pedir("/api/chat", {"model": self.modelo, "messages": conversa, "tools": _CONTRATO["ferramentas"], "stream": False,
                                          "think": False, "options": {"temperature": 0.1}, "keep_alive": "30m"})
            mensagem = r.get("message", {})
        else:
            corpo = {"messages": conversa, "tools": _CONTRATO["ferramentas"], "temperature": 0.1, "max_tokens": 400,
                     "chat_template_kwargs": {"enable_thinking": False}}
            if self.modelo:
                corpo["model"] = self.modelo
            mensagem = self._pedir("/v1/chat/completions", corpo)["choices"][0]["message"]
            if self.motor and self._arquivo and self._pronto != self._arquivo:
                try:
                    self.motor._pedir("/slots/0?action=save", {"filename": self._arquivo}).close()
                    self._pronto = self._arquivo
                    for velho in pastas.CACHE.glob("*.bin"):         # a data no prompt muda todo dia: não acumula no cartão
                        if velho.name != self._arquivo and time.time() - velho.stat().st_mtime > 2 * 86400:
                            velho.unlink()
                except (OSError, ValueError):
                    pass
        chamadas = mensagem.get("tool_calls") or []
        if chamadas:
            funcao = chamadas[0]["function"]
            argumentos = funcao.get("arguments") or {}
            if isinstance(argumentos, str):
                try:
                    argumentos = json.loads(argumentos)
                except ValueError:
                    argumentos = {}
            return (funcao["name"], {k: str(v) for k, v in argumentos.items()}), ""
        fala = re.sub(r"<think>.*?</think>", "", mensagem.get("content") or "", flags=re.S).strip()
        if ao_pedaco and fala:
            ao_pedaco(fala)
        return None, fala

    def conversar(self, voltas, pedido, ao_pedaco=None):
        mensagens = [{"role": "system", "content": self.sistema([], "pt" if re.search(r"[ãõçáéíóúê]| (você|voce|é|não|nao) ", " " + pedido.lower()) else "en")}]
        for usuario, resposta in voltas:
            mensagens += [{"role": "user", "content": usuario}, {"role": "assistant", "content": resposta}]
        mensagens.append({"role": "user", "content": pedido})
        self.preparar(None)
        return self.jogada(mensagens, ao_pedaco)[1]


def escolher(motor):
    """O cérebro configurado. OPENTARS_PI_CEREBRO (ou "cerebro" na config): "lite" usa o Gargantua Lite da placa; um endereço usa o da rede."""
    escolha = os.environ.get("OPENTARS_PI_CEREBRO") or pastas.config().get("cerebro") or ""
    if isinstance(escolha, dict):
        return CerebroGargantua(escolha.get("url", ""), escolha.get("modelo", ""), nome=escolha.get("nome") or "Gargantua")
    if escolha == "lite":                # o mesmo motor, com o Lite: quem desliga o motor no fim desliga este
        motor.modelo = os.environ.get("OPENTARS_PI_MODELO_LITE") or os.environ.get("OPENTARS_PI_MODELO") or str(pastas.MODELOS / ARQUIVO_LITE)
        motor.jinja = True
        return CerebroGargantua(f"http://127.0.0.1:{motor.porta}", motor=motor, nome="Gargantua Lite")
    if escolha.startswith("http"):
        url, _, modelo = escolha.partition("#")
        return CerebroGargantua(url, modelo or "ProjectOpenTARS/Gargantua-2", nome="Gargantua")
    return CerebroPi(motor)


ARQUIVO_LITE = "gargantua-1.2-lite-qwen3.5-0.8b-Q4_0.gguf"
SHA_LITE = "c519103c65de13742ed3fded28aad066d75834dada4c651ce1bbcb87747d9c27"
URL_LITE = "https://huggingface.co/OpenTARS/Gargantua-2-Lite/resolve/main/" + ARQUIVO_LITE
MB_LITE = 479


def descricao():
    """Uma linha dizendo quem pensa agora."""
    escolha = os.environ.get("OPENTARS_PI_CEREBRO") or pastas.config().get("cerebro") or ""
    if isinstance(escolha, dict):
        return f"{escolha.get('nome') or 'Gargantua'} at {escolha.get('url')} ({escolha.get('modelo') or 'default model'})"
    return "Gargantua Lite (0.8B, on this board)" if escolha == "lite" else "Gargantua Pi (270M, on this board)"


def testar_rede(url, modelo):
    """(ok, modelo, mensagem). Confere se há um Gargantua respondendo nesse endereço."""
    url = url.rstrip("/")
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            nomes = [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
        if not modelo:
            modelo = next((n for n in nomes if "gargantua-2" in n.lower() and "lite" not in n.lower()), "") or next((n for n in nomes if "gargantua" in n.lower()), "")
        if not modelo:
            return False, "", "Ollama answered, but it has no Gargantua model. On that computer: ollama pull ProjectOpenTARS/Gargantua-2"
        return True, modelo, f"Ollama with {modelo}"
    except (OSError, ValueError):
        pass
    try:
        with urllib.request.urlopen(url + "/v1/models", timeout=5) as r:
            dados = json.loads(r.read())
        modelo = modelo or (dados.get("data") or [{}])[0].get("id", "")
        return True, modelo, f"OpenAI-compatible server ({modelo or 'one model'})"
    except (OSError, ValueError) as e:
        return False, "", f"nothing answered at {url} ({e.__class__.__name__})"
