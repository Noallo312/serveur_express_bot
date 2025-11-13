import os
import threading
import sqlite3
import csv
import time
import asyncio
from datetime import datetime
from io import StringIO
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import requests

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6976573567, 6193535472]

# Flask app (doit être défini en premier pour Gunicorn)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Telegram actif !"

@app.route('/health')
def health():
    return "OK", 200

# Base de données
def init_db():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  service TEXT,
                  photo_id TEXT,
                  price REAL,
                  address TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  payment_method TEXT,
                  timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# États des utilisateurs
user_states = {}

def force_kill_all_instances():
    """Force la suppression de TOUTES les instances actives"""
    print("🔥 Forçage de la suppression de toutes les instances...")
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url, timeout=10)
        print(f"🔧 Webhook supprimé: {response.json()}")
        time.sleep(2)
        
        print("⚡ Forçage de déconnexion des autres instances...")
        for i in range(5):
            try:
                url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1&timeout=1"
                requests.get(url2, timeout=3)
                print(f"   Tentative {i+1}/5...")
                time.sleep(1)
            except:
                pass
        
        print("✅ Toutes les instances ont été forcées à se déconnecter")
        time.sleep(3)
        
    except Exception as e:
        print(f"⚠️ Erreur pendant le nettoyage: {e}")
        time.sleep(2)

# Commande /start
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🍔 Uber Eats", callback_data='service_ubereats')],
        [InlineKeyboardButton("🎵 Deezer", callback_data='service_deezer')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bonjour ! Bienvenue sur Serveur Express Bot\n\n"
        "🎯 Choisissez le service que vous souhaitez :",
        reply_markup=reply_markup
    )

# Commande /stats (admin)
async def stats(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM orders")
    total_clients = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT SUM(price) FROM orders WHERE price IS NOT NULL")
    total_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM orders WHERE service='Uber Eats'")
    ubereats_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE service='Deezer'")
    deezer_orders = c.fetchone()[0]
    
    profit = total_orders * 5
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 **Statistiques Serveur Express**\n\n"
        f"👥 Nombre de clients : {total_clients}\n"
        f"📦 Nombre de commandes : {total_orders}\n"
        f"🍔 Uber Eats : {ubereats_orders}\n"
        f"🎵 Deezer : {deezer_orders}\n"
        f"💰 Chiffre d'affaires : {total_revenue:.2f}€\n"
        f"💵 Bénéfices (5€/commande) : {profit:.2f}€",
        parse_mode='Markdown'
    )

# Commande /historique (admin)
async def historique(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("Aucune commande trouvée.")
        return
    
    message = "📜 **10 dernières commandes :**\n\n"
    for order in orders:
        if order[3] == 'Uber Eats':
            message += (
                f"🆔 #{order[0]}\n"
                f"🍔 Service : {order[3]}\n"
                f"👤 @{order[2]} (ID: {order[1]})\n"
                f"💰 Prix : {order[5]}€\n"
                f"📍 Adresse : {order[6]}\n"
                f"💳 Paiement : {order[9]}\n"
                f"🕐 {order[10]}\n\n"
            )
        else:  # Deezer
            message += (
                f"🆔 #{order[0]}\n"
                f"🎵 Service : {order[3]}\n"
                f"👤 @{order[2]} (ID: {order[1]})\n"
                f"📝 Nom : {order[7]} {order[8]}\n"
                f"💳 Paiement : {order[9]}\n"
                f"🕐 {order[10]}\n\n"
            )
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Commande /export (admin)
async def export(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT * FROM orders")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("Aucune commande à exporter.")
        return
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'User ID', 'Username', 'Service', 'Photo ID', 'Prix', 'Adresse', 'Prénom', 'Nom', 'Paiement', 'Date'])
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
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
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
    
    # Choix du service
    if query.data == 'service_ubereats':
        user_states[query.from_user.id] = {'state': 'waiting_photo', 'service': 'Uber Eats'}
        await query.message.reply_text("🍔 **Uber Eats sélectionné**\n\n📸 Envoyez la photo de votre article :")
    
    elif query.data == 'service_deezer':
        user_states[query.from_user.id] = {'state': 'waiting_firstname', 'service': 'Deezer'}
        await query.message.reply_text("🎵 **Deezer sélectionné**\n\n📝 Entrez votre prénom :")
    
    # Choix du paiement (Uber Eats)
    elif query.data in ['paypal', 'virement', 'revolut']:
        state = user_states.get(query.from_user.id)
        if state and state.get('service') == 'Uber Eats' and state['state'] == 'waiting_payment':
            payment_methods = {
                'paypal': '💳 PayPal',
                'virement': '🏦 Virement',
                'revolut': '📱 Revolut'
            }
            state['payment_method'] = payment_methods[query.data]
            
            conn = sqlite3.connect('orders.db', check_same_thread=False)
            c = conn.cursor()
            c.execute("""INSERT INTO orders (user_id, username, service, photo_id, price, address, first_name, last_name, payment_method, timestamp)
                         VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)""",
                      (query.from_user.id,
                       query.from_user.username or 'Unknown',
                       state['service'],
                       state['photo_id'],
                       state['price'],
                       state['address'],
                       state['payment_method'],
                       datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            await query.message.reply_text(
                "✅ Votre commande 🍔 **Uber Eats** a bien été envoyée ! 🎉\n\n"
                "📦 Vous recevrez le lien de suivi d'ici peu 🚚💨"
            )
            
            admin_message = (
                f"🔔 **Nouvelle commande !**\n\n"
                f"🍔 Service : Uber Eats\n"
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
            
            del user_states[query.from_user.id]
    
    # Confirmation PayPal (Deezer)
    elif query.data == 'paypal_deezer':
        state = user_states.get(query.from_user.id)
        if state and state.get('service') == 'Deezer' and state['state'] == 'waiting_payment_deezer':
            state['payment_method'] = '💳 PayPal'
            
            conn = sqlite3.connect('orders.db', check_same_thread=False)
            c = conn.cursor()
            c.execute("""INSERT INTO orders (user_id, username, service, photo_id, price, address, first_name, last_name, payment_method, timestamp)
                         VALUES (?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?)""",
                      (query.from_user.id,
                       query.from_user.username or 'Unknown',
                       state['service'],
                       state['first_name'],
                       state['last_name'],
                       state['payment_method'],
                       datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            conn.commit()
            conn.close()
            
            await query.message.reply_text(
                "✅ Votre commande 🎵 **Deezer** a bien été envoyée ! 🎉\n\n"
                "📦 Vous recevrez les informations d'ici peu 🚚💨"
            )
            
            admin_message = (
                f"🔔 **Nouvelle commande !**\n\n"
                f"🎵 Service : Deezer\n"
                f"👤 Client : @{query.from_user.username or 'Unknown'} (ID: {query.from_user.id})\n"
                f"📝 Nom : {state['first_name']} {state['last_name']}\n"
                f"💳 Paiement : {state['payment_method']}\n"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')
                except:
                    pass
            
            del user_states[query.from_user.id]

# Gestion des messages
async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    
    if not state:
        return
    
    # ===== FLUX UBER EATS =====
    if state.get('service') == 'Uber Eats':
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
    
    # ===== FLUX DEEZER =====
    elif state.get('service') == 'Deezer':
        if state['state'] == 'waiting_firstname':
            state['first_name'] = update.message.text.strip()
            state['state'] = 'waiting_lastname'
            await update.message.reply_text("📝 Entrez maintenant votre nom :")
        
        elif state['state'] == 'waiting_lastname':
            state['last_name'] = update.message.text.strip()
            state['state'] = 'waiting_payment_deezer'
            keyboard = [[InlineKeyboardButton("💳 PayPal", callback_data='paypal_deezer')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Informations enregistrées :\n"
                f"📝 {state['first_name']} {state['last_name']}\n\n"
                f"💳 Cliquez pour confirmer le paiement PayPal :",
                reply_markup=reply_markup
            )

# Fonction asynchrone pour démarrer le bot
async def run_telegram_bot():
    """Démarre le bot Telegram en mode polling avec event loop"""
    print("🤖 Initialisation du bot Telegram...")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('historique', historique))
    application.add_handler(CommandHandler('export', export))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    force_kill_all_instances()
    
    print("🤖 Bot Telegram démarré en mode POLLING...")
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
            
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
            break
        except Exception as e:
            if "Conflict" in str(e) and attempt < max_retries - 1:
                print(f"⚠️ CONFLIT DÉTECTÉ ! Nouvelle tentative dans 10 secondes... ({attempt + 1}/{max_retries})")
                await asyncio.sleep(10)
                force_kill_all_instances()
            else:
                print(f"❌ Échec après {max_retries} tentatives: {e}")
                raise

def start_telegram_bot():
    """Démarre le bot dans un nouveau event loop"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_telegram_bot())
    except Exception as e:
        print(f"❌ Erreur bot Telegram: {e}")
    finally:
        loop.close()

print("🚀 Lancement du bot Telegram en arrière-plan...")
bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
bot_thread.start()
print("🌐 Flask prêt pour Gunicorn")

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
