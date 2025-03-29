import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from PyPDF2 import PdfReader
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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PDF_BASE_URL = os.getenv("PDF_BASE_URL")

# Cache para PDFs
pdf_cache = {}

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
    """Lista de PDFs disponibles"""
    return [
        "CG-AX-CAM-IND-D22.pdf",
        "CG-AX-GMM-IND-F24.pdf",
        "CG-AXA-AUT-IND-AG24.pdf",
    ]

def process_pdf_text(pdf_url: str) -> str:
    """Descarga y extrae texto de un PDF"""
    try:
        response = requests.get(pdf_url, timeout=15)
        response.raise_for_status()
        
        with open('temp.pdf', 'wb') as f:
            f.write(response.content)
        
        reader = PdfReader('temp.pdf')
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        logger.error(f"Error procesando PDF {pdf_url}: {str(e)}")
        return None

async def generate_response(query: str, context: str) -> str:
    """Genera respuesta usando OpenAI"""
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Responde basado en este contexto:\n{context}"},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content[:4000]  # Limite de Telegram
    except Exception as e:
        logger.error(f"Error en OpenAI: {str(e)}")
        return "❌ Error al generar respuesta. Intenta nuevamente."

async def handle_message(update: Update, context):
    """Maneja los mensajes del usuario"""
    user_query = update.message.text
    logger.info(f"Consulta recibida: {user_query}")
    
    await update.message.reply_chat_action(action="typing")
    
    try:
        # 1. Obtener texto de los PDFs
        pdf_texts = []
        for pdf_file in get_pdf_list():
            pdf_url = urljoin(PDF_BASE_URL, pdf_file)
            
            if pdf_url not in pdf_cache:
                text = process_pdf_text(pdf_url)
                if text:
                    pdf_cache[pdf_url] = text
            
            if pdf_url in pdf_cache and pdf_cache[pdf_url]:
                pdf_texts.append(f"=== {pdf_file} ===\n{pdf_cache[pdf_url]}")
        
        if not pdf_texts:
            await update.message.reply_text("⚠️ No pude acceder a los documentos. Intenta más tarde.")
            return
        
        # 2. Generar y enviar respuesta
        response = await generate_response(user_query, "\n\n".join(pdf_texts))
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error en handle_message: {str(e)}")
        await update.message.reply_text("❌ Error al procesar tu consulta. Intenta nuevamente.")

async def error_handler(update: Update, context):
    """Manejador global de errores"""
    logger.error(f"Error no controlado: {context.error}")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="❌ Ocurrió un error inesperado. Por favor, inténtalo más tarde."
    )

def main():
    """Configuración principal del bot"""
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Manejadores
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # Manejo de errores
        application.add_error_handler(error_handler)
        
        logger.info("🚀 Bot iniciado correctamente")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"🚨 Error crítico: {str(e)}")
        raise

if __name__ == '__main__':
    main()
