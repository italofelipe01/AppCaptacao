import ast
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app_captacao.automacao import campos
from app_captacao.automacao.relatorios import executores
from app_captacao.automacao.relatorios.executores import analitico_propriedade, extrato_cliente_historico

PASTA_EXECUTORES = Path(executores.__file__).parent


def _blocos(arvore):
    """Listas de comandos (corpo de funcao, laco, if, try...) da arvore."""
    for no in ast.walk(arvore):
        for campo in ("body", "orelse", "finalbody"):
            bloco = getattr(no, campo, None)
            if isinstance(bloco, list) and bloco and isinstance(bloco[0], ast.stmt):
                yield bloco


def _chama(comando, nome):
    return any(isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == nome for no in ast.walk(comando))


class JanelaDoRelatorioTests(unittest.TestCase):
    """A janela "please_wait_frame" do Sienge pede o arquivo: fechada antes, o download nao comeca.

    Execucao real de 2026-10-16: o Extrato demorou mais que os 5 s fixos, a janela foi fechada e a
    automacao esperou 600 s por um arquivo que nunca veio.
    """

    def test_nenhum_executor_fecha_a_janela_antes_de_esperar_o_arquivo(self):
        conferidos, fora_de_ordem = 0, []
        for modulo in sorted(PASTA_EXECUTORES.glob("*.py")):
            arvore = ast.parse(modulo.read_text(encoding="utf-8"))
            for bloco in _blocos(arvore):
                fechar = [i for i, c in enumerate(bloco) if _chama(c, "_fechar_janelas_extras") and not _chama(c, "renomear_download")]
                esperar = [i for i, c in enumerate(bloco) if _chama(c, "renomear_download") and not _chama(c, "_fechar_janelas_extras")]
                if fechar and esperar:
                    conferidos += 1
                    if min(fechar) < max(esperar):
                        fora_de_ordem.append(f"{modulo.name}:{bloco[min(fechar)].lineno}")
        self.assertEqual(fora_de_ordem, [])
        self.assertGreaterEqual(conferidos, 15, "o teste deixou de encontrar os executores que baixam arquivo")

    def test_extrato_espera_cada_arquivo_antes_de_fechar_a_janela(self):
        eventos = []

        class _Acoes:
            def __init__(self, _driver):
                pass

            def send_keys(self, *_teclas):
                return self

            def perform(self):
                eventos.append("enter")

        contexto = {
            "logger": Mock(),
            "normalizar_valor": lambda valor: valor,
            "default_report_wait": 5,
            "marcar_inicio_download": lambda: {"inicio_ns": 0, "arquivos_antes": {}},
            "renomear_download": lambda _config, empresa, _inicio: eventos.append(f"arquivo {empresa}"),
        }
        relatorio = {"nome": "Extrato Cliente Historico", "filtros": [
            {"campo_identificador": "filter.empresa.cdEmpresaView", "valor": "242,101"},
            {"campo_identificador": "filter.empreend.cdEmpreendView", "valor": "1002,1330"},
        ]}
        with patch.object(extrato_cliente_historico, "_preencher_campo_legado"), patch.object(
            extrato_cliente_historico, "ActionChains", _Acoes
        ), patch.object(extrato_cliente_historico.time, "sleep"), patch.object(
            extrato_cliente_historico, "_fechar_janelas_extras", lambda _driver: eventos.append("fechar janela")
        ):
            extrato_cliente_historico.executar(object(), object(), relatorio, contexto)

        self.assertEqual(eventos, ["enter", "arquivo 242", "fechar janela", "enter", "arquivo 101", "fechar janela"])


class _AcoesFalsas:
    eventos: list

    def __init__(self, _driver):
        pass

    def send_keys(self, *_teclas):
        return self

    def perform(self):
        self.eventos.append("enter")


class PosicaoEmDoExtratoTests(unittest.TestCase):
    """O Extrato (page/3012) tem "Posição em*" (name dtHistorico); antes o filtro era descartado."""

    def _executar(self, *filtros_extras, tela_aceita=True):
        eventos = []
        _AcoesFalsas.eventos = eventos
        tela = {"dtHistorico": "20/10/2026"}

        def preencher(_driver, _wait, identificador, valor, _by, _logger):
            eventos.append(f"{identificador}={valor}")
            if identificador != "dtHistorico" or tela_aceita:
                tela[identificador] = valor

        def confirmar(_driver, _wait, identificador, valor, _by, rotulo):
            if tela.get(identificador) != valor:
                raise ValueError(f"{rotulo} ficou com {tela.get(identificador)}")
            eventos.append(f"confirmado {identificador}")

        contexto = {
            "logger": Mock(),
            "normalizar_valor": campos.normalizar_valor_automacao,
            "default_report_wait": 5,
            "marcar_inicio_download": lambda: None,
            "renomear_download": lambda _config, empresa, _inicio: eventos.append(f"arquivo {empresa}"),
        }
        relatorio = {"nome": "Extrato Cliente Historico", "filtros": [
            {"campo_identificador": "filter.empresa.cdEmpresaView", "valor": "242"},
            {"campo_identificador": "filter.empreend.cdEmpreendView", "valor": "1002"},
            *filtros_extras,
        ]}
        with patch.object(extrato_cliente_historico, "_preencher_campo_legado", preencher), patch.object(
            extrato_cliente_historico, "_confirmar_valor_legado", confirmar
        ), patch.object(extrato_cliente_historico, "ActionChains", _AcoesFalsas), patch.object(
            extrato_cliente_historico.time, "sleep"
        ), patch.object(extrato_cliente_historico, "_fechar_janelas_extras"):
            extrato_cliente_historico.executar(object(), object(), relatorio, contexto)
        return eventos

    def test_posicao_em_pelo_nome_vai_para_a_tela_antes_do_enter(self):
        eventos = self._executar({"nome": "Posição em", "campo_identificador": "x", "valor": "2026-09-30", "tipo_campo_valor": "DATE"})
        self.assertEqual(
            eventos[:3],
            ["dtHistorico=30/09/2026", "confirmado dtHistorico", "filter.empresa.cdEmpresaView=242"],
        )
        self.assertLess(eventos.index("confirmado dtHistorico"), eventos.index("enter"))

    def test_data_que_nao_fica_na_tela_falha_antes_de_baixar(self):
        with self.assertRaisesRegex(ValueError, "Posicao em ficou com 20/10/2026"):
            self._executar({"campo_identificador": "dtHistorico", "valor": "2026-09-30"}, tela_aceita=False)

    def test_sem_posicao_em_o_fluxo_nao_muda(self):
        eventos = self._executar()
        self.assertFalse([evento for evento in eventos if "dtHistorico" in evento])
        self.assertEqual(eventos[-2:], ["enter", "arquivo 242"])


class CorrecaoAteDoAnaliticoTests(unittest.TestCase):
    """O Analitico (page/473) tem "Correção até*" como o sintetico; antes o filtro era descartado."""

    def _executar(self, *filtros):
        preenchidos = []
        contexto = {
            "logger": Mock(),
            "normalizar_valor": campos.normalizar_valor_automacao,
            "default_report_wait": 5,
            "marcar_inicio_download": lambda: None,
            "renomear_download": lambda *_args: None,
        }
        relatorio = {"nome": "Analitico de Apropriacoes", "filtros": list(filtros)}
        with patch.object(analitico_propriedade, "_selecionar_select"), patch.object(
            analitico_propriedade, "_marcar_radio"
        ), patch.object(
            analitico_propriedade,
            "_preencher_campo",
            lambda _driver, _wait, identificadores, valor, _logger: preenchidos.append((identificadores[0], valor)),
        ), patch.object(analitico_propriedade, "_clicar_botao_visualizar"), patch.object(
            analitico_propriedade.time, "sleep"
        ), patch.object(analitico_propriedade, "_fechar_janelas_extras"):
            analitico_propriedade.executar(object(), object(), relatorio, contexto)
        return preenchidos

    def test_correcao_ate_e_preenchida(self):
        preenchidos = self._executar(
            {"campo_identificador": "analise.dtCorrecaoAte", "valor": "2026-09-30", "tipo_campo_valor": "DATE"},
            {"campo_identificador": "analise.empresa.cdEmpresaView", "valor": "242"},
        )
        self.assertEqual(preenchidos[0], ("analise.dtCorrecaoAte", "30/09/2026"))
        self.assertIn(("analise.empresa.cdEmpresaView", "242"), preenchidos)

    def test_sem_correcao_ate_nada_muda(self):
        preenchidos = self._executar({"campo_identificador": "analise.empresa.cdEmpresaView", "valor": "242"})
        self.assertEqual(preenchidos, [("analise.empresa.cdEmpresaView", "242")])


class ExtratoClienteHistoricoTests(unittest.TestCase):
    def test_empreendimento_unico_vale_para_todas_as_empresas(self):
        self.assertEqual(extrato_cliente_historico._calcular_pares_empresa_empreendimento(["1", "2", "3"], ["10"]), 3)

    def test_listas_de_tamanhos_diferentes_sao_erro_e_nao_perdem_empresa(self):
        with self.assertRaises(ValueError):
            extrato_cliente_historico._calcular_pares_empresa_empreendimento(["1", "2", "3"], ["10", "20"])

    def test_sem_empreendimento_o_erro_e_claro(self):
        with self.assertRaisesRegex(ValueError, "empresa e empreendimento"):
            extrato_cliente_historico._calcular_pares_empresa_empreendimento(["1"], [])


if __name__ == "__main__":
    unittest.main()
