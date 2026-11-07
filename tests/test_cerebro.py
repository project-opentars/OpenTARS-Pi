"""Os cérebros: o padrão é o Gargantua Pi; o Lite e o da rede falam pela API de chat com o contrato do app."""
import http.server
import json
import threading
import unittest

import _util  # noqa: F401
from opentars_pi import agente, cerebro, pastas


class Falso(http.server.BaseHTTPRequestHandler):
    pedidos = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Falso.pedidos.append(corpo)
        ja_rodou = any(m["role"] == "tool" for m in corpo["messages"])
        mensagem = {"content": "Downloads tem 3 arquivos."} if ja_rodou else \
            {"content": "", "tool_calls": [{"id": "x", "type": "function", "function": {"name": "execute_terminal", "arguments": json.dumps({"command": "ls ~/Downloads | wc -l"})}}]}
        dados = json.dumps({"choices": [{"message": mensagem}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


class TesteCerebro(unittest.TestCase):
    def setUp(self):
        pastas.salvar_config(cerebro=None)

    def test_padrao_e_o_pi(self):
        self.assertIsInstance(cerebro.escolher(None), cerebro.CerebroPi)

    def test_prompt_do_app_byte_a_byte(self):
        c = cerebro.CerebroGargantua("http://x")
        sistema = c.sistema(["meu gato é o Rex"], "pt")
        self.assertTrue(sistema.startswith(cerebro._CONTRATO["sistema"]))
        self.assertIn("NO graphical session", sistema)
        self.assertIn("- meu gato é o Rex", sistema)
        self.assertTrue(sistema.endswith(cerebro.IDIOMA_APP["pt"] + "\n"))
        self.assertEqual(len(cerebro._CONTRATO["ferramentas"]), 19)

    def test_laco_com_servidor_compativel_com_openai(self):
        servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Falso)
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        self.addCleanup(servidor.shutdown)
        pastas.salvar_config(cerebro={"url": f"http://127.0.0.1:{servidor.server_port}", "modelo": "", "nome": "Gargantua"})
        a = agente.Agente(None, lambda *x: True)
        a.idioma_base = "pt"
        resposta = a.responder("zzz qqq www")          # nada de regra: vai para o cérebro
        self.assertEqual(resposta, "Downloads tem 3 arquivos.")
        segundo = Falso.pedidos[-1]["messages"]
        self.assertEqual(segundo[-2]["tool_calls"][0]["function"]["name"], "execute_terminal")
        self.assertEqual(segundo[-1]["role"], "tool")
        self.assertIn("exit_code", segundo[-1]["content"])

    def test_ferramenta_de_tela_nao_roda(self):
        class Tela:
            nome = "x"

            def sistema(self, *a):
                return ""

            def preparar(self, *a):
                pass

            def jogada(self, *a, **k):
                return ("click_element", {"name": "OK"}), ""
        a = agente.Agente(None, lambda *x: True)
        a.cerebro = Tela()
        a.idioma_base = "en"
        self.assertIn("screen", a.responder("zzz qqq www"))


if __name__ == "__main__":
    unittest.main()
