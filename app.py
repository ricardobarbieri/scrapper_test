from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import simpleSplit
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import fake_useragent
import os
import logging
from retrying import retry
import unicodedata

app = Flask(__name__)

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Simula progresso (em produção, usaríamos WebSockets para progresso real)
progress_state = {'value': 0, 'message': 'Aguardando início...'}

def retry_if_exception(exception):
    return isinstance(exception, Exception)

@retry(retry_on_exception=retry_if_exception, stop_max_attempt_number=3, wait_fixed=2000)
def scrape_website(url):
    global progress_state
    logging.info(f"Iniciando scrape da URL: {url}")
    progress_state = {'value': 0, 'message': 'Inicializando...'}

    # Configuração do Selenium
    ua = fake_useragent.UserAgent()
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(f"user-agent={ua.random}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # Opcional: Proxy (descomente e configure se necessário)
    # chrome_options.add_argument('--proxy-server=http://seu_proxy:porta')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Etapa 1: Acessa a URL (20% do progresso)
        progress_state['value'] = 20
        progress_state['message'] = 'Carregando página...'
        driver.get(url)
        time.sleep(random.uniform(2, 5))
        logging.info("Página carregada")

        # Tenta aceitar cookies
        try:
            cookie_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'aceitar')]"))
            )
            cookie_button.click()
            logging.info("Cookies aceitos")
            time.sleep(random.uniform(1, 2))
        except:
            logging.info("Nenhum pop-up de cookies encontrado")

        # Etapa 2: Scroll para carregar conteúdo (50% do progresso)
        progress_state['value'] = 50
        progress_state['message'] = 'Carregando conteúdo dinâmico...'
        for i in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 3))
            logging.info(f"Scroll {i+1} executado")

        # Etapa 3: Parsing do HTML (70% do progresso)
        progress_state['value'] = 70
        progress_state['message'] = 'Analisando página...'
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        logging.info("HTML obtido para parsing")

        # Extrai elementos
        results = {
            'titles': [],
            'paragraphs': [],
            'links': [],
            'lists': []
        }

        # Função para normalizar texto
        def normalize_text(text):
            # Remove caracteres não ASCII e normaliza
            text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
            return text.strip()

        # Títulos (h1, h2, h3)
        for tag in ['h1', 'h2', 'h3']:
            for element in soup.find_all(tag):
                text = normalize_text(element.text)
                if text:
                    results['titles'].append({'tag': tag, 'text': text})

        # Parágrafos
        for element in soup.find_all('p'):
            text = normalize_text(element.text)
            if text:
                results['paragraphs'].append(text)

        # Links
        for element in soup.find_all('a', href=True):
            text = normalize_text(element.text) or "Link sem texto"
            href = element['href']
            if href:
                # Remove caracteres problemáticos da URL
                href = href.encode('ASCII', 'ignore').decode('ASCII')
                results['links'].append({'text': text, 'href': href})

        # Listas (ul, ol)
        for tag in ['ul', 'ol']:
            for element in soup.find_all(tag):
                items = [normalize_text(li.text) for li in element.find_all('li') if li.text.strip()]
                if items:
                    results['lists'].append({'type': tag, 'items': items})

        # Etapa 4: Geração do PDF (90% do progresso)
        progress_state['value'] = 90
        progress_state['message'] = 'Gerando PDF...'
        os.makedirs('static', exist_ok=True)
        pdf_file = "static/scrape_results.pdf"
        doc = SimpleDocTemplate(pdf_file, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"Resultados do Scraping: {url}", styles['Title']))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Títulos", styles['Heading2']))
        for title in results['titles']:
            story.append(Paragraph(f"{title['tag'].upper()}: {title['text']}", styles['Normal']))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Parágrafos", styles['Heading2']))
        for para in results['paragraphs']:
            story.append(Paragraph(para, styles['Normal']))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Links", styles['Heading2']))
        for link in results['links']:
            # Evita o uso de <a> no PDF, apenas exibe o texto e a URL como texto
            story.append(Paragraph(f"{link['text']}: {link['href']}", styles['Normal']))
        story.append(Spacer(1, 12))

        story.append(Paragraph("Listas", styles['Heading2']))
        for lst in results['lists']:
            story.append(Paragraph(f"Tipo: {lst['type'].upper()}", styles['Normal']))
            for item in lst['items']:
                story.append(Paragraph(f"- {item}", styles['Normal']))
        story.append(Spacer(1, 12))

        doc.build(story)
        logging.info(f"PDF gerado: {pdf_file}")

        # Etapa 5: Concluído (100% do progresso)
        progress_state['value'] = 100
        progress_state['message'] = 'Concluído!'
        return results, pdf_file

    except Exception as e:
        logging.error(f"Erro durante o scrape: {str(e)}")
        raise

    finally:
        driver.quit()
        logging.info("Driver encerrado")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    url = request.form.get('url')
    if not url:
        return jsonify({'error': 'URL não fornecida'}), 400

    try:
        results, pdf_file = scrape_website(url)
        return jsonify({'results': results, 'pdf': pdf_file})
    except Exception as e:
        logging.error(f"Erro na rota /scrape: {str(e)}")
        return jsonify({'error': f'Falha no scraping: {str(e)}'}), 500

@app.route('/progress', methods=['GET'])
def progress():
    global progress_state
    return jsonify(progress_state)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')