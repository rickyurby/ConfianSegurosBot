import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from PyPDF2 import PdfReader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from urllib.parse import urljoin
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Obtener credenciales de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PDF_BASE_URL = os.getenv('PDF_BASE_URL')

# Validación de credenciales
if not TELEGRAM_TOKEN or not OPENAI_API_KEY or not PDF_BASE_URL:
    logger.error("❌ Faltan credenciales en .env")
    exit(1)

# Inicializar OpenAI
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.3,
    api_key=OPENAI_API_KEY
)

async def start(update: Update, context):
    """Mensaje de bienvenida"""
    welcome_msg = (
        "👋 ¡Hola! Soy ConfianSegurosBot.\n\n"
        "Puedo responder preguntas sobre pólizas de seguros basándome en documentos oficiales.\n"
        "Pregúntame lo que necesites."
    )
    await update.message.reply_text(welcome_msg)

def obtener_lista_pdfs():
    """Devuelve una lista de archivos PDF disponibles."""
    try:
        response = requests.get(urljoin(PDF_BASE_URL, 'listado.txt'), timeout=10)
        response.raise_for_status()
        return response.text.strip().split('\n')
    except Exception as e:
        logger.error(f"⚠️ Error obteniendo lista de PDFs: {e}")
        return []

def descargar_pdf(pdf_url):
    """Descarga un PDF."""
    logger.info(f"📥 Descargando PDF: {pdf_url}")
    response = requests.get(pdf_url, timeout=60)
    response.raise_for_status()
    return response.content

def procesar_pdf(pdf_url):
    """Descarga y extrae texto de un PDF."""
    try:
        pdf_data = descargar_pdf(pdf_url)
        
        if not pdf_data:
            logger.warning(f"⚠️ El PDF está vacío: {pdf_url}")
            return ""

        with open('temp.pdf', 'wb') as f:
            f.write(pdf_data)

        reader = PdfReader('temp.pdf')
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        
        if not text.strip():
            logger.warning(f"⚠️ No se pudo extraer texto del PDF: {pdf_url}")
            return ""
        
        return text
    except Exception as e:
        logger.error(f"❌ Error procesando PDF {pdf_url}: {str(e)}")
    return ""

async def generar_respuesta(pregunta, contexto):
    """Genera una respuesta con LangChain."""
    try:
        prompt = ChatPromptTemplate.from_template(
            "Eres un asistente experto en seguros. Basado en el siguiente contexto:\n{context}\n\n"
            "Pregunta: {query}\n\n"
            "Responde en español de manera clara y precisa. Si no tienes información relevante, dilo claramente."
        )
        
        chain = prompt | llm
        response = await chain.ainvoke({"context": contexto, "query": pregunta})
        return response.content
    except Exception as e:
        logger.error(f"❌ Error generando respuesta: {str(e)}")
        return "❌ No pude generar una respuesta. Intenta nuevamente."

async def handle_message(update: Update, context):
    """Procesa mensajes de los usuarios."""
    pregunta = update.message.text
    user = update.message.from_user
    logger.info(f"📩 Consulta de {user.first_name}: {pregunta}")
    
    await update.message.reply_chat_action(action="typing")
    
    pdfs = obtener_lista_pdfs()
    if not pdfs:
        await update.message.reply_text("⚠️ No hay documentos disponibles en este momento.")
        return
    
    textos_pdfs = []
    for pdf in pdfs:
        pdf_url = urljoin(PDF_BASE_URL, pdf)
        texto = procesar_pdf(pdf_url)
        if texto:
            textos_pdfs.append(f"=== {pdf} ===\n{texto}")
    
    if not textos_pdfs:
        await update.message.reply_text("⚠️ No pude extraer información de los documentos.")
        return
    
    respuesta = await generar_respuesta(pregunta, "\n\n".join(textos_pdfs))
    await update.message.reply_text(respuesta[:4000])

def main():
    """Inicia el bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 Bot iniciado correctamente")
    application.run_polling()

if __name__ == '__main__':
    main()
