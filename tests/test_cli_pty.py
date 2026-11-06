"""A pergunta de aprovação num terminal de verdade (pty), com o agente inteiro e um motor de mentira no lugar do modelo."""
import os
import pty
import subprocess
import sys
import tempfile
import time
import unittest

import _util  # noqa: F401

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def conversar(pedido, respostas):
    mestre, escravo = pty.openpty()
    env = {**os.environ, "NO_COLOR": "1", "OPENTARS_PI_HOME": tempfile.mkdtemp(), "LANG": "en_US.UTF-8"}
    p = subprocess.Popen([sys.executable, os.path.join(RAIZ, "opentars-pi"), pedido], stdin=escravo, stdout=escravo, stderr=escravo, env=env, close_fds=True)
    os.close(escravo)
    saida = b""
    limite = time.time() + 20
    pendentes = list(respostas)
    while time.time() < limite:
        try:
            pedaco = os.read(mestre, 4096)
        except OSError:
            break
        if not pedaco:
            break
        saida += pedaco
        if pendentes and (b"[y/N]" in saida or b"Type yes" in saida):
            os.write(mestre, pendentes.pop(0).encode() + b"\n")
            saida += b"<respondeu>"
    p.wait(5)
    return saida.decode()


class TesteAprovacao(unittest.TestCase):
    def test_sim_roda(self):
        with tempfile.TemporaryDirectory() as pasta:
            alvo = os.path.join(pasta, "nova")
            texto = conversar(f"create the folder {alvo}", ["y"])
            self.assertIn("Run this command?", texto)
            self.assertTrue(os.path.isdir(alvo), texto)

    def test_nao_nao_roda(self):
        with tempfile.TemporaryDirectory() as pasta:
            alvo = os.path.join(pasta, "nova")
            texto = conversar(f"create the folder {alvo}", ["n"])
            self.assertFalse(os.path.exists(alvo))
            self.assertIn("did not run", texto)

    def test_perigoso_pede_a_palavra_inteira(self):
        with tempfile.TemporaryDirectory() as pasta:
            alvo = os.path.join(pasta, "pasta")
            os.mkdir(alvo)
            texto = conversar(f"delete the folder {alvo}", ["y"])      # 'y' não basta para o que destrói
            self.assertIn("This can destroy data", texto)
            self.assertTrue(os.path.isdir(alvo), texto)
            conversar(f"delete the folder {alvo}", ["yes"])
            self.assertFalse(os.path.exists(alvo))


if __name__ == "__main__":
    unittest.main()
