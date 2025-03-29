import os
import logging
import requests
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from PyPDF2 import PdfReader
from urllib.parse import urljoin
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuración
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PDF_BASE_URL = "https://confianseguros.com/docs/"
openai.api_key = OPENAI_API_KEY

# Cache para PDFs
pdf_cache = {}

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
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        logger.error(f"Error procesando PDF: {str(e)}")
        return None

async def generate_response(query, context):
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un experto en seguros. Responde basándote en este contexto:\n" + context},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content[:4096]
    except Exception as e:
        logger.error(f"Error en OpenAI: {str(e)}")
        return "❌ Error al generar respuesta. Intenta nuevamente."

async def handle_message(update: Update, context):
    user_query = update.message.text
    logger.info(f"Consulta recibida: {user_query}")
    
    await update.message.reply_chat_action(action="typing")
    
    try:
        context = []
        for pdf_file in get_pdf_list():
            pdf_url = urljoin(PDF_BASE_URL, pdf_file)
            if pdf_url not in pdf_cache:
                pdf_cache[pdf_url] = process_pdf_text(pdf_url)
            if pdf_cache[pdf_url]:
                context.append(f"=== {pdf_file} ===\n{pdf_cache[pdf_url]}")
        
        if not context:
            await update.message.reply_text("⚠️ Documentos no disponibles")
            return
        
        response = await generate_response(user_query, "\n\n".join(context))
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error general: {str(e)}")
        await update.message.reply_text("❌ Error procesando consulta")

def main():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
