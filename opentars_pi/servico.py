"""O serviço em segundo plano pelo systemd do usuário: desligado até a pessoa ligar."""
import shutil
import subprocess
import sys
from pathlib import Path

UNIDADE = Path.home() / ".config/systemd/user/opentars-pi.service"


def _systemctl(*args):
    if not shutil.which("systemctl"):       # contêiner ou placa sem systemd: não há serviço para mexer
        return subprocess.CompletedProcess(args, 1, "", "no systemd")
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def ligar(rede=False):
    if not shutil.which("systemctl"):
        sys.exit("This system has no systemd. Run it by hand: opentars --serve")
    UNIDADE.parent.mkdir(parents=True, exist_ok=True)
    raiz = Path(__file__).resolve().parent.parent
    UNIDADE.write_text("[Unit]\nDescription=openTARS Pi\nAfter=network-online.target\n\n[Service]\n"
                       f"ExecStart={sys.executable} {raiz / 'opentars-pi'} --serve{' --network' if rede else ''}\n"
                       "Restart=on-failure\nRestartSec=5\n\n[Install]\nWantedBy=default.target\n", encoding="utf-8")
    _systemctl("daemon-reload")
    r = _systemctl("enable", "--now", "opentars-pi.service")
    return r.returncode == 0, (r.stderr or "").strip()


def desligar():
    _systemctl("disable", "--now", "opentars-pi.service")
    UNIDADE.unlink(missing_ok=True)
    _systemctl("daemon-reload")


def estado():
    return _systemctl("is-active", "opentars-pi.service").stdout.strip() or "inactive"
