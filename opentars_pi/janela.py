"""A janela mínima para placas com desktop: conversa, aprovação e o estado da placa. Tk vem com o Python e pesa pouco."""
import queue
import threading
import tkinter as tk

from . import VERSAO, placa, seguranca, textos
from .agente import Agente
from .motor import Motor, MotorForaDoAr
from .textos import t

FUNDO, PAINEL, TEXTO, CINZA, VERDE, AMBAR = "#141C38", "#0D1329", "#E8ECF4", "#9AA6C8", "#5BD18B", "#F2B04A"


class Janela:
    def __init__(self, auto=False):
        self.raiz = tk.Tk()
        self.raiz.title("openTARS Pi")
        self.raiz.geometry("480x520")
        self.raiz.configure(bg=FUNDO)
        self.idioma = textos.idioma_padrao()
        self.falando = False
        self.eventos = queue.Queue()
        self.resposta_aprovacao = queue.Queue()
        self.motor = Motor()
        self.agente = Agente(self.motor, self.aprovar, lambda tipo, texto: self.eventos.put((tipo, texto)), auto)
        self.estado = tk.Label(self.raiz, bg=PAINEL, fg=CINZA, anchor="w", padx=10, pady=6)
        self.estado.pack(fill="x")
        self.conversa = tk.Text(self.raiz, bg=FUNDO, fg=TEXTO, wrap="word", bd=0, highlightthickness=0, padx=10, pady=10, state="disabled")
        self.conversa.tag_config("voce", foreground="#7FA4FF")
        self.conversa.tag_config("gp", foreground=VERDE)
        self.conversa.tag_config("cinza", foreground=CINZA)
        self.conversa.pack(fill="both", expand=True)
        self.aviso = tk.Frame(self.raiz, bg=PAINEL)
        self.aviso_texto = tk.Label(self.aviso, bg=PAINEL, fg=AMBAR, wraplength=440, justify="left")
        self.aviso_texto.pack(anchor="w", padx=10, pady=(8, 4))
        botoes = tk.Frame(self.aviso, bg=PAINEL)
        botoes.pack(anchor="w", padx=10, pady=(0, 8))
        tk.Button(botoes, text="Allow", bg=AMBAR, command=lambda: self.decidir(True)).pack(side="left")
        tk.Button(botoes, text="Deny", command=lambda: self.decidir(False)).pack(side="left", padx=6)
        self.entrada = tk.Entry(self.raiz, bg=PAINEL, fg=TEXTO, insertbackground=TEXTO, bd=0, highlightthickness=1, highlightbackground=PAINEL, highlightcolor=VERDE)
        self.entrada.pack(fill="x", ipady=8, padx=10, pady=10)
        self.entrada.bind("<Return>", self.enviar)
        self.entrada.focus()
        self.raiz.after(100, self.processar)
        self.atualizar_estado()

    def atualizar_estado(self):
        _, livre = placa.memoria()
        temp = placa.temperatura()
        self.estado.config(text=f"openTARS Pi {VERSAO}   {livre} MB free" + (f"   {temp:.0f} °C" if temp is not None else ""))
        self.raiz.after(5000, self.atualizar_estado)

    def escrever(self, texto, marca=None):
        self.conversa.config(state="normal")
        self.conversa.insert("end", texto, marca or ())
        self.conversa.see("end")
        self.conversa.config(state="disabled")

    def aprovar(self, descricao, nivel):
        """Roda na linha do agente: pede à janela e espera o botão."""
        self.eventos.put(("aprovar", (descricao, nivel)))
        return self.resposta_aprovacao.get()

    def decidir(self, sim):
        self.aviso.pack_forget()
        self.resposta_aprovacao.put(sim)

    def processar(self):
        while not self.eventos.empty():
            tipo, dados = self.eventos.get()
            if tipo == "pedaco":
                if not self.falando:
                    self.escrever("gp  ", "gp")
                    self.falando = True
                self.escrever(dados)
            elif tipo == "comando":
                self.escrever(f"  ⎿ {dados}\n", "cinza")
            elif tipo == "saida":
                self.escrever("\n".join(dados.splitlines()[:12]) + "\n", "cinza")
            elif tipo == "aprovar":
                chave = {"perigoso": "pergunta_perigo", "pino": "pergunta_pino"}.get(dados[1], "pergunta")
                self.aviso_texto.config(text=t(chave, self.idioma) + "\n" + seguranca.visivel(dados[0]))
                self.aviso.pack(fill="x", before=self.entrada)
            elif tipo == "fim":
                if dados and not self.falando:
                    self.escrever("gp  ", "gp")
                self.escrever(dados + "\n\n")
                self.falando = False
                self.entrada.config(state="normal")
                self.entrada.focus()
        self.raiz.after(100, self.processar)

    def enviar(self, _=None):
        pedido = self.entrada.get().strip()
        if not pedido:
            return
        self.entrada.delete(0, "end")
        self.entrada.config(state="disabled")
        self.escrever("you  ", "voce")
        self.escrever(pedido + "\n")
        threading.Thread(target=self.trabalhar, args=(pedido,), daemon=True).start()

    def trabalhar(self, pedido):
        falou = []
        original = self.agente.mostrar

        def mostrar(tipo, texto):
            falou.append(tipo == "pedaco")
            original(tipo, texto)
        self.agente.mostrar = mostrar
        try:
            resposta = self.agente.responder(pedido)
        except MotorForaDoAr as e:
            resposta = str(e)
        finally:
            self.agente.mostrar = original
        self.eventos.put(("fim", "" if any(falou) else resposta))


def abrir(auto=False):
    janela = Janela(auto)
    try:
        janela.raiz.mainloop()
    finally:
        janela.motor.desligar()
