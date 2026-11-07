"""O que saiu errado na primeira sessão real na placa (06/11), para não voltar."""
import unittest

import _util  # noqa: F401
from opentars_pi import agente, atalhos, cli, comandos, conta, contrato, memoria, pastas, seguranca


class Motor:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.prompts = []

    def ligar(self):
        pass

    def preparar_prefixo(self, _):
        pass

    def completar(self, prompt, ao_pedaco=None, **_):
        self.prompts.append(prompt)
        return self.respostas.pop(0)


def chamada(comando):
    return f"<start_function_call>call:execute_terminal{{command:<escape>{comando}<escape>}}<end_function_call>"


class TesteSessao(unittest.TestCase):
    def setUp(self):
        pastas.MEMORIA.unlink(missing_ok=True)
        pastas.CONFIG.unlink(missing_ok=True)

    def plano(self, pedido, idioma="en"):
        return atalhos.resolver(pedido, idioma) or {}

    def test_contas(self):
        for pedido, certo in (("what is the square root of 128", "11.313708"), ("2+2", "4"), ("15% of 200", "30"), ("half of 90", "45"), ("what's 7 times 6?", "42"), ("calculate (3+4)*2", "14")):
            self.assertEqual(self.plano(pedido).get("fala"), certo, pedido)
        self.assertEqual(self.plano("qual a raiz quadrada de 2", "pt").get("fala"), "1,414214")
        self.assertEqual(self.plano("quanto é 12 vezes 8", "pt").get("fala"), "96")
        self.assertEqual(self.plano("o dobro de 21", "pt").get("fala"), "42")

    def test_o_que_nao_e_conta(self):
        for pedido in ("2026-11-06", "12/10/2026", "192.168.1.1", "version 5.2", "pi 5", "9**9**9", "10 / 0"):
            self.assertIsNone(conta.resolver(pedido, "en"), pedido)

    def test_rodar_programa(self):
        self.assertEqual(comandos.plano("run fastfetch", "run fastfetch"), "fastfetch")
        self.assertEqual(comandos.plano("run fastfetch on the terminal", "run fastfetch on the terminal"), "fastfetch")
        self.assertEqual(comandos.plano("roda o htop", "roda o htop"), "top -bn1 | head -20")
        self.assertEqual(comandos.plano("run ls -la /tmp", "run ls -la /tmp"), "ls -la /tmp")
        self.assertEqual(comandos.plano("df -h", "df -h"), "df -h")
        self.assertIsNone(comandos.plano("run a speed test", "run a speed test"))
        self.assertIsNone(comandos.plano("start the backup now", "start the backup now"))

    def test_processos(self):
        self.assertIn("%mem", self.plano("what processes are using ram").get("comando", ""))
        self.assertIn("%mem", self.plano("what processes are using ram on the board").get("comando", ""))
        self.assertIn("%cpu", self.plano("which processes use the most cpu").get("comando", ""))

    def test_perguntas_sobre_o_produto_nao_vao_para_a_busca(self):
        self.assertIn("run fastfetch", self.plano("what are your capabilities").get("fala", ""))
        self.assertIn("270", self.plano("what is gargantua pi").get("fala", ""))
        self.assertIn("código aberto", self.plano("o que é o opentars", "pt").get("fala", ""))
        self.assertIn("Enzo", self.plano("who made you").get("fala", ""))

    def test_perguntas_sobre_a_placa_nao_vao_para_a_busca(self):
        for pedido in ("what is this board", "what board do you run"):
            self.assertIn("Memory:", self.plano(pedido).get("fala", ""), pedido)

    def test_hello_world_sem_linguagem(self):
        self.assertEqual(self.plano("make me a hello world script").get("fala"), 'print("Hello, world!")')

    def test_depois_da_saida_o_modelo_nao_comenta(self):
        motor = Motor([chamada("echo oi"), "I have saved that you can use the swap command"])
        a = agente.Agente(motor, lambda *_: True)
        a._usar_ferramenta = lambda nome, argumentos: {"success": True, "stdout": "oi\n"}
        mensagens = a._mensagens("say hi", "en")
        self.assertTrue(contrato.renderizar(mensagens))
        atalhos_resolver, atalhos.resolver = atalhos.resolver, lambda *_: None
        try:
            self.assertEqual(a.responder("say hi with the terminal"), "")
        finally:
            atalhos.resolver = atalhos_resolver
        self.assertEqual(len(motor.prompts), 1)

    def test_trocar_de_idioma(self):
        a = agente.Agente(Motor([]), lambda *_: True)
        a.idioma_base = "pt"
        self.assertIn("English", a.responder("back to english"))
        self.assertEqual(a.idioma_base, "en")
        self.assertIn("português", a.responder("fala em português"))

    def test_serie_de_07_11(self):
        self.assertEqual(atalhos.resolver("cria uma pasta chamada fotos na minha home", "pt")["comando"], "mkdir -p ~/fotos")
        self.assertEqual(atalhos.resolver("search for the word error in app.log", "en"), {"comando": "grep -n -- error app.log | head -50"})
        self.assertEqual(atalhos.resolver("what kernel is running here", "en"), {"comando": "uname -r"})
        self.assertEqual(atalhos.resolver("quais portas estão abertas", "pt"), {"comando": "ss -tuln"})
        self.assertEqual(atalhos.resolver("cria um arquivo vazio chamado teste.txt", "pt"), {"comando": "touch teste.txt"})
        self.assertIn("Rex", atalhos.resolver("my dog is called Rex, keep that", "en")["fala"])
        self.assertIn("gaveta", atalhos.resolver("deixa registrado que a chave fica na gaveta", "pt")["fala"])
        self.assertIn("calma", atalhos.resolver("tô cansado hoje", "pt")["fala"])
        self.assertIn("completo", atalhos.resolver("crie uma foto de um gato", "pt")["fala"])

    def test_vinte_perguntas_de_07_11(self):
        r = atalhos.resolver
        self.assertEqual(r("quais usuários existem nessa placa", "pt"), {"comando": "ls /home"})
        self.assertEqual(r("mostra as últimas 5 linhas do log do sistema", "pt"), {"comando": "journalctl -n 5 --no-pager"})
        self.assertEqual(r("qual o tamanho da pasta Downloads", "pt")["comando"], "du -sh ~/Downloads")
        self.assertEqual(r("procura arquivos .py na minha home", "pt")["comando"], "find ~ -iname '*.py' -not -path '*/.*' 2>/dev/null | head -50")
        self.assertEqual(r("apaga tudo da pasta /tmp", "pt"), {"comando": "rm -rf -- /tmp/*"})
        self.assertEqual(seguranca.nivel("rm -rf -- /tmp/*"), "perigoso")
        self.assertIsNone(r("apaga tudo da pasta /", "pt"), "a raiz não vira regra")
        self.assertIn("núcleos", r("how many cpu cores do you have?", "pt")["fala"])
        self.assertNotIn("Esquecido", r("apaga tudo da pasta /tmp/x", "pt").get("fala", ""), "esvaziar pasta não mexe na memória")
        self.assertIn("backup", r("remind me that the backup runs on sunday", "en")["fala"])
        self.assertIn("vazia", r("esquece tudo", "pt")["fala"])
        self.assertEqual(memoria.ler(), [])
        self.assertEqual(seguranca.nivel("journalctl -n 5 --no-pager"), "livre")
        self.assertEqual(seguranca.nivel("journalctl --vacuum-size=1M"), "perguntar")

    def test_comando_inventado_nem_pede_aprovacao(self):
        pedidos = []
        a = agente.Agente(Motor([chamada("sudoulp --error")]), lambda *x: pedidos.append(x) or False)
        a.idioma_base = "en"
        resposta = a.responder("zzz qqq")
        self.assertIn("sudoulp: command not found", resposta)
        self.assertEqual(pedidos, [])
        self.assertIsNone(agente._programa_que_falta("sudo LANG=C ls -la"))
        self.assertIsNone(agente._programa_que_falta("cd /tmp && ls"))

    def test_endereco_de_busca_morto_nao_muda_nada(self):
        pastas.salvar_config(busca=True, searxng=None)
        with self.assertRaises(SystemExit) as saida:
            cli.comando_busca(["http://127.0.0.1:9"])
        self.assertIn("Nothing changed", str(saida.exception))
        self.assertIsNone(pastas.config().get("searxng"))


if __name__ == "__main__":
    unittest.main()
