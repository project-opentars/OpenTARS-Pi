"""Pesquisa na web, só leitura e só com a biblioteca padrão: o SearXNG da pessoa, se ela tiver um, ou a API pública da Wikipédia."""
import html
import json
import re
import unicodedata
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
              "an in on at for to it its explain tell define please my mine i eu meu minha meus minhas you voce você".split())


def chaves(texto):
    """As palavras que importam: 'what is the' na busca da Wikipédia trazia 'What Is a Nation?' (medido na placa, 06/11)."""
    return [p for p in re.findall(r"\w+", texto.lower()) if p not in _VAZIAS and (len(p) > 1 or p.isdigit())]


def raizes(texto):
    """As chaves cortadas em 5 letras: "descobriu" acha "descoberta", "invented" acha "invention"."""
    return {p[:5] for p in chaves(texto)}


# O que a pergunta quer de volta. Escolher a frase pelo tipo da resposta acerta mais que só contar palavras:
# "quem pintou Guernica" quer um nome, "quando acabou a guerra" quer um ano (prova de capacidade, 07/11).
_TIPOS = (("ano", r"\b(em que ano|que ano|qual ano|quando|when|what year|which year|in what year)\b"),
          ("medida", r"\b(altura|alto|alta|tall|height|high|comprimento|length|long|distancia|distance|far|longe|peso|weight|profundidade|deep|depth|area)\b"),
          ("numero", r"\b(quantos|quantas|how many|how much|populacao|population)\b"),
          ("nome", r"\bcapital\b|\b(qual|what|which|quem|who)\b.{0,12}\b(maior|menor|mais|largest|biggest|smallest|longest|highest|tallest|first|primeir[oa]|extenso)\b"),
          ("definicao", r"^(quem foi|quem e|who was|who is|who were|o que e|o que sao|what is|what are|what was|define|defina)\b"),
          ("nome", r"^(quem|who|whom)\b"),
          ("lugar", r"^(onde|where)\b"))
_PADRAO_TIPO = {
    "ano": r"\b(1[0-9]{3}|20[0-9]{2})\b",
    "medida": r"\d[\d.,\s\u00a0]*\s?(m|metros|metres|meters|km|quil[oô]metros|kilometres|kilometers|ft|feet|p[eé]s|mi|miles|milhas|kg|toneladas|tonnes)\b",
    "numero": r"\d",
}
# Relações comuns e as raízes que aparecem no texto (o verbo da pergunta raramente é o da frase: "wrote" e "written").
_RELACOES = (({"pintou", "pintado", "pintor", "painted", "painter", "painting", "pintura", "quadro"}, {"pint", "pain", "quad"}),
             ({"escreveu", "escrito", "escritor", "autor", "wrote", "written", "writer", "author", "write"}, {"escr", "writ", "wrot", "auto", "auth", "nove", "roma"}),
             ({"descobriu", "descoberta", "descobridor", "discovered", "discovery", "discoverer"}, {"desc", "disc", "cheg"}),
             ({"inventou", "invencao", "inventor", "invented", "invention"}, {"inve", "pate"}),
             ({"fundou", "fundada", "fundado", "fundador", "founded", "founder"}, {"fund", "foun"}),
             ({"nasceu", "nascimento", "born", "birth"}, {"nasc", "born", "birt"}),
             ({"morreu", "morte", "died", "death", "die"}, {"morr", "mort", "died", "deat"}),
             ({"terminou", "acabou", "fim", "end", "ended", "ending"}, {"term", "acab", "fim", "end", "ende"}),
             ({"comecou", "inicio", "began", "start", "started", "begin"}, {"come", "inic", "bega", "star"}),
             ({"pisou", "pousou", "chegou", "walked", "landed", "landing"}, {"pis", "pous", "cheg", "walk", "land", "aterr"}),
             ({"caiu", "queda", "fell", "fall"}, {"cai", "qued", "fell", "fall", "derr"}),
             ({"maior", "largest", "biggest"}, {"maior", "larg", "bigg"}), ({"menor", "smallest"}, {"menor", "smal"}),
             ({"extenso", "longest", "comprido"}, {"exte", "long", "compr"}),
             ({"capital"}, {"capi"}), ({"altura", "tall", "height", "alta", "alto", "high"}, {"altu", "tall", "heig", "metr", "high", "alt"}))
_SO_DA_PERGUNTA = {"ano", "year", "quando", "when", "vez", "pela", "time", "mais", "most", "fica", "ficam", "located", "localizada", "localizado",
                   "situada", "situado", "esta", "está"}
_INICIO_PERGUNTA = re.compile(r"^(?:quem|qual|quais|quando|onde|como|o que|em que ano|que ano|who|what|which|when|where|how|why|did|does|do|is|are|was|were)"
                              r"(?:\s+(?:e|é|foi|era|são|sao|is|was|are|were|did|does|do|the|a|o|os|as))*\s+", re.IGNORECASE)
_ROMANOS = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5"}
_MAIUSCULAS_COMUNS = {"the", "it", "its", "in", "a", "an", "o", "os", "as", "em", "no", "na", "este", "esta", "this", "he", "she", "ele", "ela", "segundo",
                      "according", "also", "however", "during", "durante", "after", "depois", "before", "antes"}


def tipo_de_resposta(consulta):
    n = "".join(c for c in unicodedata.normalize("NFKD", consulta) if not unicodedata.combining(c)).lower().strip()
    return next((tipo for tipo, padrao in _TIPOS if re.search(padrao, n)), None)


def _relacao(palavras):
    """(palavras que são a relação, raízes que a frase deve ter)."""
    usadas, raizes_ = set(), set()
    for formas, alvo in _RELACOES:
        achadas = formas & set(palavras)
        if achadas:
            usadas |= achadas
            raizes_ |= alvo
    return usadas, raizes_


def _r4(texto):
    return {_ROMANOS.get(p, p)[:4] for p in chaves(texto)}


_INTERVALO = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\)?\s*[–-]\s*(?:\d{1,2}\s+\w+\s+)?(1[0-9]{3}|20[0-9]{2})\b")


def _tem_relacao(frase, raizes_rel, titulo=""):
    """Quantas raízes da relação a frase tem, sem contar as que só repetem o título ("Discover America" não descobriu nada)."""
    do_titulo = set(chaves(titulo))
    palavras = [p for p in chaves(frase) if p not in do_titulo]
    achadas = sum(1 for r in raizes_rel if any(p.startswith(r) for p in palavras))
    if not achadas and raizes_rel & {"term", "end", "come", "star"} and _INTERVALO.search(frase):
        achadas = 1                      # "(1939 – 1945)": o intervalo diz quando começou e quando acabou
    return achadas


def nomes_novos(frase, pergunta):
    """Nomes próprios da frase que não estão na pergunta (a primeira palavra da frase não conta: é maiúscula por ser a primeira)."""
    ja = {p[:4] for p in chaves(pergunta)}
    tokens = re.findall(r"[\wÀ-ú'-]+", frase)
    return [p for p in tokens[1:] if p[:1].isupper() and p.lower() not in _MAIUSCULAS_COMUNS and p.lower()[:4] not in ja and not p.isupper()]


def _titulo_e_outro_nome(titulo, consulta):
    """O título é um nome que a pergunta não tem (Júpiter para "maior planeta"), e não o próprio assunto ("Lista de planetas")."""
    do_titulo, da_pergunta = _r4(titulo), _r4(consulta)
    return bool(titulo) and not (do_titulo & da_pergunta) and titulo[:1].isupper()


def _nota_da_frase(frase, consulta, tipo, raizes_rel, assunto, titulo=""):
    """(nota, responde?). Responde quando tem o tipo de resposta que a pergunta quer junto com a relação pedida."""
    rel = _tem_relacao(frase, raizes_rel, titulo)
    if rel and re.search(r"\b(segund[oa]|terceir[oa]|quart[oa]|second|third|fourth)\s+(maior|menor|mais|largest|biggest|smallest|longest|highest)\b", frase.lower()):
        rel -= 1                         # "o segundo maior planeta anão" não é o maior
    nota = len(_r4(frase) & {_ROMANOS.get(p, p)[:4] for p in assunto}) + 2 * rel
    tem_tipo = False
    if tipo == "nome":                   # o nome novo pode ser o próprio título: "Júpiter é o maior planeta"
        novo = nomes_novos(frase, consulta) or _titulo_e_outro_nome(titulo, consulta)
        tem_tipo = bool(novo) and (rel or not raizes_rel)
    elif tipo in _PADRAO_TIPO:
        tem_tipo = bool(re.search(_PADRAO_TIPO[tipo], frase, re.IGNORECASE)) and (rel or not raizes_rel)
    if tem_tipo:
        nota += 3
    if tipo in ("nome", "lugar") and re.search(r"\b(maior|menor|largest|biggest|smallest|longest|mais extenso)\s+(\w+)", frase.lower()):
        nota += 2 * any(p[:4] in {a[:4] for a in assunto} for p in re.findall(r"\b(?:maior|menor|largest|biggest|smallest|longest|extenso)\s+(\w+)", frase.lower()))
    return nota, bool(tem_tipo or (rel and tipo is None))


def melhor_frase(texto, consulta, assunto=""):
    """A frase do resumo que melhor responde: a que tem a relação e o tipo de resposta que a pergunta pede.
    As palavras do título não contam: na página France, quem responde "capital of France" é a frase que fala de capital."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú])", texto) if f.strip()]
    if not frases:
        return ""
    palavras = chaves(consulta)
    usadas, raizes_rel = _relacao(palavras)
    resto = [p for p in palavras if p not in usadas and p not in _SO_DA_PERGUNTA]
    procura = set(resto) - set(chaves(assunto)) or set(resto)
    tipo = tipo_de_resposta(consulta)
    return max(frases, key=lambda f: (_nota_da_frase(f, consulta, tipo, raizes_rel, procura, assunto)[0], -frases.index(f)))


def _resumo(idioma, pagina):
    try:
        chave = urllib.parse.quote(pagina.get("key", ""), safe="")
        dados = json.loads(_baixar(f"https://{idioma}.wikipedia.org/api/rest_v1/page/summary/{chave}"))
        return None if dados.get("type") == "disambiguation" else dados.get("extract", "")
    except (OSError, ValueError):
        return ""


def _procurar_paginas(consulta, idioma, limite=5):
    url = f"https://{idioma}.wikipedia.org/w/rest.php/v1/search/page?" + urllib.parse.urlencode({"q": consulta, "limit": limite})
    return json.loads(_baixar(url)).get("pages", [])


def wikipedia(consulta, idioma="en"):
    """A API pública da Wikipédia. Procura pelo assunto, pelo assunto com a relação e pela pergunta inteira, lê os resumos
    e fica com a frase que responde. O primeiro sai com 'fraco' quando nenhuma frase tem o que a pergunta pede."""
    palavras = list(dict.fromkeys(chaves(consulta))) or consulta.split()
    usadas, raizes_rel = _relacao(palavras)
    assunto = [p for p in palavras if p not in usadas and p not in _SO_DA_PERGUNTA] or palavras
    com_relacao = [p for p in palavras if p not in _SO_DA_PERGUNTA]
    tipo = tipo_de_resposta(consulta)
    natural = _INICIO_PERGUNTA.sub("", consulta.strip(" ?!.")).strip()      # "maior planeta do sistema solar": a busca acha Júpiter assim
    consultas = list(dict.fromkeys(q for q in (" ".join(assunto), " ".join(com_relacao), natural) if q))
    paginas, vistas = [], set()
    for q in consultas:
        try:
            achadas = _procurar_paginas(q, idioma, 4)
        except (OSError, ValueError):
            if q == consultas[-1] and not paginas:
                raise
            continue
        for p in achadas:
            if p.get("key") not in vistas:
                vistas.add(p.get("key"))
                paginas.append(p)
    paginas = paginas[:10]
    with ThreadPoolExecutor(8) as grupo:
        resumos = list(grupo.map(lambda p: _resumo(idioma, p), paginas))
    achados = []
    for ordem, (pagina, resumo) in enumerate(zip(paginas, resumos)):
        if resumo is None:      # página de desambiguação não responde nada
            continue
        titulo = pagina.get("title", "")
        limpo = re.sub(r"\s*\(.*?\)", "", titulo)
        frase = melhor_frase(resumo, consulta, limpo) or _limpar(pagina.get("excerpt", ""))
        do_titulo = _r4(limpo)
        cobre = len(do_titulo & {_ROMANOS.get(p, p)[:4] for p in assunto})
        nota_frase, responde = _nota_da_frase(frase, consulta, tipo, raizes_rel, [p for p in assunto if p[:4] not in do_titulo], limpo)
        if tipo in ("definicao", "lugar"):        # aqui a página do próprio assunto é a resposta
            responde = cobre >= max(1, len(assunto) - (tipo == "definicao"))
        sobra = 0 if responde else len(do_titulo - {_ROMANOS.get(p, p)[:4] for p in palavras})
        # o assunto ganha da página que só repete as palavras ("France", não "Capital punishment in France"), menos quando a resposta é outro nome
        nota = 3 * cobre - sobra + nota_frase + (4 if responde else 0) - 0.1 * ordem
        if re.match(r"(lista|list|history|historia|formacao|formação|timeline|cronologia|index|indice|índice|outline|glossary|glossario)\b", limpo.lower()):
            nota -= 5                    # páginas de lista e de história raramente respondem em uma frase
        achados.append((nota, responde, pagina, frase))
    achados.sort(key=lambda a: -a[0])
    saida = [{"titulo": p.get("title", ""), "url": f"https://{idioma}.wikipedia.org/wiki/{urllib.parse.quote(p.get('key', ''), safe='')}",
              "trecho": _recorte(f, raizes_rel)} for _, _, p, f in achados]
    if saida:
        saida[0]["fraco"] = not achados[0][1]
    return saida


def _recorte(frase, raizes_rel, tamanho=300):
    """A frase inteira se couber; senão o pedaço em volta da relação, que é onde a resposta costuma estar."""
    if len(frase) <= tamanho:
        return frase
    minusculas = frase.lower()
    posicoes = [m.start() for r in raizes_rel for m in re.finditer(r"\b" + re.escape(r), minusculas)]
    if not posicoes or min(posicoes) < tamanho - 80:
        return frase[:tamanho - 1].rsplit(" ", 1)[0] + "…"
    inicio = max(0, min(posicoes) - 120)
    return "…" + frase[inicio:inicio + tamanho - 2].split(" ", 1)[-1].rsplit(" ", 1)[0] + "…"


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
