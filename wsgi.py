import os
import logging
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import app and bot setup
from app import app, setup_telegram_bot

# Setup Telegram bot with webhook
logger.info("🚀 Initialisation du bot Telegram avec webhook...")

# Create event loop and setup bot
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

try:
    loop.run_until_complete(setup_telegram_bot())
    logger.info("✅ Bot Telegram configuré avec webhook")
except Exception as e:
    logger.error(f"❌ Erreur lors de la configuration du bot: {e}")
    import traceback
    traceback.print_exc()

logger.info("🌐 Flask app prête à recevoir des requêtes")

# This 'app' object is what Gunicorn will use
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🏃 Mode développement - Flask démarre sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
