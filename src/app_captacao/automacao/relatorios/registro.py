from app_captacao.automacao.relatorios.executores.extrato_cliente_historico import (
    executar as executar_extrato_cliente_historico,
)
from app_captacao.automacao.relatorios.executores.analise_resultado_sintetico import (
    executar as executar_analise_resultado_sintetico,
)
from app_captacao.automacao.relatorios.executores.analitico_propriedade import (
    executar as executar_analitico_propriedade,
)
from app_captacao.automacao.relatorios.executores.contas_recebidas import (
    executar as executar_contas_recebidas,
)
from app_captacao.automacao.relatorios.executores.contas_a_receber import (
    executar as executar_contas_a_receber,
)
from app_captacao.automacao.relatorios.executores.extrato_conciliado import (
    executar as executar_extrato_conciliado,
)
from app_captacao.automacao.relatorios.executores.extrato_saldo_devedor_presente import (
    executar as executar_extrato_saldo_devedor_presente,
)
from app_captacao.automacao.relatorios.executores.mapa_venda import (
    executar as executar_mapa_venda,
)
from app_captacao.automacao.relatorios.executores.posicao_saldos import (
    executar as executar_posicao_saldos,
)
from app_captacao.automacao.relatorios.executores.preco_total_vendas import (
    executar as executar_preco_total_vendas,
)
from app_captacao.automacao.relatorios.executores.quadro_espelho import (
    executar as executar_quadro_espelho,
)
from app_captacao.automacao.relatorios.executores.relatorio_reparcelamento import (
    executar as executar_relatorio_reparcelamento,
)
from app_captacao.automacao.relatorios.executores.retencao import (
    executar as executar_retencao,
)
from app_captacao.automacao.relatorios.executores.titulos_quitados import (
    executar as executar_titulos_quitados,
)
from app_captacao.automacao.relatorios.executores.titulos_distratados import (
    executar as executar_titulos_distratados,
)
from app_captacao.automacao.relatorios.executores.unidades import (
    executar as executar_unidades,
)
from app_captacao.automacao.relatorios.executores.vendas import (
    executar as executar_vendas,
)


EXECUTORES_RELATORIO = {
    "extrato_cliente_historico": executar_extrato_cliente_historico,
    "analise_resultado_sintetico": executar_analise_resultado_sintetico,
    "analitico_propriedade": executar_analitico_propriedade,
    "contas_a_receber": executar_contas_a_receber,
    "contas_recebidas": executar_contas_recebidas,
    "extrato_conciliado": executar_extrato_conciliado,
    "extrato_saldo_devedor_presente": executar_extrato_saldo_devedor_presente,
    "mapa_venda": executar_mapa_venda,
    "posicao_saldos": executar_posicao_saldos,
    "preco_total_vendas": executar_preco_total_vendas,
    "quadro_espelho": executar_quadro_espelho,
    "relatorio_reparcelamento": executar_relatorio_reparcelamento,
    "retencao": executar_retencao,
    "titulos_quitados": executar_titulos_quitados,
    "titulos_distratados": executar_titulos_distratados,
    "unidades": executar_unidades,
    "vendas": executar_vendas,
}


def obter_executor(executor_relatorio):
    return EXECUTORES_RELATORIO.get(str(executor_relatorio or "").strip().lower())
