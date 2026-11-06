"""O laço do assistente: atalhos primeiro, depois o modelo com as ferramentas, até ele responder."""
import re
import urllib.parse

from . import atalhos, contrato, gpio, memoria, textos
from .ferramentas import NAO_APROVOU, Ferramentas
from .textos import t

PASSOS = 5
_DIZ_QUE_FEZ = re.compile(r"\b(criei|criada|criado|feito|pronto|apaguei|apagado|salvei|salvo|movi|movido|instalei|instalado|renomeei|escrevi|"
                          r"done|created|deleted|saved|moved|installed|renamed|wrote|finished|success)\b", re.IGNORECASE)


class Agente:
    def __init__(self, motor, aprovar, mostrar=None, auto=False):
        """aprovar(descricao, nivel) -> bool. mostrar(tipo, texto): 'comando', 'saida', 'pedaco' (a fala saindo aos poucos)."""
        self.motor = motor
        self.aprovar = aprovar
        self.mostrar = mostrar or (lambda tipo, texto: None)
        self.ferramentas = Ferramentas(aprovar, auto)
        self.historico = []
        self.idioma_base = textos.idioma_padrao()
        self.ultimo_nivel = None

    def _sistema(self):
        return contrato.sistema("", memoria.ler(), self.idioma_base)

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

    def _comando(self, comando, idioma):
        resultado = self._usar_ferramenta("execute_terminal", {"command": comando})
        if resultado.get("message") == NAO_APROVOU:
            return t("negado", idioma)
        if not resultado.get("success"):
            erro = (resultado.get("stderr") or resultado.get("message") or "?").strip().splitlines()
            return t("falhou", idioma, erro=erro[-1])
        return "" if resultado.get("stdout", "").strip() else t("feito", idioma)     # a saída já apareceu

    def _usar_ferramenta(self, nome, argumentos):
        self.mostrar("comando", argumentos.get("command") or argumentos.get("query") or argumentos.get("fact") or nome)
        resultado = self.ferramentas.chamar(nome, argumentos)
        saida = (resultado.get("stdout") or "") + (resultado.get("stderr") or "")
        if saida.strip():
            self.mostrar("saida", saida.strip())
        return resultado

    def _falar_do_modelo(self, mensagens, ao_pedaco=None):
        """(chamada, fala) da próxima jogada do modelo. A fala sai aos poucos; a chamada não aparece."""
        estado = {"chamada": False}

        def pedaco(texto):
            if texto.startswith("<start_function_call>"):
                estado["chamada"] = True
            if not estado["chamada"] and not texto.startswith("<") and ao_pedaco:
                ao_pedaco(texto)
        return contrato.ler_resposta(self.motor.completar(contrato.renderizar(mensagens), pedaco))

    def _pesquisar(self, consulta, idioma):
        """A resposta sai dos resultados, sem passar pelo modelo: com 270M ele diz que abriu o navegador em vez de ler (medido em 06/11)."""
        resultado = self._usar_ferramenta("search_web", {"query": consulta})
        if not resultado.get("success"):
            return t("sem_busca", idioma)
        site = lambda r: urllib.parse.urlsplit(r["url"]).hostname or r["url"]   # noqa: E731
        primeiro, *resto = resultado["resultados"]
        linhas = [t("de_onde", idioma, site=site(primeiro), trecho=primeiro["trecho"] or primeiro["titulo"])]
        linhas += [t("tambem", idioma, site=site(r), titulo=r["titulo"]) for r in resto[:2]]
        return "\n".join(linhas)

    def responder(self, pedido):
        """A resposta final, em texto. O que mudou na placa já aconteceu quando isto volta."""
        pedido = pedido.strip()
        idioma = textos.detectar(pedido, self.idioma_base)
        self.ferramentas.idioma = idioma
        plano = atalhos.resolver(pedido, idioma)
        if plano and "fala" in plano:
            return self._guardar(pedido, plano["fala"])
        if plano and "pino" in plano:
            return self._guardar(pedido, self._pino(plano["pino"], idioma))
        if plano and "comando" in plano:
            return self._guardar(pedido, self._comando(plano["comando"], idioma))
        if plano and "pesquisa" in plano:
            return self._guardar(pedido, self._pesquisar(plano["pesquisa"], idioma))
        self.motor.ligar()
        self.motor.preparar_prefixo(contrato.prefixo(self._sistema()))
        mensagens = self._mensagens(pedido, idioma)
        usou, ultimo, vistas = 0, None, set()
        for _ in range(PASSOS):
            chamada, fala = self._falar_do_modelo(mensagens, lambda p: self.mostrar("pedaco", p))
            if not chamada:
                return self._guardar(pedido, self._conferir(fala, usou, ultimo, idioma))
            nome, argumentos = chamada
            if nome == "search_web" and argumentos.get("query"):
                return self._guardar(pedido, self._pesquisar(argumentos["query"], idioma))
            chave = (nome, tuple(sorted(argumentos.items())))
            if chave in vistas:         # modelo pequeno repete a mesma chamada: para aqui, com o que já tem
                break
            vistas.add(chave)
            ultimo = self._usar_ferramenta(nome, argumentos)
            usou += 1
            if ultimo.get("message") == NAO_APROVOU:     # a pessoa disse não: o modelo não tenta outro caminho
                return self._guardar(pedido, t("negado", idioma))
            mensagens += [{"role": "assistant", "content": "", "chamada": chamada},
                          {"role": "tool", "name": nome, "content": contrato.resultado(ultimo)}]
        return self._guardar(pedido, self._conferir("", usou, ultimo, idioma))

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
