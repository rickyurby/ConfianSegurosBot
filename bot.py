import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from PyPDF2 import PdfReader
from urllib.parse import urljoin
from dotenv import load_dotenv

# 1. Cargar variables primero
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PDF_BASE_URL = os.getenv("PDF_BASE_URL")

# 2. Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 3. Crear la aplicación después de cargar variables
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Resto del código (manejadores, funciones, etc.)
async def start(update: Update, context):
    await update.message.reply_text("¡Bot funcionando correctamente! ✅")

# ... (tus demás funciones aquí)

def main():
    application.add_handler(CommandHandler("start", start))
    application.run_polling()

if __name__ == '__main__':
    main()
