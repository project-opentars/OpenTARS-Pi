"""O contrato do Gargantua Pi: o prompt, as 4 ferramentas e o texto exato que o modelo viu no treino.

O modelo foi treinado com o molde de conversa do FunctionGemma. O llama.cpp não lê esse formato de chamada, então o app monta
o texto e lê a resposta aqui. tests/test_contrato.py confere byte a byte contra o molde real. Mudar qualquer linha pede retreino.
"""
import json
import re

SISTEMA = (
    "You are Gargantua Pi, a small local AI assistant that runs on this computer with a few tools, inside the openTARS Pi app.\n"
    "- Your name is Gargantua Pi. openTARS Pi is the app you run in, not your name.\n"
    "- When the user asks you to DO something, do it with the tools (terminal, web search, memory), step by step, and check the result.\n"
    "- When it is just a question or small talk, answer directly, without tools.\n"
    "- You have no screen, windows, mouse or apps. If asked for one, say you cannot do it here.\n"
    "- Never say something worked unless a tool result confirmed it.\n"
    "- Destructive actions (deleting many files, formatting, rm -rf) need the user's explicit confirmation.\n"
    "- Answer short, in the user's language.\n"
)
BLOCO_MEMORIA = "WHAT THE USER ASKED YOU TO REMEMBER (use it: e.g. their browser, folders, names; don't ask again what is here):\n"
IDIOMA = {
    "pt": "IDIOMA: responda sempre em português do Brasil, de forma natural e breve. Se a pessoa escrever em outro idioma, responda nesse idioma.",
    "en": "LANGUAGE: always reply in English, naturally and briefly. If the user writes in another language, reply in that language.",
}
AVISO_IDIOMA = {"pt": "[Context from openTARS, not a new request] The user writes in Portuguese: answer in Portuguese.",
                "en": "[Context from openTARS, not a new request] The user writes in English: answer in English."}

# (nome, descrição, parâmetros, obrigatórios): igual às 4 da lista do treino
FERRAMENTAS = (
    ("execute_terminal", "Run a shell command (non-interactive).", ("command",), ("command",)),
    ("search_web", "Search the web (or a service like youtube) and open the results.", ("query", "service"), ("query",)),
    ("remember", "Save a fact about the user for future conversations.", ("fact",), ("fact",)),
    ("forget", "Forget saved facts containing these words.", ("fact",), ("fact",)),
)
PARADAS = ["<end_function_call>", "<start_function_response>", "<end_of_turn>"]


def sistema(computador="", memoria=(), idioma="en"):
    """O prompt de sistema: o fixo, o bloco THIS COMPUTER, a memória e a linha de idioma, nessa ordem."""
    texto = SISTEMA
    if computador:
        texto += "\n" + computador + "\n"
    if memoria:
        texto += "\n" + BLOCO_MEMORIA + "".join(f"- {f}\n" for f in memoria)
    return texto + "\n" + IDIOMA[idioma] + "\n"


def _declaracao(nome, descricao, parametros, obrigatorios):
    campos = ",".join(f"{p}:{{description:<escape><escape>,type:<escape>STRING<escape>}}" for p in sorted(parametros))
    exigidos = ",".join(f"<escape>{p}<escape>" for p in obrigatorios)
    return (f"<start_function_declaration>declaration:{nome}{{description:<escape>{descricao}<escape>,parameters:{{"
            f"properties:{{{campos}}},required:[{exigidos}],type:<escape>OBJECT<escape>}}}}<end_function_declaration>")


def _argumentos(argumentos):
    return ",".join(f"{k}:<escape>{v}<escape>" for k, v in sorted(argumentos.items()))


def renderizar(mensagens):
    """O texto para o modelo continuar. Sem <bos>: o llama.cpp põe sozinho.

    mensagens: a de sistema primeiro; depois {"role": "user", "content"}, {"role": "assistant", "content"},
    {"role": "assistant", "chamada": (nome, argumentos)} e {"role": "tool", "name", "content"}.
    """
    saida = ["<start_of_turn>developer\n", mensagens[0]["content"].strip()]
    saida += [_declaracao(*f) for f in FERRAMENTAS]
    saida.append("<end_of_turn>\n")
    anterior = None
    for m in mensagens[1:]:
        if m["role"] == "tool":
            saida.append(f"<start_function_response>response:{m['name']}{{value:<escape>{m['content']}<escape>}}<end_function_response>")
            anterior = "resposta"
            continue
        papel = "model" if m["role"] == "assistant" else m["role"]
        if anterior != "resposta":
            saida.append(f"<start_of_turn>{papel}\n")
        if m.get("chamada"):
            nome, argumentos = m["chamada"]
            saida.append(f"<start_function_call>call:{nome}{{{_argumentos(argumentos)}}}<end_function_call>")
            anterior = "chamada"
        else:
            saida.append(m["content"].strip() + "<end_of_turn>\n")
            anterior = None
    if anterior != "resposta":
        saida.append("<start_of_turn>model\n")
    return "".join(saida)


def renderizar_conversa(historico, pedido):
    """Conversa sem ferramentas: sem prompt de sistema, como nos exemplos 'simples' do treino. O modelo fala melhor assim, e o texto
    é curto: na placa não há prompt de 360 tokens para ler."""
    voltas = "".join(f"<start_of_turn>user\n{u.strip()}<end_of_turn>\n<start_of_turn>model\n{r.strip()}<end_of_turn>\n" for u, r in historico)
    return f"{voltas}<start_of_turn>user\n{pedido.strip()}<end_of_turn>\n<start_of_turn>model\n"


def prefixo(texto_do_sistema):
    """O começo fixo do prompt: o que o motor pode guardar pronto de um pedido para o outro."""
    return renderizar([{"role": "system", "content": texto_do_sistema}]).removesuffix("<start_of_turn>model\n")


_CHAMADA = re.compile(r"<start_function_call>\s*call:([A-Za-z_]+)\{(.*)\}?\s*$", re.DOTALL)
_ARGUMENTO = re.compile(r"([A-Za-z_]+):<escape>(.*?)<escape>", re.DOTALL)


def ler_resposta(texto):
    """(chamada, fala). chamada = (nome, argumentos) ou None. O texto vem sem a marca de fim, que é parada do llama.cpp."""
    achou = _CHAMADA.search(texto)
    if achou:
        return (achou.group(1), dict(_ARGUMENTO.findall(achou.group(2)))), ""
    return None, re.sub(r"<[a-z_]+>", "", texto).strip()


def resultado(dados):
    """O resultado de uma ferramenta como o treino viu: JSON, sem escapar acento."""
    return json.dumps(dados, ensure_ascii=False)
