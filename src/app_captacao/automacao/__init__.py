"""Automacao do Sienge via Selenium: navegador, login, executores dedicados e downloads.

Ponto de entrada publico: executar_relatorio e executar_relatorios_em_sequencia.
"""

from app_captacao.automacao.execucao import executar_relatorio, executar_relatorios_em_sequencia

__all__ = ["executar_relatorio", "executar_relatorios_em_sequencia"]
