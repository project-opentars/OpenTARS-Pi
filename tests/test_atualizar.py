"""Atualização por partes contra um servidor local: baixa só o que mudou, confere o hash, desfaz e refaz."""
import hashlib
import http.server
import io
import json
import os
import shutil
import tarfile
import threading
import time
import unittest

import _util  # noqa: F401
from opentars_pi import atualizar, pastas
from opentars_pi.motor import Motor

SERVIDO = os.path.join(pastas.BASE.parent, "servido-" + pastas.BASE.name)


def _tar(nome, conteudo):
    dados = io.BytesIO()
    with tarfile.open(fileobj=dados, mode="w:gz") as t:
        info = tarfile.TarInfo(nome)
        info.size = len(conteudo)
        t.addfile(info, io.BytesIO(conteudo))
    return dados.getvalue()


class Servidor(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=SERVIDO, **k)

    def log_message(self, *a):
        pass


class TesteAtualizar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(SERVIDO, exist_ok=True)
        cls.http = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Servidor)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.http.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()

    def setUp(self):
        shutil.rmtree(pastas.BASE, ignore_errors=True)
        pastas.BASE.mkdir(parents=True)

    def publicar(self, app=b"app 1", motor=b"motor 1", modelo=b"modelo 1", sha_errado=False):
        arquivos = {"opentars-pi.tar.gz": _tar("opentars_pi/v.txt", app),
                    f"opentars-pi-motor-{atualizar.arquitetura()}.tar.gz": _tar("llama-server", motor),
                    "modelo.gguf": modelo}
        for nome, dados in arquivos.items():
            with open(os.path.join(SERVIDO, nome), "wb") as f:
                f.write(dados)
        sha = {n: hashlib.sha256(d).hexdigest() for n, d in arquivos.items()}
        if sha_errado:
            sha["modelo.gguf"] = "0" * 64
        motor_arq = f"opentars-pi-motor-{atualizar.arquitetura()}.tar.gz"
        return {"versao": "1.0", "revisao": int(time.time() * 1000), "url": self.url,
                "app": {"arquivo": "opentars-pi.tar.gz", "sha256": sha["opentars-pi.tar.gz"], "mb": 1},
                "motor": {atualizar.arquitetura(): {"arquivo": motor_arq, "sha256": sha[motor_arq], "mb": 1}},
                "modelo": {"arquivo": "modelo.gguf", "url": self.url + "/modelo.gguf", "sha256": sha["modelo.gguf"], "mb": 1}}

    def ler(self, *caminho):
        with open(pastas.BASE.joinpath(*caminho), "rb") as f:
            return f.read()

    def test_instala_tudo_e_depois_so_o_que_mudou(self):
        m = self.publicar()
        self.assertEqual(atualizar.o_que_mudou(m), ["app", "motor", "modelo"])
        atualizar.aplicar(m, atualizar.o_que_mudou(m), mostrar=None)
        self.assertEqual(self.ler("app", "opentars_pi", "v.txt"), b"app 1")
        self.assertEqual(self.ler("modelos", "modelo.gguf"), b"modelo 1")
        self.assertEqual(atualizar.o_que_mudou(m), [])
        (pastas.CACHE).mkdir(parents=True)
        m2 = self.publicar(app=b"app 2")
        self.assertEqual(atualizar.o_que_mudou(m2), ["app"])
        self.assertEqual(atualizar.aplicar(m2, ["app"], mostrar=None), ["app"])
        self.assertEqual(self.ler("app", "opentars_pi", "v.txt"), b"app 2")
        self.assertTrue(pastas.CACHE.exists(), "o modelo não mudou: o prompt guardado continua valendo")
        self.assertEqual(atualizar.instalado()["revisao"], m2["revisao"])

    def test_desfazer_volta_e_refaz(self):
        m = self.publicar()
        atualizar.aplicar(m, atualizar.o_que_mudou(m), mostrar=None)
        pastas.CACHE.mkdir(parents=True)
        m2 = self.publicar(app=b"app 2", modelo=b"modelo 2")
        atualizar.aplicar(m2, atualizar.o_que_mudou(m2), mostrar=None)
        self.assertFalse(pastas.CACHE.exists(), "modelo novo: o prompt guardado do velho sai")
        self.assertEqual(sorted(atualizar.desfazer()), ["app", "modelo"])
        self.assertEqual(self.ler("app", "opentars_pi", "v.txt"), b"app 1")
        self.assertEqual(self.ler("modelos", "modelo.gguf"), b"modelo 1")
        self.assertEqual(atualizar.instalado()["revisao"], m["revisao"])
        self.assertEqual(atualizar.o_que_mudou(m), [])
        atualizar.desfazer()
        self.assertEqual(self.ler("app", "opentars_pi", "v.txt"), b"app 2")
        self.assertEqual(atualizar.o_que_mudou(m2), [])

    def test_hash_errado_nao_muda_nada(self):
        m = self.publicar()
        atualizar.aplicar(m, atualizar.o_que_mudou(m), mostrar=None)
        ruim = self.publicar(app=b"app 2", modelo=b"modelo 2", sha_errado=True)
        with self.assertRaises(ValueError):
            atualizar.aplicar(ruim, atualizar.o_que_mudou(ruim), mostrar=None)
        self.assertEqual(self.ler("app", "opentars_pi", "v.txt"), b"app 1")
        self.assertEqual(self.ler("modelos", "modelo.gguf"), b"modelo 1")
        self.assertEqual(atualizar.o_que_mudou(m), [])
        self.assertEqual([n for n in os.listdir(pastas.BASE) if n.startswith(".")], [], "nada temporário fica para trás")

    def test_instalacao_antiga_confere_o_modelo_pelo_arquivo(self):
        m = self.publicar()
        pastas.MODELOS.mkdir(parents=True)
        (pastas.MODELOS / "modelo.gguf").write_bytes(b"modelo 1")
        self.assertEqual(atualizar.o_que_mudou(m), ["app", "motor"])

    def test_sem_internet_a_conversa_nao_espera(self):
        inicio = time.time()
        fio = atualizar.consultar_em_segundo_plano()
        self.assertLess(time.time() - inicio, 0.5)
        fio.join(15)
        self.assertGreater(pastas.config().get("ultima_consulta", 0), 0)
        self.assertIsNone(atualizar.consultar_em_segundo_plano(), "uma consulta por dia")
        self.assertIsNone(atualizar.aviso())
        pastas.salvar_config(atualizacao_disponivel=123)
        self.assertEqual(atualizar.aviso(), 123)
        pastas.salvar_config(atualizar_auto=False)
        self.assertIsNone(atualizar.aviso())

    def test_prompt_guardado_depende_do_modelo(self):
        pastas.MODELOS.mkdir(parents=True)
        caminho = pastas.MODELOS / "m.gguf"
        caminho.write_bytes(b"velho")
        motor = Motor(modelo=str(caminho))
        antes = motor._arquivo_do_prefixo("prompt")
        caminho.write_bytes(b"modelo novo")
        self.assertNotEqual(motor._arquivo_do_prefixo("prompt"), antes)


if __name__ == "__main__":
    unittest.main()
