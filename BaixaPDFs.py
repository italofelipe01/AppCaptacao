# ================= INSTALAÇÃO AUTOMÁTICA DE DEPENDÊNCIAS =================
import subprocess
import sys

def instalar_dependencias():
    bibliotecas = [
        "selenium", "requests", "pillow", "webdriver-manager", "pandas", "openpyxl"
    ]
    for lib in bibliotecas:
        try:
            __import__(lib.replace("-", "_"))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

if __name__ == "__main__" and not getattr(sys, "frozen", False):
    instalar_dependencias()

# ================= IMPORTAÇÕES =================
import time
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import os
import requests
import re
import pandas as pd
import logging
from datetime import datetime
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageTk

# ================= VARIÁVEIS DE CONTROLE GLOBAL =================
parar_solicitado = threading.Event()

# ================= CONFIGURAÇÃO DE LOG TÉCNICO =================
logging.basicConfig(
    filename='execucao_debug.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S'
)

# ================= UTILITÁRIOS =================
def recurso_caminho(relativo):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relativo)

def sanitizar_nome_arquivo(nome):
    if not nome:
        return "EmpresaDesconhecida"
    return re.sub(r'[\\/*?:"<>|]', "", nome).strip()

def registrar_nova_pasta_log(caminho_pasta):
    """Cria um log notificando a criação de uma nova pasta de empresa"""
    nome_log = "pastas_criadas.txt"
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    try:
        with open(nome_log, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] NOVA PASTA CRIADA: {caminho_pasta}\n")
    except Exception as e:
        logging.error(f"Erro ao registrar log de pasta: {e}")

def obter_caminho_sharepoint(email, data, nome_empresa, empresa_codigo):
    usuario = email.split('@')[0]
    mes_ano = f"{data[2:4]}.{data[4:]}"
    ano_pasta = data[4:]
    nome_limpo = sanitizar_nome_arquivo(nome_empresa)
    
    caminho = os.path.join(
        "C:\\", "Users", usuario, "EBM", "Intranet EBM - Extratos", 
        f"ANO {ano_pasta}", f"{empresa_codigo} - {nome_limpo}", mes_ano
    )
    
    # NOTIFICAÇÃO DE NOVA PASTA: Se a pasta base da empresa não existir, logamos
    # Verificamos a pasta da empresa (um nível acima do mês/ano)
    pasta_empresa = os.path.dirname(caminho)
    if not os.path.exists(pasta_empresa):
        registrar_nova_pasta_log(pasta_empresa)
        
    return caminho

def esperar_tela_senha_ou_sso(driver, timeout=30):
    wait = WebDriverWait(driver, timeout)
    try:
        wait.until(lambda d: 
            d.find_elements(By.NAME, "loginfmt") or
            d.find_elements(By.NAME, "passwd") or
            d.find_elements(By.NAME, "password") or
            d.find_elements(By.XPATH, "//input[@type='password']")
        )
        return True
    except Exception as e:
        logging.error(
            "Timeout esperando tela de login Microsoft ou campo de senha. URL atual: %s",
            driver.current_url
        )
        raise

def salvar_relatorio_final(sucessos, erros):
    nome_arquivo = f"Relatorio_Final_{datetime.now().strftime('%d-%m-%Y_%H-%M')}.txt"
    try:
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            f.write("="*50 + "\n")
            f.write(f"RELATÓRIO DE EXECUÇÃO - {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            f.write("="*50 + "\n\n")
            f.write(f"RESUMO:\n")
            f.write(f"✅ SUCESSOS: {len(sucessos)}\n")
            f.write(f"❌ ERROS:    {len(erros)}\n\n")
            if parar_solicitado.is_set():
                f.write("⚠️ OBSERVAÇÃO: A execução foi interrompida pelo usuário.\n\n")
            
            f.write("-" * 20 + " LISTA DE ERROS " + "-" * 20 + "\n")
            if erros:
                for item in erros: f.write(f"[FALHA] Cód: {item}\n")
            else: f.write("Nenhum erro registrado.\n")
                
            f.write("\n" + "-" * 20 + " LISTA DE SUCESSOS " + "-" * 20 + "\n")
            if sucessos:
                for item in sucessos: f.write(f"[OK] Cód: {item}\n")
            else: f.write("Nenhum sucesso registrado.\n")
        os.startfile(nome_arquivo)
    except Exception as e:
        logging.error(f"Erro ao salvar relatório TXT: {e}")

def importar_excel():
    caminho_arquivo = filedialog.askopenfilename(
        title="Selecione a planilha de empresas",
        filetypes=[("Arquivos de Excel", "*.xlsx *.xls")]
    )
    if caminho_arquivo:
        try:
            df = pd.read_excel(caminho_arquivo, usecols=[0], header=None)
            lista_codigos = df[0].dropna().astype(str).tolist()
            lista_codigos = [c.split('.')[0].strip() for c in lista_codigos]
            texto_formatado = ", ".join(lista_codigos)
            entry_empresa.delete(0, tk.END)
            entry_empresa.insert(0, texto_formatado)
            messagebox.showinfo("Sucesso", f"{len(lista_codigos)} empresas carregadas!")
        except Exception as e:
            messagebox.showerror("Erro ao ler Excel", f"Erro: {e}")

# ================= LÓGICA SIENGE (MANTIDA INTEGRALMENTE) =================
def _aguardar_primeiro_elemento(driver, wait, locators, descricao="elemento"):
    ultimo_erro = None

    for locator in locators:
        try:
            return wait.until(EC.presence_of_element_located(locator))
        except (TimeoutException, NoSuchElementException) as exc:
            ultimo_erro = exc
            logging.info("Locator %s nao encontrado para %s.", locator, descricao)

    if ultimo_erro:
        raise ultimo_erro

    raise TimeoutException(f"Nenhum locator informado para localizar {descricao}.")


def _clicar_elemento_com_fallback(driver, locator, descricao=None):
    if descricao:
        logging.info("Tentando clicar em %s.", descricao)

    ultimo_erro = None
    for tentativa in range(1, 5):
        try:
            elemento = driver.find_element(*locator)
            elemento.click()
            return
        except (StaleElementReferenceException, NoSuchElementException, Exception) as exc:
            ultimo_erro = exc
            logging.warning(
                "Tentativa %s de clique falhou para %s: %s",
                tentativa,
                descricao or "elemento",
                type(exc).__name__,
            )
            try:
                elemento = driver.find_element(*locator)
                driver.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", elemento)
                return
            except (StaleElementReferenceException, NoSuchElementException, Exception) as exc2:
                ultimo_erro = exc2
                logging.warning(
                    "Fallback JS falhou para %s: %s",
                    descricao or "elemento",
                    type(exc2).__name__,
                )
            try:
                elemento = driver.find_element(*locator)
                elemento.send_keys(Keys.ENTER)
                return
            except (StaleElementReferenceException, NoSuchElementException, Exception) as exc3:
                ultimo_erro = exc3
                logging.warning(
                    "ENTER falhou para %s: %s",
                    descricao or "elemento",
                    type(exc3).__name__,
                )
            try:
                elemento = driver.find_element(*locator)
                driver.execute_script(
                    "var el = arguments[0]; var form = el.closest('form'); if(form){form.submit();} else {el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));}",
                    elemento,
                )
                return
            except (StaleElementReferenceException, NoSuchElementException, Exception) as exc4:
                ultimo_erro = exc4
                logging.warning(
                    "Submit de formulario falhou para %s: %s",
                    descricao or "elemento",
                    type(exc4).__name__,
                )
            time.sleep(0.5)

    logging.error("Nao foi possivel clicar no elemento %s apos varias tentativas: %s", descricao or "elemento", ultimo_erro)
    raise ultimo_erro


def login_sienge(email, senha):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = webdriver.Chrome(options=options)
    driver.get("https://ebm.sienge.com.br/sienge/")

    try:
        wait = WebDriverWait(driver, 30)

        btn_entrar = wait.until(EC.element_to_be_clickable((By.ID, "btnEntrarComSiengeID")))
        btn_entrar.click()

        campo_email = _aguardar_primeiro_elemento(
            driver,
            wait,
            [
                (By.NAME, "email"),
                (By.NAME, "username"),
            ],
            descricao="campo inicial de email do Sienge ID",
        )
        campo_email.clear()
        campo_email.send_keys(email)

        botao_continuar_locator = (
            By.XPATH,
            "//button[@data-testid='sign-in-v2-submit-button'] | //button[contains(normalize-space(.), 'Continuar') or contains(normalize-space(.), 'CONTINUAR')] | //button[@type='submit' and contains(normalize-space(.), 'Continuar')]",
        )
        wait.until(EC.presence_of_element_located(botao_continuar_locator))
        _clicar_elemento_com_fallback(driver, botao_continuar_locator, descricao="botao Continuar do Sienge ID")

        try:
            botao_continuar_element = driver.find_element(*botao_continuar_locator)
            wait.until(EC.staleness_of(botao_continuar_element))
        except Exception:
            logging.debug("Botao Continuar nao saiu da pagina antes de continuar.")

        try:
            campo_autenticador_email = wait.until(
                EC.presence_of_element_located((By.NAME, "loginfmt"))
            )
            campo_autenticador_email.clear()
            campo_autenticador_email.send_keys(email)
            botao_microsoft_locator = (
                By.XPATH,
                "//input[@id='idSIButton9'] | //button[contains(normalize-space(.), 'Entrar') or contains(normalize-space(.), 'Continuar')]",
            )
            wait.until(EC.presence_of_element_located(botao_microsoft_locator))
            _clicar_elemento_com_fallback(driver, botao_microsoft_locator, descricao="botao de avançar da Microsoft")
            wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//input[@type='password' or @name='passwd' or @name='password']")
                )
            )
        except (TimeoutException, NoSuchElementException):
            logging.info("Tela Microsoft de login nao apareceu; continuando para o campo de senha.")

        campo_senha = _aguardar_primeiro_elemento(
            driver,
            wait,
            [
                (By.NAME, "passwd"),
                (By.NAME, "password"),
                (By.XPATH, "//input[@type='password']"),
            ],
            descricao="campo senha do Sienge/Microsoft",
        )
        campo_senha.clear()
        campo_senha.send_keys(senha)

        try:
            btn_entrar_locator = (By.ID, "idSIButton9")
            wait.until(EC.element_to_be_clickable(btn_entrar_locator))
            _clicar_elemento_com_fallback(driver, btn_entrar_locator, descricao="botao Entrar Microsoft")
            logging.info("Botao Entrar Microsoft pressionado.")
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
            logging.warning("Botao Entrar Microsoft nao encontrado ou nao clicavel; tentanto botao alternativo.")
            try:
                btn_login_locator = (
                    By.XPATH,
                    "//button[contains(normalize-space(.), 'Entrar') or contains(normalize-space(.), 'Login') or contains(normalize-space(.), 'Continuar') ]",
                )
                wait.until(EC.presence_of_element_located(btn_login_locator))
                _clicar_elemento_com_fallback(driver, btn_login_locator, descricao="botao de login final alternativo")
            except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
                logging.info("Botao de login final alternativo nao encontrado; enviando ENTER no campo de senha.")
                campo_senha.send_keys(Keys.ENTER)

        logging.info("Aguardando 60 segundos apos envio de senha Microsoft antes de continuar.")
        time.sleep(30)

        try:
            back_button = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, "idBtn_Back")))
            back_button.click()
        except Exception:
            pass

        logging.info("Login realizado com sucesso.")
    except Exception as e:
        logging.error(f"Erro crítico no login: {e}")
        raise
    return driver

def preencher_campo(driver, identificador, valor, by=By.ID):
    wait = WebDriverWait(driver, 30)
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)
    campo = wait.until(EC.element_to_be_clickable((by, identificador)))
    campo.clear()
    campo.send_keys(valor)
    campo.send_keys(Keys.TAB)
    driver.switch_to.default_content()

def acessar_pagina_e_preencher_capturar_nome(driver, data, empresa_codigo):
    driver.get("https://ebm.sienge.com.br/sienge/8/index.html#/common/page/376")
    wait = WebDriverWait(driver, 30)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))

    preencher_campo(driver, "dtFim", data, By.ID)
    preencher_campo(driver, "empresa.cdEmpresaView", empresa_codigo, By.ID)

    nome_capturado = ""
    try:
        iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        driver.switch_to.frame(iframe)
        nome_field = WebDriverWait(driver, 15).until(
            lambda d: d.find_element(By.ID, "empresa.nmEmpresa").get_attribute("value").strip() != ""
        )
        elem_nome = driver.find_element(By.ID, "empresa.nmEmpresa")
        nome_capturado = elem_nome.get_attribute("value")
        driver.switch_to.default_content()
    except Exception:
        nome_capturado = "NomeNaoCapturado"
        driver.switch_to.default_content()
    return nome_capturado

def clicar_botao_visualizar(driver):
    wait = WebDriverWait(driver, 30)
    driver.switch_to.default_content()
    iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
    driver.switch_to.frame(iframe)

    botao_visualizar = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='holderConteudo2']/form/p/span[1]/span/input")))
    try:
        botao_visualizar.click()
    except Exception:
        driver.execute_script("arguments[0].scrollIntoView(true);", botao_visualizar)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", botao_visualizar)

    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, 30).until(lambda d: len(d.window_handles) >= 2)
    except: pass

def baixar_pdf_requests(driver, empresa_codigo, nome_empresa, data, email_usuario):
    try:
        try:
            WebDriverWait(driver, 20).until(lambda d: len(d.window_handles) >= 2)
        except: pass
        abas = driver.window_handles
        if len(abas) < 2: return False
        driver.switch_to.window(abas[-1])
        WebDriverWait(driver, 20).until(
            lambda d: "url=" in d.current_url or d.execute_script("return document.readyState") == "complete"
        )
        url_intermediaria = driver.current_url
        if "url=" not in url_intermediaria:
            driver.close()
            driver.switch_to.window(abas[0])
            return False
        url_pdf_real = "https://ebm.sienge.com.br" + url_intermediaria.split("url=")[1]
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        response = requests.get(url_pdf_real, cookies=cookies, timeout=60)
        if response.status_code == 200:
            pasta_destino = obter_caminho_sharepoint(email_usuario, data, nome_empresa, empresa_codigo)
            os.makedirs(pasta_destino, exist_ok=True)
            nome_arquivo = f"{data}_{empresa_codigo}_{sanitizar_nome_arquivo(nome_empresa)}.pdf"
            with open(os.path.join(pasta_destino, nome_arquivo), "wb") as f:
                f.write(response.content)
            driver.close()
            driver.switch_to.window(abas[0])
            return True
        driver.close()
        driver.switch_to.window(abas[0])
        return False
    except Exception as e:
        logging.error(f"Erro no download: {e}")
        return False

# ================= FLUXO PRINCIPAL (COM CONTROLE DE PARADA) =================
def executar_automacao():
    parar_solicitado.clear() 
    email = entry_email.get().strip()
    senha = entry_senha.get().strip()
    data = entry_data.get().strip()
    empresas_raw = entry_empresa.get().strip()

    if not all([email, senha, data, empresas_raw]):
        messagebox.showerror("Erro", "Preencha todos os campos")
        return

    lista_empresas = [e.strip() for e in empresas_raw.split(",") if e.strip()]
    driver = None
    sucesso_log, erro_log = [], []

    try:
        logging.info("Iniciando automação...")
        driver = login_sienge(email, senha)
        
        for empresa in lista_empresas:
            if parar_solicitado.is_set():
                logging.info("Execução interrompida pelo usuário.")
                break

            logging.info(f"Processando empresa: {empresa}")
            try:
                nome = acessar_pagina_e_preencher_capturar_nome(driver, data, empresa)
                clicar_botao_visualizar(driver)
                ok = baixar_pdf_requests(driver, empresa, nome, data, email)
                
                if ok: sucesso_log.append(f"{empresa} - {nome}")
                else: erro_log.append(f"{empresa} - {nome}")
            except Exception as e:
                erro_log.append(f"{empresa} (Erro: {str(e)})")

        salvar_relatorio_final(sucesso_log, erro_log)
        msg_status = "Interrompido!" if parar_solicitado.is_set() else "Finalizado!"
        messagebox.showinfo("Status", f"{msg_status}\nSucessos: {len(sucesso_log)}\nErros: {len(erro_log)}")
        
    except Exception as e:
        messagebox.showerror("Erro Fatal", f"Erro: {e}")
    finally:
        if driver: 
            driver.quit()

# ================= GESTÃO DE THREADS E INTERFACE =================
def iniciar_thread():
    btn_iniciar.config(state=tk.DISABLED, text="Rodando...")
    btn_parar.config(state=tk.NORMAL)
    threading.Thread(target=wrapper_thread, daemon=True).start()

def parar_automacao():
    parar_solicitado.set()
    btn_parar.config(state=tk.DISABLED, text="Parando...")

def wrapper_thread():
    executar_automacao()
    root.after(0, resetar_botoes)

def resetar_botoes():
    btn_iniciar.config(state=tk.NORMAL, text="🚀 Iniciar Automação")
    btn_parar.config(state=tk.DISABLED, text="🛑 Parar Automação")

# ================= GUI =================
root = tk.Tk()
root.title("Baixar PDFs - EBM")
root.geometry("420x580")
root.resizable(False, False)

try:
    img = Image.open(recurso_caminho("ebm.png"))
    img = img.resize((150, int(150 * img.size[1] / img.size[0])))
    img_tk = ImageTk.PhotoImage(img)
    lbl = tk.Label(root, image=img_tk)
    lbl.image = img_tk
    lbl.pack(pady=(15, 5))
except: pass

tk.Label(root, text="Email").pack(pady=(5, 0))
entry_email = tk.Entry(root, width=45)
entry_email.pack()

tk.Label(root, text="Senha").pack(pady=(5, 0))
entry_senha = tk.Entry(root, show="*", width=45)
entry_senha.pack()

tk.Label(root, text="Data Fim (ddmmaaaa)").pack(pady=(5, 0))
entry_data = tk.Entry(root, width=20)
entry_data.pack()

tk.Label(root, text="Cód. Empresas (separados por vírgula)").pack(pady=(5, 0))
entry_empresa = tk.Entry(root, width=45)
entry_empresa.pack()

tk.Button(
    root, text="📂 Importar Empresas da Coluna A (Excel)", 
    command=importar_excel, bg="#4CAF50", fg="white", width=35
).pack(pady=10)

btn_iniciar = tk.Button(
    root, text="🚀 Iniciar Automação", command=iniciar_thread,
    bg="#1976D2", fg="white", width=25, font=("Arial", 10, "bold")
)
btn_iniciar.pack(pady=10)

btn_parar = tk.Button(
    root, text="🛑 Parar Automação", command=parar_automacao,
    bg="#d32f2f", fg="white", width=25, font=("Arial", 10, "bold"),
    state=tk.DISABLED
)
btn_parar.pack(pady=5)

root.mainloop()