"""Série de caminhos escrita em 06/11 antes de treinar a Murph do Pi, no jeito de quem usa a placa. Roda sem modelo:
    python3 tools/murph/serie_rotas.py [pasta do código]
Depois de ajustar por causa dela, ela deixa de valer como prova: escreva outra."""
import os
import re
import sys
import tempfile

os.environ["OPENTARS_PI_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from opentars_pi import atalhos  # noqa: E402

PLACA = r"MB|GB|°C|Running|Ligada|Memory|Memória|cores|núcleos|sensor|\d+:\d+|\d+\.\d+\.\d+"
SOBRE = r"openTARS|Gargantua|Murph|Enzo|plain words|palavras simples|this board|nesta placa"
RECUSA = r"no screen|não tem tela|full openTARS|openTARS completo"
CODIGO = r"too much for a model|demais para um modelo|print\(|echo |console\.log|puts\("
S = [
    ("how much memory am i using right now", "fala", PLACA), ("tem espaço no cartão?", "fala", PLACA), ("is it hot in there", "fala", PLACA), ("quantos núcleos tem aqui", "fala", PLACA),
    ("what machine is this", "fala", PLACA), ("essa placa é o quê", "fala", PLACA), ("what distro is this", "agir", ""), ("what's your hardware", "fala", PLACA), ("como tá a placa", "fala", PLACA), ("give me a health check", "fala", PLACA),
    ("what can i ask you", "fala", SOBRE), ("o que você sabe fazer", "fala", SOBRE), ("do you need internet", "fala", SOBRE), ("você manda meus dados pra algum lugar?", "fala", SOBRE), ("what's murph", "fala", SOBRE),
    ("quem te criou", "fala", SOBRE), ("which model are you", "fala", SOBRE), ("tell me about opentars pi", "fala", SOBRE), ("o que é gargantua", "fala", SOBRE), ("help", "fala", SOBRE),
    ("9 times 12", "fala", r"108"), ("sqrt of 81", "fala", r"\b9\b"), ("quanto é 45 menos 17", "fala", r"28"), ("20% de 350", "fala", r"70"), ("100 / 8", "fala", r"12[.,]5"), ("2 to the power of 8", "fala", r"256"),
    ("run btop", "comando", "top"), ("execute lsblk", "comando", "lsblk"), ("roda o neofetch", "comando", "neofetch"), ("ls -la /tmp", "comando", "ls"), ("which processes eat the most memory", "comando", "ps"),
    ("mostra os processos", "comando", "ps"), ("o que tá comendo cpu", "agir", ""), ("list usb devices", "agir", ""), ("show my network interfaces", "agir", ""), ("reinicia o ssh", "agir", ""), ("reboot the board", "agir", ""), ("instala o git", "agir", ""), ("list the services running", "agir", ""),
    ("what is the population of canada", "pesquisa", ""), ("quem pintou a mona lisa", "pesquisa", ""), ("how does a transistor work", "pesquisa", ""), ("what is swap", "pesquisa", ""), ("o que é um kernel", "pesquisa", ""), ("raspberry pi 5 specs", "pesquisa", ""), ("temperatura em manaus hoje", "pesquisa", ""), ("what time is it in tokyo", "pesquisa", ""), ("qual a diferença entre ram e rom", "pesquisa", ""),
    ("how are you doing", "conversa", ""), ("conta uma piada", "conversa", ""), ("write me a haiku", "conversa", ""), ("estou cansado", "conversa", ""), ("you're funny", "conversa", ""), ("boa noite gargantua, até amanhã", "conversa", ""),
    ("write a python script that reads a sensor", "fala", CODIGO), ("faz uma função em c que soma dois números", "fala", CODIGO), ("hello world in bash", "fala", CODIGO), ("make a hello world", "fala", CODIGO),
    ("open firefox", "fala", RECUSA), ("tira um print", "fala", RECUSA), ("toca uma música", "fala", RECUSA), ("desenha um gato", "fala", RECUSA), ("fala comigo por voz", "fala", RECUSA),
]


def ok(plano, tipo, padrao):
    plano = plano or {}
    if tipo == "agir":
        return not plano or "comando" in plano
    if tipo == "fala":
        return bool(re.search(padrao, plano.get("fala") or ""))
    if tipo == "comando":
        return padrao in (plano.get("comando") or "")
    return tipo in plano


certas = 0
for pedido, tipo, padrao in S:
    idioma = "pt" if atalhos.normalizar(pedido) != pedido.lower() or re.search(r"\b(o|a|é|tem|quanto|quem|mostra|roda|conta|faz|essa|como|tá)\b", pedido) else "en"
    plano = atalhos.resolver(pedido, idioma)
    if ok(plano, tipo, padrao):
        certas += 1
    else:
        print(f"errou [{tipo}] {pedido!r}: {str(plano)[:90]}")
print(f"{certas}/{len(S)}")
