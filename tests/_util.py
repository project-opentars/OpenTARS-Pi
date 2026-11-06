"""Pasta temporária no lugar da pasta do usuário: os testes não tocam a instalação de verdade."""
import os
import sys
import tempfile

os.environ["OPENTARS_PI_HOME"] = tempfile.mkdtemp(prefix="opentars-pi-teste-")
os.environ.setdefault("LANG", "en_US.UTF-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
