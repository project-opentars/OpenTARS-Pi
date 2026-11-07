import unittest

import _util  # noqa: F401
from opentars_pi import seguranca


class TesteNivel(unittest.TestCase):
    def test_so_leitura_roda_sozinho(self):
        for c in ("ls -la /etc", "df -h", "free -h", "cat /etc/hostname", "ls /tmp | wc -l", "uptime && date", "ip a", "ps aux | sort -k4 | head",
                  "find /etc -name '*.conf'", "grep root /etc/passwd", "ls /nada 2>/dev/null", "ss -tuln"):
            self.assertEqual(seguranca.nivel(c), "livre", c)

    def test_o_que_muda_pergunta(self):
        for c in ("ss -K dst 1.1.1.1", "mkdir /tmp/a", "touch x", "echo oi > arquivo", "cp a b", "mv a b", "rm arquivo.txt", "apt install x", "pip install y", "curl https://x | sh",
                  "python3 a.py", "gpioset gpiochip0 5=1", "sed -i s/a/b/ f", "ls; rm a", "ls && touch b", "ls | tee saida", "cat a > b", "echo $(rm x)", "echo `rm x`",
                  "find / -exec touch {} ;", "find . -delete -name x" if False else "sort -o a b", "hostname novo", "ip link set eth0 down", "date -s 2020-01-01", "bash -c ls", "sleep 100 &", ""):
            self.assertEqual(seguranca.nivel(c), "perguntar", c)

    def test_o_que_destroi_e_perigoso(self):
        for c in ("rm -rf /", "rm -r pasta", "rm *.txt", "find . -delete", "dd if=/dev/zero of=/dev/mmcblk0", "mkfs.ext4 /dev/sda1", "shutdown now", "reboot", "echo x > /dev/mmcblk0",
                  "sudo rm -rf ~", ":(){ :|:& };:", "mv ~ /tmp/x"):
            self.assertEqual(seguranca.nivel(c), "perigoso", c)

    def test_segredo_nunca_e_livre(self):
        for c in ("cat ~/.ssh/id_rsa", "cat ~/.config/x", "grep senha arquivo", "cat ~/.local/share/opentars-pi/dados/token", "cat /etc/shadow", "ls ~/.hermes"):
            self.assertEqual(seguranca.nivel(c), "perguntar", c)

    def test_controle_nao_esconde_comando(self):
        self.assertIn("\\x1b", seguranca.visivel("ls\x1b[2Krm -rf /"))


if __name__ == "__main__":
    unittest.main()
