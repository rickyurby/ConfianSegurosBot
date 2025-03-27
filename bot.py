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

# Configuración inicial
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PDF_BASE_URL = "https://confianseguros.com/docs/"

# Cache para PDFs
pdf_cache = {}

# Configuración de LangChain
llm = ChatOpenAI(
    model="gpt-3.5-turbo",
    temperature=0.3,
    api_key=OPENAI_API_KEY
)

async def start(update: Update, context):
    """Manejador del comando /start"""
    welcome_msg = (
        "👋 ¡Hola! Soy ConfianSegurosBot.\n\n"
        "Puedo responderte preguntas sobre las condiciones generales de contratos de seguros.\n\n"
        "Ejemplos de preguntas:\n"
        "- ¿Qué cubre el seguro de auto en caso de accidente?\n"
        "- ¿Cuál es el período de espera del seguro de salud?\n"
        "- ¿Qué exclusiones tiene el seguro de hogar?\n\n"
        "¡Pregúntame lo que necesites saber!"
    )
    await update.message.reply_text(welcome_msg)

def get_pdf_list():
    """Lista de PDFs disponibles (actualiza con tus archivos)"""
    return [
        "CG-AX-CAM-IND-D22.pdf",
        "CG-AX-GMM-IND-F24.pdf",
        "CG-AXA-AUT-IND-AG24.pdf",
        # Añade más archivos según necesites
    ]

def process_pdf_text(pdf_url):
    """Descarga y extrae texto de un PDF"""
    try:
        response = requests.get(pdf_url, timeout=10)
        response.raise_for_status()
        
        with open('temp.pdf', 'wb') as f:
            f.write(response.content)
        
        reader = PdfReader('temp.pdf')
        text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
        return text
    except Exception as e:
        logger.error(f"Error procesando PDF {pdf_url}: {str(e)}")
        return None

async def generate_response(query, context):
    """Genera respuesta usando LangChain"""
    prompt = ChatPromptTemplate.from_template(
        "Eres un experto en seguros. Responde basándote en este contexto:\n\n"
        "{context}\n\n"
        "Pregunta: {query}\n\n"
        "Instrucciones:\n"
        "- Responde en español de forma clara y profesional\n"
        "- Si la información no está en el contexto, dilo\n"
        "- Usa viñetas para listar coberturas/exclusiones\n"
        "- Destaca plazos y límites importantes"
    )
    
    chain = prompt | llm
    response = await chain.ainvoke({"context": context, "query": query})
    return response.content

async def handle_message(update: Update, context):
    """Maneja los mensajes del usuario"""
    user_query = update.message.text
    user = update.message.from_user
    logger.info(f"Consulta de {user.first_name}: {user_query}")
    
    await update.message.reply_chat_action(action="typing")
    
    try:
        # 1. Obtener texto de los PDFs relevantes
        pdf_texts = []
        for pdf_file in get_pdf_list():
            pdf_url = urljoin(PDF_BASE_URL, pdf_file)
            
            if pdf_url not in pdf_cache:
                text = process_pdf_text(pdf_url)
                if text:
                    pdf_cache[pdf_url] = text
            
            if pdf_url in pdf_cache:
                pdf_texts.append(f"=== {pdf_file} ===\n{pdf_cache[pdf_url]}")
        
        if not pdf_texts:
            await update.message.reply_text("⚠️ No pude acceder a los documentos. Intenta más tarde.")
            return
        
        full_context = "\n\n".join(pdf_texts)
        
        # 2. Generar respuesta
        response = await generate_response(user_query, full_context)
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await update.message.reply_text("❌ Error al procesar tu consulta. Intenta nuevamente.")

def main():
    """Inicia el bot"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Manejadores
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Iniciar el bot
    application.run_polling()

if __name__ == '__main__':
    main()