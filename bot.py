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
from langchain.llms import OpenAI  # Cambiado de langchain_openai
from langchain.prompts import PromptTemplate  # Cambiado de langchain_core

# Configuración inicial
load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variables de entorno
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7824585491:AAHy4M-fGSluRUdLFzFv2TbMA4_EzmhgmGE')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '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')
PDF_BASE_URL = os.getenv('PDF_BASE_URL', 'https://confianseguros.com/docs/')

# Cache para PDFs
pdf_cache = {}

llm = OpenAI(
    model_name="gpt-3.5-turbo",
    temperature=0.3,
    openai_api_key=OPENAI_API_KEY
)

async def start(update: Update, context):
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
    return [
        "CG-AX-CAM-IND-D22.pdf",
        "CG-AX-GMM-IND-F24.pdf",
        "CG-AXA-AUT-IND-AG24.pdf",
    ]

def process_pdf_text(pdf_url):
    try:
        response = requests.get(pdf_url, timeout=15)
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
    try:
        prompt = ChatPromptTemplate.from_template(
            "Eres un experto en seguros. Contexto:\n{context}\n\n"
            "Pregunta: {query}\n\n"
            "Responde en español de forma clara y profesional. "
            "Si la información no está en el contexto, dilo claramente."
        )
        
        chain = prompt | llm
        response = await chain.ainvoke({"context": context, "query": query})
        return response.content[:4096]  # Límite de Telegram
    except Exception as e:
        logger.error(f"Error en generate_response: {str(e)}")
        return "❌ Error al generar respuesta. Por favor, intenta nuevamente."

async def handle_message(update: Update, context):
    user_query = update.message.text
    logger.info(f"Consulta recibida: {user_query}")
    
    await update.message.reply_chat_action(action="typing")
    
    try:
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
        
        response = await generate_response(user_query, "\n\n".join(pdf_texts))
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error en handle_message: {str(e)}")
        await update.message.reply_text("❌ Error al procesar tu consulta. Intenta nuevamente.")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN no configurado")
        exit(1)
        
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Bot iniciado correctamente")
    application.run_polling()

if __name__ == '__main__':
    main()
