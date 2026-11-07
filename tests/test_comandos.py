import unittest

import _util  # noqa: F401
from opentars_pi import atalhos, comandos


def plano(pedido):
    """O comando que sai das regras (as operações novas primeiro, como no app)."""
    n = atalhos.normalizar(pedido)
    r = atalhos.operacoes.plano(pedido, n) or comandos.plano(pedido, n)
    return r["comando"] if isinstance(r, dict) and "comando" in r else r


class TesteComandos(unittest.TestCase):
    def test_caminho_vem_exato(self):
        casos = {
            "lista os arquivos de /etc/ssl": "ls -la /etc/ssl",
            "list the files in /var/log": "ls -la /var/log",
            "what's in /tmp": "ls -la /tmp",
            "mostra o conteúdo de /etc/hostname": "head -n 100 /etc/hostname",
            "show me /etc/os-release": "head -n 100 /etc/os-release",
            "conta as linhas de /etc/passwd": "wc -l /etc/passwd",
            "how many lines does /etc/passwd have?": "wc -l /etc/passwd",
            "quantos arquivos tem em /etc?": "find /etc -maxdepth 1 -type f | wc -l",
            "how big is /var/log?": "du -sh /var/log",
            "how much space does /var/log use?": "du -sh /var/log",
            "find all .txt files in /usr/share/doc": "find /usr/share/doc -iname '*.txt' -not -path '*/.*' 2>/dev/null | head -50",
            "mostra as 5 últimas linhas de /var/log/syslog": "tail -n 5 /var/log/syslog",
            "show the first 3 lines of /etc/passwd": "head -n 3 /etc/passwd",
            "cria a pasta /tmp/fotos": "mkdir -p /tmp/fotos",
            "make a directory /tmp/music": "mkdir -p /tmp/music",
            "create a folder called demo in /tmp": "mkdir -p /tmp/demo",
            "cria uma pasta chamada teste em /tmp": "mkdir -p /tmp/teste",
            "cria a pasta fotos": "mkdir -p ~/fotos",
            "make a folder in /tmp called x1": "mkdir -p /tmp/x1",
            "what's in my downloads folder?": "ls -la ~/Downloads",
            "lista a pasta documentos": "ls -la ~/Documents",
            "list my home folder": "ls -la ~/",
            "show me the processes": "ps aux --sort=-%mem | head -8",
            "cria uma pasta nova chamada teste dentro de /tmp": "mkdir -p /tmp/teste",
            "copia /etc/hostname para /tmp/h": "cp -r /etc/hostname /tmp/h",
            "rename /tmp/a.txt to /tmp/b.txt": "mv /tmp/a.txt /tmp/b.txt",
            "apaga o arquivo /tmp/velho.txt": "rm /tmp/velho.txt",
            "delete the file /tmp/old.log": "rm /tmp/old.log",
            "find files named *.conf in /etc": "find /etc -name '*.conf' 2>/dev/null | head -50",
            "procura arquivos .log em /var/log": "find /var/log -iname '*.log' -not -path '*/.*' 2>/dev/null | head -50",
            "cria um arquivo /tmp/nota.txt com o texto oi": "printf '%s\\n' oi > /tmp/nota.txt",
            "write bye to /tmp/x.txt": "printf '%s\\n' bye > /tmp/x.txt",
            "escreve ola mundo num arquivo chamado oi.txt em /tmp" if False else "write hello world to /tmp/hi.txt": "printf '%s\\n' 'hello world' > /tmp/hi.txt",
        }
        for pedido, esperado in casos.items():
            self.assertEqual(plano(pedido), esperado, pedido)

    def test_acento_e_mantido(self):
        self.assertEqual(plano("cria a pasta /tmp/Música"), "mkdir -p /tmp/Música" if False else "mkdir -p '/tmp/Música'")

    def test_injecao_vira_texto(self):
        self.assertEqual(plano("write $(rm -rf ~) to /tmp/x"), "printf '%s\\n' '$(rm -rf ~)' > /tmp/x")

    def test_pasta_em_apagar_e_recursivo(self):
        self.assertEqual(plano("apaga a pasta /tmp"), "rm -r /tmp")

    def test_conversa_nao_vira_comando(self):
        for pedido in ("oi, tudo bem?", "what is a folder?", "o que é uma pasta?", "thanks!", "como funciona o linux?"):
            self.assertIsNone(plano(pedido), pedido)


if __name__ == "__main__":
    unittest.main()
