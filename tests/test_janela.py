"""A janela de verdade num X virtual: pedido, aprovação por botão e resposta."""
import os
import shutil
import tempfile
import time
import unittest

import _util  # noqa: F401

try:
    import tkinter
except ImportError:
    tkinter = None


@unittest.skipIf(tkinter is None or not os.environ.get("DISPLAY"), "precisa de tkinter e de um DISPLAY (xvfb-run)")
class TesteJanela(unittest.TestCase):
    def rodar_ate(self, janela, condicao, tempo=8):
        limite = time.time() + tempo
        while time.time() < limite and not condicao():
            janela.raiz.update()
            time.sleep(0.02)
        self.assertTrue(condicao())

    def test_aprovar_por_botao(self):
        from opentars_pi import janela as j
        janela = j.Janela()
        pasta = tempfile.mkdtemp()
        alvo = os.path.join(pasta, "nova")
        janela.entrada.insert(0, f"create the folder {alvo}")
        janela.enviar()
        self.rodar_ate(janela, lambda: janela.aviso.winfo_ismapped())
        self.assertIn("mkdir", janela.aviso_texto.cget("text"))
        janela.decidir(True)
        self.rodar_ate(janela, lambda: os.path.isdir(alvo))
        self.rodar_ate(janela, lambda: janela.entrada.cget("state") == "normal")
        janela.entrada.insert(0, "how much ram is free?")
        janela.enviar()
        self.rodar_ate(janela, lambda: "MB of memory" in janela.conversa.get("1.0", "end"))
        if os.environ.get("CAPTURA"):
            janela.raiz.update()
            os.system(f"import -window root {os.environ['CAPTURA']}")
        janela.raiz.destroy()
        shutil.rmtree(pasta)


if __name__ == "__main__":
    unittest.main()
