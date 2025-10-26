import os
import threading
import sqlite3
import csv
from datetime import datetime
from io import StringIO
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6976573567, 6193535472]  # Vos IDs admin

# Flask app pour garder le service actif
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot Telegram actif!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# Base de données
def init_db():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  photo_id TEXT,
                  price REAL,
                  address TEXT,
                  payment TEXT,
                  date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_seen TEXT)''')
    conn.commit()
    conn.close()

init_db()

# État des utilisateurs
user_states = {}

# Handlers du bot
async def start(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Inconnu"
    
    # Enregistrer l'utilisateur
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users VALUES (?, ?, ?)',
              (user_id, username, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    keyboard = [[InlineKeyboardButton("📦 Nouvelle commande", callback_data='order')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 Bienvenue chez Serveur Express !\n\n"
        f"Cliquez sur le bouton ci-dessous pour passer commande.",
        reply_markup=reply_markup
    )

async def stats(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Commande réservée aux admins")
        return
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*), SUM(price) FROM orders')
    count, total = c.fetchone()
    c.execute('SELECT COUNT(*) FROM users')
    user_count = c.fetchone()[0]
    conn.close()
    
    total = total or 0
    profit = count * 5 if count else 0
    
    await update.message.reply_text(
        f"📊 **Statistiques Serveur Express**\n\n"
        f"👥 Clients: {user_count}\n"
        f"📦 Commandes: {count}\n"
        f"💰 CA total: {total:.2f}€\n"
        f"💵 Bénéfices (5€/cmd): {profit:.2f}€",
        parse_mode='Markdown'
    )

async def historique(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Commande réservée aux admins")
        return
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 10')
    orders = c.fetchall()
    conn.close()
    
    if not orders:
        await update.message.reply_text("📭 Aucune commande")
        return
    
    text = "📜 **10 dernières commandes:**\n\n"
    for order in orders:
        text += f"#{order[0]} - @{order[2]} - {order[4]:.2f}€ - {order[5][:30]}...\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def export(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Commande réservée aux admins")
        return
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('SELECT * FROM orders')
    orders = c.fetchall()
    conn.close()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'User ID', 'Username', 'Photo ID', 'Prix', 'Adresse', 'Paiement', 'Date'])
    writer.writerows(orders)
    
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8'),
        filename=f'commandes_{datetime.now().strftime("%Y%m%d")}.csv'
    )

async def broadcast(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Commande réservée aux admins")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('SELECT user_id FROM users')
    users = c.fetchall()
    conn.close()
    
    sent = 0
    for user in users:
        try:
            await context.bot.send_message(user[0], f"📢 {message}")
            sent += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Message envoyé à {sent}/{len(users)} utilisateurs")

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'order':
        user_states[query.from_user.id] = 'waiting_photo'
        await query.message.reply_text("📸 Envoyez la photo de ce que vous voulez commander")

async def handle_message(update: Update, context):
    user_id = update.effective_user.id
    state = user_states.get(user_id)
    
    if state == 'waiting_photo' and update.message.photo:
        user_states[user_id] = {'state': 'waiting_price', 'photo': update.message.photo[-1].file_id}
        await update.message.reply_text("💰 Quel est le prix ?")
    
    elif state and isinstance(state, dict) and state['state'] == 'waiting_price':
        try:
            price = float(update.message.text)
            state['price'] = price
            state['state'] = 'waiting_address'
            await update.message.reply_text("📍 Quelle est l'adresse de livraison ?")
        except:
            await update.message.reply_text("❌ Prix invalide. Entrez un nombre.")
    
    elif state and isinstance(state, dict) and state['state'] == 'waiting_address':
        state['address'] = update.message.text
        state['state'] = 'waiting_payment'
        keyboard = [[InlineKeyboardButton("💳 CB", callback_data='pay_cb'),
                    InlineKeyboardButton("💵 Espèces", callback_data='pay_cash')]]
        await update.message.reply_text("💳 Mode de paiement ?", reply_markup=InlineKeyboardMarkup(keyboard))

async def payment_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states.get(user_id)
    
    if not state or not isinstance(state, dict):
        return
    
    payment = "CB" if query.data == 'pay_cb' else "Espèces"
    username = query.from_user.username or "Inconnu"
    
    # Enregistrer la commande
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute('INSERT INTO orders VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)',
              (user_id, username, state['photo'], state['price'], 
               state['address'], payment, datetime.now().isoformat()))
    conn.commit()
    order_id = c.lastrowid
    conn.close()
    
    # Confirmation client
    await query.message.reply_text(
        f"✅ Commande #{order_id} enregistrée !\n\n"
        f"Prix: {state['price']:.2f}€\n"
        f"Adresse: {state['address']}\n"
        f"Paiement: {payment}\n\n"
        f"Nous vous contacterons bientôt !"
    )
    
    # Notification admin
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                admin_id,
                state['photo'],
                caption=f"🆕 Nouvelle commande #{order_id}\n\n"
                        f"Client: @{username}\n"
                        f"Prix: {state['price']:.2f}€\n"
                        f"Adresse: {state['address']}\n"
                        f"Paiement: {payment}"
            )
        except:
            pass
    
    del user_states[user_id]

def main():
    # Supprimer le webhook s'il existe
    import requests
    requests.get(f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook')
    print("🔧 Webhook supprimé")
    
    # Démarrer Flask dans un thread séparé
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("🌐 Flask démarré")
    
    # Application Telegram
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app_bot.add_handler(CommandHandler('start', start))
    app_bot.add_handler(CommandHandler('stats', stats))
    app_bot.add_handler(CommandHandler('historique', historique))
    app_bot.add_handler(CommandHandler('export', export))
    app_bot.add_handler(CommandHandler('broadcast', broadcast))
    app_bot.add_handler(CallbackQueryHandler(button_callback, pattern='^order$'))
    app_bot.add_handler(CallbackQueryHandler(payment_callback, pattern='^pay_'))
    app_bot.add_handler(MessageHandler(filters.ALL, handle_message))
    
    # Démarrer le bot en mode POLLING (drop_pending_updates pour éviter les conflits)
    print("🤖 Bot Telegram démarré en mode POLLING...")
    app_bot.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
