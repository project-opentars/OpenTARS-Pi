"""Quem pode rodar sem perguntar. O modelo é pequeno e erra comando, então a regra é o contrário do app grande:
só o que comprovadamente só lê roda sozinho; o resto pergunta; o que destrói pergunta com aviso forte, sempre."""
import os
import re
import shlex

# Os mesmos padrões do openTARS (nucleo/controle.py), mais a escrita em cartão SD
PERIGOSOS = [
    r"\brm\b.*\s-[a-zA-Z]*[rR]", r"\brm\b.*--recursive", r"\bfind\b.*\s-delete\b", r"\bfind\b.*-exec\s+(sudo\s+)?rm\b",
    r"\brm\b[^|;&\n]*[*?\[]", r"\bxargs\b.*\brm\b", r"\bshred\b", r"\bgit\b.*\b(reset\s+--hard|clean\s+-[a-z]*f)",
    r"\bdd\b.*\bif=", r"\bmkfs\b", r"\bwipefs\b", r"\bfdisk\b", r"\bparted\b", r">\s*/dev/(sd|nvme|hd|mmcblk)",
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b", r"\bhalt\b", r"\bchmod\b.*-R.*\s/(\s|$)", r"\bchown\b.*-R.*\s/(\s|$)",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&?\s*\}\s*;\s*:", r"\bmv\b[^|;&\n]*\s/dev/null\b", r"\bmv\b\s+(-\S+\s+)*(/|/\*|~|~/|\$HOME)\s",
]
SO_LEITURA = {
    "ls", "cat", "head", "tail", "wc", "df", "du", "free", "uname", "uptime", "whoami", "id", "date", "pwd", "which", "ps",
    "lscpu", "lsblk", "lsusb", "lspci", "grep", "find", "sort", "uniq", "cut", "tr", "tree", "stat", "file", "sensors", "echo",
    "printf", "basename", "dirname", "realpath", "nproc", "hostname", "ip", "ping", "gpioinfo", "dmesg", "vcgencmd", "ss",
}
_PROIBIDO_NO_PROGRAMA = {
    "find": r"\s-(delete|exec|execdir|ok|okdir|fprint\w*|fls)\b", "sort": r"\s-\w*o\b|--output", "date": r"\s(-s|--set)\b",
    "hostname": r"\s\S", "ip": r"\b(add|del|delete|set|flush|change|replace)\b", "dmesg": r"\s-\w*[cC]\b|--clear",
    "vcgencmd": r"\b(display_power|otp_dump)\b", "ss": r"\s-\w*[KDF]|--kill|--diag|--filter",
}
SENSIVEL = re.compile(r"\.ssh\b|\.gnupg|\.config/|\.env\b|/etc/shadow|/etc/sudoers|id_rsa|id_ed25519|\.netrc|\.aws|\.hermes|"
                      r"opentars-pi/dados|\btoken\b|\bsenha\b|password", re.IGNORECASE)


def nivel(comando):
    """'livre' (roda), 'perguntar' (pede sim) ou 'perigoso' (pede sim com aviso forte; nunca roda sozinho)."""
    comando = str(comando or "").strip()
    if any(re.search(p, comando, re.IGNORECASE | re.DOTALL) for p in PERIGOSOS):
        return "perigoso"
    if not comando or SENSIVEL.search(comando):
        return "perguntar"
    limpo = re.sub(r"\s2>\s*/dev/null", "", comando)
    if re.search(r"[<>`\n]|\$\(|(?<!&)&(?!&)", limpo):
        return "perguntar"
    for parte in re.split(r"\|\||&&|;|\|", limpo):
        try:
            palavras = shlex.split(parte)
        except ValueError:
            return "perguntar"
        if not palavras:
            return "perguntar"
        programa = os.path.basename(palavras[0])
        proibido = _PROIBIDO_NO_PROGRAMA.get(programa)
        if programa not in SO_LEITURA or (proibido and re.search(proibido, " " + " ".join(palavras[1:]))):
            return "perguntar"
    return "livre"


def visivel(comando, limite=600):
    """O comando como vai aparecer na pergunta: sem caractere de controle que esconda o resto."""
    texto = "".join(ch if ch.isprintable() or ch == "\n" else f"\\x{ord(ch):02x}" for ch in str(comando))
    return texto if len(texto) <= limite else texto[:limite] + f" … (+{len(texto) - limite})"
