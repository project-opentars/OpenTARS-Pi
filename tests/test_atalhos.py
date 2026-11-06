import unittest

import _util  # noqa: F401
from opentars_pi import atalhos, memoria, pastas


class TesteAtalhos(unittest.TestCase):
    def setUp(self):
        pastas.MEMORIA.unlink(missing_ok=True)

    def fala(self, pedido, idioma="en"):
        return (atalhos.resolver(pedido, idioma) or {}).get("fala")

    def test_estado_da_placa_sem_modelo(self):
        self.assertIn("MB of memory", self.fala("how much RAM is free?"))
        self.assertIn("memória", self.fala("quanta memória livre eu tenho?", "pt"))
        self.assertIn("disk", self.fala("how much free disk space do I have?"))
        self.assertIn("disco", self.fala("quanto espaço livre tem no disco?", "pt"))
        self.assertIn("cores", self.fala("how many cores does it have?"))

    def test_jeitos_curtos_de_perguntar_da_placa(self):
        self.assertIn("board", self.fala("how warm is the cpu right now?"))
        self.assertIn("address", self.fala("ip?"))
        self.assertIn("Memory:", self.fala("show me the board status"))

    def test_uso_de_memoria_e_ram(self):
        self.assertIn("MB", self.fala("qual o uso de memória agora?", "pt"))

    def test_pergunta_sobre_o_que_guardou_nao_vai_para_a_web(self):
        memoria.lembrar("o backup roda às 3 da manhã")
        self.assertIsNone(atalhos.resolver("quando roda o backup?", "pt"))

    def test_memoria_do_assistente_nao_vira_ram(self):
        self.assertIn("empty", self.fala("what do you remember?"))
        memoria.lembrar("my cat is Luna")
        self.assertIn("Luna", self.fala("show your memory"))

    def test_lembrar_guarda_o_texto_original(self):
        self.assertIn("Noted", self.fala("remember that my server user is admin"))
        self.assertIn("anotado", self.fala("grava que meu usuário do servidor é admin", "pt").lower())
        self.assertIn("meu usuário do servidor é admin", memoria.ler())

    def test_lembrar_com_comeco_de_frase(self):
        self.assertIn("Noted", self.fala("from now on remember that the fan is on pin PC2"))

    def test_salvar_arquivo_nao_e_memoria(self):
        self.assertIsNone(self.fala("save the file to /tmp"))
        self.assertIsNone(self.fala("salva o arquivo em /tmp", "pt"))

    def test_esquecer(self):
        memoria.lembrar("eu prefiro o editor nano")
        memoria.lembrar("eu moro em Natal")
        self.assertIn("nano", self.fala("esquece o que eu disse sobre o nano", "pt"))
        self.assertEqual(memoria.ler(), ["eu moro em Natal"])
        self.assertIn("nothing", self.fala("forget about Luna").lower())

    def test_recusas(self):
        for pedido in ("click file and then save", "take a screenshot", "close the window", "launch gimp", "open firefox", "what is on my screen?"):
            self.assertIn("no screen", self.fala(pedido), pedido)
        for pedido in ("draw a picture of a cat", "edit this photo", "read this out loud"):
            self.assertIn("full openTARS", self.fala(pedido), pedido)

    def test_pinos(self):
        self.assertEqual(atalhos.resolver("turn PC5 on", "en"), {"pino": ("escrever", "PC5", 1)})
        self.assertEqual(atalhos.resolver("desliga o pino PC5", "pt"), {"pino": ("escrever", "PC5", 0)})
        self.assertEqual(atalhos.resolver("read pin GPIO17", "en"), {"pino": ("ler", "GPIO17")})
        self.assertEqual(atalhos.resolver("turn the relay on", "en"), {"pino": ("qual",)})
        memoria.lembrar("the relay is on pin PC5")
        self.assertEqual(atalhos.resolver("turn the relay on", "en"), {"pino": ("escrever", "PC5", 1)})
        memoria.lembrar("o relé está no pino PC7")
        self.assertEqual(atalhos.resolver("desliga o rele", "pt"), {"pino": ("escrever", "PC7", 0)})

    def test_ligar_outra_coisa_vai_para_o_modelo(self):
        self.assertNotIn("pino", atalhos.resolver("liga o wifi", "pt") or {})

    def test_pergunta_sobre_o_mundo_vai_para_a_busca(self):
        for pedido in ("qual a capital da Mongólia?", "who is the president of France?", "o que é uma pasta?", "explain what a pipe is in linux", "how do I install docker?"):
            self.assertIn("pesquisa", atalhos.resolver(pedido, "en") or {}, pedido)

    def test_papo_fica_com_o_modelo(self):
        for pedido in ("how are you?", "tudo bem com você?", "me conta uma piada"):
            self.assertIsNone(atalhos.resolver(pedido, "en"), pedido)

    def test_saudacao_e_agradecimento_saem_na_hora(self):
        for pedido in ("oi", "bom dia!", "hello there", "thanks a lot!", "valeu"):
            self.assertIn("fala", atalhos.resolver(pedido, "en"), pedido)

    def test_pergunta_pessoal_sem_memoria_nao_inventa(self):
        self.assertIn("told me", self.fala("what is my name?"))

    def test_pesquisa_explicita(self):
        self.assertEqual(atalhos.resolver("pesquisa como instalar o docker", "pt"), {"pesquisa": "como instalar o docker"})
        self.assertEqual(atalhos.resolver("search the web for armbian static ip", "en"), {"pesquisa": "armbian static ip"})


if __name__ == "__main__":
    unittest.main()
