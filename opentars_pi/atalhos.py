"""O que não precisa de modelo. Numa placa o modelo é pequeno e lento: estado da placa, memória, pinos e recusas saem aqui,
na hora e sem errar. O que sobra (comandos livres e conversa) vai para o Gargantua Pi."""
import os
import re
import time
import unicodedata

from . import comandos, memoria, murph, placa
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
                   r"\b(placa|cpu|processador|board|chip)\b.{0,25}\b(temperatura|temperature|temp|quente|hot)\b|\bhow (hot|warm)\b|\boverheat|\b(superaquec|esquentando)|^(qual a )?temperatura\??$|^temperature\??$")
_LIGADA = re.compile(r"\buptime\b|\b(ha )?quanto tempo\b.{0,30}\b(ligad|rodando)|\bhow long\b.{0,30}\b(running|been on|been up|up)\b")
_IP = re.compile(r"\b(meu ip|o ip|endereco ip|ip address|my ip|the ip|ip local|ip da placa)\b|^ip\??$")
_CPU = re.compile(r"\b(uso|carga|usage|load)\b.{0,15}\b(cpu|processador)\b|\b(cpu|processador)\b.{0,15}\b(uso|carga|usage|load)\b|\b(quantos nucleos|how many cores)\b")
_QUE_PLACA = re.compile(r"\b(que|qual|which|what)\b.{0,12}\b(placa|board|computador|computer|hardware)\b.{0,12}\b(e|esta|essa|is|this)\b|"
                        r"\b(modelo|model)\b.{0,20}\b(placa|board|computador|computer)\b")
_HORA = re.compile(r"\b(que horas|what time|horas sao)\b")
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
_PEDE_CODIGO = re.compile(r"\b(escreve|escreva|escrever|write|cria|crie|criar|create|make|faz|faca|fazer|gera|gere|generate|programa|programe|code)\b.{0,40}"
                          r"\b(codigo|script|programa|program|code|funcao|function|app|aplicativo|site|website|hello world|ola mundo)\b")
_OLA_MUNDO = {"python": 'print("Hello, world!")', "bash": 'echo "Hello, world!"', "shell": 'echo "Hello, world!"', "javascript": 'console.log("Hello, world!");',
              "node": 'console.log("Hello, world!");', "c": '#include <stdio.h>\n\nint main(void) {\n    puts("Hello, world!");\n    return 0;\n}'}


def _codigo(n, idioma):
    if re.search(r"\b(hello world|ola mundo)\b", n):
        for linguagem, exemplo in _OLA_MUNDO.items():
            if re.search(rf"\b{linguagem}\b", n):
                return exemplo
    return t("codigo", idioma)


_QUEM = re.compile(r"\b(quem (e|es) (voce|tu)|qual (e )?o seu nome|como voce se chama|who are you|what are you|what is your name|what's your name|"
                   r"o que voce (faz|sabe fazer|consegue fazer)|what can you do)\b")


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
                                 r"( ai| isso| disso| this| na memoria| to memory)?( que| that|:)\s*")
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
_PAPO = re.compile(r"\b(tudo bem|tudo bom|como vai|como voce esta|como esta voce|how are you|how's it going|what'?s up|e ai|ta bem)\b")
_DE_QUEM_PEDE = re.compile(r"\b(meu|minha|meus|minhas|my|mine)\b|\b(onde eu|where do i) (moro|live|trabalho|work)\b")
_SAUDACAO = re.compile(r"^(oi|ola|opa|e ai|bom dia|boa tarde|boa noite|hi|hello|hey|good (morning|afternoon|evening))\b[\s!.,]*(tudo bem|gargantua|there)?[\s!?.]*$")
_OBRIGADO = re.compile(r"^(valeu|obrigad[oa]|brigad[oa]|thanks|thank you|thx)\b.{0,20}$")


def _sabe_de_memoria(n):
    """A pergunta fala de algo que a pessoa mandou lembrar? Aí a resposta está no prompt, não na web."""
    palavras = {p for p in re.findall(r"\w{4,}", n)}
    return any(palavras & set(re.findall(r"\w{4,}", normalizar(f))) for f in memoria.ler())


def resolver(pedido, idioma):
    """{'fala': texto}, {'pino': (...)}, {'comando': shell}, {'pesquisa': consulta}, {'conversa': True} ou None (o modelo com as ferramentas)."""
    n = normalizar(pedido)
    if pino := _pino(n):
        return {"pino": pino}
    fala = _memoria(pedido, n, idioma) or _estado(n, idioma) or _recusa(n, idioma) or (t("quem", idioma) if _QUEM.search(n) else None)
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
    tarefa, confianca = murph.classificar(pedido)
    if tarefa == "visao" and confianca > 0.85:     # "o que é isso aqui na tela", que as regras não pegaram
        return {"fala": t("tela", idioma)}
    if _sabe_de_memoria(n):
        return None
    if _PAPO.search(n):
        return {"conversa": True}
    pergunta = _PERGUNTA.search(n)
    if pergunta and _DE_QUEM_PEDE.search(n):
        return {"fala": t("nao_me_contou", idioma)}
    if pergunta or (tarefa == "busca" and confianca > 0.6):
        return {"pesquisa": pedido.strip(" ?.")}
    if _PEDE_CODIGO.search(n) or (tarefa == "codigo" and confianca > 0.8):
        return {"fala": _codigo(n, idioma)}
    return {"conversa": True} if tarefa in ("simples", "geral") else None
