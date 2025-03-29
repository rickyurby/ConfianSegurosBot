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
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tenacity import retry, stop_after_attempt, wait_exponential

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

# Configuración de retries para requests
retry_strategy = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)

adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

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
            await asyncio.sleep(3600)
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
        logger.info(f"Intentando descargar: {pdf_url}")
        
        response = session.get(
            pdf_url,
            timeout=(10, 30),  # 10 segundos para conexión, 30 para lectura
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; ConfianSegurosBot/1.0; +https://confianseguros.com)',
                'Accept-Encoding': 'gzip, deflate'
            },
            verify=False  # ⚠️ Solo para pruebas, eliminar en producción
        )
        
        response.raise_for_status()
        
        # Verificar que sea un PDF válido
        if 'pdf' not in response.headers.get('Content-Type', ''):
            logger.error(f"El archivo {pdf_url} no es un PDF válido")
            return None
            
        with open('temp.pdf', 'wb') as f:
            f.write(response.content)
        
        reader = PdfReader('temp.pdf')
        return "\n".join([page.extract_text() or '' for page in reader.pages])
        
    except Exception as e:
        logger.error(f"Error procesando PDF ({pdf_url}): {str(e)}")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def generate_response(query: str, context: str) -> str:
    try:
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Eres un experto en seguros. Contexto:\n{context}"},
                {"role": "user", "content": query}
            ],
            temperature=0.3,
            max_tokens=1500,
            request_timeout=30  # Timeout específico para OpenAI
        )
        return response.choices[0].message.content[:4000]
    except Exception as e:
        logger.warning(f"Intento fallido en OpenAI: {str(e)}")
        raise

async def handle_message(update: Update, context):
    user_query = update.message.text
    logger.info(f"Consulta: {user_query}")
    
    await update.message.reply_chat_action(action="typing")
    
    try:
        pdf_texts = []
        for pdf_file in get_pdf_list():
            pdf_url = urljoin(PDF_BASE_URL, pdf_file)
            
            if pdf_url not in pdf_cache:
                logger.info(f"Procesando PDF: {pdf_file}")
                pdf_cache[pdf_url] = process_pdf_text(pdf_url)
            
            if pdf_cache.get(pdf_url):
                pdf_texts.append(f"=== {pdf_file} ===\n{pdf_cache[pdf_url]}")
        
        if not pdf_texts:
            await update.message.reply_text("🔴 No se pudieron cargar los documentos. Por favor, inténtalo más tarde.")
            return
            
        response = await generate_response(user_query, "\n\n".join(pdf_texts))
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error en handle_message: {str(e)}")
        await update.message.reply_text("⚠️ Lo siento, ocurrió un error procesando tu solicitud. Por favor, inténtalo de nuevo.")

async def error_handler(update: Update, context):
    error = context.error
    logger.error(f"Error no controlado: {error}", exc_info=True)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔴 Ocurrió un error inesperado. Nuestro equipo técnico ha sido notificado."
    )

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot detenido manualmente")
    except Exception as e:
        logger.critical(f"Falla crítica: {str(e)}", exc_info=True)
