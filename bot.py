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
ADMIN_IDS = [6976573567, 6193535472, 5174507979]

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
                  timestamp TEXT,
                  status TEXT DEFAULT 'en_attente',
                  admin_id INTEGER,
                  admin_username TEXT,
                  taken_at TEXT)''')
    
    # Ajouter les colonnes si elles n'existent pas (pour migration)
    try:
        c.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'en_attente'")
    except:
        pass
    try:
        c.execute("ALTER TABLE orders ADD COLUMN admin_id INTEGER")
    except:
        pass
    try:
        c.execute("ALTER TABLE orders ADD COLUMN admin_username TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE orders ADD COLUMN taken_at TEXT")
    except:
        pass
    
    conn.commit()
    conn.close()

init_db()

# États des utilisateurs
user_states = {}

def force_kill_all_instances():
    """Force la suppression de TOUTES les instances actives"""
    print("🔥 Forçage de la suppression de toutes les instances...")
    
    try:
        # Supprimer le webhook ET les mises à jour en attente
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url, timeout=10)
        print(f"🔧 Webhook supprimé: {response.json()}")
        time.sleep(3)
        
        # Forcer la lecture de TOUTES les mises à jour en attente
        print("⚡ Vidage des mises à jour en attente...")
        for i in range(10):
            try:
                url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1&timeout=1"
                resp = requests.get(url2, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('result'):
                        # Obtenir le dernier update_id et le confirmer
                        last_id = max([u['update_id'] for u in data['result']])
                        url3 = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id+1}&timeout=1"
                        requests.get(url3, timeout=5)
                print(f"   Nettoyage {i+1}/10...")
                time.sleep(1)
            except Exception as e:
                print(f"   Erreur nettoyage: {e}")
                pass
        
        print("✅ Toutes les instances ont été forcées à se déconnecter")
        time.sleep(5)
        
    except Exception as e:
        print(f"⚠️ Erreur pendant le nettoyage: {e}")
        time.sleep(3)

# Commande /start
async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("🍔 Uber Eats", callback_data='service_ubereats')],
        [InlineKeyboardButton("🎵 Deezer", callback_data='service_deezer')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bonjour ! Bienvenue sur Serveur Express Bot\n\n"
        "🎯 Choisissez le service que vous souhaitez :\n\n"
        "💡 Tapez /help pour voir toutes les commandes disponibles",
        reply_markup=reply_markup
    )

# Commande /help
async def help_command(update: Update, context):
    user_id = update.effective_user.id
    is_admin = user_id in ADMIN_IDS
    
    if is_admin:
        message = (
            "📋 **COMMANDES DISPONIBLES**\n\n"
            "👤 **Commandes utilisateur :**\n"
            "/start - Démarrer le bot et passer une commande\n"
            "/help - Afficher cette aide\n\n"
            "👨‍💼 **Commandes administrateur :**\n"
            "/stats - Afficher les statistiques complètes\n"
            "/disponibles - Voir les commandes disponibles à prendre\n"
            "/encours - Voir les commandes en attente/en cours\n"
            "/historique - Voir les 10 dernières commandes\n"
            "/export - Exporter toutes les commandes en CSV\n"
            "/broadcast [message] - Envoyer un message à tous les clients\n\n"
            "🔔 **Fonctionnalités :**\n"
            "• Commandes Uber Eats (20-23€)\n"
            "• Comptes Deezer Premium\n"
            "• Suivi en temps réel\n"
            "• Paiement : PayPal, Virement, Revolut"
        )
    else:
        message = (
            "📋 **COMMANDES DISPONIBLES**\n\n"
            "/start - Démarrer le bot et passer une commande\n"
            "/help - Afficher cette aide\n\n"
            "🍔 **Uber Eats** - Commandes de 20€ à 23€\n"
            "🎵 **Deezer** - Comptes Premium\n\n"
            "💳 **Modes de paiement :**\n"
            "• PayPal\n"
            "• Virement bancaire\n"
            "• Revolut\n\n"
            "📦 Vous recevrez votre commande rapidement !"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

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
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_attente'")
    pending_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_cours'")
    in_progress_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='terminee'")
    completed_orders = c.fetchone()[0]
    
    profit = total_orders * 5
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 **Statistiques Serveur Express**\n\n"
        f"👥 Nombre de clients : {total_clients}\n"
        f"📦 Nombre de commandes : {total_orders}\n"
        f"🍔 Uber Eats : {ubereats_orders}\n"
        f"🎵 Deezer : {deezer_orders}\n\n"
        f"📋 Statuts :\n"
        f"⏳ En attente : {pending_orders}\n"
        f"🔄 En cours : {in_progress_orders}\n"
        f"✅ Terminées : {completed_orders}\n\n"
        f"💰 Chiffre d'affaires : {total_revenue:.2f}€\n"
        f"💵 Bénéfices (5€/commande) : {profit:.2f}€",
        parse_mode='Markdown'
    )

# Commande /encours (admin) - voir commandes en attente
async def encours(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT id, user_id, username, service, price, address, first_name, last_name, 
                        payment_method, timestamp, status, admin_username 
                 FROM orders 
                 WHERE status IN ('en_attente', 'en_cours')
                 ORDER BY id DESC""")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("✅ Aucune commande en attente ou en cours.")
        return
    
    message = "📋 **Commandes en attente/cours :**\n\n"
    for order in orders:
        status_emoji = "⏳" if order[10] == "en_attente" else "🔄"
        admin_info = f"\n👨‍💼 Pris par : @{order[11]}" if order[11] else ""
        
        if order[3] == 'Uber Eats':
            message += (
                f"{status_emoji} **#{order[0]}**\n"
                f"🍔 Uber Eats\n"
                f"👤 @{order[2]} (ID: {order[1]})\n"
                f"💰 {order[4]}€\n"
                f"📍 {order[5]}\n"
                f"💳 {order[8]}{admin_info}\n"
                f"🕐 {order[9]}\n\n"
            )
        else:
            message += (
                f"{status_emoji} **#{order[0]}**\n"
                f"🎵 Deezer\n"
                f"👤 @{order[2]} (ID: {order[1]})\n"
                f"📝 {order[6]} {order[7]}\n"
                f"💳 {order[8]}{admin_info}\n"
                f"🕐 {order[9]}\n\n"
            )
    
    await update.message.reply_text(message, parse_mode='Markdown')

# Commande /disponibles (admin) - voir uniquement les commandes disponibles
async def disponibles(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT id, user_id, username, service, photo_id, price, address, first_name, last_name, 
                        payment_method, timestamp 
                 FROM orders 
                 WHERE status='en_attente'
                 ORDER BY id DESC""")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("✅ Aucune commande disponible pour le moment.")
        return
    
    await update.message.reply_text(f"🛒 **{len(orders)} commande(s) disponible(s) :**\n")
    
    for order in orders:
        if order[3] == 'Uber Eats':
            message = (
                f"⏳ **Commande #{order[0]} - Uber Eats**\n\n"
                f"👤 Client : @{order[2]} (ID: {order[1]})\n"
                f"💰 Prix : {order[5]}€\n"
                f"📍 Adresse : {order[6]}\n"
                f"💳 Paiement : {order[9]}\n"
                f"🕐 {order[10]}"
            )
            
            keyboard = [
                [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order[0]}')],
                [InlineKeyboardButton("✅ Terminer directement", callback_data=f'complete_order_{order[0]}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
            if order[4]:  # Si photo existe
                try:
                    await update.message.reply_photo(photo=order[4])
                except:
                    pass
        
        else:  # Deezer
            message = (
                f"⏳ **Commande #{order[0]} - Deezer**\n\n"
                f"👤 Client : @{order[2]} (ID: {order[1]})\n"
                f"📝 Nom : {order[7]} {order[8]}\n"
                f"💳 Paiement : {order[9]}\n"
                f"🕐 {order[10]}"
            )
            
            keyboard = [
                [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order[0]}')],
                [InlineKeyboardButton("✅ Terminer directement", callback_data=f'complete_order_{order[0]}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

# Commande /historique (admin)
async def historique(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT id, user_id, username, service, price, address, first_name, last_name, 
                        payment_method, timestamp, status, admin_username 
                 FROM orders 
                 ORDER BY id DESC LIMIT 10""")
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("Aucune commande trouvée.")
        return
    
    message = "📜 **10 dernières commandes :**\n\n"
    for order in orders:
        status_map = {
            "en_attente": "⏳ En attente",
            "en_cours": "🔄 En cours",
            "terminee": "✅ Terminée"
        }
        status_text = status_map.get(order[10], order[10])
        admin_info = f" (@{order[11]})" if order[11] else ""
        
        if order[3] == 'Uber Eats':
            message += (
                f"🆔 #{order[0]} - {status_text}{admin_info}\n"
                f"🍔 Uber Eats\n"
                f"👤 @{order[2]} (ID: {order[1]})\n"
                f"💰 {order[4]}€\n"
                f"📍 {order[5]}\n"
                f"💳 {order[8]}\n"
                f"🕐 {order[9]}\n\n"
            )
        else:
            message += (
                f"🆔 #{order[0]} - {status_text}{admin_info}\n"
                f"🎵 Deezer\n"
                f"👤 @{order[2]} (ID: {order[1]})\n"
                f"📝 {order[6]} {order[7]}\n"
                f"💳 {order[8]}\n"
                f"🕐 {order[9]}\n\n"
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
    writer.writerow(['ID', 'User ID', 'Username', 'Service', 'Photo ID', 'Prix', 'Adresse', 
                     'Prénom', 'Nom', 'Paiement', 'Date', 'Status', 'Admin ID', 'Admin Username', 'Taken At'])
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
        await query.message.reply_text("📸 Envoyez la photo de votre article :")
    
    elif query.data == 'service_deezer':
        user_states[query.from_user.id] = {'state': 'waiting_firstname', 'service': 'Deezer'}
        await query.message.reply_text("📝 Entrez votre prénom :")
    
    # Admin prend en charge une commande
    elif query.data.startswith('take_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT status, admin_username FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        if result[0] == 'en_cours':
            await query.answer(f"⚠️ Déjà prise en charge par @{result[1]}", show_alert=True)
            conn.close()
            return
        
        c.execute("""UPDATE orders 
                     SET status='en_cours', admin_id=?, admin_username=?, taken_at=?
                     WHERE id=?""",
                  (query.from_user.id, query.from_user.username or str(query.from_user.id),
                   datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
        conn.commit()
        conn.close()
        
        # Modifier les boutons pour afficher "Terminer" et "Remettre en ligne"
        keyboard = [
            [InlineKeyboardButton("✅ Terminer", callback_data=f'complete_order_{order_id}')],
            [InlineKeyboardButton("🔄 Remettre en ligne", callback_data=f'release_order_{order_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                query.message.text + f"\n\n🔄 **En cours par @{query.from_user.username or query.from_user.id}**",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except:
            pass
        
        await query.answer(f"✅ Commande #{order_id} prise en charge !", show_alert=True)
    
    # Admin termine une commande
    elif query.data.startswith('complete_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT admin_id FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        # Vérifier que c'est bien l'admin qui a pris la commande
        if result[0] and result[0] != query.from_user.id:
            await query.answer("⚠️ Seul l'admin en charge peut terminer cette commande.", show_alert=True)
            conn.close()
            return
        
        c.execute("UPDATE orders SET status='terminee' WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
        
        try:
            await query.edit_message_text(
                query.message.text.split('\n\n🔄')[0] + f"\n\n✅ **Terminée par @{query.from_user.username or query.from_user.id}**",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await query.answer(f"✅ Commande #{order_id} marquée comme terminée !", show_alert=True)
    
    # Admin remet une commande en ligne
    elif query.data.startswith('release_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT admin_id FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        # Vérifier que c'est bien l'admin qui a pris la commande
        if result[0] != query.from_user.id:
            await query.answer("⚠️ Seul l'admin en charge peut remettre cette commande en ligne.", show_alert=True)
            conn.close()
            return
        
        c.execute("""UPDATE orders 
                     SET status='en_attente', admin_id=NULL, admin_username=NULL, taken_at=NULL
                     WHERE id=?""", (order_id,))
        conn.commit()
        conn.close()
        
        # Remettre les boutons d'origine
        keyboard = [
            [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order_id}')],
            [InlineKeyboardButton("✅ Terminer", callback_data=f'complete_order_{order_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                query.message.text.split('\n\n🔄')[0] + f"\n\n🔄 **Remise en ligne par @{query.from_user.username or query.from_user.id}**",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except:
            pass
        
        await query.answer(f"🔄 Commande #{order_id} remise en ligne !", show_alert=True)
    
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
            c.execute("""INSERT INTO orders (user_id, username, service, photo_id, price, address, first_name, last_name, payment_method, timestamp, status)
                         VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, 'en_attente')""",
                      (query.from_user.id,
                       query.from_user.username or 'Unknown',
                       state['service'],
                       state['photo_id'],
                       state['price'],
                       state['address'],
                       state['payment_method'],
                       datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            order_id = c.lastrowid
            conn.commit()
            conn.close()
            
            await query.message.reply_text(
                "✅ Votre commande 🍔 **Uber Eats** a bien été envoyée ! 🎉\n\n"
                "📦 Vous recevrez le lien de suivi d'ici peu 🚚💨"
            )
            
            admin_message = (
                f"🔔 **Nouvelle commande #{order_id}**\n\n"
                f"🍔 Service : Uber Eats\n"
                f"👤 Client : @{query.from_user.username or 'Unknown'} (ID: {query.from_user.id})\n"
                f"💰 Prix : {state['price']}€\n"
                f"📍 Adresse : {state['address']}\n"
                f"💳 Paiement : {state['payment_method']}\n"
            )
            
            keyboard = [
                [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order_id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_message, 
                                                   parse_mode='Markdown', reply_markup=reply_markup)
                    await context.bot.send_photo(chat_id=admin_id, photo=state['photo_id'])
                except:
                    pass
            
            del user_states[query.from_user.id]
    
    # Choix du paiement (Deezer)
    elif query.data in ['paypal_deezer', 'virement_deezer', 'revolut_deezer']:
        state = user_states.get(query.from_user.id)
        if state and state.get('service') == 'Deezer' and state['state'] == 'waiting_payment_deezer':
            payment_methods = {
                'paypal_deezer': '💳 PayPal',
                'virement_deezer': '🏦 Virement',
                'revolut_deezer': '📱 Revolut'
            }
            state['payment_method'] = payment_methods[query.data]
            
            conn = sqlite3.connect('orders.db', check_same_thread=False)
            c = conn.cursor()
            c.execute("""INSERT INTO orders (user_id, username, service, photo_id, price, address, first_name, last_name, payment_method, timestamp, status)
                         VALUES (?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, 'en_attente')""",
                      (query.from_user.id,
                       query.from_user.username or 'Unknown',
                       state['service'],
                       state['first_name'],
                       state['last_name'],
                       state['payment_method'],
                       datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            order_id = c.lastrowid
            conn.commit()
            conn.close()
            
            await query.message.reply_text(
                "✅ Votre commande 🎵 **Deezer** a bien été envoyée ! 🎉\n\n"
                "📦 Vous recevrez les informations d'ici peu 🚚💨"
            )
            
            admin_message = (
                f"🔔 **Nouvelle commande #{order_id}**\n\n"
                f"🎵 Service : Deezer\n"
                f"👤 Client : @{query.from_user.username or 'Unknown'} (ID: {query.from_user.id})\n"
                f"📝 Nom : {state['first_name']} {state['last_name']}\n"
                f"💳 Paiement : {state['payment_method']}\n"
            )
            
            keyboard = [
                [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order_id}')],
                [InlineKeyboardButton("✅ Terminer", callback_data=f'complete_order_{order_id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(chat_id=admin_id, text=admin_message, 
                                                   parse_mode='Markdown', reply_markup=reply_markup)
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
            keyboard = [
                [InlineKeyboardButton("💳 PayPal", callback_data='paypal_deezer')],
                [InlineKeyboardButton("🏦 Virement", callback_data='virement_deezer')],
                [InlineKeyboardButton("📱 Revolut", callback_data='revolut_deezer')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"✅ Informations enregistrées :\n"
                f"📝 {state['first_name']} {state['last_name']}\n\n"
                f"💳 Choisissez votre mode de paiement :",
                reply_markup=reply_markup
            )

# Fonction asynchrone pour démarrer le bot
async def run_telegram_bot():
    """Démarre le bot Telegram en mode polling avec event loop"""
    print("🤖 Initialisation du bot Telegram...")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Enregistrer toutes les commandes
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('encours', encours))
    application.add_handler(CommandHandler('disponibles', disponibles))
    application.add_handler(CommandHandler('historique', historique))
    application.add_handler(CommandHandler('export', export))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    
    force_kill_all_instances()
    
    print("🤖 Bot Telegram démarré en mode POLLING...")
    
    max_retries = 3
    retry_delay = 15
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Tentative de connexion {attempt + 1}/{max_retries}...")
            
            await application.initialize()
            await application.start()
            
            # Configuration du polling avec paramètres optimisés
            await application.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
                timeout=10,
                bootstrap_retries=-1,
                read_timeout=10,
                write_timeout=10,
                connect_timeout=10,
                pool_timeout=10
            )
            
            print("✅ Bot Telegram connecté avec succès!")
            
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, SystemExit):
                print("🛑 Arrêt du bot...")
            finally:
                print("🔄 Nettoyage en cours...")
                await application.updater.stop()
                await application.stop()
                await application.shutdown()
                print("✅ Bot arrêté proprement")
            break
            
        except Exception as e:
            error_msg = str(e)
            if "Conflict" in error_msg:
                print(f"⚠️ CONFLIT DÉTECTÉ (tentative {attempt + 1}/{max_retries})")
                print(f"   Une autre instance du bot est probablement active.")
                
                if attempt < max_retries - 1:
                    print(f"   ⏳ Attente de {retry_delay} secondes avant nouvelle tentative...")
                    await asyncio.sleep(retry_delay)
                    print(f"   🔥 Nettoyage forcé des instances...")
                    force_kill_all_instances()
                else:
                    print("❌ Échec après toutes les tentatives.")
                    print("💡 SOLUTION : Arrêtez toutes les autres instances du bot (Render, local, etc.)")
                    raise
            else:
                print(f"❌ Erreur inattendue: {error_msg}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                else:
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
