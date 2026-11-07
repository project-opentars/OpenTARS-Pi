"""As frases do app, em português e inglês."""
import os
import re

from . import pastas

TEXTOS = {
    "en": {
        "mem": "{usada} MB of memory in use, {livre} MB free, out of {total} MB.",
        "disco": "{usado:.1f} GB used on the disk, {livre:.1f} GB free, out of {total:.1f} GB.",
        "temp": "The board is at {temp:.0f} °C.", "sem_temp": "This board has no temperature sensor I can read.",
        "ligada": "Running for {tempo}.", "ip": "This board's address is {ip}.", "sem_ip": "No network address right now.",
        "cpu": "{nucleos} cores, load {carga:.2f}.", "placa": "This is a {modelo}, running {sistema}.",
        "estado": "{modelo}\nMemory: {livre} of {total} MB free\nDisk: {disco:.1f} GB free\n{temp}Running for {tempo}",
        "temp_linha": "Temperature: {temp:.0f} °C\n",
        "tela": "This board has no screen for me to use, so I can't click, see windows or open apps. I can run a terminal command, search the web, remember things and use the pins.",
        "completo": "That needs the full openTARS app on a computer: https://project-opentars.github.io/OpenTARS/ Here I have the terminal, web search, memory and the pins.",
        "anotado": "Noted: {fato}.", "esqueci": "Forgotten: {fato}.", "nada_guardado": "I have nothing saved about that.", "esqueci_tudo": "Done, my memory is empty now.",
        "wifi": "Wi-Fi connected ({iface}), address {ip}.", "wifi_fora": "Wi-Fi is not connected.", "sem_wifi": "This board has no Wi-Fi.",
        "memoria_vazia": "My memory is empty.", "memoria": "Here is what I remember:\n{fatos}",
        "qual_pino": "Which pin? Use its name (like PC5 or GPIO17), or teach me first: remember that the relay is on pin PC5.",
        "pino_ligado": "{pino} is on.", "pino_desligado": "{pino} is off.", "pino_valor": "{pino} reads {valor}.",
        "pino_negado": "Okay, I did not touch the pin.", "pino_erro": "I could not use that pin: {erro}",
        "abatido": "I'm sorry to hear that. Take it easy; I'm here when you need me.",
        "nao_fiz": "I did not run anything, so nothing changed. Try asking in other words.",
        "oi": "Hi! What can I do on this board?", "lembro": "You told me: {fato}.", "nao_achei": "I could not find a good answer. The closest I found: {titulo} ({site}).",
        "codigo": "Writing programs is too much for a model this small, and I would rather not hand you broken code. The full openTARS has Gargantua Code Gen 2 for that: https://project-opentars.github.io/OpenTARS/", "de_nada": "You're welcome.",
        "sem_busca": "I could not search right now, and I would rather not guess.", "nao_me_contou": "You haven't told me that yet. Say: remember that…",
        "falhou": "That did not work: {erro}", "feito": "Done.", "negado": "Okay, I did not run it.", "sem_resposta": "I don't have an answer for that.",
        "de_onde": "From {site}: {trecho}", "tambem": "Also: {site} ({titulo})",
        "quem": "I'm Gargantua Pi, the AI of openTARS Pi. I run right here on this board, with no cloud: I run terminal commands, search the web, remember things and use the pins.",
        "sobre_opentars": "openTARS is an open source AI assistant that runs on your own computer, local by default. openTARS Pi is its edition for small boards: no desktop needed, just the terminal. Site: https://project-opentars.github.io/OpenTARS/",
        "sobre_modelo": "Gargantua Pi is the model that runs here: 270 million parameters, about 300 MB, trained by the openTARS project on top of FunctionGemma. It is small on purpose, so it fits on a board like this one.",
        "sobre_murph": "Murph is the small classifier that reads each request and decides where it goes: the board, the terminal, the web or the model. It needs no GPU and answers in a fraction of a second.",
        "sobre_autor": "openTARS was created by Enzo, who founded the project. The code is open source under the MIT license.",
        "sobre_local": "The model, your memory and your commands stay on this board. Only the text of a web search leaves, and `opentars search off` turns that off.",
        "sobre_ajuda": "Ask in plain words. For example: how much ram is free, run fastfetch, what is the capital of Peru, remember that the fan is on pin PC2, turn on PC2, square root of 128.",
        "conta_nao": "I do arithmetic when it is written out, like 90 / 3 or 15% of 200. Try it that way.",
        "idioma_ok": "Okay, English from now on.",
        "pergunta": "Run this command?", "pergunta_perigo": "This can destroy data. Run it anyway?", "pergunta_pino": "Change a pin?",
        "sim_nao": "Allow [y/N] ", "sim_digitado": "Type yes to allow: ", "sim": ("y", "yes", "s", "sim"), "sim_forte": ("yes", "sim"),
        "ligando": "Starting the engine…", "pronto": "ready in {s:.0f} s", "ajuda": "Ask in plain words. /memory shows what I remember, /exit leaves.",
    },
    "pt": {
        "mem": "{usada} MB de memória em uso, {livre} MB livres, de {total} MB.",
        "disco": "{usado:.1f} GB usados no disco, {livre:.1f} GB livres, de {total:.1f} GB.",
        "temp": "A placa está a {temp:.0f} °C.", "sem_temp": "Esta placa não tem um sensor de temperatura que eu consiga ler.",
        "ligada": "Ligada há {tempo}.", "ip": "O endereço desta placa é {ip}.", "sem_ip": "Sem endereço de rede agora.",
        "cpu": "{nucleos} núcleos, carga {carga:.2f}.", "placa": "Esta é uma {modelo}, com {sistema}.",
        "estado": "{modelo}\nMemória: {livre} de {total} MB livres\nDisco: {disco:.1f} GB livres\n{temp}Ligada há {tempo}",
        "temp_linha": "Temperatura: {temp:.0f} °C\n",
        "tela": "Esta placa não tem tela para eu usar, então não consigo clicar, ver janelas nem abrir programas. Consigo rodar comandos, pesquisar na web, lembrar de coisas e usar os pinos.",
        "completo": "Isso precisa do openTARS completo, num computador: https://project-opentars.github.io/OpenTARS/ Aqui eu tenho o terminal, a busca, a memória e os pinos.",
        "anotado": "Anotado: {fato}.", "esqueci": "Esquecido: {fato}.", "nada_guardado": "Não tenho nada guardado sobre isso.", "esqueci_tudo": "Pronto, minha memória está vazia.",
        "wifi": "Wi-Fi conectado ({iface}), endereço {ip}.", "wifi_fora": "O Wi-Fi não está conectado.", "sem_wifi": "Esta placa não tem Wi-Fi.",
        "memoria_vazia": "Minha memória está vazia.", "memoria": "Isto é o que eu lembro:\n{fatos}",
        "qual_pino": "Qual pino? Diga o nome (como PC5 ou GPIO17) ou me ensine antes: lembra que o relé está no pino PC5.",
        "pino_ligado": "{pino} está ligado.", "pino_desligado": "{pino} está desligado.", "pino_valor": "{pino} está em {valor}.",
        "pino_negado": "Certo, não mexi no pino.", "pino_erro": "Não consegui usar esse pino: {erro}",
        "abatido": "Sinto muito. Vai com calma; estou aqui quando precisar.",
        "nao_fiz": "Não rodei nada, então nada mudou. Tente pedir de outro jeito.",
        "oi": "Oi! O que eu faço nesta placa?", "lembro": "Você me disse: {fato}.", "nao_achei": "Não achei uma boa resposta. O mais perto que encontrei: {titulo} ({site}).",
        "codigo": "Escrever programas é demais para um modelo deste tamanho, e prefiro não te entregar código quebrado. O openTARS completo tem o Gargantua Code Gen 2 para isso: https://project-opentars.github.io/OpenTARS/", "de_nada": "De nada.",
        "sem_busca": "Não consegui pesquisar agora, e prefiro não chutar.", "nao_me_contou": "Você ainda não me contou isso. Diga: lembra que…",
        "falhou": "Não deu certo: {erro}", "feito": "Pronto.", "negado": "Certo, não rodei.", "sem_resposta": "Não tenho resposta para isso.",
        "de_onde": "Segundo {site}: {trecho}", "tambem": "Também: {site} ({titulo})",
        "quem": "Sou o Gargantua Pi, a IA do openTARS Pi. Rodo aqui nesta placa, sem nuvem: uso o terminal, pesquiso na web, guardo o que você pede e mexo nos pinos.",
        "sobre_opentars": "O openTARS é um assistente de IA de código aberto que roda no seu próprio computador, local por padrão. O openTARS Pi é a edição para placas pequenas: sem área de trabalho, só o terminal. Site: https://project-opentars.github.io/OpenTARS/",
        "sobre_modelo": "O Gargantua Pi é o modelo que roda aqui: 270 milhões de parâmetros, uns 300 MB, treinado pelo projeto openTARS em cima do FunctionGemma. Ele é pequeno de propósito, para caber numa placa como esta.",
        "sobre_murph": "A Murph é a classificadora pequena que lê cada pedido e decide para onde ele vai: a placa, o terminal, a web ou o modelo. Ela não precisa de placa de vídeo e responde numa fração de segundo.",
        "sobre_autor": "O openTARS foi criado pelo Enzo, fundador do projeto. O código é aberto, com licença MIT.",
        "sobre_local": "O modelo, a sua memória e os seus comandos ficam nesta placa. Só o texto de uma pesquisa na web sai, e `opentars search off` desliga isso.",
        "sobre_ajuda": "Peça em palavras simples. Por exemplo: quanta ram está livre, roda o fastfetch, qual a capital do Peru, lembra que a ventoinha está no pino PC2, liga o PC2, raiz quadrada de 128.",
        "conta_nao": "Faço contas quando vêm escritas, como 90 / 3 ou 15% de 200. Tente desse jeito.",
        "idioma_ok": "Certo, em português a partir de agora.",
        "pergunta": "Rodar este comando?", "pergunta_perigo": "Isso pode destruir dados. Rodar mesmo assim?", "pergunta_pino": "Mudar um pino?",
        "sim_nao": "Permitir [s/N] ", "sim_digitado": "Digite sim para permitir: ", "sim": ("s", "sim", "y", "yes"), "sim_forte": ("sim", "yes"),
        "ligando": "Ligando o motor…", "pronto": "pronto em {s:.0f} s", "ajuda": "Peça em palavras simples. /memoria mostra o que eu lembro, /sair sai.",
    },
}
_MARCAS_PT = re.compile(r"[ãõçáéíóúâêô]|\b(o|a|os|as|um|uma|de|do|da|que|qual|quanto|quanta|quem|como|onde|por|para|pra|meu|minha|tem|tenho|é|e aí|oi|ola|olá|valeu|liga|desliga|abre|cria|faz|lembra|esquece|pesquisa)\b", re.IGNORECASE)
_MARCAS_EN = re.compile(r"\b(the|a|an|of|what|which|who|how|where|is|are|my|me|do|does|can|please|hi|hello|hey|turn|open|create|make|remember|forget|search|and|in|to)\b", re.IGNORECASE)


def idioma_padrao():
    escolhido = pastas.config().get("idioma")
    if escolhido in TEXTOS:
        return escolhido
    return "pt" if (os.environ.get("LC_ALL") or os.environ.get("LANG") or "").lower().startswith("pt") else "en"


def detectar(texto, padrao=None):
    """O idioma do pedido, pelas palavras dele; sem pista, o padrão."""
    pt, en = len(_MARCAS_PT.findall(texto)), len(_MARCAS_EN.findall(texto))
    if pt == en:
        return padrao or idioma_padrao()
    return "pt" if pt > en else "en"


def t(chave, idioma, **campos):
    texto = TEXTOS[idioma][chave]
    return texto.format(**campos) if campos and isinstance(texto, str) else texto


def duracao(segundos, idioma):
    dias, resto = divmod(int(segundos), 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    d, h, m = ("d", "h", "min")
    return " ".join(p for p in (f"{dias} {d}" if dias else "", f"{horas} {h}" if horas else "", f"{minutos} {m}") if p)
