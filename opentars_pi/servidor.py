"""O serviço: mantém o motor de pé e responde a outros aparelhos com token. Escuta só nesta máquina até a pessoa pedir --rede.
API própria e pequena: GET /v1/saude, POST /v1/conversa {"mensagem": "..."} com Authorization: Bearer TOKEN."""
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import VERSAO, aprovacoes
from .agente import Agente
from .motor import Motor, MotorForaDoAr

PORTA = 18100
LIMITE_CORPO = 16 * 1024


def criar(host="127.0.0.1", porta=PORTA, motor=None, chave=None):
    motor = motor or Motor()
    chave = chave or aprovacoes.token()
    agente = Agente(motor, aprovacoes.pedir)
    fila = threading.Lock()

    class Pedido(BaseHTTPRequestHandler):
        server_version = "openTARS-Pi"
        sys_version = ""

        def log_message(self, formato, *args):
            pass

        def _enviar(self, codigo, dados):
            corpo = json.dumps(dados, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self):
            if self.path == "/v1/saude":
                return self._enviar(200, {"ok": True, "nome": "openTARS Pi", "versao": VERSAO})
            self._enviar(404, {"erro": "not found"})

        def do_POST(self):
            cabecalho = self.headers.get("Authorization", "")
            if not hmac.compare_digest(cabecalho.encode(), f"Bearer {chave}".encode()):
                return self._enviar(401, {"erro": "invalid token"})
            if self.path != "/v1/conversa":
                return self._enviar(404, {"erro": "not found"})
            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
                if not 0 < tamanho <= LIMITE_CORPO:
                    return self._enviar(413, {"erro": "body too large"})
                mensagem = json.loads(self.rfile.read(tamanho)).get("mensagem")
            except (ValueError, AttributeError):
                return self._enviar(400, {"erro": "invalid JSON"})
            if not isinstance(mensagem, str) or not mensagem.strip():
                return self._enviar(400, {"erro": "empty message"})
            if not fila.acquire(blocking=False):      # a placa só pensa em um pedido por vez
                return self._enviar(429, {"erro": "busy, try again"})
            passos = []
            agente.mostrar = lambda tipo, texto: passos.append({"tipo": tipo, "texto": texto}) if tipo in ("comando", "saida") else None
            try:
                self._enviar(200, {"resposta": agente.responder(mensagem[:2000]), "passos": passos})
            except MotorForaDoAr as e:
                self._enviar(503, {"erro": str(e)})
            finally:
                fila.release()

    return ThreadingHTTPServer((host, porta), Pedido), motor


def servir(rede=False, porta=PORTA):
    servidor, motor = criar("0.0.0.0" if rede else "127.0.0.1", porta)
    motor.ligar()
    print(f"openTARS Pi {VERSAO} listening on {'0.0.0.0 (network)' if rede else '127.0.0.1 (this board only)'}:{porta}", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()
        motor.desligar()
