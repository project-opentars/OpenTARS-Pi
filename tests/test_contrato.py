"""Confere o texto do app contra o molde real do FunctionGemma (o mesmo do treino) e contra as linhas do kit."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from opentars_pi import contrato as c   # noqa: E402

try:
    import jinja2
except ImportError:
    jinja2 = None

AQUI = os.path.dirname(__file__)


def ferramentas_json():
    saida = []
    for nome, descricao, parametros, exigidos in c.FERRAMENTAS:
        saida.append({"type": "function", "function": {"name": nome, "description": descricao, "parameters": {
            "type": "object", "properties": {p: {"type": "string"} for p in parametros}, "required": list(exigidos)}}})
    return saida


def molde(mensagens, tools=True):
    """mensagens no formato do treino, pelo chat_template.jinja do modelo."""
    ambiente = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(AQUI, "fixtures")),
                                  extensions=["jinja2.ext.loopcontrols"])
    ambiente.filters.setdefault("tojson", json.dumps)
    texto = ambiente.get_template("functiongemma.jinja").render(
        messages=mensagens, tools=ferramentas_json() if tools else None, bos_token="<bos>", add_generation_prompt=True)
    return texto[len("<bos>"):]


def para_treino(m):
    if m.get("chamada"):
        nome, argumentos = m["chamada"]
        return {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": nome, "arguments": argumentos}}]}
    return m


@unittest.skipIf(jinja2 is None, "precisa do jinja2 (só para o teste)")
class TesteMolde(unittest.TestCase):
    def conferir(self, mensagens):
        self.assertEqual(c.renderizar(mensagens), molde([para_treino(m) for m in mensagens]))

    def test_pedido_simples(self):
        self.conferir([{"role": "system", "content": c.sistema("THIS COMPUTER\n- User: a", ["fato um"], "pt")},
                       {"role": "user", "content": "oi"}])

    def test_aviso_de_idioma_vem_como_segundo_user(self):
        self.conferir([{"role": "system", "content": c.sistema(idioma="pt")}, {"role": "user", "content": "hello"},
                       {"role": "user", "content": c.AVISO_IDIOMA["en"]}])

    def test_depois_de_uma_ferramenta(self):
        self.conferir([{"role": "system", "content": c.sistema(idioma="en")}, {"role": "user", "content": "free memory?"},
                       {"role": "assistant", "content": "", "chamada": ("execute_terminal", {"command": "free -h"})},
                       {"role": "tool", "name": "execute_terminal", "content": '{"success": true}'}])

    def test_duas_ferramentas_e_conversa_anterior(self):
        self.conferir([{"role": "system", "content": c.sistema(idioma="en")}, {"role": "user", "content": "one"},
                       {"role": "assistant", "content": "", "chamada": ("remember", {"fact": "x"})},
                       {"role": "tool", "name": "remember", "content": "ok"}, {"role": "assistant", "content": "Saved."},
                       {"role": "user", "content": "two"},
                       {"role": "assistant", "content": "", "chamada": ("search_web", {"query": "q", "service": "google"})},
                       {"role": "tool", "name": "search_web", "content": "r"},
                       {"role": "assistant", "content": "", "chamada": ("forget", {"fact": "x"})},
                       {"role": "tool", "name": "forget", "content": "ok"}])


    def test_conversa_sem_ferramentas(self):
        mensagens = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "Olá!"}, {"role": "user", "content": "tudo bem?"}]
        self.assertEqual(c.renderizar_conversa([("oi", "Olá!")], "tudo bem?"), molde(mensagens, tools=False))


class TesteLeitura(unittest.TestCase):
    def test_chamada_com_dois_argumentos(self):
        chamada, fala = c.ler_resposta("<start_function_call>call:search_web{query:<escape>a b<escape>,service:<escape>google<escape>}")
        self.assertEqual(chamada, ("search_web", {"query": "a b", "service": "google"}))
        self.assertEqual(fala, "")

    def test_comando_com_chaves_e_aspas(self):
        chamada, _ = c.ler_resposta('<start_function_call>call:execute_terminal{command:<escape>awk \'{print $1}\' "a b"<escape>}')
        self.assertEqual(chamada[1]["command"], "awk '{print $1}' \"a b\"")

    def test_fala_sem_chamada(self):
        self.assertEqual(c.ler_resposta("Olá, tudo bem?"), (None, "Olá, tudo bem?"))


if __name__ == "__main__":
    unittest.main()
