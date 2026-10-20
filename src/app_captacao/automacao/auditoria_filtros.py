"""Auditoria dos filtros contra a tela do Sienge (docs/specs/filtros-validados-no-sienge.md, regra 6).

Abre cada relatorio no Edge da automacao, le o formulario de filtros e cruza com as declaracoes
de catalogo/campos_sienge.py e, quando o banco responde, com o cadastro. So le: nao gera
relatorio nem altera o cadastro. Divergencias:

- (a) filtro do cadastro sem campo correspondente na tela;
- (b) campo declarado que nao existe na tela;
- (c) campo obrigatorio na tela, sem valor padrao, que nenhum filtro preenche;
- (d) obrigatoriedade ou valor padrao da declaracao diferente da tela.

Uso: python tools/auditar_filtros_sienge.py --email voce@empresa.com.br [--sem-banco]
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from app_captacao.catalogo import regras
from app_captacao.catalogo.campos_sienge import TELAS, CampoSienge, associar, normalizar
from app_captacao.core.config.environment import PROJECT_ROOT

logger = logging.getLogger(__name__)

SAIDA_PADRAO = PROJECT_ROOT / "docs" / "auditoria-filtros-sienge.md"
SEM_VALOR_NO_SELECT = {"", "-- selecione --"}

LER_FORMULARIO_JS = r"""
function rotuloLegado(el) {
  let no = el;
  while (no && no !== document.body) {
    if (no.tagName === 'TR') {
      for (const c of Array.from(no.children)) {
        if (c.contains(el)) break;
        const t = c.innerText.replace(/\s+/g, ' ').trim();
        if (t.endsWith(':')) return t;
      }
    }
    no = no.parentElement;
  }
  return '';
}
function rotuloMui(el) {
  const fc = el.closest('.MuiFormControl-root, .MuiTextField-root, .MuiAutocomplete-root');
  const l = fc && fc.querySelector('label');
  return l ? l.innerText.replace(/\s+/g, ' ').trim() : '';
}
const campos = [];
document.querySelectorAll('input,select,textarea').forEach(el => {
  if (['hidden', 'button', 'submit'].includes(el.type)) return;
  let rotulo = '';
  if (el.id) {
    const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
    if (l) rotulo = l.innerText.replace(/\s+/g, ' ').trim();
  }
  rotulo = rotuloLegado(el) || rotuloMui(el) || rotulo;
  const valor = el.tagName === 'SELECT' ? ((el.options[el.selectedIndex] || {}).text || '')
    : (['checkbox', 'radio'].includes(el.type) ? (el.checked ? 'marcado' : '') : el.value);
  campos.push({
    id: el.id || '', name: el.name || '', rotulo, tipo: el.type || el.tagName.toLowerCase(),
    valor: (valor || '').trim(), visivel: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
    obrigatorio: rotulo.includes('*') || el.getAttribute('obrigatorio') === 'true',
  });
});
return campos;
"""


@dataclass(frozen=True)
class CampoNaTela:
    id: str
    name: str
    rotulo: str
    tipo: str
    valor: str
    visivel: bool
    obrigatorio: bool

    @property
    def rotulo_limpo(self) -> str:
        return normalizar(self.rotulo.replace("*", "").replace(":", " "))

    @property
    def tem_padrao(self) -> bool:
        return normalizar(self.valor) not in SEM_VALOR_NO_SELECT


@dataclass(frozen=True)
class Divergencia:
    tipo: str
    descricao: str


@dataclass
class ResultadoTela:
    executor: str
    url: str
    lida: bool
    motivo: str = ""
    campos: list[tuple[CampoSienge, CampoNaTela | None]] = field(default_factory=list)
    divergencias: list[Divergencia] = field(default_factory=list)


def localizar(campo: CampoSienge, campos_tela: list[CampoNaTela]) -> CampoNaTela | None:
    """Campo da tela pelo id/name; na tela MUI (id muda a cada carga), pelo rótulo."""
    for campo_tela in campos_tela:
        if campo.campo_tela in (campo_tela.id, campo_tela.name):
            return campo_tela
    alvo = normalizar(campo.campo_tela)
    return next((campo_tela for campo_tela in campos_tela if campo_tela.rotulo_limpo == alvo), None)


def auditar_tela(executor: str, campos_tela: list[CampoNaTela], filtros_cadastro: list[dict] | None = None) -> ResultadoTela:
    tela = TELAS[executor]
    resultado = ResultadoTela(executor, tela.rota, lida=True)
    rotulos_declarados = set()
    for campo in tela.campos:
        achado = localizar(campo, campos_tela)
        resultado.campos.append((campo, achado))
        if achado is None:
            resultado.divergencias.append(
                Divergencia("b", f"'{campo.rotulo}' ({campo.campo_tela}) está declarado, mas não existe na tela.")
            )
            continue
        rotulos_declarados.add(achado.rotulo_limpo)
        if achado.obrigatorio != campo.obrigatorio:
            resultado.divergencias.append(
                Divergencia(
                    "d",
                    f"'{campo.rotulo}': obrigatório na tela = {_sim_nao(achado.obrigatorio)}, "
                    f"na declaração = {_sim_nao(campo.obrigatorio)}.",
                )
            )
        if campo.obrigatorio and not campo.valor_fixo and bool(campo.padrao_na_tela) != achado.tem_padrao:
            resultado.divergencias.append(
                Divergencia(
                    "d",
                    f"'{campo.rotulo}': a tela {'traz' if achado.tem_padrao else 'não traz'} valor padrão "
                    f"('{achado.valor}'), a declaração diz '{campo.padrao_na_tela or 'sem padrão'}'.",
                )
            )

    for campo_tela in campos_tela:
        if (
            campo_tela.visivel
            and campo_tela.obrigatorio
            and not campo_tela.tem_padrao
            and campo_tela.rotulo_limpo not in rotulos_declarados
        ):
            resultado.divergencias.append(
                Divergencia("c", f"'{campo_tela.rotulo}' é obrigatório na tela, não tem padrão e nenhum filtro o preenche.")
            )
            rotulos_declarados.add(campo_tela.rotulo_limpo)

    if filtros_cadastro is not None:
        for filtro, campo in zip(filtros_cadastro, associar(executor, filtros_cadastro)):
            if campo is None and regras.acao_exige_valor(filtro.get("acao")) and not filtro.get("automatico"):
                resultado.divergencias.append(
                    Divergencia(
                        "a",
                        f"Filtro do cadastro '{filtro.get('nome', '')}' ({filtro.get('campo_identificador', '')}) "
                        "não tem campo correspondente na tela.",
                    )
                )
    return resultado


def _sim_nao(valor: bool) -> str:
    return "sim" if valor else "não"


def ler_formulario(driver) -> list[CampoNaTela]:
    """Campos do formulário: dentro do iframe da página antiga ou direto na página MUI."""
    driver.switch_to.default_content()
    iframes = [frame for frame in driver.find_elements(By.TAG_NAME, "iframe") if frame.get_attribute("id") == "iFramePage"]
    try:
        if iframes:
            driver.switch_to.frame(iframes[0])
        brutos = driver.execute_script(LER_FORMULARIO_JS) or []
    finally:
        driver.switch_to.default_content()
    return [CampoNaTela(**campo) for campo in brutos]


def _aguardar_formulario(driver, limite: float = 60) -> list[CampoNaTela]:
    prazo = time.time() + limite
    campos: list[CampoNaTela] = []
    while time.time() < prazo:
        try:
            campos = ler_formulario(driver)
        except Exception:  # pagina ainda montando o iframe
            campos = []
        if len(campos) > 2:
            time.sleep(3)
            return ler_formulario(driver)
        time.sleep(2)
    return campos


def _preparacoes(driver, wait) -> dict[str, Callable[[], None]]:
    """O que o executor faz antes de preencher e muda os campos da tela."""
    from app_captacao.automacao.relatorios.executores import extrato_saldo_devedor_presente, quadro_espelho, unidades, vendas

    return {
        "unidades": lambda: unidades._selecionar_select(driver, wait, unidades.SELECAO_CAMPO, unidades.SELECAO_VALOR, logger),
        "vendas": lambda: vendas._selecionar_select(driver, wait, vendas.SELECAO_CAMPO, vendas.SELECAO_VALOR, logger),
        "quadro_espelho": lambda: quadro_espelho._abrir_aba_lista(driver, logger),
        "extrato_saldo_devedor_presente": lambda: driver.find_element(
            By.XPATH, extrato_saldo_devedor_presente.XPATH_ABRIR_FILTROS_DATAS
        ).click(),
    }


def _cadastro() -> tuple[dict[str, tuple[str, list[dict]]], str]:
    """Relatorios ativos do banco por executor: (url, filtros). Sem banco: vazio e o motivo."""
    try:
        from app_captacao.catalogo import relatorios as relatorios_repo

        por_executor: dict[str, tuple[str, list[dict]]] = {}
        for resumo in relatorios_repo.load_relatorios_disponiveis():
            relatorio = relatorios_repo.buscar_relatorio_com_filtros(resumo["id"]) or {}
            executor = regras.executor_do_relatorio(relatorio)
            if executor:
                por_executor[executor] = (relatorio.get("url", ""), relatorio.get("filtros", []))
        return por_executor, ""
    except Exception as exc:  # banco fora do ar ou sem permissao: audita so a tela
        # O texto do driver traz usuario e servidor: fica so no log, o relatorio leva o tipo.
        logger.warning("Cadastro nao lido; a auditoria segue so com a tela.", exc_info=True)
        return {}, f"banco indisponível: {type(exc).__name__}"


def auditar(driver, wait, base_url: str, cadastro: dict[str, tuple[str, list[dict]]] | None) -> list[ResultadoTela]:
    preparacoes = _preparacoes(driver, wait)
    resultados = []
    for executor, tela in TELAS.items():
        url_cadastro, filtros = (cadastro or {}).get(executor, ("", None))
        url = url_cadastro or (f"{base_url.rstrip('/')}/8/index.html#{tela.rota}" if tela.rota else "")
        if not url:
            resultados.append(ResultadoTela(executor, "", lida=False, motivo="tela não localizada (sem URL no código e no cadastro)"))
            continue
        try:
            driver.get(url)
            _aguardar_formulario(driver)
            if executor in preparacoes:
                preparacoes[executor]()
                time.sleep(4)
            resultado = auditar_tela(executor, _aguardar_formulario(driver, limite=20), filtros)
            resultado.url = url
            resultados.append(resultado)
            logger.info("Auditoria %s: %s divergencia(s).", executor, len(resultado.divergencias))
        except Exception as exc:
            logger.exception("Auditoria %s: a tela nao foi lida.", executor)
            resultados.append(ResultadoTela(executor, url, lida=False, motivo=f"tela não lida: {type(exc).__name__}"))
            driver.switch_to.default_content()
    return resultados


def gerar_markdown(resultados: list[ResultadoTela], motivo_sem_cadastro: str, quando: datetime) -> str:
    cadastro = "lido do banco" if not motivo_sem_cadastro else f"não lido ({motivo_sem_cadastro}); divergência (a) não avaliada"
    linhas = [
        "# Auditoria dos filtros no Sienge",
        "",
        f"Gerada em {quando:%d/%m/%Y %H:%M} por `tools/auditar_filtros_sienge.py`. Cadastro: {cadastro}.",
        "",
        "Divergências: (a) filtro do cadastro sem campo na tela; (b) campo declarado que não existe na",
        "tela; (c) campo obrigatório da tela, sem padrão, que nenhum filtro preenche; (d) obrigatoriedade",
        "ou padrão da declaração diferente da tela. Regras em",
        "[specs/filtros-validados-no-sienge.md](specs/filtros-validados-no-sienge.md).",
        "",
        "## Resumo",
        "",
        "| Executor | Tela | Campos declarados | Divergências |",
        "| --- | --- | --- | --- |",
    ]
    for resultado in resultados:
        situacao = str(len(resultado.divergencias)) if resultado.lida else f"— ({resultado.motivo})"
        rota = resultado.url.split("#", 1)[-1] if resultado.url else "—"
        linhas.append(f"| `{resultado.executor}` | `{rota}` | {len(TELAS[resultado.executor].campos)} | {situacao} |")

    for resultado in resultados:
        linhas += ["", f"## {resultado.executor}", ""]
        if not resultado.lida:
            linhas.append(f"Não auditado: {resultado.motivo}.")
            continue
        linhas += [
            "| Campo no Sienge | id/name | Tipo | Obrigatório na tela | Padrão da tela | Opcional no app | Situação |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for campo, achado in resultado.campos:
            if achado is None:
                linhas.append(f"| {campo.rotulo} | `{campo.campo_tela}` | {campo.tipo} | — | — | — | não existe na tela |")
                continue
            padrao = campo.valor_fixo and f"fixo: {campo.valor_fixo}" or campo.padrao_na_tela or "—"
            linhas.append(
                f"| {campo.rotulo} | `{campo.campo_tela}` | {campo.tipo} | {_sim_nao(achado.obrigatorio)} | "
                f"{padrao} | {_sim_nao(campo.opcional_no_app)} | ok |"
            )
        if resultado.divergencias:
            linhas += ["", "Divergências:", ""]
            linhas += [f"- ({divergencia.tipo}) {divergencia.descricao}" for divergencia in resultado.divergencias]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audita os filtros do app contra a tela de cada relatório no Sienge.")
    parser.add_argument("--email", required=True, help="Conta do Sienge (a mesma da tela de execução).")
    parser.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    parser.add_argument("--sem-banco", action="store_true", help="Não tenta ler o cadastro.")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stdout)

    from app_captacao.automacao import login, navegador
    from app_captacao.automacao.config import DEFAULT_TIMEOUT, LOGIN_URL

    cadastro, motivo = ({}, "--sem-banco") if args.sem_banco else _cadastro()
    senha = os.getenv("SIENGE_SENHA") or getpass.getpass("Senha do Sienge (vazio: login na janela do Edge): ")
    driver = navegador.criar_driver()
    wait = WebDriverWait(driver, DEFAULT_TIMEOUT)
    try:
        login.fazer_login(driver, wait, args.email, senha)
        navegador.definir_janela_principal(driver)
        resultados = auditar(driver, wait, LOGIN_URL, cadastro or None)
    finally:
        navegador.encerrar_driver(driver)
    args.saida.write_text(gerar_markdown(resultados, motivo, datetime.now()), encoding="utf-8")
    total = sum(len(resultado.divergencias) for resultado in resultados)
    print(f"Auditoria gravada em {args.saida}: {total} divergência(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
