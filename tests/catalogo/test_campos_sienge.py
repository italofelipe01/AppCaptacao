"""A declaracao dos campos do Sienge e o codigo dos executores precisam dizer a mesma coisa.

Se um executor passa a procurar outro filtro (ou deixa de procurar) sem atualizar
catalogo/campos_sienge.py, um filtro do cadastro seria descartado sem aviso: e o que estes
testes impedem (docs/specs/filtros-validados-no-sienge.md).
"""

import ast
import importlib
import unittest
from collections import Counter
from pathlib import Path

from app_captacao.automacao.relatorios import executores
from app_captacao.automacao.relatorios.registro import EXECUTORES_RELATORIO
from app_captacao.catalogo import campos_sienge, regras
from app_captacao.catalogo.campos_sienge import TELAS, associar

PASTA_EXECUTORES = Path(executores.__file__).parent


def _constantes(arvore):
    constantes = {}
    for no in arvore.body:
        if isinstance(no, ast.Assign) and len(no.targets) == 1 and isinstance(no.targets[0], ast.Name):
            try:
                constantes[no.targets[0].id] = ast.literal_eval(no.value)
            except ValueError:
                continue
    return constantes


def _argumentos(chamada, constantes):
    valores = []
    for argumento in chamada.args[1:]:
        if isinstance(argumento, ast.Starred) and isinstance(argumento.value, ast.Name):
            valores.extend(constantes[argumento.value.id])
        elif isinstance(argumento, ast.Name):
            valores.append(constantes[argumento.id])
        elif isinstance(argumento, ast.Constant):
            valores.append(argumento.value)
    return [str(valor).strip().lower() for valor in valores]


def _buscas_do_executor(executor):
    """Grupos de identificadores e trechos de nome que o codigo do executor procura no payload."""
    arvore = ast.parse((PASTA_EXECUTORES / f"{executor}.py").read_text(encoding="utf-8"))
    constantes = _constantes(arvore)
    por_campo, por_nome = Counter(), set()
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.args):
            continue
        if not (isinstance(no.args[0], ast.Name) and no.args[0].id == "filtros"):
            continue
        if no.func.id == "_obter_filtro_por_campo":
            por_campo[frozenset(_argumentos(no, constantes))] += 1
        elif no.func.id == "_obter_filtro_por_nome":
            por_nome.update(_argumentos(no, constantes))
    return por_campo, por_nome, constantes


class DeclaracaoIgualAoExecutorTests(unittest.TestCase):
    def test_todo_executor_registrado_tem_tela_declarada(self):
        self.assertEqual(set(TELAS), set(EXECUTORES_RELATORIO))

    def test_identificadores_declarados_sao_os_que_o_executor_procura(self):
        for executor, tela in TELAS.items():
            with self.subTest(executor=executor):
                por_campo, _, _ = _buscas_do_executor(executor)
                declarados = Counter(
                    frozenset(identificador.lower() for identificador in campo.identificadores)
                    for campo in tela.campos
                    if not campo.valor_fixo
                )
                self.assertEqual(por_campo, declarados)

    def test_trechos_de_nome_declarados_sao_os_que_o_executor_aceita(self):
        for executor, tela in TELAS.items():
            with self.subTest(executor=executor):
                _, por_nome, _ = _buscas_do_executor(executor)
                self.assertEqual(por_nome, {trecho.lower() for campo in tela.campos for trecho in campo.nomes})

    def test_campo_de_valor_fixo_e_um_campo_que_o_executor_usa(self):
        for executor, tela in TELAS.items():
            _, _, constantes = _buscas_do_executor(executor)
            for campo in tela.campos:
                if campo.valor_fixo:
                    with self.subTest(executor=executor, campo=campo.rotulo):
                        self.assertIn(campo.campo_tela, constantes.values())

    def test_filtros_fixos_do_catalogo_estao_declarados_com_o_mesmo_valor(self):
        for executor, fixos in regras.FILTROS_FIXOS_POR_EXECUTOR.items():
            for identificador, valor in fixos.items():
                campo = associar(executor, [{"campo_identificador": identificador}])[0]
                self.assertIsNotNone(campo)
                assert campo is not None
                self.assertEqual(campo.valor_fixo, valor)

    def test_regra_de_busca_declarada_e_a_do_executor(self):
        """Exata ou por sufixo: a declaracao casa exatamente os mesmos campos que o executor."""
        for executor, tela in TELAS.items():
            modulo = importlib.import_module(f"app_captacao.automacao.relatorios.executores.{executor}")
            for campo in tela.campos:
                if campo.valor_fixo:
                    continue
                for identificador in campo.identificadores:
                    for campo_cadastro in (identificador.upper(), f"filter.{identificador}", f"{identificador}x"):
                        filtro = {"campo_identificador": campo_cadastro, "nome": ""}
                        with self.subTest(executor=executor, campo=campo_cadastro):
                            no_executor = any(
                                modulo._obter_filtro_por_campo([filtro], ident) for ident in campo.identificadores
                            )
                            self.assertEqual(associar(executor, [filtro])[0] is not None, no_executor)


class AssociacaoTests(unittest.TestCase):
    def test_nome_so_vale_quando_nenhum_identificador_casa(self):
        pelo_nome = {"nome": "Posição em", "campo_identificador": "qualquer"}
        pelo_campo = {"nome": "Data", "campo_identificador": "filter.dtHistorica"}
        sem_campo, posicao_em = associar("unidades", [pelo_nome, pelo_campo])
        self.assertIsNone(sem_campo)
        self.assertIsNotNone(posicao_em)
        assert posicao_em is not None
        self.assertEqual(posicao_em.rotulo, "Posição em")

    def test_nome_sem_acento_casa(self):
        campo = associar("extrato_cliente_historico", [{"nome": "POSICAO EM", "campo_identificador": ""}])[0]
        self.assertIsNotNone(campo)
        assert campo is not None
        self.assertEqual(campo.campo_tela, "dtHistorico")

    def test_primeiro_filtro_vence_e_o_repetido_fica_sem_campo(self):
        primeiro = {"nome": "Empresa", "campo_identificador": "cdEmpresaView"}
        repetido = {"nome": "Empresa 2", "campo_identificador": "filter.empresa.cdEmpresaView"}
        self.assertEqual([campo is not None for campo in associar("vendas", [primeiro, repetido])], [True, False])

    def test_executor_desconhecido_nao_associa(self):
        self.assertEqual(associar("", [{"campo_identificador": "cdEmpresaView"}]), [None])


class ObrigatoriedadeTests(unittest.TestCase):
    def _opcional(self, nome_relatorio, campo_identificador, nome=""):
        filtro = {"id": 1, "nome": nome, "campo_identificador": campo_identificador, "acao": "", "valor": ""}
        return regras.eh_filtro_opcional_relatorio({"nome": nome_relatorio, "filtros": [filtro]}, filtro)

    def test_empreendimento_do_unidades_e_obrigatorio_como_no_sienge(self):
        # Sem ele o Sienge recusa: "O campo 'Empreendimento' deve ser preenchido." (2026-10-20).
        self.assertFalse(self._opcional("Unidades", "cdEmpreendView"))

    def test_posicao_em_tem_padrao_na_tela_e_pode_ficar_vazia(self):
        self.assertTrue(self._opcional("Unidades", "filter.dtHistorica"))
        self.assertTrue(self._opcional("Extrato Cliente Historico", "x", nome="Posição em"))

    def test_campo_com_padrao_que_o_executor_sobrescreve_continua_obrigatorio(self):
        # O executor do Extrato digita o valor vazio por cima do padrao: o app nao pode deixar vazio.
        self.assertFalse(self._opcional("Extrato Cliente Historico", "filter.dtCorrecao"))

    def test_opcionais_que_ja_existiam_continuam_opcionais(self):
        self.assertTrue(self._opcional("Titulos Quitados", "centroCusto.cdEmpreendView"))
        self.assertTrue(self._opcional("Relatório de Reparcelamento", "entity.empreend.cdEmpreendView"))
        self.assertTrue(self._opcional("Relatório de Preço Total de Vendas", "filter.empreend.cdEmpreendView"))

    def test_campo_sem_declaracao_continua_obrigatorio(self):
        self.assertFalse(self._opcional("Vendas", "campo.que.nao.existe"))

    def test_opcional_no_app_segue_tela_e_executor(self):
        campo = campos_sienge.CampoSienge("X", "x", campos_sienge.DATA, obrigatorio=True, aceita_vazio=True)
        self.assertFalse(campo.opcional_no_app)
        self.assertTrue(campos_sienge.CampoSienge("X", "x", campos_sienge.DATA, aceita_vazio=True).opcional_no_app)
        self.assertFalse(campos_sienge.CampoSienge("X", "x", campos_sienge.DATA).opcional_no_app)


if __name__ == "__main__":
    unittest.main()
