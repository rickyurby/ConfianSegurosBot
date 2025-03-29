import os
import logging
import requests
import openai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from PyPDF2 import PdfReader
from urllib.parse import urljoin
from dotenv import load_dotenv
from aiohttp import web
import asyncio

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
PORT = int(os.getenv("PORT", 10000))

# Configurar OpenAI
openai.api_key = OPENAI_API_KEY

# Cache para PDFs
pdf_cache = {}

# Servidor web para health checks
async def health_check(request):
    return web.Response(text="OK")

def setup_web_server():
    app = web.Application()
    app.add_routes([web.get("/health", health_check)])
    return app

async def start_bot_and_server():
    # Configurar aplicación de Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    # Configurar servidor web
    web_app = setup_web_server()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    
    # Iniciar ambos servicios
    await site.start()
    logger.info(f"✅ Servidor health check iniciado en puerto {PORT}")
    await application.run_polling(drop_pending_updates=True)

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

def process_pdf_text(pdf_url: str) -> str:
    try:
        # Aumentamos el timeout a 30 segundos y permitimos redirecciones
        response = requests.get(pdf_url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        with open('temp.pdf', 'wb') as f:
            f.write(response.content)
        
        reader = PdfReader('temp.pdf')
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        logger.error(f"Error procesando PDF {pdf_url}: {str(e)}")
        return None

async def generate_response(query: str, context: str) -> str:
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Eres un experto en seguros. Contexto:\n{context}"},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content[:4000]
    except Exception as e:
        logger.error(f"Error en OpenAI: {str(e)}")
        return "❌ Error al generar respuesta. Intenta nuevamente."

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
            
            if pdf_url in pdf_cache and pdf_cache[pdf_url]:
                pdf_texts.append(f"=== {pdf_file} ===\n{pdf_cache[pdf_url]}")
        
        if not pdf_texts:
            await update.message.reply_text("⚠️ No pude acceder a los documentos. Intenta más tarde.")
            return
        
        response = await generate_response(user_query, "\n\n".join(pdf_texts))
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error en handle_message: {str(e)}")
        await update.message.reply_text("❌ Error al procesar tu consulta. Intenta nuevamente.")

async def error_handler(update: Update, context):
    logger.error(f"Error no controlado: {context.error}")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="❌ Ocurrió un error inesperado. Por favor, inténtalo más tarde."
    )

def main():
    try:
        asyncio.run(start_bot_and_server())
    except Exception as e:
        logger.error(f"🚨 Error crítico: {str(e)}")
        raise

if __name__ == '__main__':
    main()
