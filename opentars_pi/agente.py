"""O laço do assistente: atalhos primeiro, depois o modelo com as ferramentas, até ele responder."""
import re
import shlex
import shutil
import urllib.parse

from . import atalhos, busca, cerebro, contrato, gpio, memoria, operacoes, passos, pastas, textos
from .ferramentas import NAO_APROVOU, Ferramentas
from .textos import t

PASSOS = 5
_PRONOME = re.compile(r"\b(it|its|there|ele|ela|dele|dela|disso|la)\b")
_TROCA_IDIOMA = re.compile(r"^(?:(?:back|switch|go back|change|volta|voltar|muda|mudar|troca|trocar)(?: to| para| pra| pro| o idioma para)?|(?:speak|talk|answer|reply|fala|fale|responde|responda)(?: in| em)?|in|em)\s+"
                           r"(english|ingles|portuguese|portugues)(?: please| por favor)?[.!]?$")
_DIZ_QUE_FEZ = re.compile(r"\b(criei|criada|criado|feito|pronto|apaguei|apagado|salvei|salvo|movi|movido|instalei|instalado|renomeei|escrevi|"
                          r"done|created|deleted|saved|moved|installed|renamed|wrote|finished|success)\b", re.IGNORECASE)

_DO_SHELL = {"cd", "export", "set", "source", ".", "for", "if", "while", "[", "(", "{", "exit", "type", "ulimit", "umask", "read"}


def _programa_que_falta(comando):
    """O primeiro programa do comando, se ele não existe aqui. Só olha o começo: o resto da linha é com o shell."""
    partes = [p for p in comando.split() if p != "sudo" and "=" not in p]
    programa = partes[0] if partes else ""
    if not programa or "/" in programa or programa in _DO_SHELL or shutil.which(programa):
        return None
    return programa


class Agente:
    def __init__(self, motor, aprovar, mostrar=None, auto=False):
        """aprovar(descricao, nivel) -> bool. mostrar(tipo, texto): 'comando', 'saida', 'pedaco' (a fala saindo aos poucos)."""
        self.motor = motor
        self.cerebro = cerebro.escolher(motor)
        self.aprovar = aprovar
        self.mostrar = mostrar or (lambda tipo, texto: None)
        self.ferramentas = Ferramentas(aprovar, auto, ao_rodar=lambda comando: self.mostrar("comando", comando))
        self.historico = []
        self.ultimo_resultado, self.ultimo_comando, self.lugar = None, None, None      # para o passo seguinte: "salva isso", "copia para ela"
        self.idioma_base = textos.idioma_padrao()
        self.assunto = ""

    def _sistema(self):
        return self.cerebro.sistema(memoria.ler(), self.idioma_base)

    def _mensagens(self, pedido, idioma):
        mensagens = [{"role": "system", "content": self._sistema()}]
        for usuario, resposta in self.historico[-2:]:
            mensagens += [{"role": "user", "content": usuario}, {"role": "assistant", "content": resposta}]
        mensagens.append({"role": "user", "content": pedido})
        if idioma != self.idioma_base:
            mensagens.append({"role": "user", "content": contrato.AVISO_IDIOMA[idioma]})
        return mensagens

    def _pino(self, plano, idioma):
        acao, pino = plano[0], plano[1] if len(plano) > 1 else None
        try:
            if acao == "qual":
                return t("qual_pino", idioma)
            if acao == "ler":
                return t("pino_valor", idioma, pino=pino, valor=gpio.ler(pino))
            valor = plano[2]
            if not self.aprovar(f"{pino} {'on' if valor else 'off'}", "pino"):
                return t("pino_negado", idioma)
            gpio.escrever(pino, valor)
            return t("pino_ligado" if valor else "pino_desligado", idioma, pino=pino)
        except (gpio.ErroGpio, OSError) as e:
            return t("pino_erro", idioma, erro=e)

    def _comando(self, plano, idioma):
        """Roda o comando de uma regra. plano: {"comando", e talvez "resumo", "alvo", "nota"} (operacoes.py)."""
        plano = plano if isinstance(plano, dict) else {"comando": plano}
        resultado = self._usar_ferramenta("execute_terminal", {"command": plano["comando"]})
        self.ultimo_resultado = resultado
        if resultado.get("message") == NAO_APROVOU:
            return t("negado", idioma)
        nada_achado = plano.get("resumo") in ("ocorrencias", "arquivos_com") and resultado.get("exit_code") == 1 and not resultado.get("stderr", "").strip()
        if not resultado.get("success") and not nada_achado:      # grep sem achar sai com 1: é resposta, não erro
            erro = (resultado.get("stderr") or resultado.get("message") or "?").strip().splitlines()
            return t("falhou", idioma, erro=erro[-1])
        if plano.get("lugar"):
            self.lugar = plano["lugar"]
        resumo = operacoes.resumir(plano, resultado, idioma)
        if not resumo and not resultado.get("stdout", "").strip():
            resumo = t("feito", idioma)
        return " ".join(p for p in (plano.get("nota"), resumo) if p)       # sem resumo, a saída já apareceu

    def _usar_ferramenta(self, nome, argumentos):
        if nome != "execute_terminal":      # o comando aparece depois da aprovação
            self.mostrar("comando", argumentos.get("query") or argumentos.get("fact") or nome)
        resultado = self.ferramentas.chamar(nome, argumentos)
        if nome == "execute_terminal":       # o passo seguinte pode querer "salva isso"
            self.ultimo_comando, self.ultimo_resultado = argumentos.get("command"), resultado
        saida = (resultado.get("stdout") or "") + (resultado.get("stderr") or "")
        if saida.strip():
            self.mostrar("saida", saida.strip())
        return resultado

    def _falar_do_modelo(self, mensagens, ao_pedaco=None):
        """(chamada, fala) da próxima jogada do modelo. A fala sai aos poucos; a chamada não aparece."""
        return self.cerebro.jogada(mensagens, ao_pedaco)

    def _pesquisar(self, consulta, idioma):
        """A resposta sai dos resultados, sem passar pelo modelo: com 270M ele diz que abriu o navegador em vez de ler (medido em 06/11)."""
        if self.assunto and _PRONOME.search(atalhos.normalizar(consulta)):      # "e a capital dele?"
            consulta = f"{consulta} {self.assunto}"
        self.assunto = " ".join(busca.chaves(consulta))
        resultado = self._usar_ferramenta("search_web", {"query": consulta})
        if not resultado.get("success"):
            return t("sem_busca", idioma)
        site = lambda r: urllib.parse.urlsplit(r["url"]).hostname or r["url"]   # noqa: E731
        primeiro, *resto = resultado["resultados"]
        if primeiro.get("fraco"):
            return t("nao_achei", idioma, site=site(primeiro), titulo=primeiro["titulo"])
        linhas = [t("de_onde", idioma, site=site(primeiro), trecho=primeiro["trecho"] or primeiro["titulo"])]
        linhas += [t("tambem", idioma, site=site(r), titulo=r["titulo"]) for r in resto[:2]]
        return "\n".join(linhas)

    def _conversar(self, pedido, idioma):
        """Papo: sem ferramentas e sem prompt. Só voltas curtas entram: uma resposta de placa no meio atrapalha um modelo deste tamanho."""
        voltas = [(u, r) for u, r in self.historico[-2:] if r and len(r) < 200]
        return self._conferir(self.cerebro.conversar(voltas, pedido, lambda p: self.mostrar("pedaco", p)), 0, None, idioma)

    def responder(self, pedido):
        """A resposta final, em texto. O que mudou na placa já aconteceu quando isto volta."""
        pedido = pedido.strip()
        troca = _TROCA_IDIOMA.search(atalhos.normalizar(pedido))
        if troca:
            self.idioma_base = "pt" if troca.group(1).startswith("portugu") else "en"
            pastas.salvar_config(idioma=self.idioma_base)
            return self._guardar(pedido, t("idioma_ok", self.idioma_base))
        idioma = textos.detectar(pedido, self.idioma_base)
        self.ferramentas.idioma = idioma
        partes = passos.dividir(pedido, atalhos.normalizar(pedido))
        if partes:
            resposta = self._varios(partes, idioma)
            if resposta is not None:
                return self._guardar(pedido, resposta)
        resposta = self._por_regra(atalhos.resolver(pedido, idioma), pedido, idioma)
        return self._guardar(pedido, resposta if resposta is not None else self._pelo_modelo(pedido, idioma))

    def _por_regra(self, plano, pedido, idioma):
        """A resposta de um plano das regras, ou None quando é com o modelo."""
        if not plano:
            return None
        if "fala" in plano:
            return plano["fala"]
        if "pino" in plano:
            return self._pino(plano["pino"], idioma)
        if "comando" in plano:
            return self._comando(plano, idioma)
        if "pesquisa" in plano:
            return self._pesquisar(plano["pesquisa"], idioma)
        if "conversa" in plano:
            return self._conversar(pedido, idioma)
        return None

    def _varios(self, partes, idioma):
        """Um passo depois do outro. Para no primeiro que falha ou que a pessoa nega. None: o primeiro passo não é de regra."""
        falas, anterior = [], None
        self.lugar, self.ultimo_resultado, self.ultimo_comando, self.alvo = None, None, None, None
        for i, parte in enumerate(partes):
            n = atalhos.normalizar(parte)
            if i and passos.pede_contagem(n) and anterior is not None:
                saida = (self.ultimo_resultado or {}).get("stdout") or ""
                falas.append(t("r_sao", idioma, n=len([l for l in saida.splitlines() if l.strip()])))
                continue
            destino = passos.salvar_em(n) if i else None
            anterior = anterior or (self.ultimo_comando if (self.ultimo_resultado or {}).get("success") else None)
            if destino and not anterior:
                falas.append(t("nada_para_salvar", idioma))
                break
            if destino and anterior:
                comeco = n.rfind(destino)
                destino = parte[comeco:comeco + len(destino)] if comeco >= 0 else destino
                plano = {"comando": f"{anterior} > {operacoes._q(destino)}"}
            else:
                parte = passos.com_lugar(parte, self.lugar) if i else parte
                plano = atalhos.resolver(parte, idioma)
                if i == 0 and (not plano or "conversa" in plano):
                    return None
                if i and self.alvo and (not plano or "conversa" in plano or "pesquisa" in plano):
                    junto = atalhos.resolver(f"{parte} {'de' if idioma == 'pt' else 'of'} {self.alvo}", idioma)     # "mostra as 3 primeiras": do arquivo de antes
                    if junto and "comando" in junto:
                        plano = junto
            resposta = self._por_regra(plano, parte, idioma)
            if resposta is None:
                resposta = self._pelo_modelo(parte, idioma)
            falas.append(resposta)
            if plano and plano.get("alvo"):
                self.alvo = plano["alvo"]
            if plano and "comando" in plano:
                r = self.ultimo_resultado or {}
                if r.get("message") == NAO_APROVOU or not (r.get("success") or plano.get("resumo") in ("ocorrencias", "arquivos_com")):
                    break
                anterior = plano["comando"]
                if plano["comando"].startswith("mkdir -p ") and "&&" not in plano["comando"]:
                    self.lugar = shlex.split(plano["comando"])[-1]
        juntas = []
        for fala in falas:              # "Pronto." de cada passo vira um só
            if fala and (not juntas or fala != juntas[-1]):
                juntas.append(fala)
        return "\n".join(juntas)

    def _pelo_modelo(self, pedido, idioma):
        self.cerebro.preparar(self._sistema())
        mensagens = self._mensagens(pedido, idioma)
        usou, ultimo, vistas = 0, None, set()
        for _ in range(PASSOS):
            chamada, fala = self._falar_do_modelo(mensagens, lambda p: self.mostrar("pedaco", p))
            if not chamada:
                return self._conferir(fala, usou, ultimo, idioma)
            nome, argumentos = chamada
            if nome not in cerebro.FERRAMENTAS_DA_PLACA:          # o Gargantua do app conhece 19; tela, janela e mouse não existem aqui
                return t("tela", idioma)
            if nome == "search_web" and argumentos.get("query"):
                return self._pesquisar(argumentos["query"], idioma)
            if nome == "execute_terminal" and not argumentos.get("command"):
                return t("nao_fiz", idioma)
            if nome == "execute_terminal" and (faltando := _programa_que_falta(argumentos["command"])):      # "sudoulp": não vale pedir aprovação do que nem existe
                return t("falhou", idioma, erro=f"{faltando}: command not found")
            chave = (nome, tuple(sorted(argumentos.items())))
            if chave in vistas:         # modelo pequeno repete a mesma chamada: para aqui, com o que já tem
                break
            vistas.add(chave)
            ultimo = self._usar_ferramenta(nome, argumentos)
            usou += 1
            if ultimo.get("message") == NAO_APROVOU:     # a pessoa disse não: o modelo não tenta outro caminho
                return t("negado", idioma)
            if not ultimo.get("success"):                # um modelo deste tamanho não se recupera: só pediria mais aprovações à toa
                return self._conferir("", usou, ultimo, idioma)
            if nome == "execute_terminal" and ultimo.get("stdout", "").strip() and isinstance(self.cerebro, cerebro.CerebroPi):
                return ""                # a saída já apareceu; o comentário do 270M só inventava ("I have saved that..."). O da rede comenta.
            mensagens += [{"role": "assistant", "content": "", "chamada": chamada},
                          {"role": "tool", "name": nome, "content": contrato.resultado(ultimo)}]
        return self._conferir("", usou, ultimo, idioma)

    def _conferir(self, fala, usou, ultimo, idioma):
        """O modelo não pode dizer que fez o que não fez: aqui quem manda é o resultado da ferramenta."""
        if ultimo is not None and not ultimo.get("success"):
            erro = (ultimo.get("stderr") or ultimo.get("message") or "").strip().splitlines()
            if not fala or _DIZ_QUE_FEZ.search(fala):
                return t("falhou", idioma, erro=erro[-1] if erro else "?")
        if not usou and _DIZ_QUE_FEZ.search(fala):
            return t("nao_fiz", idioma)
        if fala:
            return fala
        return t("feito", idioma) if usou else t("sem_resposta", idioma)

    def _guardar(self, pedido, resposta):
        self.historico.append((pedido, resposta))
        return resposta
