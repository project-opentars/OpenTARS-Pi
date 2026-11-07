"""O que não precisa de modelo. Numa placa o modelo é pequeno e lento: estado da placa, memória, pinos e recusas saem aqui,
na hora e sem errar. O que sobra (comandos livres e conversa) vai para o Gargantua Pi."""
import os
import re
import time
import unicodedata

from . import busca, comandos, conta, memoria, murph, placa
from .textos import duracao, t

_POLIDEZ = r"^(por favor,? |please,? |pode |voce pode |can you |could you |from now on,? |a partir de agora,? |de agora em diante,? )?"


def normalizar(texto):
    """Minúsculas, sem acento, com o mesmo tamanho do texto original quando possível."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower().strip()


# ---- estado da placa ----
_DA_ASSISTENTE = re.compile(r"\b(sua memoria|your memory|na memoria|da memoria|in memory|from memory|to memory)\b")
_MEMORIA = re.compile(r"\b(ram|memoria|memory)\b")
_QUANTO = re.compile(r"\b(quanta|quanto|livre|disponivel|sobrando|usada|uso|usando|how much|free|usage|used|left|available)\b")
_DISCO = re.compile(r"\b(disco|disk|armazenamento|storage|sd card|cartao sd|espaco livre|espaco no|free space)\b")
_TEMP = re.compile(r"\b(temperatura|temperature|temp)\b.{0,20}\b(placa|cpu|processador|sistema|board|soc|system|chip)\b|"
                   r"\b(placa|cpu|processador|board|chip)\b.{0,25}\b(temperatura|temperature|temp|quente|hot)\b|\bhow (hot|warm)\b|\boverheat|^(what'?s|whats|what is|qual e|qual) (the |a )?(temperature|temperatura)\??$|\b(superaquec|esquentando)|^(qual a )?temperatura\??$|^temperature\??$")
_LIGADA = re.compile(r"\buptime\b|\b(ha )?quanto tempo\b.{0,30}\b(ligad|rodando)|\bhow long\b.{0,30}\b(running|been on|been up|up)\b")
_IP = re.compile(r"\b(meu ip|o ip|endereco ip|ip address|my ip|the ip|ip local|ip da placa)\b|^ip\??$")
_CPU = re.compile(r"\b(uso|carga|usage|load)\b.{0,15}\b(cpu|processador)\b|\b(cpu|processador)\b.{0,15}\b(uso|carga|usage|load)\b|\b(quantos nucleos|how many cores)\b")
_QUE_PLACA = re.compile(r"\b(que|qual|which|what)\b.{0,12}\b(placa|board|computador|computer|hardware)\b.{0,12}\b(e|esta|essa|is|this)\b|"
                        r"\b(modelo|model)\b.{0,20}\b(placa|board|computador|computer)\b|\b(distro|distribuicao|sistema operacional|operating system)\b")
_HORA = re.compile(r"\b(que horas|what time|horas sao)\b")
_OUTRO_LUGAR = re.compile(r"\b(in|em|no|na|nos|at)\s+(?!(this|the|esta|essa|aqui|here|placa|board)\b)[a-z]{3,}\??$")
_DATA = re.compile(r"\b(que dia|qual a data|que data|what day|what's the date|whats the date|what is the date|today's date)\b")
_ESTADO = re.compile(r"\b(status|estado|como esta)\b.{0,15}\b(placa|board|sistema|system)\b|\b(placa|board|sistema|system)\b.{0,10}\b(status|estado)\b|"
                     r"^status\??$|^estado\??$|\bhow is the (board|system)\b")


def _estado(n, idioma):
    if _DA_ASSISTENTE.search(n):
        return None
    if _MEMORIA.search(n) and _QUANTO.search(n):
        total, livre = placa.memoria()
        return t("mem", idioma, total=total, livre=livre, usada=total - livre)
    if _DISCO.search(n):
        total, livre = placa.disco()
        return t("disco", idioma, total=total, livre=livre, usado=total - livre)
    if _TEMP.search(n):
        temp = placa.temperatura()
        return t("temp", idioma, temp=temp) if temp is not None else t("sem_temp", idioma)
    if _LIGADA.search(n):
        return t("ligada", idioma, tempo=duracao(placa.ligada_ha(), idioma))
    if _IP.search(n):
        ip = placa.ip_local()
        return t("ip", idioma, ip=ip) if ip else t("sem_ip", idioma)
    if _CPU.search(n):
        return t("cpu", idioma, nucleos=os.cpu_count(), carga=os.getloadavg()[0])
    if _QUE_PLACA.search(n):
        return t("placa", idioma, modelo=placa.modelo(), sistema=placa.sistema())
    if _ESTADO.search(n):
        return estado_completo(idioma)
    if _OUTRO_LUGAR.search(n):       # "what time is it in tokyo": isso é com a busca
        return None
    if _HORA.search(n):
        return time.strftime("%H:%M")
    if _DATA.search(n):
        return time.strftime("%d/%m/%Y" if idioma == "pt" else "%Y-%m-%d")
    return None


def estado_completo(idioma):
    total, livre = placa.memoria()
    temp = placa.temperatura()
    return t("estado", idioma, modelo=placa.modelo(), total=total, livre=livre, disco=placa.disco()[1],
             temp=t("temp_linha", idioma, temp=temp) if temp is not None else "", tempo=duracao(placa.ligada_ha(), idioma))


# Código: o modelo de 270M não sustenta. O script de "imprime a data" saiu `echo "21 28 31 30..."` (medido em 06/11).
_OLA_MUNDO = {"python": 'print("Hello, world!")', "bash": 'echo "Hello, world!"', "shell": 'echo "Hello, world!"', "javascript": 'console.log("Hello, world!");',
              "node": 'console.log("Hello, world!");', "c": '#include <stdio.h>\n\nint main(void) {\n    puts("Hello, world!");\n    return 0;\n}'}


def _codigo(n, idioma):
    if re.search(r"\b(hello world|ola mundo)\b", n):
        return next((exemplo for linguagem, exemplo in _OLA_MUNDO.items() if re.search(rf"\b{linguagem}\b", n)), _OLA_MUNDO["python"])
    return t("codigo", idioma)


# ---- sobre o próprio produto: a busca devolvia uma página qualquer da Wikipédia ----
_SOBRE = (("sobre_murph", r"\bmurph\b"),
          ("sobre_autor", r"\b(criou|criador|desenvolveu|quem fez|made you|made this|created|creator|built|developer|author|autor)\b"),
          ("sobre_local", r"\b(offline|nuvem|cloud|internet|privad\w*|private|privacy|dados|data|sem rede|espiona\w*|spy)\b"),
          ("sobre_modelo", r"\b(gargantua|modelo|model|parametros|parameters|llm)\b"),
          ("sobre_opentars", r"\bopen ?tars\b"),
          ("sobre_ajuda", r"\b(ajuda|help|capabilit\w*|skills?|features?|comandos|commands|pode fazer|can you do|consegue|sabe fazer|como (te )?us\w+|how (to|do i) use|exemplos?|examples?|funcoes|funcionalidades|recursos|what can i)\b"))


def _sobre(n, idioma):
    return next((t(chave, idioma) for chave, padrao in _SOBRE if re.search(padrao, n)), t("quem", idioma))


# ---- o que a placa não faz ----
_TELA = re.compile(r"\b(clica|clique|clicar|click|arrasta|arraste|drag|mouse)\b|\b(screenshot|print da tela|captura de tela)\b|"
                   r"\b(fecha|feche|abre|abra|move|mova|minimiza|maximiza|close|open|minimize|maximize)\b.{0,12}\b(janela|window)\b|"
                   r"\b(na|da|minha) tela\b|\b(my|the) screen\b")
_ABRIR = re.compile(_POLIDEZ + r"(abre|abra|abrir|open|launch|inicia|inicie|start|fecha|feche|close)\s+(o |a |the |my |meu |minha )?([\w-]+|bloco de notas)\??$")
_COMPLETO = re.compile(r"\b(por voz|com voz|em voz alta|out loud|read aloud|use your voice|voice mode|modo de voz)\b|"
                       r"\b(edita|edite|corta|corte|desenha|desenhe|gera|gere|cria|crie|faz|faca|tira|tire|draw|generate|create|make|edit|crop|take)\b.{0,30}\b(foto|fotografia|imagem|desenho|photo|picture|image)\b")


def _recusa(n, idioma):
    if _TELA.search(n):
        return t("tela", idioma)
    if _COMPLETO.search(n):
        return t("completo", idioma)
    aberto = _ABRIR.search(n)
    if aberto and not os.path.exists(os.path.expanduser("~/" + aberto.group(4))):
        return t("tela", idioma)
    return None


# ---- memória ----
_LEMBRAR = re.compile(_POLIDEZ + r"(lembra|lembre|lembrar|anota|anote|grava|grave|guarda|guarde|salva|salve|memoriza|memorize|nao esquece|nao esqueca|"
                                 r"remember|note|save|make a note|keep in mind|don'?t forget|write down)\b"
                                 r"( ai| isso| disso| this| na memoria| to memory)?( que| that|:|(?= (my|meu|minha|eu|i)\b))\s*")
_ESQUECER = re.compile(_POLIDEZ + r"(esquece|esqueca|esquecer|forget)\b|\b(apaga|apague|remove|remova|tira|tire|limpa|delete|clear|take)\b.{0,40}\b(memoria|memory)\b")
_VER_MEMORIA = re.compile(r"\bo que (voce )?(lembra|guardou|sabe (de|sobre) mim)\b|\bwhat do you (remember|know about me)\b|\b(mostra|mostre|show)( a| your)? (sua )?(memoria|memory)\b|^/mem")


def _memoria(pedido, n, idioma):
    if _VER_MEMORIA.search(n):
        fatos = memoria.ler()
        return t("memoria", idioma, fatos="\n".join("- " + f for f in fatos)) if fatos else t("memoria_vazia", idioma)
    achado = _LEMBRAR.search(n)
    if achado:
        fato = (pedido.strip() if len(pedido.strip()) == len(n) else n)[achado.end():].strip(" .")
        return t("anotado", idioma, fato=fato) if fato and memoria.lembrar(fato) else None
    if _ESQUECER.search(n):
        saiu = memoria.esquecer(n)
        return t("esqueci", idioma, fato="; ".join(saiu)) if saiu else t("nada_guardado", idioma)
    return None


# ---- pinos ----
_NOME_PINO = re.compile(r"\b(p[a-k]\d{1,2}|gpio ?\d{1,3})\b")
_LIGAR = re.compile(r"\b(liga|ligue|ligar|acende|acenda|ativa|ative|turn on|switch on|enable)\b|\bturn\b.{1,30}\bon\b|\bset\b.{1,30}\bhigh\b")
_DESLIGAR = re.compile(r"\b(desliga|desligue|desligar|apaga|apague|desativa|desative|turn off|switch off|disable)\b|\bturn\b.{1,30}\boff\b|\bset\b.{1,30}\blow\b")
_LER = re.compile(r"\b(le|leia|ler|read|estado|state|valor|value)\b")
_FALA_DE_PINO = re.compile(r"\b(pino|pin|gpio|rele|relay|led)\b")
_SEM_PESO = {"liga", "ligue", "ligar", "acende", "acenda", "ativa", "ative", "desliga", "desligue", "desligar", "apaga", "apague", "turn", "switch",
             "para", "por", "favor", "please", "the", "pino", "pin", "gpio", "off", "low", "high", "set", "leia", "read", "enable", "disable"}


def _achar_pino(n):
    nome = _NOME_PINO.search(n)
    if nome:
        return nome.group(1).replace(" ", "").upper()
    for palavra in re.findall(r"[a-z0-9_-]{3,}", n):
        pino = None if palavra in _SEM_PESO else memoria.pino_de(palavra)
        if pino:
            return pino
    return None


def _pino(n):
    """('escrever', pino, 1|0), ('ler', pino), ('qual',) ou None."""
    desligar, ligar = bool(_DESLIGAR.search(n)), bool(_LIGAR.search(n))
    pino = _achar_pino(n)
    if (ligar or desligar) and (pino or _FALA_DE_PINO.search(n)):
        return ("escrever", pino, 0 if desligar else 1) if pino else ("qual",)
    if _LER.search(n) and (_NOME_PINO.search(n) or (pino and _FALA_DE_PINO.search(n))):
        return ("ler", pino)
    return None


# ---- pesquisa ----
_PESQUISA = re.compile(_POLIDEZ + r"(pesquisa|pesquise|pesquisar|procura|procure|busca|busque|search|look up|google)\b"
                                  r"( na web| na internet| the web| the internet| online)?( for| about| sobre| por)?\s+")


# O modelo de 270M inventa fatos ("a capital da Mongólia é Tóquio", medido em 06/11): pergunta sobre o mundo vai para a busca.
_PERGUNTA = re.compile(r"^(quem|qual|quais|quando|onde|quanto|quanta|quantos|quantas|como|por que|porque|pra que|o que|oque|"
                       r"what|what's|whats|who|who's|which|when|where|why|how|is|are|does|did|do|can|explain|explique|explica|define|defina|me explica)\b")
_DE_QUEM_PEDE = re.compile(r"\b(meu|minha|meus|minhas|my|mine)\b|\b(onde eu|where do i) (moro|live|trabalho|work)\b")
_SAUDACAO = re.compile(r"^(oi|ola|opa|e ai|bom dia|boa tarde|boa noite|hi|hello|hey|good (morning|afternoon|evening))\b[\s!.,]*(tudo bem|gargantua|there)?[\s!?.]*$")
_OBRIGADO = re.compile(r"^(valeu|obrigad[oa]|brigad[oa]|thanks|thank you|thx)\b.{0,20}$")
_COMO_FAZ = re.compile(r"^(how (do|can|to|should) |como (eu |faco|fazer|posso|se )|what('s| is) the (best )?way to )")
_COM_VOCE = re.compile(r"\b(voce|tu|te|teu|tua|seu|sua|you|your|yourself)\b")
CONFIANCA_MINIMA = 0.45


def _fato_que_responde(n):
    """O fato guardado que responde a pergunta, ou None. A resposta sai dele: o modelo de 270M lê a memória e responde outra coisa (medido em 06/11).
    Pede pergunta pessoal ou que o fato cubra todas as palavras, senão "how does a fan work" traria "the fan is on pin PC2"."""
    procura = set(busca.chaves(n))
    notas = [(len(procura & set(busca.chaves(normalizar(f)))), f) for f in memoria.ler()]
    melhor, fato = max(notas, default=(0, None), key=lambda x: x[0])
    if melhor and (_DE_QUEM_PEDE.search(n) or melhor == len(procura)):
        return fato
    return None


def resolver(pedido, idioma):
    """{'fala': texto}, {'pino': (...)}, {'comando': shell}, {'pesquisa': consulta}, {'conversa': True} ou None (o modelo com as ferramentas).
    As regras cuidam do que precisa sair exato (pinos, memória, contas, caminhos); o resto a Murph separa pela intenção."""
    n = normalizar(pedido)
    if pino := _pino(n):
        return {"pino": pino}
    fala = _memoria(pedido, n, idioma) or _estado(n, idioma) or _recusa(n, idioma) or conta.resolver(n, idioma)
    if fala:
        return {"fala": fala}
    comando = comandos.plano(pedido, n)
    if comando:
        return {"comando": comando}
    achado = _PESQUISA.search(n)
    if achado:
        return {"pesquisa": (pedido.strip() if len(pedido.strip()) == len(n) else n)[achado.end():].strip(" ?.")}
    if _SAUDACAO.search(n):
        return {"fala": t("oi", idioma)}
    if _OBRIGADO.search(n):
        return {"fala": t("de_nada", idioma)}
    pergunta = _PERGUNTA.search(n)
    fato = _fato_que_responde(n) if pergunta else None
    if fato:
        return {"fala": t("lembro", idioma, fato=fato)}
    classe, confianca = murph.classificar(pedido)
    if confianca < CONFIANCA_MINIMA:
        classe = "mundo" if pergunta else "comando"
    if pergunta and _DE_QUEM_PEDE.search(n) and classe in ("mundo", "sobre", "papo"):
        return {"fala": t("nao_me_contou", idioma)}
    if classe == "comando" and _COMO_FAZ.search(n):     # quer aprender, não que rode: "how do I install docker?"
        return {"pesquisa": pedido.strip(" ?.")}
    if classe == "placa":
        return {"fala": estado_completo(idioma)}
    if classe == "sobre":
        fala = _sobre(n, idioma)
        if fala != t("quem", idioma) or _COM_VOCE.search(n) or not pergunta:
            return {"fala": fala}
        return {"pesquisa": pedido.strip(" ?.")}       # "quem pintou a mona lisa" não é sobre mim
    if classe == "tela":
        return {"fala": t("tela", idioma)}
    if classe == "conta":
        return {"fala": t("conta_nao", idioma)}
    if classe == "codigo":
        return {"fala": _codigo(n, idioma)}
    if classe == "papo":
        return {"conversa": True}
    if classe == "mundo":
        return {"pesquisa": pedido.strip(" ?.")}
    return None
