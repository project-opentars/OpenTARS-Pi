"""O que a pessoa pediu para lembrar: uma lista de frases num arquivo, que entra no prompt."""
import re
import unicodedata

from . import pastas


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()


def ler():
    fatos = pastas.ler_json(pastas.MEMORIA, [])
    return [str(f) for f in fatos] if isinstance(fatos, list) else []


def lembrar(fato):
    fato = " ".join(str(fato or "").split())
    if not fato:
        return False
    fatos = ler()
    if _sem_acento(fato) not in map(_sem_acento, fatos):
        pastas.gravar_json(pastas.MEMORIA, fatos + [fato])
    return True


def _palavras(texto):
    return {p for p in re.findall(r"[\w./~-]+", _sem_acento(texto)) if len(p) > 1}


_VAZIAS = _palavras("o a os as um uma de do da dos das que eu meu minha sobre isso disse the of my i that about what told is on em no na")


def esquecer(texto):
    """Apaga os fatos que dividem mais palavras com o texto. Devolve os que saíram."""
    procura = _palavras(texto) - _VAZIAS
    notas = [(len(_palavras(f) & procura), f) for f in ler()]
    melhor = max((n for n, _ in notas), default=0)
    if not melhor:
        return []
    saiu = [f for n, f in notas if n == melhor]
    pastas.gravar_json(pastas.MEMORIA, [f for f in ler() if f not in saiu])
    return saiu


def pino_de(palavra):
    """O pino que a pessoa guardou para esse nome ('o relé está no pino PC5'), ou None."""
    alvo = _sem_acento(palavra)
    for fato in ler():
        pino = re.search(r"\b(P[A-K]\d{1,2}|GPIO\d{1,3})\b", fato, re.IGNORECASE)
        if pino and alvo in _sem_acento(fato):
            return pino.group(1).upper()
    return None
