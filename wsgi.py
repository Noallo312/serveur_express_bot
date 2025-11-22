import os
import threading
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import app and bot runner
from app import app, run_bot

# Start the Telegram bot in a background thread
logger.info("🚀 Démarrage du bot Telegram...")
bot_thread = threading.Thread(target=run_bot, daemon=True, name="TelegramBot")
bot_thread.start()

# Wait for bot to initialize
time.sleep(3)
logger.info("✅ Bot Telegram démarré dans un thread séparé")

# Gunicorn will use this 'app' object
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🌐 Démarrage Flask sur le port {port}")
    app.run(host='0.0.0.0', port=port)
