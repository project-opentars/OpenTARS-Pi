import json
import threading
import unittest
import urllib.error
import urllib.request

import _util  # noqa: F401
from opentars_pi import servidor


class MotorDeMentira:
    def ligar(self):
        pass

    def preparar_prefixo(self, prefixo):
        pass

    def completar(self, prompt, ao_pedaco=None, **_):
        return "Oi."


class TesteServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http, _ = servidor.criar(porta=0, motor=MotorDeMentira(), chave="certo")
        cls.base = f"http://127.0.0.1:{cls.http.server_address[1]}"
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()

    def pedir(self, corpo, token="certo", caminho="/v1/conversa"):
        pedido = urllib.request.Request(self.base + caminho, json.dumps(corpo).encode(), {"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(pedido) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_escuta_so_nesta_maquina_por_padrao(self):
        self.assertEqual(self.http.server_address[0], "127.0.0.1")

    def test_sem_token_nao_entra(self):
        self.assertEqual(self.pedir({"mensagem": "oi"}, "errado")[0], 401)

    def test_conversa(self):
        self.assertEqual(self.pedir({"mensagem": "bom dia, tudo certo?"}), (200, {"resposta": "Oi.", "passos": []}))

    def test_corpo_invalido(self):
        self.assertEqual(self.pedir({"mensagem": ""})[0], 400)
        self.assertEqual(self.pedir({"mensagem": "x" * 20000})[0], 413)

    def test_saude_nao_pede_token(self):
        with urllib.request.urlopen(self.base + "/v1/saude") as r:
            self.assertTrue(json.loads(r.read())["ok"])


if __name__ == "__main__":
    unittest.main()
