"""O estado da placa, lido direto do sistema: rápido e sem chance de o modelo inventar o número."""
import glob
import os
import re
import socket


def _ler(caminho, padrao=""):
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            return f.read().strip("\x00\n ")
    except OSError:
        return padrao


def temperatura():
    """A maior temperatura dos sensores do sistema, em °C, ou None."""
    valores = []
    for zona in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            valores.append(int(_ler(zona)) / 1000)
        except ValueError:
            pass
    return max(valores) if valores else None


def memoria():
    """(total, disponível) em MB."""
    campos = {}
    for linha in _ler("/proc/meminfo").splitlines():
        nome, _, valor = linha.partition(":")
        if valor.split():
            campos[nome] = int(valor.split()[0]) // 1024
    return campos.get("MemTotal", 0), campos.get("MemAvailable", 0)


def disco(caminho="~"):
    """(total, livre) em GB."""
    s = os.statvfs(os.path.expanduser(caminho))
    return s.f_blocks * s.f_frsize / 1e9, s.f_bavail * s.f_frsize / 1e9


def ligada_ha():
    """Segundos desde que a placa ligou."""
    return int(float((_ler("/proc/uptime") or "0").split()[0]))


def modelo():
    return _ler("/proc/device-tree/model") or os.uname().machine


def sistema():
    for linha in _ler("/etc/os-release").splitlines():
        if linha.startswith("PRETTY_NAME="):
            return linha.split("=", 1)[1].strip('"')
    return "Linux"


def ip_local():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # UDP não manda nada: só escolhe a interface
            return s.getsockname()[0]
    except OSError:
        return None


def processador():
    """O nome do processador: 'model name' no x86; nas placas ARM o lscpu diz o núcleo (Cortex-A53) e a device tree o chip."""
    for linha in _ler("/proc/cpuinfo").splitlines():
        if linha.lower().startswith(("model name", "hardware", "cpu model")):
            return linha.split(":", 1)[1].strip()
    try:
        import subprocess
        saida = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=5).stdout
        achado = re.search(r"Model name:\s*(.+)", saida)
        if achado:
            return achado.group(1).strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.uname().machine


def wifi():
    """(interface, conectada) da primeira placa de Wi-Fi, ou None se não houver. Lê o /sys: sem programa e sem rede."""
    for caminho in sorted(glob.glob("/sys/class/net/*/wireless")):
        pasta = os.path.dirname(caminho)
        return os.path.basename(pasta), _ler(pasta + "/operstate") == "up"
    return None


def tem_desktop():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
