"""
Gerador de Manual de Utilização - AppCaptação
==============================================

Script para gerar documentação técnica em formato DOCX.

Autor: Equipe de Desenvolvimento
Versão: 1.0.0
Data: Abril 2026
"""

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
import os


def criar_manual():
    """Gera o manual de utilização em formato DOCX."""
    
    # Criar documento
    doc = Document()
    
    # ============================================================
    # TÍTULO PRINCIPAL
    # ============================================================
    titulo = doc.add_heading('MANUAL DE UTILIZAÇÃO', 0)
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    subtitulo = doc.add_paragraph('AppCaptação - Sistema de Captação e Automação')
    subtitulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph('Versão 1.0.0 - Abril 2026')
    doc.add_paragraph('')
    
    # ============================================================
    # ÍNDICE
    # ============================================================
    doc.add_heading('Índice', 1)
    indice = doc.add_paragraph()
    indice.add_run('1. Introdução\n').bold = True
    indice.add_run('2. Requisitos do Sistema\n').bold = True
    indice.add_run('3. Instalação\n').bold = True
    indice.add_run('4. Configuração\n').bold = True
    indice.add_run('5. Interface do Usuário\n').bold = True
    indice.add_run('6. Funcionalidades\n').bold = True
    indice.add_run('7. Variáveis de Ambiente\n').bold = True
    indice.add_run('8. Solução de Problemas\n').bold = True
    
    doc.add_page_break()
    
    # ============================================================
    # 1. INTRODUÇÃO
    # ============================================================
    doc.add_heading('1. Introdução', 1)
    
    intro = doc.add_paragraph()
    intro.add_run('O AppCaptação é uma aplicação Flask desenvolvida para automatizar ')
    intro.add_run('a execução de relatórios no sistema Sienge. ').bold = True
    intro.add_run('\n\nA aplicação fornece:')
    
    itens_intro = doc.add_paragraph()
    itens_intro.add_run('• Interface web para gestão de usuários e relatórios\n')
    itens_intro.add_run('• Automação de navegação via Selenium WebDriver\n')
    itens_intro.add_run('• Execução agendada de relatórios\n')
    itens_intro.add_run('• Download automático de arquivos gerados\n')
    itens_intro.add_run('• Controle de acesso por perfis de usuário')
    
    doc.add_page_break()
    
    # ============================================================
    # 2. REQUISITOS DO SISTEMA
    # ============================================================
    doc.add_heading('2. Requisitos do Sistema', 1)
    
    req = doc.add_paragraph()
    req.add_run('Hardware:\n').bold = True
    req.add_run('• Processador: Dual Core ou superior\n')
    req.add_run('• Memória RAM: 4 GB ou superior\n')
    req.add_run('• Espaço em disco: 500 MB (para dependências)')
    
    doc.add_paragraph('')
    
    req2 = doc.add_paragraph()
    req2.add_run('Software:\n').bold = True
    req2.add_run('• Python 3.8 ou superior\n')
    req2.add_run('• Google Chrome (versão mais recente)\n')
    req2.add_run('• SQL Server (para banco de dados)\n')
    req2.add_run('• Windows 10/11 ou Linux')
    
    doc.add_page_break()
    
    # ============================================================
    # 3. INSTALAÇÃO
    # ============================================================
    doc.add_heading('3. Instalação', 1)
    
    inst = doc.add_paragraph()
    inst.add_run('3.1 Clone o repositório\n').bold = True
    inst.add_run('git clone <repositorio> AppCaptação\n')
    inst.add_run('cd AppCaptação')
    
    doc.add_paragraph('')
    
    inst2 = doc.add_paragraph()
    inst2.add_run('3.2 Crie o ambiente virtual\n').bold = True
    inst2.add_run('python -m venv venv\n')
    inst2.add_run('venv\\Scripts\\activate  # Windows\n')
    inst2.add_run('source venv/bin/activate  # Linux')
    
    doc.add_paragraph('')
    
    inst3 = doc.add_paragraph()
    inst3.add_run('3.3 Instale as dependências\n').bold = True
    inst3.add_run('pip install -r requirements.txt')
    
    doc.add_page_break()
    
    # ============================================================
    # 4. CONFIGURAÇÃO
    # ============================================================
    doc.add_heading('4. Configuração', 1)
    
    conf = doc.add_paragraph()
    conf.add_run('4.1 Arquivo .env\n').bold = True
    conf.add_run('Crie um arquivo .env na raiz do projeto com as seguintes variáveis:')
    
    # Tabela de configuração
    table = doc.add_table(rows=15, cols=2)
    table.style = 'Table Grid'
    
    # Cabeçalho
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = 'Variável'
    hdr_cells[1].text = 'Descrição'
    
    configuracoes = [
        ('APP_HOST', 'Endereço do servidor (padrão: 0.0.0.0 para acesso na rede)'),
        ('APP_PORT', 'Porta da aplicação (padrão: 4732)'),
        ('APP_DEBUG', 'Modo debug (true/false)'),
        ('FLASK_SECRET_KEY', 'Chave secreta do Flask'),
        ('DB_DRIVER', 'Driver ODBC (padrão: SQL Server)'),
        ('DB_HOST', 'Servidor do banco de dados'),
        ('DB_DATABASE', 'Nome do banco de dados'),
        ('DB_USER', 'Usuário do banco'),
        ('DB_PASSWORD', 'Senha do banco'),
        ('SIENGE_LOGIN_URL', 'URL do sistema Sienge'),
        ('SELENIUM_DEFAULT_TIMEOUT', 'Timeout Selenium (segundos)'),
        ('SELENIUM_DOWNLOAD_DIR', 'Pasta para downloads'),
    ]
    
    for i, (var, desc) in enumerate(configuracoes, 1):
        cells = table.rows[i].cells
        cells[0].text = var
        cells[1].text = desc
    
    doc.add_paragraph('')
    
    conf2 = doc.add_paragraph()
    conf2.add_run('4.2 Banco de Dados\n').bold = True
    conf2.add_run('Execute os scripts SQL para criar as tabelas necessárias:')
    
    doc.add_paragraph('• CapRecursoUsuario - Tabela de usuários')
    doc.add_paragraph('• CapRecursoRelatorio - Catálogo de relatórios')
    doc.add_paragraph('• CapRecursoFiltro - Filtros dos relatórios')
    doc.add_paragraph('• CapRecursoRelatorio_X_Operacao - Relação relatório-operação')
    
    doc.add_page_break()
    
    # ============================================================
    # 5. INTERFACE DO USUÁRIO
    # ============================================================
    doc.add_heading('5. Interface do Usuário', 1)
    
    interface = doc.add_paragraph()
    interface.add_run('A aplicação possui as seguintes telas:\n\n').bold = True
    interface.add_run('5.1 Login\n').bold = True
    interface.add_run('Página inicial de autenticação. O usuário deve inserir login e senha.\n\n')
    interface.add_run('5.2 Menu Principal\n').bold = True
    interface.add_run('Dashboard com acesso às funcionalidades conforme perfil.\n\n')
    interface.add_run('5.3 Acompanhamento\n').bold = True
    interface.add_run('Visualização do status de execuções em andamento.\n\n')
    interface.add_run('5.4 Usuários (Admin)\n').bold = True
    interface.add_run('Gerenciamento de usuários do sistema.\n\n')
    interface.add_run('5.5 Perfil (Admin)\n').bold = True
    interface.add_run('Configurações de perfil e preferências.')
    
    doc.add_page_break()
    
    # ============================================================
    # 6. FUNCIONALIDADES
    # ============================================================
    doc.add_heading('6. Funcionalidades', 1)
    
    func = doc.add_paragraph()
    func.add_run('6.1 Execução de Relatórios\n').bold = True
    func.add_run('A aplicação permite executar relatórios automaticamente no Sienge. ')
    func.add_run('O processo inclui:\n')
    
    doc.add_paragraph('1. Login automático no sistema Sienge')
    doc.add_paragraph('2. Navegação até o relatório desejado')
    doc.add_paragraph('3. Preenchimento de filtros')
    doc.add_paragraph('4. Execução do relatório')
    doc.add_paragraph('5. Download do arquivo gerado')
    
    doc.add_paragraph('')
    
    func2 = doc.add_paragraph()
    func2.add_run('6.2 Gestão de Usuários\n').bold = True
    func2.add_run('O administrador pode criar, editar e desativar usuários do sistema.')
    
    doc.add_paragraph('')
    
    func3 = doc.add_paragraph()
    func3.add_run('6.3 Perfis de Acesso\n').bold = True
    func3.add_run('• Administrador: Acesso total ao sistema')
    
    doc.add_paragraph('• Operação: Cadastro de operações e relatórios')
    doc.add_paragraph('• Execução: Apenas executar relatórios')
    
    doc.add_page_break()
    
    # ============================================================
    # 7. VARIÁVEIS DE AMBIENTE
    # ============================================================
    doc.add_heading('7. Variáveis de Ambiente', 1)
    
    var = doc.add_paragraph()
    var.add_run('Todas as configurações são feitas via variáveis de ambiente:\n').bold = True
    
    table2 = doc.add_table(rows=20, cols=3)
    table2.style = 'Table Grid'
    
    hdr2 = table2.rows[0].cells
    hdr2[0].text = 'Variável'
    hdr2[1].text = 'Padrão'
    hdr2[2].text = 'Descrição'
    
    variaveis = [
        ('APP_HOST', '0.0.0.0', 'Host do servidor Flask para acesso pela rede'),
        ('APP_PORT', '4732', 'Porta da aplicação'),
        ('APP_DEBUG', 'false', 'Modo debug'),
        ('FLASK_SECRET_KEY', '<valor removido>', 'Chave secreta'),
        ('DB_DRIVER', 'SQL Server', 'Driver ODBC'),
        ('DB_HOST', '', 'Servidor SQL'),
        ('DB_DATABASE', '', 'Nome do banco'),
        ('DB_USER', '', 'Usuário SQL'),
        ('DB_PASSWORD', '', 'Senha SQL'),
        ('DB_TIMEOUT', '5', 'Timeout conexão (s)'),
        ('SIENGE_LOGIN_URL', 'https://ebm.sienge.com.br/sienge/', 'URL Sienge'),
        ('SELENIUM_DEFAULT_TIMEOUT', '20', 'Timeout Selenium (s)'),
        ('SELENIUM_REPORT_WAIT_SECONDS', '8', 'Espera relatório (s)'),
        ('SELENIUM_DOWNLOAD_WAIT_TIMEOUT_SECONDS', '600', 'Timeout download (s)'),
        ('SELENIUM_POST_LOGIN_WAIT_SECONDS', '8', 'Espera pós-login (s)'),
        ('SELENIUM_FIELD_INTERACTION_WAIT_SECONDS', '1.5', 'Espera campo (s)'),
        ('SELENIUM_FIELD_RETRY_COUNT', '3', 'Tentativas campo'),
        ('SIENGE_SESSION_REUSE_ENABLED', 'true', 'Reutilizar sessão'),
    ]
    
    for i, (var, pad, desc) in enumerate(variaveis, 1):
        cells = table2.rows[i].cells
        cells[0].text = var
        cells[1].text = pad
        cells[2].text = desc
    
    doc.add_page_break()
    
    # ============================================================
    # 8. SOLUÇÃO DE PROBLEMAS
    # ============================================================
    doc.add_heading('8. Solução de Problemas', 1)
    
    sol = doc.add_paragraph()
    sol.add_run('8.1 Erro de conexão com banco\n').bold = True
    sol.add_run('Verifique as variáveis DB_HOST, DB_DATABASE, DB_USER e DB_PASSWORD no arquivo .env\n')
    
    doc.add_paragraph('')
    
    sol2 = doc.add_paragraph()
    sol2.add_run('8.2 Selenium não inicia\n').bold = True
    sol2.add_run('• Verifique se o Chrome está instalado\n')
    sol2.add_run('• Confirme que chromedriver está no PATH\n')
    sol2.add_run('• Execute: pip install selenium\n')
    
    doc.add_paragraph('')
    
    sol3 = doc.add_paragraph()
    sol3.add_run('8.3 Porta em uso\n').bold = True
    sol3.add_run('Altere a variável APP_PORT no arquivo .env para uma porta disponível\n')
    
    doc.add_paragraph('')
    
    sol4 = doc.add_paragraph()
    sol4.add_run('8.4 Login no Sienge falha\n').bold = True
    sol4.add_run('• Verifique credenciais em execucao_email e execucao_senha\n')
    sol4.add_run('• Confirme que URL do Sienge está correta\n')
    
    # ============================================================
    # RODAPÉ
    # ============================================================
    doc.add_page_break()
    rodape = doc.add_paragraph()
    rodape.add_run('---').bold = True
    rodape.add_run('\nManual gerado automaticamente pelo AppCaptação')
    rodape.add_run('\n© 2026 - Equipe de Desenvolvimento')
    
    # Salvar documento
    output_path = os.path.join(os.path.dirname(__file__), 'Manual_AppCaptação.docx')
    doc.save(output_path)
    
    return output_path


if __name__ == '__main__':
    caminho = criar_manual()
    print(f'Manual gerado com sucesso: {caminho}')
