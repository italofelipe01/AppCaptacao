"""Consolidacao dos relatorios baixados: uma planilha plana por relatorio, conferida com o Sienge.

So depende de `core/`: recebe o executor e os caminhos dos arquivos, nunca o driver ou o job.
"""

from app_captacao.consolidacao.consolidador import (
    ResultadoConferencia,
    ResultadoConsolidacao,
    consolidar,
    formatar_valor,
    suporta,
)

__all__ = ["ResultadoConferencia", "ResultadoConsolidacao", "consolidar", "formatar_valor", "suporta"]
