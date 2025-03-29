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

async def start_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Manejadores
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)
    
    await application.initialize()
    await application.start()
    return application

async def start_server():
    app = web.Application()
    app.add_routes([web.get("/health", health_check)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ Health check activo en puerto {PORT}")
    return runner

async def main():
    bot = await start_bot()
    server = await start_server()
    
    try:
        await bot.updater.start_polling()
        while True:
            await asyncio.sleep(3600)  # Mantener el loop activo
    except asyncio.CancelledError:
        await bot.updater.stop()
        await bot.stop()
        await bot.shutdown()
        await server.cleanup()

async def start(update: Update, context):
    welcome_msg = (
        "👋 ¡Hola! Soy ConfianSegurosBot.\n"
        "Puedo responder tus consultas sobre pólizas de seguros.\n\n"
        "Ejemplo: ¿Qué cubre el seguro de auto en caso de colisión?"
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
        response = requests.get(pdf_url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        with open('temp.pdf', 'wb') as f:
            f.write(response.content)
        
        reader = PdfReader('temp.pdf')
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except Exception as e:
        logger.error(f"Error procesando PDF: {str(e)}")
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
        return "⚠️ Error al procesar tu consulta. Intenta nuevamente."

async def handle_message(update: Update, context):
    user_query = update.message.text
    logger.info(f"Consulta: {user_query}")
    
    await update.message.reply_chat_action(action="typing")
    
    try:
        context = []
        for pdf in get_pdf_list():
            pdf_url = urljoin(PDF_BASE_URL, pdf)
            if pdf_url not in pdf_cache:
                pdf_cache[pdf_url] = process_pdf_text(pdf_url)
            if pdf_cache.get(pdf_url):
                context.append(f"=== {pdf} ===\n{pdf_cache[pdf_url]}")
        
        if not context:
            await update.message.reply_text("🔴 Error accediendo a documentos")
            return
            
        response = await generate_response(user_query, "\n\n".join(context))
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        await update.message.reply_text("⚠️ Error procesando tu solicitud")

async def error_handler(update: Update, context):
    logger.error(f"Error crítico: {context.error}")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔴 Error interno. Contacta al soporte técnico."
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.error(f"Falla crítica: {str(e)}")
