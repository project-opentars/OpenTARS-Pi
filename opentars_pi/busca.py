"""Pesquisa na web, só leitura e só com a biblioteca padrão: o SearXNG da pessoa, se ela tiver um, ou a API pública da Wikipédia."""
import html
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import VERSAO, pastas

AGENTE = f"openTARS-Pi/{VERSAO} (+https://github.com/project-opentars/OpenTARS-Pi)"
TEMPO = 12
MAXIMO = 3


def _baixar(url, dados=None):
    pedido = urllib.request.Request(url, data=dados, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(pedido, timeout=TEMPO) as r:
        return r.read(1_000_000).decode("utf-8", "replace")


def _limpar(texto):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", texto)).split())


def searxng(consulta, endereco):
    dados = json.loads(_baixar(f"{endereco.rstrip('/')}/search?" + urllib.parse.urlencode({"q": consulta, "format": "json"})))
    return [{"titulo": _limpar(r.get("title", ""))[:120], "url": r["url"], "trecho": _limpar(r.get("content", ""))[:300]}
            for r in dados.get("results", [])[:MAXIMO] if str(r.get("url", "")).startswith("http")]


_VAZIAS = set("o a os as um uma uns umas de do da dos das no na nos nas em que qual quais quem como onde quando quanto quanta quantos quantas e é foi são "
              "era por para pra sobre me explica explique explicar diga fala the of what whats which who whom how where when why is are was were do does did "
              "an in on at for to it its explain tell define please".split())


def chaves(texto):
    """As palavras que importam: 'what is the' na busca da Wikipédia trazia 'What Is a Nation?' (medido na placa, 06/11)."""
    return [p for p in re.findall(r"\w+", texto.lower()) if p not in _VAZIAS and (len(p) > 1 or p.isdigit())]


def melhor_frase(texto, consulta, assunto=""):
    """A frase do resumo que mais divide palavras com a pergunta. As palavras do título não contam: na página France, quem responde
    "capital of France" é a frase que fala de capital."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])", texto) if f.strip()]
    procura = set(chaves(consulta))
    procura = (procura - set(chaves(assunto))) or procura
    return max(frases, key=lambda f: len(set(chaves(f)) & procura), default="")


def _resumo(idioma, pagina):
    try:
        chave = urllib.parse.quote(pagina.get("key", ""), safe="")
        dados = json.loads(_baixar(f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{chave}"))
        return None if dados.get("type") == "disambiguation" else dados.get("extract", "")
    except (OSError, ValueError):
        return ""


def wikipedia(consulta, idioma="en"):
    """A API pública da Wikipédia. Lê o resumo das primeiras páginas e fica com a frase que melhor responde.
    O primeiro resultado sai com 'fraco' quando nenhuma frase cobre metade das palavras da pergunta."""
    palavras = list(dict.fromkeys(chaves(consulta))) or consulta.split()
    url = f"https://{idioma}.wikipedia.org/w/rest.php/v1/search/page?" + urllib.parse.urlencode({"q": " ".join(palavras), "limit": 5})
    paginas = json.loads(_baixar(url)).get("pages", [])
    with ThreadPoolExecutor(5) as grupo:
        resumos = list(grupo.map(lambda p: _resumo(idioma, p), paginas))
    procura, achados = set(palavras), []
    for pagina, resumo in zip(paginas, resumos):
        if resumo is None:      # página de desambiguação não responde nada
            continue
        titulo = pagina.get("title", "")
        limpo = re.sub(r"\s*\(.*?\)", "", titulo)
        frase = melhor_frase(resumo, consulta, limpo) or _limpar(pagina.get("excerpt", ""))
        cobertas = len((set(chaves(frase)) | set(chaves(limpo))) & procura)
        # a página do assunto ganha da que só repete as palavras: "France", não "Capital punishment in France" nem "Capital (French magazine)"
        nota = cobertas * 2 - len(set(chaves(limpo)) - procura) - (limpo != titulo)
        o_resto = procura - set(chaves(limpo))
        if o_resto and not o_resto & set(chaves(frase)):      # a frase só repete o título: não responde "capital da Argentina"
            nota -= 1
        achados.append((nota, cobertas, pagina, frase))
    achados.sort(key=lambda a: -a[0])
    saida = [{"titulo": p.get("title", ""), "url": f"https://{idioma}.wikipedia.org/wiki/{urllib.parse.quote(p.get('key', ''), safe='')}", "trecho": f[:300]}
             for _, _, p, f in achados]
    if saida:
        saida[0]["fraco"] = achados[0][1] * 2 < len(procura)
    return saida


def buscar(consulta, idioma="en"):
    """(resultados, erro). Tenta um caminho depois do outro; nada é aberto na placa."""
    if pastas.config().get("busca") is False:
        return [], "web search is off"
    consulta = " ".join(str(consulta or "").split())[:200]
    endereco = pastas.config().get("searxng")
    caminhos = ([lambda: searxng(consulta, endereco)] if endereco else []) + [lambda: wikipedia(consulta, idioma)]
    erro = "no results"
    for caminho in caminhos:
        try:
            resultados = caminho()
            if resultados:
                return resultados, None
        except (OSError, ValueError, KeyError) as e:
            erro = str(e)[:120]
    return [], erro
