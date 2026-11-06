import json
import unittest

import _util  # noqa: F401
from opentars_pi import aprovacoes, contrato, ferramentas, memoria, pastas


class TesteTerminal(unittest.TestCase):
    def test_formato_do_treino(self):
        r = ferramentas.rodar("echo oi")
        self.assertEqual(r, {"success": True, "exit_code": 0, "stdout": "oi\n", "stderr": "", "message": "Command finished."})

    def test_erro(self):
        r = ferramentas.rodar("ls /nao/existe")
        self.assertFalse(r["success"])
        self.assertEqual(r["message"], "Command finished with an error.")

    def test_tempo_limite_mata_o_grupo(self):
        r = ferramentas.rodar("sleep 30 & sleep 30", tempo=1)
        self.assertIn("stopped", r["message"])

    def test_saida_enorme_nao_enche_a_memoria(self):
        r = ferramentas.rodar("yes | head -c 5000000")
        self.assertLessEqual(len(r["stdout"]), ferramentas.LIMITE_SAIDA)

    def test_o_que_muda_passa_pela_aprovacao(self):
        pedidos = []
        f = ferramentas.Ferramentas(lambda c, n: pedidos.append((c, n)) or False)
        r = f.chamar("execute_terminal", {"command": "touch /tmp/opentars-pi-teste"})
        self.assertEqual(pedidos, [("touch /tmp/opentars-pi-teste", "perguntar")])
        self.assertEqual(r["message"], ferramentas.NAO_APROVOU)

    def test_auto_nao_libera_o_perigoso(self):
        pedidos = []
        f = ferramentas.Ferramentas(lambda c, n: pedidos.append(n) or False, auto=True)
        f.chamar("execute_terminal", {"command": "rm -rf /tmp/nada-disso"})
        self.assertEqual(pedidos, ["perigoso"])

    def test_ferramenta_desconhecida(self):
        self.assertFalse(ferramentas.Ferramentas(lambda c, n: False).chamar("open_website", {})["success"])


class TesteMemoria(unittest.TestCase):
    def setUp(self):
        pastas.MEMORIA.unlink(missing_ok=True)

    def test_lembrar_e_esquecer_com_as_frases_do_treino(self):
        f = ferramentas.Ferramentas(lambda c, n: False)
        self.assertEqual(f.chamar("remember", {"fact": "gato é Mingau"})["message"], "SUCCESS: saved. It will be in your instructions from now on.")
        self.assertEqual(memoria.ler(), ["gato é Mingau"])
        self.assertEqual(f.chamar("forget", {"fact": "Mingau"})["message"], "SUCCESS: forgot: gato é Mingau")
        self.assertFalse(f.chamar("forget", {"fact": "zebra"})["success"])

    def test_resultado_entra_no_prompt(self):
        memoria.lembrar("meu gato é Mingau")
        self.assertIn("- meu gato é Mingau\n", contrato.sistema("", memoria.ler(), "pt"))


class TesteSemSystemd(unittest.TestCase):
    def test_estado_e_desligar_nao_quebram(self):
        import os
        from unittest import mock
        from opentars_pi import servico
        with mock.patch.dict(os.environ, {"PATH": "/nada"}):
            self.assertEqual(servico.estado(), "inactive")
            servico.desligar()


class TesteBusca(unittest.TestCase):
    def test_melhor_frase_e_a_que_responde(self):
        from opentars_pi import busca
        resumo = "O Peru é um país da América do Sul. Tem costa no Pacífico. A capital do Peru é Lima, a maior cidade do país."
        self.assertIn("Lima", busca.melhor_frase(resumo, "qual a capital do Peru?"))

    def test_desligada_nada_sai_da_placa(self):
        from opentars_pi import busca
        pastas.salvar_config(busca=False)
        self.addCleanup(pastas.CONFIG.unlink, missing_ok=True)
        self.assertEqual(busca.buscar("qualquer coisa"), ([], "web search is off"))


class TesteAprovacaoPelaRede(unittest.TestCase):
    def test_sem_resposta_e_nao(self):
        self.assertFalse(aprovacoes.pedir("ls", "perguntar", espera=0.2))

    def test_token_fica_so_para_o_dono(self):
        aprovacoes.novo_token()
        self.assertEqual(pastas.TOKEN.stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
