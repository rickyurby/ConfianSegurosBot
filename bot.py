import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx

# Configuración del logger
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Token de tu bot
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Función para manejar el comando /start
async def start(update, context):
    """Envía un mensaje cuando el comando /start es ejecutado"""
    await update.message.reply_text("Hola! Soy el bot, ¿en qué puedo ayudarte?")

# Función para manejar los mensajes de texto
async def handle_message(update, context):
    """Responde a los mensajes de texto con un mensaje genérico"""
    user_text = update.message.text
    await update.message.reply_text(f"Has escrito: {user_text}")

# Función para obtener los PDFs desde un archivo listado.txt
async def obtener_pdfs():
    """Función para obtener los PDFs desde el archivo listado.txt en tu servidor"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://confianseguros.com/docs/listado.txt")
            if response.status_code == 200:
                pdf_list = response.text.splitlines()
                return pdf_list
            else:
                logger.error(f"Error al obtener listado de PDFs: {response.status_code}")
                return []
    except httpx.RequestError as e:
        logger.error(f"Error de conexión al obtener los PDFs: {e}")
        return []

# Función para manejar la consulta de PDFs en el bot
async def consulta_pdfs(update, context):
    """Función para enviar un mensaje con los PDFs disponibles"""
    pdf_list = await obtener_pdfs()
    if pdf_list:
        await update.message.reply_text(f"Lista de PDFs:\n\n" + "\n".join(pdf_list))
    else:
        await update.message.reply_text("No se pudieron obtener los PDFs en este momento.")

# Función principal
def main():
    """Función principal que configura el bot y sus handlers"""
    # Crear la aplicación de Telegram
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Agregar los handlers para los comandos y mensajes
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("consultapdf", consulta_pdfs))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Ejecutar el bot
    application.run_polling()

if __name__ == '__main__':
    main()
