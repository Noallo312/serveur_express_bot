import os
import threading
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import app and bot runner
from app import app, run_bot

# Start the Telegram bot in a background thread
logger.info("🚀 Démarrage du bot Telegram en arrière-plan...")
bot_thread = threading.Thread(target=run_bot, daemon=True, name="TelegramBotPolling")
bot_thread.start()

# Wait for bot to initialize
time.sleep(3)
logger.info("✅ Bot Telegram lancé dans un thread séparé")
logger.info("🌐 Flask app prête à recevoir des requêtes")

# This 'app' object is what Gunicorn will use
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🏃 Mode développement - Flask démarre sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
