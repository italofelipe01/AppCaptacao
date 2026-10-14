"""
Gerador de Manual de UtilizaÃ§Ã£o - AppCaptaÃ§Ã£o
==============================================

Script para gerar documentaÃ§Ã£o tÃ©cnica em formato DOCX.
"""

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


def criar_manual():
    """Gera o manual de utilizaÃ§Ã£o em formato DOCX."""
    doc = Document()
    titulo = doc.add_heading("MANUAL DE UTILIZACAO", 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save("Manual_AppCaptacao.docx")
