"""A linha de comando do openTARS Pi."""
import argparse
import os
import shutil
import sys
import time

from . import SHA_MODELO, VERSAO, aprovacoes, atualizar, busca, gpio, pastas, placa, seguranca, servico, textos
from .agente import Agente
from .motor import Motor, MotorForaDoAr
from .textos import t

COR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
NOME = "Gargantua"


def cor(codigo, texto):
    return f"\033[{codigo}m{texto}\033[0m" if COR else texto


def cinza(texto):
    return cor("90", texto)


def ambar(texto):
    return cor("33", texto)


def verde(texto):
    return cor("32", texto)


class Terminal:
    """O que aparece na tela e a pergunta de aprovação."""

    def __init__(self):
        self.idioma = textos.idioma_padrao()
        self.falando = False
        self.aprovado = None

    def mostrar(self, tipo, texto):
        if tipo == "pedaco":
            if not self.falando:
                print(verde(NOME) + "  ", end="")
                self.falando = True
            print(texto, end="", flush=True)
        elif tipo == "comando":
            if texto != self.aprovado:       # o que acabou de ser aprovado já está na tela
                print(cinza(f"  ⎿ {texto}"))
        elif tipo == "saida":
            linhas = texto.splitlines()
            for linha in linhas[:40]:
                print(cinza("    " + linha))
            if len(linhas) > 40:
                print(cinza(f"    … (+{len(linhas) - 40})"))

    def aprovar(self, descricao, nivel):
        chave = {"perigoso": "pergunta_perigo", "pino": "pergunta_pino"}.get(nivel, "pergunta")
        print(ambar(t(chave, self.idioma)))
        print(ambar("  " + seguranca.visivel(descricao)))
        if not sys.stdin.isatty():
            return False
        try:
            resposta = input(ambar(t("sim_digitado" if nivel == "perigoso" else "sim_nao", self.idioma))).strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        sim = resposta in t("sim_forte" if nivel == "perigoso" else "sim", self.idioma)
        self.aprovado = descricao if sim else None
        return sim

    def fala(self, resposta):
        if self.falando:
            print()
            self.falando = False
            return
        if resposta:
            print(verde(NOME) + "  " + resposta)


def conversar(motor, auto, pedido=None):
    tela = Terminal()
    agente = Agente(motor, tela.aprovar, tela.mostrar, auto)
    if pedido:
        tela.fala(agente.responder(pedido))
        return
    total, livre = placa.memoria()
    print(cinza(f"openTARS Pi {VERSAO} · {agente.cerebro.nome} · {placa.modelo()} · {livre} MB free"))
    print(cinza(t("ajuda", tela.idioma)))
    if atualizar.aviso():
        print(ambar("An update is ready: opentars update"))
    atualizar.consultar_em_segundo_plano()
    while True:
        try:
            texto = input(cor("34", "you") + " ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if texto in ("/exit", "/sair", "/quit", "exit", "sair"):
            return
        if not texto:
            continue
        try:
            tela.fala(agente.responder(texto))
        except KeyboardInterrupt:
            print()
        except MotorForaDoAr as e:
            print(ambar(str(e)))


def comando_gpio(args):
    uso = "usage: opentars gpio list | read PIN | on PIN | off PIN | release PIN"
    if not args:
        sys.exit(uso)
    acao, pino = args[0], (args[1] if len(args) > 1 else None)
    try:
        if acao == "list":
            for linha in gpio.linhas():
                if linha["flags"] & gpio.USADA:
                    print(f"{linha['chip']} {linha['deslocamento']:>3} {linha['nome'] or '-':<12} used by {linha['dono'] or 'kernel'}")
            print(cinza("Only the lines in use are listed. The others are free."))
        elif pino is None:
            sys.exit(uso)
        elif acao == "read":
            print(gpio.ler(pino))
        elif acao in ("on", "off"):
            gpio.escrever(pino, acao == "on")
            print(f"{pino} {acao}")
        elif acao == "release":
            gpio.soltar(pino)
            print(f"{pino} released")
        else:
            sys.exit(uso)
    except gpio.ErroGpio as e:
        sys.exit(str(e))


def comando_servico(args):
    acao = args[0] if args else "status"
    if acao in ("on", "ligar", "start"):
        ok, erro = servico.ligar(rede="--network" in args or "--rede" in args)
        print("openTARS Pi service is on." if ok else f"Could not turn it on: {erro}")
        if ok:
            print("To keep it running after you log out: sudo loginctl enable-linger $USER")
    elif acao in ("off", "desligar", "stop"):
        servico.desligar()
        print("openTARS Pi service is off.")
    else:
        print(f"service: {servico.estado()}")
        print(f"token: {pastas.TOKEN}" if pastas.TOKEN.exists() else "token: none yet")
        print(f"approvals waiting: {len(aprovacoes.pendentes())}")


def comando_busca(args):
    valor = args[0] if args else ""
    if valor == "off":
        pastas.salvar_config(busca=False)
        print("Web search is off. Nothing leaves this board.")
    elif valor == "on":
        pastas.salvar_config(busca=True, searxng=None)
        print("Web search is on (Wikipedia).")
    elif valor.startswith(("http://", "https://")):
        try:
            busca.searxng("test", valor)
        except (OSError, ValueError) as e:      # um endereço de exemplo colado aqui deixava toda pesquisa esperando à toa
            sys.exit(f"No SearXNG answered at {valor} ({e}). Nothing changed.")
        pastas.salvar_config(busca=True, searxng=valor)
        print(f"Web search goes to your SearXNG: {valor}")
    else:
        sys.exit("usage: opentars search on | off | http://your-searxng:8888")


def comando_cerebro(args):
    """opentars brain [pi | URL [modelo]]"""
    from . import cerebro
    valor = args[0] if args else ""
    if not valor or valor in ("status", "estado"):
        print("Thinking with: " + cerebro.descricao())
        return print("Change with: opentars brain pi | http://your-pc:11434")
    if valor == "pi":
        pastas.salvar_config(cerebro=None)
        return print("Back to Gargantua Pi (270M): small and fast on any board.")
    if valor.startswith(("http://", "https://")):
        ok, modelo, mensagem = cerebro.testar_rede(valor, args[1] if len(args) > 1 else "")
        if not ok:
            sys.exit(f"No Gargantua there: {mensagem}. Nothing changed.")
        pastas.salvar_config(cerebro={"url": valor.rstrip("/"), "modelo": modelo, "nome": "Gargantua"})
        return print(f"Thinking with {mensagem} at {valor}. What the rules can't answer goes only to that address. Back with: opentars brain pi")
    sys.exit("usage: opentars brain [pi | http://your-pc:11434 [model]]")


def progresso(texto):
    """Uma linha que se reescreve no terminal; fora dele, só o fim de cada arquivo."""
    if sys.stdout.isatty():
        print("\r" + cinza(texto), end="\n" if texto.endswith("100%") else "", flush=True)
    elif texto.endswith("100%"):
        print(texto)


def comando_atualizar(args):
    """opentars update [check | undo | auto on | auto off]"""
    if args[:1] == ["auto"] and args[1:2] in (["on"], ["off"]):
        pastas.salvar_config(atualizar_auto=args[1] == "on")
        return print("Daily update check: " + args[1] + ".")
    if args[:1] in (["undo"], ["desfazer"]):
        trocou = atualizar.desfazer()
        if not trocou:
            return print("There is no previous version to go back to.")
        servico.reiniciar_se_ligado()
        return print("Back to the previous version: " + ", ".join(trocou) + ". Run opentars update undo again to redo.")
    if args and args[0] not in ("check", "verificar"):
        sys.exit("Use: opentars update [check | undo | auto on | auto off]")
    local = atualizar.instalado()
    print(f"Installed: openTARS Pi {VERSAO}" + (f" ({local['revisao']})" if local.get("revisao") else ""))
    try:
        manifesto = atualizar.publicado()
        mudou = atualizar.o_que_mudou(manifesto, local)
    except Exception as e:
        sys.exit(f"Could not reach the update server ({e.__class__.__name__}). Check the internet and try again.")
    pastas.salvar_config(ultima_consulta=time.time(), atualizacao_disponivel=manifesto["revisao"] if mudou else None)
    if not mudou:
        return print(verde("Everything is up to date."))
    partes = atualizar._partes(manifesto)
    nomes = {"app": "app and Murph", "motor": "engine (llama.cpp)", "modelo": "Gargantua Pi model"}
    print(f"New: {manifesto['versao']} ({manifesto['revisao']})" + (f". {manifesto['notas']}" if manifesto.get("notas") else ""))
    for nome in mudou:
        print(f"  {nomes[nome]}: {partes[nome][3]} MB")
    if args[:1] in (["check"], ["verificar"]):
        return print("Install it with: opentars update")
    if sys.stdin.isatty() and input("Update now? [Y/n] ").strip().lower() in ("n", "no", "nao", "não"):
        return print("Nothing was changed.")
    try:
        trocou = atualizar.aplicar(manifesto, mudou, mostrar=progresso)
    except (OSError, ValueError) as e:
        sys.exit(f"Update stopped, nothing was changed: {e}")
    if servico.reiniciar_se_ligado():
        print("The background service was restarted.")
    print(verde("Updated: " + ", ".join(nomes[n] for n in trocou) + ".") + " To go back: opentars update undo")


def responder_aprovacoes():
    pendentes = aprovacoes.pendentes()
    if not pendentes:
        print("Nothing is waiting for approval.")
    tela = Terminal()
    for caminho, dados in pendentes:
        aprovacoes.responder(caminho, tela.aprovar(dados["descricao"], dados["nivel"]))


def diagnostico():
    motor = Motor()
    binario = motor.binario()
    total, livre = placa.memoria()
    revisao = atualizar.instalado().get("revisao")
    linhas = [("Version", VERSAO + (f" ({revisao})" if revisao else "")), ("Board", placa.modelo()), ("System", f"{placa.sistema()} ({os.uname().machine}, kernel {os.uname().release})"),
              ("Memory", f"{livre} of {total} MB free"), ("Disk", f"{placa.disco()[1]:.1f} GB free"),
              ("Python", sys.version.split()[0]), ("Engine", binario or "NOT FOUND")]
    if os.path.exists(motor.modelo):
        soma = atualizar.sha256(motor.modelo)
        linhas.append(("Model", "ok (SHA-256 verified)" if soma == SHA_MODELO else f"different from the published one: {soma[:16]}…"))
    else:
        linhas.append(("Model", "NOT FOUND"))
    chips = gpio.chips()
    linhas.append(("GPIO", ", ".join(f"{os.path.basename(c)} {'ok' if os.access(c, os.R_OK | os.W_OK) else 'no permission'}" for c in chips) or "no chips"))
    from . import cerebro
    linhas.append(("Brain", cerebro.descricao()))
    linhas.append(("Service", servico.estado()))
    linhas.append(("Window", "available" if placa.tem_desktop() else "no desktop here"))
    for nome, valor in linhas:
        print(f"{nome + ':':<9} {valor}")


def remover():
    print(f"This removes openTARS Pi, its model and what it remembers: {pastas.BASE}")
    if sys.stdin.isatty() and input("Type yes to remove: ").strip().lower() not in ("yes", "sim"):
        return print("Nothing was removed.")
    servico.desligar()
    for nome in ("opentars-pi", "opentars"):      # `opentars` só sai se for nosso: pode ser o do app completo
        lancador = os.path.expanduser("~/.local/bin/" + nome)
        if os.path.islink(lancador) and os.path.realpath(lancador).startswith(os.path.realpath(pastas.BASE)):
            os.remove(lancador)
    atalho = os.path.expanduser("~/.local/share/applications/opentars-pi.desktop")
    if os.path.exists(atalho):
        os.remove(atalho)
    for perfil in ("~/.profile", "~/.bashrc"):    # a linha do PATH que o instalador pôs
        caminho = os.path.expanduser(perfil)
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8", errors="replace") as f:
                linhas = f.readlines()
            with open(caminho, "w", encoding="utf-8") as f:
                f.writelines(l for l in linhas if "# openTARS Pi" not in l)
    shutil.rmtree(pastas.BASE, ignore_errors=True)
    print("openTARS Pi was removed.")


def opcoes():
    p = argparse.ArgumentParser(prog="opentars", description="openTARS Pi: a local AI assistant for small boards.",
                                epilog="Also: opentars brain [pi|URL], opentars update [check|undo|auto on|off], opentars gpio ..., opentars service on|off|status, opentars search on|off|URL")
    p.add_argument("pedido", nargs="*", help="what to do; leave empty to chat")
    p.add_argument("--version", action="version", version=f"openTARS Pi {VERSAO}")
    p.add_argument("--auto", action="store_true", help="run commands that change things without asking (dangerous ones still ask)")
    p.add_argument("--window", "--janela", action="store_true", help="open the small window, if there is a desktop")
    p.add_argument("--serve", "--servir", action="store_true", help="keep the model running and answer with a token")
    p.add_argument("--network", "--rede", action="store_true", help="with --serve: also listen on the network")
    p.add_argument("--token", action="store_true", help="show the service token")
    p.add_argument("--new-token", action="store_true", help="make a new service token")
    p.add_argument("--approvals", "--aprovacoes", action="store_true", help="answer the approvals waiting from the network")
    p.add_argument("--doctor", "--diagnostico", action="store_true", help="check this installation")
    p.add_argument("--test", "--prova", action="store_true", help="run the built-in test with the real model")
    p.add_argument("--update", "--atualizar", action="store_true", help="same as: opentars update")
    p.add_argument("--uninstall", "--remover", action="store_true", help="remove openTARS Pi")
    return p


def main():
    if sys.argv[1:2] == ["gpio"]:
        return comando_gpio(sys.argv[2:])
    if sys.argv[1:2] in (["service"], ["servico"]):
        return comando_servico(sys.argv[2:])
    if sys.argv[1:2] in (["brain"], ["cerebro"], ["model"], ["modelo"]):
        return comando_cerebro(sys.argv[2:])
    if sys.argv[1:2] in (["update"], ["atualizar"]):
        return comando_atualizar(sys.argv[2:])
    if sys.argv[1:2] in (["search"], ["busca"]):
        return comando_busca(sys.argv[2:])
    a = opcoes().parse_args()
    if a.doctor:
        return diagnostico()
    if a.uninstall:
        return remover()
    if a.update:
        return comando_atualizar([])
    if a.token or a.new_token:
        return print(aprovacoes.novo_token() if a.new_token else aprovacoes.token())
    if a.approvals:
        return responder_aprovacoes()
    if a.serve:
        from . import servidor
        return servidor.servir(a.network)
    if a.test:
        from . import prova
        prova.rodar()
        return None
    if a.window:
        if placa.tem_desktop():
            try:
                from . import janela
                return janela.abrir(a.auto)
            except ImportError:
                print("The window needs python3-tk: sudo apt install python3-tk. Using the terminal.", file=sys.stderr)
    motor = Motor()
    try:
        conversar(motor, a.auto, " ".join(a.pedido))
    except MotorForaDoAr as e:
        sys.exit(str(e))
    finally:
        motor.desligar()
