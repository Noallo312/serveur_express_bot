# app.py - Version complète et fonctionnelle
import os
import sqlite3
import requests
import random
import traceback
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from functools import wraps
import threading

BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_IMAGE_URL = os.getenv('BOT_IMAGE_URL', 'https://raw.githubusercontent.com/Noallo312/serveur_express_bot/refs/heads/main/514B1CC0-791F-47CA-825C-F82A4100C02E.png')
ADMIN_IDS = [6976573567, 5174507979]
WEB_PASSWORD = os.getenv('WEB_PASSWORD')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'votre_secret_key_aleatoire_ici')

SERVICES_CONFIG = {
    'netflix': {'name': '🎬 Netflix', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'standard': {'label': 'Netflix Premium', 'price': 10.00, 'cost': 1.00}}},
    'hbo': {'name': '🎬 HBO Max', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'standard': {'label': 'HBO Max', 'price': 6.00, 'cost': 1.00}}},
    'crunchyroll': {'name': '🎬 Crunchyroll', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'standard': {'label': 'Crunchyroll Premium', 'price': 5.00, 'cost': 1.00}}},
    'canal': {'name': '🎬 Canal+', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'standard': {'label': 'Canal+', 'price': 8.00, 'cost': 1.00}}},
    'disney': {'name': '🎬 Disney+', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'standard': {'label': 'Disney+', 'price': 6.00, 'cost': 1.00}}},
    'ufc': {'name': '🎬 UFC Fight Pass', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'standard': {'label': 'UFC Fight Pass', 'price': 5.00, 'cost': 1.00}}},
    'chatgpt': {'name': '🤖 ChatGPT+', 'active': True, 'visible': True, 'category': 'ai',
        'plans': {'1_mois': {'label': 'ChatGPT+ 1 mois', 'price': 4.00, 'cost': 1.00},
                  '1_an': {'label': 'ChatGPT+ 1 an', 'price': 18.00, 'cost': 1.00}}},
    'youtube': {'name': '▶️ YouTube Premium', 'active': True, 'visible': True, 'category': 'streaming',
        'plans': {'1_mois': {'label': 'YouTube Premium 1 mois', 'price': 4.00, 'cost': 1.00}}},
    'spotify': {'name': '🎧 Spotify Premium', 'active': True, 'visible': True, 'category': 'music',
        'plans': {'2_mois': {'label': 'Spotify Premium 2 mois', 'price': 10.00, 'cost': 1.00},
                  '1_an': {'label': 'Spotify Premium 1 an', 'price': 20.00, 'cost': 1.00}}},
    'deezer': {'name': '🎵 Deezer Premium', 'active': True, 'visible': True, 'category': 'music',
        'plans': {'premium': {'label': 'Deezer Premium', 'price': 6.00, 'cost': 3.00}}}
}

user_states = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, service TEXT,
                  plan TEXT, price REAL, cost REAL, first_name TEXT, last_name TEXT, email TEXT,
                  address TEXT, payment_method TEXT, timestamp TEXT, status TEXT DEFAULT 'en_attente',
                  admin_id INTEGER, admin_username TEXT, taken_at TEXT, cancelled_by INTEGER,
                  cancelled_at TEXT, cancel_reason TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS order_messages (order_id INTEGER, admin_id INTEGER, message_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT,
                  first_seen TEXT, last_activity TEXT, total_orders INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cumulative_stats
                 (id INTEGER PRIMARY KEY CHECK (id = 1), total_revenue REAL DEFAULT 0,
                  total_profit REAL DEFAULT 0, last_updated TEXT)''')
    c.execute("SELECT COUNT(*) FROM cumulative_stats WHERE id=1")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO cumulative_stats (id, total_revenue, total_profit, last_updated) VALUES (1, 0, 0, ?)",
                  (datetime.now().isoformat(),))
    conn.commit()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect('/dashboard')
        return "Erreur de connexion", 401
    return "<h1>Login Page</h1><form method='POST'><input type='password' name='password'><button>Login</button></form>"

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    return "<h1>Dashboard</h1><a href='/logout'>Logout</a>"

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("SELECT id, username, service, plan, price, cost, first_name, last_name, email, payment_method, status FROM orders ORDER BY id DESC")
    orders = [{'id': r[0], 'username': r[1], 'service': r[2], 'plan': r[3], 'price': r[4],
               'cost': r[5], 'first_name': r[6], 'last_name': r[7], 'email': r[8],
               'payment_method': r[9], 'status': r[10]} for r in c.fetchall()]
    c.execute("SELECT COUNT(*) FROM orders")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_attente'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_cours'")
    inprogress = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='terminee'")
    completed = c.fetchone()[0]
    c.execute("SELECT total_revenue, total_profit FROM cumulative_stats WHERE id=1")
    cumul = c.fetchone()
    revenue = cumul[0] if cumul else 0
    profit = cumul[1] if cumul else 0
    conn.close()
    return jsonify({'orders': orders, 'stats': {'total_orders': total, 'pending_orders': pending,
                    'inprogress_orders': inprogress, 'completed_orders': completed,
                    'revenue': revenue, 'profit': profit}})

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'bot': 'running'})

def update_user_activity(user_id, username, first_name, last_name):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if c.fetchone():
        c.execute("UPDATE users SET last_activity=?, username=?, first_name=?, last_name=? WHERE user_id=?",
                  (now, username, first_name, last_name, user_id))
    else:
        c.execute("""INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_activity, total_orders)
                     VALUES (?, ?, ?, ?, ?, ?, 0)""", (user_id, username, first_name, last_name, now, now))
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"User_{user_id}"
    first_name = update.message.from_user.first_name or "Utilisateur"
    last_name = update.message.from_user.last_name or ""
    update_user_activity(user_id, username, first_name, last_name)
    
    keyboard = [
        [InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],
        [InlineKeyboardButton("🎧 Musique (Spotify, Deezer)", callback_data="cat_music")],
        [InlineKeyboardButton("🤖 IA (ChatGPT+)", callback_data="cat_ai")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = ("🎯 *Bienvenue sur B4U Deals !*\n\n"
                    "Profite de nos offres premium à prix réduits :\n"
                    "• Comptes streaming\n• Abonnements musique\n• Services IA\n\n"
                    "Choisis une catégorie pour commencer :")
    
    if BOT_IMAGE_URL:
        try:
            await update.message.reply_photo(photo=BOT_IMAGE_URL, caption=welcome_text, 
                                            parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            print(f"Erreur envoi photo: {e}")
            await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or f"User_{user_id}"
    first_name = query.from_user.first_name or "Utilisateur"
    last_name = query.from_user.last_name or ""
    update_user_activity(user_id, username, first_name, last_name)
    
    # Gestion des catégories
    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        keyboard = []
        for service_key, service_data in SERVICES_CONFIG.items():
            if service_data['active'] and service_data.get('visible', True) and service_data['category'] == category:
                keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
        keyboard.append([InlineKeyboardButton("⬅️ Retour au menu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        category_labels = {'streaming': '🎬 Streaming', 'music': '🎧 Musique', 'ai': '🤖 Intelligence Artificielle'}
        await query.edit_message_text(f"*{category_labels.get(category, category)}*\n\nChoisis ton service :",
                                      parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Gestion des services
    if data.startswith("service_"):
        service_key = data.replace("service_", "")
        service = SERVICES_CONFIG[service_key]
        keyboard = []
        for plan_key, plan_data in service['plans'].items():
            keyboard.append([InlineKeyboardButton(f"{plan_data['label']} - {plan_data['price']}€",
                                                  callback_data=f"plan_{service_key}_{plan_key}")])
        keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data=f"cat_{service['category']}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"*{service['name']}*\n\nChoisis ton abonnement :",
                                      parse_mode='Markdown', reply_markup=reply_markup)
        return
    
    # Gestion des plans
    if data.startswith("plan_"):
        parts = data.replace("plan_", "").split("_")
        service_key = parts[0]
        plan_key = "_".join(parts[1:])
        service = SERVICES_CONFIG[service_key]
        plan = service['plans'][plan_key]
        
        user_states[user_id] = {
            'service': service_key, 'plan': plan_key, 'service_name': service['name'],
            'plan_label': plan['label'], 'price': plan['price'], 'cost': plan['cost'],
            'step': 'waiting_deezer_form' if service_key == 'deezer' else 'waiting_form'
        }
        
        if service_key == 'deezer':
            await query.edit_message_text(
                f"✅ *Commande confirmée*\n\nService: {service['name']}\nPlan: {plan['label']}\nPrix: {plan['price']}€\n\n"
                f"📝 Envoie ton nom, prénom et mail (chacun sur une ligne)", parse_mode='Markdown')
        else:
            form_text = (f"✅ *{plan['label']} - {plan['price']}€*\n\n📝 *Formulaire de commande*\n\n"
                        "Envoie-moi les informations suivantes (une par ligne) :\n\n"
                        "1️⃣ Nom\n2️⃣ Prénom\n3️⃣ Adresse email\n4️⃣ Moyen de paiement (PayPal / Virement / Revolut)\n\n"
                        "📌 Exemple :\nDupont\nJean\njean.dupont@email.com\nPayPal")
            await query.edit_message_text(form_text, parse_mode='Markdown')
        return
    
    # Retour au menu
    if data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],
            [InlineKeyboardButton("🎧 Musique (Spotify, Deezer)", callback_data="cat_music")],
            [InlineKeyboardButton("🤖 IA (ChatGPT+)", callback_data="cat_ai")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎯 *B4U Deals*\n\nChoisis une catégorie :",
                                      parse_mode='Markdown', reply_markup=reply_markup)
        return

    # Gestion admin
    if data.startswith("admin_"):
        parts = data.split("_")
        if len(parts) < 3:
            await query.answer("Données invalides", show_alert=True)
            return
        action = parts[1]
        try:
            order_id = int(parts[2])
        except ValueError:
            await query.answer("ID invalide", show_alert=True)
            return

        admin_user_id = query.from_user.id
        admin_username = query.from_user.username or (query.from_user.first_name or "").strip()
        if admin_user_id not in ADMIN_IDS:
            await query.answer("Non autorisé", show_alert=True)
            return

        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT service, plan, price, cost, user_id FROM orders WHERE id=?", (order_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            await query.answer("Commande introuvable", show_alert=True)
            return
        service_name, plan_label, price, cost, customer_user_id = row
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        if action == "take":
            c.execute("UPDATE orders SET status='en_cours', admin_id=?, admin_username=?, taken_at=? WHERE id=?",
                      (admin_user_id, admin_username, datetime.now().isoformat(), order_id))
            conn.commit()
            new_text = (f"🔔 *COMMANDE #{order_id} — PRISE EN CHARGE*\n\n"
                       f"Pris en charge par @{admin_username}\n📦 {service_name} — {plan_label}\n💰 {price}€\n\n🕒 {timestamp}")
            answer_text = "✅ Commande prise en charge"
            try:
                await context.bot.send_message(chat_id=customer_user_id,
                    text=f"✅ *Bonne nouvelle !*\n\nTa commande #{order_id} est en cours de traitement.\n\n"
                         f"Tu recevras tes identifiants très bientôt ! 🚀", parse_mode='Markdown')
            except Exception as e:
                print(f"Erreur notification client: {e}")

        elif action == "complete":
            c.execute("UPDATE cumulative_stats SET total_revenue = total_revenue + ?, total_profit = total_profit + ?, last_updated = ? WHERE id=1",
                      (price, price - cost, datetime.now().isoformat()))
            c.execute("UPDATE orders SET status='terminee', admin_id=?, admin_username=?, taken_at=? WHERE id=?",
                      (admin_user_id, admin_username, datetime.now().isoformat(), order_id))
            conn.commit()
            new_text = (f"✅ *COMMANDE #{order_id} — TERMINÉE*\n\n"
                       f"Traitée par @{admin_username}\n📦 {service_name} — {plan_label}\n💰 {price}€\n\n🕒 {timestamp}")
            answer_text = "✅ Commande terminée"
            try:
                await context.bot.send_message(chat_id=customer_user_id,
                    text=f"🎉 *Commande terminée !*\n\nTa commande #{order_id} a été livrée avec succès.\n\n"
                         f"Merci pour ta confiance ! 💙", parse_mode='Markdown')
            except Exception as e:
                print(f"Erreur notification client: {e}")

        elif action == "cancel":
            c.execute("UPDATE orders SET status='annulee', cancelled_by=?, cancelled_at=? WHERE id=?",
                      (admin_user_id, datetime.now().isoformat(), order_id))
            conn.commit()
            new_text = (f"❌ *COMMANDE #{order_id} — ANNULÉE*\n\n"
                       f"Annulée par @{admin_username}\n📦 {service_name} — {plan_label}\n🕒 {timestamp}")
            answer_text = "✅ Commande annulée"
            try:
                await context.bot.send_message(chat_id=customer_user_id,
                    text=f"ℹ️ *Mise à jour de commande*\n\nTa commande #{order_id} a été annulée.\n\n"
                         f"N'hésite pas à nous contacter si tu as des questions.", parse_mode='Markdown')
            except Exception as e:
                print(f"Erreur notification client: {e}")
        else:
            conn.close()
            await query.answer("Action inconnue", show_alert=True)
            return

        try:
            c.execute("SELECT admin_id, message_id FROM order_messages WHERE order_id=?", (order_id,))
            for admin_chat_id, message_id in c.fetchall():
                try:
                    try:
                        await context.bot.edit_message_caption(chat_id=admin_chat_id, message_id=message_id,
                                                              caption=new_text, parse_mode='Markdown')
                    except:
                        await context.bot.edit_message_text(chat_id=admin_chat_id, message_id=message_id,
                                                           text=new_text, parse_mode='Markdown')
                except Exception as e:
                    print(f"Erreur edit message: {e}")
        except Exception as e:
            print(f"Erreur fetch messages: {e}")
        finally:
            conn.close()
        await query.answer(answer_text)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"User_{user_id}"
    first_name_tg = update.message.from_user.first_name or ""
    last_name_tg = update.message.from_user.last_name or ""
    text = update.message.text
    update_user_activity(user_id, username, first_name_tg, last_name_tg)
    
    if user_id not in user_states:
        await update.message.reply_text("❌ Aucune commande en cours.\n\nUtilise /start pour commencer.")
        return
    
    state = user_states[user_id]
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    
    # Deezer (3 infos)
    if state.get('step') == 'waiting_deezer_form':
        if len(lines) < 3:
            await update.message.reply_text("❌ Envoie les 3 informations : Nom, Prénom, Mail")
            return
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("""INSERT INTO orders (user_id, username, service, plan, price, cost, timestamp, status,
                     first_name, last_name, email) VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?, ?)""",
                  (user_id, username, state['service_name'], state['plan_label'], state['price'], state['cost'],
                   datetime.now().isoformat(), lines[1].strip(), lines[0].strip(), lines[2].strip()))
        order_id = c.lastrowid
        c.execute("UPDATE users SET total_orders = total_orders + 1, last_activity = ? WHERE user_id = ?",
                  (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
    
    # Autres services (4 infos)
    elif state.get('step') == 'waiting_form':
        if len(lines) < 4:
            await update.message.reply_text("❌ Il me faut les 4 informations : Nom, Prénom, Email, Moyen de paiement")
            return
        if '@' not in lines[2]:
            await update.message.reply_text("❌ Email invalide")
            return
        if lines[3].lower() not in ['paypal', 'virement', 'revolut']:
            await update.message.reply_text("❌ Moyen de paiement invalide (PayPal, Virement, Revolut)")
            return
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("""INSERT INTO orders (user_id, username, service, plan, price, cost, timestamp, status,
                     first_name, last_name, email, payment_method) VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?, ?, ?)""",
                  (user_id, username, state['service_name'], state['plan_label'], state['price'], state['cost'],
                   datetime.now().isoformat(), lines[1].strip(), lines[0].strip(), lines[2].strip(), lines[3].strip()))
        order_id = c.lastrowid
        c.execute("UPDATE users SET total_orders = total_orders + 1, last_activity = ? WHERE user_id = ?",
                  (datetime.now().isoformat(), user_id))
        conn.commit()
        conn.close()
    else:
        return
    
    # Notifier les admins
    admin_text = (f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n👤 @{username}\n"
                 f"📦 {state['service_name']}\n💰 {state['price']}€\n💵 Coût: {state['cost']}€\n"
                 f"📈 Bénéf: {state['price'] - state['cost']}€\n\n")
    if state.get('step') == 'waiting_deezer_form':
        admin_text += f"👤 {lines[1].strip()} {lines[0].strip()}\n📧 {lines[2].strip()}\n"
    else:
        admin_text += f"👤 {lines[1].strip()} {lines[0].strip()}\n📧 {lines[2].strip()}\n💳 {lines[3].strip()}\n"
    admin_text += f"🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"),
        InlineKeyboardButton("✅ Terminer", callback_data=f"admin_complete_{order_id}"),
        InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}")
    ]])
    
    for admin_id in ADMIN_IDS:
        try:
            if BOT_IMAGE_URL:
                msg = await context.bot.send_photo(chat_id=admin_id, photo=BOT_IMAGE_URL, caption=admin_text,
                                                   parse_mode='Markdown', reply_markup=keyboard)
            else:
                msg = await context.bot.send_message(chat_id=admin_id, text=admin_text,
                                                     parse_mode='Markdown', reply_markup=keyboard)
            conn2 = sqlite3.connect('orders.db', check_same_thread=False)
            c2 = conn2.cursor()
            c2.execute("INSERT INTO order_messages (order_id, admin_id, message_id) VALUES (?, ?, ?)",
                      (order_id, admin_id, msg.message_id))
            conn2.commit()
            conn2.close()
        except Exception as e:
            print(f"Erreur notification admin: {e}")
    
    confirmation = f"✅ *Commande #{order_id} enregistrée !*\n\nMerci ! 🙏"
    if BOT_IMAGE_URL:
        try:
            await update.message.reply_photo(photo=BOT_IMAGE_URL, caption=confirmation, parse_mode='Markdown')
        except:
            await update.message.reply_text(confirmation, parse_mode='Markdown')
    else:
        await update.message.reply_text(confirmation, parse_mode='Markdown')
    del user_states[user_id]

def run_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN non configuré")
        return
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CallbackQueryHandler(button_callback))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        print("🤖 Démarrage du bot Telegram...")
        loop.run_until_complete(app_bot.bot.delete_webhook(drop_pending_updates=True))
        loop.run_until_complete(app_bot.run_polling(drop_pending_updates=True, stop_signals=None))
    except Exception as e:
        print(f"❌ Erreur bot: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
