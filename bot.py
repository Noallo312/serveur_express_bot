import os
import threading
import sqlite3
import csv
import time
from datetime import datetime
from io import StringIO
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import requests

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6976573567, 6193535472]  # Vos IDs admin

# Base de données
def init_db():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  photo_id TEXT,
                  price REAL,
                  address TEXT,
                  payment_method TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# États des utilisateurs
user_states = {}

def delete_webhook():
    """Supprime le webhook et attend pour éviter les conflits"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url)
        if response.json().get('ok'):
            print("🔧 Webhook supprimé")
            time.sleep(3)  # Attendre 3 secondes pour que Telegram traite la suppression
        
        # Vérifier qu'il n'y a plus de getUpdates actifs
        url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1&timeout=1"
        requests.get(url2, timeout=2)
        print("✅ Nettoyage des updates effectué")
        time.sleep(2)
    except Exception as e:
        print(f"❌ Erreur lors de la suppression du webhook: {e}")

# Commande /start
async def start(update: Update, context):
    keyboard = [[InlineKeyboardButton("🛒 Commander", callback_data='new_order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bonjour ! Bienvenue sur Serveur Express Bot\n\n"
        "Cliquez sur le bouton ci-dessous pour passer votre commande :",
        reply_markup=reply_markup
    )

# Commande /stats (admin)
async def stats(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM orders")
    total_clients = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT SUM(price) FROM orders")
    total_revenue = c.fetchone()[0] or 0
    
    profit = total_orders * 5  # 5€ par commande
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 **Statistiques Serveur Express**\n\n"
        f"👥 Nombre de clients : {total_clients}\n"
        f"📦 Nombre de commandes : {total_orders}\n"
        f"💰 Chiffre d'affaires : {total_revenue:.2f}€\n"
        f"💵 Bénéfices (5€/commande) : {profit:.2f}€",
        parse_mode='Markdown'
    )

# Commande /historique (admin)
async def historique(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("Aucune commande trouvée.")
        return
    
    message = "📜 **10 dernières commandes :**\n\n"
    for order in orders:
        message += (
            f"🆔 #{order[0]}\n"
            f"👤 @{order[2]} (ID: {order[1]})\n"
            f"💰 Prix : {order[4]}€\n"
            f"📍 Adresse : {order[5]}\n"
            f"💳 Paiement : {order[6]}\n"
            f"🕐 {order[7]}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Commande /export (admin)
async def export(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT * FROM orders")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("Aucune commande à exporter.")
        return
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'User ID', 'Username', 'Photo ID', 'Prix', 'Adresse', 'Paiement', 'Date'])
    writer.writerows(orders)
    
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8'),
        filename=f'orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

# Commande /broadcast (admin)
async def broadcast(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage : /broadcast [message]")
        return
    
    message = ' '.join(context.args)
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT user_id FROM orders")
    users = c.fetchall()
    conn.close()
    
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user[0], text=message)
            sent += 1
        except:
            pass
    
    await update.message.reply_text(f"📢 Message envoyé à {sent} utilisateurs.")

# Gestion des boutons
async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_order':
        user_states[query.from_user.id] = {'state': 'waiting_photo'}
        await query.message.reply_text("📸 Envoyez la photo de votre article :")
    
    elif query.data in ['paypal', 'virement', 'revolut']:
        state = user_states.get(query.from_user.id)
        if state and state['state'] == 'waiting_payment':
            payment_methods = {
                'paypal': '💳 PayPal',
                'virement': '🏦 Virement',
                'revolut': '📱 Revolut'
            }
            state['payment_method'] = payment_methods[query.data]
            
            # Enregistrer dans la base
            conn = sqlite3.connect('orders.db')
            c = conn.cursor()
            c.execute("""INSERT INTO orders (user_id, username, photo_id, price, address, payment_method, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (query.from_user.id,
                       query.from_user.username or 'Unknown',
                       state['photo_id'],
                       state['price'],
                       state['address'],
                       state['payment_method'],
                       datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            # Confirmation au client
            await query.message.reply_text(
                "✅ Votre commande a bien été envoyée ! 🎉\n\n"
                "📦 Vous recevrez le lien de suivi d'ici peu 🚚💨"
            )
            
            # Notification aux admins
            admin_message = (
                f"🔔 **Nouvelle commande !**\n\n"
                f"👤 Client : @{query.from_user.username or 'Unknown'} (ID: {query.from_user.id})\n"
                f"💰 Prix : {state['price']}€\n"
                f"📍 Adresse : {state['address']}\n"
                f"💳 Paiement : {state['payment_method']}\n"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')
                    await context.bot.send_photo(chat_id=admin_id, photo=state['photo_id'])
                except:
                    pass
            
            # Réinitialiser l'état
            del user_states[query.from_user.id]

# Gestion des messages
async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    
    if not state:
        return
    
    if state['state'] == 'waiting_photo':
        if update.message.photo:
            state['photo_id'] = update.message.photo[-1].file_id
            state['state'] = 'waiting_price'
            await update.message.reply_text("💰 Indiquez le prix (entre 20€ et 23€) :")
        else:
            await update.message.reply_text("❌ Veuillez envoyer une photo.")
    
    elif state['state'] == 'waiting_price':
        try:
            price = float(update.message.text.replace('€', '').replace(',', '.').strip())
            if 20 <= price <= 23:
                state['price'] = price
                state['state'] = 'waiting_address'
                await update.message.reply_text("🏠 Entrez maintenant votre adresse :")
            else:
                await update.message.reply_text("❌ Le prix doit être entre 20€ et 23€.")
        except ValueError:
            await update.message.reply_text("❌ Prix invalide. Exemple : 21.50")
    
    elif state['state'] == 'waiting_address':
        state['address'] = update.message.text
        state['state'] = 'waiting_payment'
        keyboard = [
            [InlineKeyboardButton("💳 PayPal", callback_data='paypal')],
            [InlineKeyboardButton("🏦 Virement", callback_data='virement')],
            [InlineKeyboardButton("📱 Revolut", callback_data='revolut')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "💳 Choisissez votre mode de paiement :",
            reply_markup=reply_markup
        )

# Flask pour garder le service actif
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Telegram actif !"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Démarrage du bot
if __name__ == '__main__':
    # Démarrer Flask en arrière-plan
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask démarré")
    
    # Créer l'application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Ajouter les handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('historique', historique))
    application.add_handler(CommandHandler('export', export))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    # Supprimer webhook et nettoyer
    delete_webhook()
    
    print("🤖 Bot Telegram démarré en mode POLLING...")
    
    # Démarrer le bot avec retry sur conflit
    max_retries = 3
    for attempt in range(max_retries):
        try:
            application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
            break
        except Exception as e:
            if "Conflict" in str(e) and attempt < max_retries - 1:
                print(f"⚠️ Conflit détecté, nouvelle tentative dans 5 secondes... ({attempt + 1}/{max_retries})")
                time.sleep(5)
                delete_webhook()  # Re-nettoyer
            else:
                raise
