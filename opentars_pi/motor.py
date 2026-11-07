"""O llama.cpp: sobe o llama-server só nesta máquina, fala com ele e guarda o prompt pronto no disco.

A placa leva ~16 s para ler o prompt de sistema na primeira vez; guardado, ele volta em instantes (medido na Orange Pi Zero 2W).
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from . import contrato, pastas

PORTA = 18099
CONTEXTO = 2048


class MotorForaDoAr(Exception):
    pass


class Motor:
    def __init__(self, porta=None, modelo=None):
        self.porta = porta or int(os.environ.get("OPENTARS_PI_PORTA") or PORTA)
        self.modelo = modelo or os.environ.get("OPENTARS_PI_MODELO") or str(pastas.MODELOS / pastas.ARQUIVO_MODELO)
        self.processo = None
        self.prefixo_pronto = None

    def _pedir(self, caminho, corpo=None, tempo=600):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        pedido = urllib.request.Request(f"http://127.0.0.1:{self.porta}{caminho}", dados, {"Content-Type": "application/json"})
        return urllib.request.urlopen(pedido, timeout=tempo)

    def vivo(self):
        try:
            with self._pedir("/health", tempo=2) as r:
                return r.status == 200
        except (OSError, ValueError):
            return False

    def binario(self):
        proprio = pastas.MOTOR / "llama-server"
        return str(proprio) if proprio.exists() else shutil.which("llama-server")

    def ligar(self, tempo=180):
        """Sobe o motor se ninguém subiu. Se o serviço já está de pé, usa esse e não mexe nele."""
        if self.vivo():
            return
        binario = self.binario()
        if not binario or not os.path.exists(self.modelo):
            raise MotorForaDoAr("engine or model not found. Reinstall with: opentars update")
        pastas.CACHE.mkdir(parents=True, exist_ok=True)
        nucleos = os.cpu_count() or 4
        comando = [binario, "-m", self.modelo, "--host", "127.0.0.1", "--port", str(self.porta), "-t", str(nucleos),
                   "--parallel", "1", "-b", "256", "-ub", "256", "--cache-ram", "0", "--no-warmup", "--no-webui", "--slot-save-path", str(pastas.CACHE)]
        comando += ["-c", str(CONTEXTO), "-sp", "--swa-full"]
        pastas.DADOS.mkdir(parents=True, exist_ok=True)
        with open(pastas.DADOS / "motor.log", "ab") as registro:
            self.processo = subprocess.Popen(comando, stdin=subprocess.DEVNULL, stdout=registro, stderr=registro, start_new_session=True,
                                             env={**os.environ, "LD_LIBRARY_PATH": str(os.path.dirname(binario))})
        limite = time.time() + tempo
        while time.time() < limite:
            if self.processo.poll() is not None:
                raise MotorForaDoAr(f"the engine stopped with code {self.processo.returncode}. See {pastas.DADOS / 'motor.log'}")
            if self.vivo():
                return
            time.sleep(0.3)
        self.desligar()
        raise MotorForaDoAr("the engine took too long to start.")

    def desligar(self):
        """Só desliga o que este processo subiu."""
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()
            try:
                self.processo.wait(5)
            except subprocess.TimeoutExpired:
                self.processo.kill()
        self.processo = None

    def _arquivo_do_prefixo(self, prefixo):
        try:
            info = os.stat(self.modelo)
            modelo = f"{self.modelo}:{info.st_size}:{info.st_mtime_ns}"
        except OSError:
            modelo = self.modelo
        # o estado guardado só vale para o mesmo modelo: com outro, voltaria lixo
        return hashlib.sha1((modelo + "\0" + prefixo).encode()).hexdigest()[:16] + ".bin"

    def preparar_prefixo(self, prefixo):
        """Traz do disco o prompt de sistema já lido; se ainda não existe, lê uma vez e guarda."""
        if prefixo == self.prefixo_pronto:
            return
        arquivo = self._arquivo_do_prefixo(prefixo)
        try:
            if (pastas.CACHE / arquivo).exists():
                self._pedir("/slots/0?action=restore", {"filename": arquivo}).close()
            else:
                self._pedir("/completion", {"prompt": prefixo, "n_predict": 0, "cache_prompt": True}).close()
                self._pedir("/slots/0?action=save", {"filename": arquivo}).close()
                for velho in pastas.CACHE.glob("*.bin"):      # a data no prompt muda todo dia: não acumula no cartão
                    if velho.name != arquivo and time.time() - velho.stat().st_mtime > 2 * 86400:
                        velho.unlink()
            self.prefixo_pronto = prefixo
        except (OSError, ValueError):
            self.prefixo_pronto = None     # sem o cache só fica mais lento

    def completar(self, prompt, ao_pedaco=None, maximo=200, temperatura=0.1):
        """O texto gerado. ao_pedaco recebe cada pedaço assim que sai."""
        corpo = {"prompt": prompt, "n_predict": maximo, "temperature": temperatura, "stop": contrato.PARADAS, "cache_prompt": True, "stream": True}
        texto = []
        try:
            with self._pedir("/completion", corpo) as resposta:
                for linha in resposta:
                    if not linha.startswith(b"data: "):
                        continue
                    pedaco = json.loads(linha[6:])
                    if pedaco.get("content"):
                        texto.append(pedaco["content"])
                        if ao_pedaco:
                            ao_pedaco(pedaco["content"])
                    if pedaco.get("stop"):
                        break
        except (OSError, ValueError) as e:
            raise MotorForaDoAr(f"the engine did not answer: {e}")
        return "".join(texto)
