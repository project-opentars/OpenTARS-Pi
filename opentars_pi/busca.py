"""Pesquisa na web, só leitura e só com a biblioteca padrão: o SearXNG da pessoa, se ela tiver um, ou a API pública da Wikipédia."""
import html
import json
import re
import urllib.parse
import urllib.request

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


_VAZIAS = set("o a os as um uma de do da dos das que qual quais quem como onde quando e the of what which who how where when is are in on for to".split())


def _palavras(texto):
    return {p for p in re.findall(r"\w+", texto.lower()) if p not in _VAZIAS and len(p) > 1}


def melhor_frase(texto, consulta):
    """A frase do resumo que mais divide palavras com a pergunta: a resposta costuma estar nela, não na primeira."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])", texto) if f.strip()]
    procura = _palavras(consulta)
    return max(frases, key=lambda f: len(_palavras(f) & procura), default="")


def wikipedia(consulta, idioma="en"):
    """A API pública da Wikipédia. O trecho vem do resumo da página, escolhido pela pergunta."""
    url = f"https://{idioma}.wikipedia.org/w/rest.php/v1/search/page?" + urllib.parse.urlencode({"q": consulta, "limit": MAXIMO})
    saida = []
    for pagina in json.loads(_baixar(url)).get("pages", []):
        chave = urllib.parse.quote(pagina.get("key", ""), safe="")
        trecho = _limpar(pagina.get("excerpt", ""))
        if not saida:      # só a primeira: cada página a mais é uma ida à rede numa placa lenta
            try:
                resumo = json.loads(_baixar(f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{chave}")).get("extract", "")
                trecho = melhor_frase(resumo, consulta) or trecho
            except (OSError, ValueError):
                pass
        saida.append({"titulo": pagina.get("title", ""), "url": f"https://{idioma}.wikipedia.org/wiki/{chave}", "trecho": trecho[:300]})
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
