"""GPIO pela interface de caracteres do Linux (ioctl v2), só com a biblioteca padrão: nada para instalar, funciona em
qualquer placa com kernel 5.10 ou mais novo. Os nomes aceitos: o da linha (GPIO17), o Allwinner (PC5) e o número no chip."""
import fcntl
import glob
import os
import re
import struct

_LINHAS_MAX = 64
_TAM_CONFIG = 272
_TAM_PEDIDO = 592
_TAM_INFO = 256
_CHIPINFO = 0x8044B401                  # GPIO_GET_CHIPINFO_IOCTL
_LINEINFO = 0xC100B405                  # GPIO_V2_GET_LINEINFO_IOCTL
_LINE = 0xC250B407                      # GPIO_V2_GET_LINE_IOCTL
_GET_VALUES = 0xC010B40E                # GPIO_V2_LINE_GET_VALUES_IOCTL
_SET_VALUES = 0xC010B40F                # GPIO_V2_LINE_SET_VALUES_IOCTL
USADA, ENTRADA, SAIDA = 1 << 0, 1 << 2, 1 << 3
_FLAG_ID = 1
_VALOR_ID = 2


class ErroGpio(Exception):
    pass


def chips():
    return sorted(glob.glob("/dev/gpiochip*"), key=lambda c: int(re.sub(r"\D", "", c) or 0))


def _abrir(caminho):
    try:
        return os.open(caminho, os.O_RDWR)
    except PermissionError:
        raise ErroGpio(f"no permission to use {caminho}. Add your user to the gpio group: sudo usermod -aG gpio $USER, then log in again.")


def _chip_info(fd):
    dados = bytearray(68)
    fcntl.ioctl(fd, _CHIPINFO, dados)
    return dados[:32].split(b"\0")[0].decode(), dados[32:64].split(b"\0")[0].decode(), struct.unpack_from("I", dados, 64)[0]


def _linha_info(fd, deslocamento):
    dados = bytearray(_TAM_INFO)
    struct.pack_into("I", dados, 64, deslocamento)
    fcntl.ioctl(fd, _LINEINFO, dados)
    return {"nome": dados[:32].split(b"\0")[0].decode(), "dono": dados[32:64].split(b"\0")[0].decode(),
            "flags": struct.unpack_from("Q", dados, 72)[0]}


def linhas():
    """[{chip, deslocamento, nome, dono, flags}] de todas as linhas das placas."""
    saida = []
    for caminho in chips():
        fd = _abrir(caminho)
        try:
            for i in range(_chip_info(fd)[2]):
                saida.append({"chip": caminho, "deslocamento": i, **_linha_info(fd, i)})
        finally:
            os.close(fd)
    return saida


def achar(nome):
    """(chip, deslocamento) do pino. Levanta ErroGpio dizendo o que aceita."""
    nome = str(nome).strip()
    todas = linhas() if chips() else []
    if not todas:
        raise ErroGpio("this computer has no GPIO chip (/dev/gpiochip*).")
    for linha in todas:
        if linha["nome"] and linha["nome"].lower() == nome.lower():
            return linha["chip"], linha["deslocamento"]
    principal = max(chips(), key=lambda c: sum(1 for l in todas if l["chip"] == c))
    allwinner = re.fullmatch(r"P([A-K])(\d{1,2})", nome.upper())
    if allwinner:    # Orange Pi, Banana Pi: deslocamento = letra * 32 + número no controlador principal
        return principal, (ord(allwinner.group(1)) - 65) * 32 + int(allwinner.group(2))
    numero = re.fullmatch(r"(?:gpio)?(\d+)", nome, re.IGNORECASE)
    if numero:
        return principal, int(numero.group(1))
    raise ErroGpio(f"no pin named {nome!r}. Use the line name (GPIO17), the Allwinner name (PC5) or the line number.")


def _pedir(caminho, deslocamento, flags, valor=None):
    """O fd da linha reservada. flags=0 mantém a direção que a linha já tem."""
    fd = _abrir(caminho)
    try:
        info = _linha_info(fd, deslocamento)
        if info["flags"] & USADA:
            raise ErroGpio(f"line {deslocamento} of {caminho} is in use by {info['dono'] or 'the kernel'}. Pick another pin.")
        pedido = bytearray(_TAM_PEDIDO)
        struct.pack_into("I", pedido, 0, deslocamento)
        pedido[256:256 + 7] = b"opentar"
        struct.pack_into("Q", pedido, 288, flags)
        if valor is not None:
            struct.pack_into("I", pedido, 296, 1)                                       # num_attrs
            struct.pack_into("IIQQ", pedido, 288 + 32, _VALOR_ID, 0, 1 if valor else 0, 1)   # atributo: valor inicial
        struct.pack_into("I", pedido, 256 + 32 + _TAM_CONFIG, 1)                        # num_lines
        fcntl.ioctl(fd, _LINE, pedido)
        return struct.unpack_from("i", pedido, _TAM_PEDIDO - 4)[0]
    except OSError as e:
        raise ErroGpio(f"could not use line {deslocamento} of {caminho}: {e.strerror}")
    finally:
        os.close(fd)


def ler(nome):
    """0 ou 1, sem mudar a direção do pino."""
    caminho, deslocamento = achar(nome)
    fd = _pedir(caminho, deslocamento, 0)
    try:
        dados = bytearray(struct.pack("QQ", 0, 1))
        fcntl.ioctl(fd, _GET_VALUES, dados)
        return struct.unpack("QQ", dados)[0] & 1
    finally:
        os.close(fd)


def escrever(nome, valor):
    """Põe o pino como saída nesse valor. O kernel mantém o valor depois que o processo sai nas placas testadas."""
    caminho, deslocamento = achar(nome)
    os.close(_pedir(caminho, deslocamento, SAIDA, valor))


def soltar(nome):
    """Devolve o pino como entrada."""
    caminho, deslocamento = achar(nome)
    os.close(_pedir(caminho, deslocamento, ENTRADA))
