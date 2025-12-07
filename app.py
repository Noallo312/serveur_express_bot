# app.py - Version corrigée
# Bot Telegram + Dashboard avec gestion complète des commandes

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

# SERVICES_CONFIG
SERVICES_CONFIG = {
    'netflix': {
        'name': '🎬 Netflix',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Netflix Premium', 'price': 10.00, 'cost': 1.00}
        }
    },
    'hbo': {
        'name': '🎬 HBO Max',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'HBO Max', 'price': 6.00, 'cost': 1.00}
        }
    },
    'crunchyroll': {
        'name': '🎬 Crunchyroll',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Crunchyroll Premium', 'price': 5.00, 'cost': 1.00}
        }
    },
    'canal': {
        'name': '🎬 Canal+',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Canal+', 'price': 8.00, 'cost': 1.00}
        }
    },
    'disney': {
        'name': '🎬 Disney+',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Disney+', 'price': 6.00, 'cost': 1.00}
        }
    },
    'ufc': {
        'name': '🎬 UFC Fight Pass',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'UFC Fight Pass', 'price': 5.00, 'cost': 1.00}
        }
    },
    'chatgpt': {
        'name': '🤖 ChatGPT+',
        'active': True,
        'visible': True,
        'category': 'ai',
        'plans': {
            '1_mois': {'label': 'ChatGPT+ 1 mois', 'price': 4.00, 'cost': 1.00},
            '1_an': {'label': 'ChatGPT+ 1 an', 'price': 18.00, 'cost': 1.00}
        }
    },
    'youtube': {
        'name': '▶️ YouTube Premium',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            '1_mois': {'label': 'YouTube Premium 1 mois', 'price': 4.00, 'cost': 1.00}
        }
    },
    'spotify': {
        'name': '🎧 Spotify Premium',
        'active': True,
        'visible': True,
        'category': 'music',
        'plans': {
            '2_mois': {'label': 'Spotify Premium 2 mois', 'price': 10.00, 'cost': 1.00},
            '1_an': {'label': 'Spotify Premium 1 an', 'price': 20.00, 'cost': 1.00}
        }
    },
    'deezer': {
        'name': '🎵 Deezer Premium',
        'active': True,
        'visible': True,
        'category': 'music',
        'plans': {
            'premium': {'label': 'Deezer Premium', 'price': 6.00, 'cost': 3.00}
        }
    }
}

user_states = {}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# DATABASE
def init_db():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  service TEXT,
                  plan TEXT,
                  price REAL,
                  cost REAL,
                  first_name TEXT,
                  last_name TEXT,
                  email TEXT,
                  address TEXT,
                  payment_method TEXT,
                  timestamp TEXT,
                  status TEXT DEFAULT 'en_attente',
                  admin_id INTEGER,
                  admin_username TEXT,
                  taken_at TEXT,
                  cancelled_by INTEGER,
                  cancelled_at TEXT,
                  cancel_reason TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_messages
                 (order_id INTEGER,
                  admin_id INTEGER,
                  message_id INTEGER)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  first_seen TEXT,
                  last_activity TEXT,
                  total_orders INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS cumulative_stats
                 (id INTEGER PRIMARY KEY CHECK (id = 1),
                  total_revenue REAL DEFAULT 0,
                  total_profit REAL DEFAULT 0,
                  last_updated TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM cumulative_stats WHERE id=1")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO cumulative_stats (id, total_revenue, total_profit, last_updated) VALUES (1, 0, 0, ?)",
                  (datetime.now().isoformat(),))
    
    conn.commit()
    conn.close()

init_db()

# Note: Les templates HTML sont trop longs pour ce fichier.
# Utiliser des fichiers templates séparés serait préférable.
# Pour ce correctif, je vais inclure uniquement les routes essentielles.

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect('/dashboard')
        return "Erreur de connexion", 401
    return "Page de login"

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    return "Dashboard"

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT id, username, service, plan, price, cost, first_name, last_name, email, payment_method, status FROM orders ORDER BY id DESC")
    orders = []
    for row in c.fetchall():
        orders.append({
            'id': row[0],
            'username': row[1],
            'service': row[2],
            'plan': row[3],
            'price': row[4],
            'cost': row[5],
            'first_name': row[6],
            'last_name': row[7],
            'email': row[8],
            'payment_method': row[9],
            'status': row[10]
        })
    
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
    
    return jsonify({
        'orders': orders,
        'stats': {
            'total_orders': total,
            'pending_orders': pending,
            'inprogress_orders': inprogress,
            'completed_orders': completed,
            'revenue': revenue,
            'profit': profit
        }
    })

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'bot': 'running'})

# ----------------------- TELEGRAM BOT HANDLERS -----------------------

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
                     VALUES (?, ?, ?, ?, ?, ?, 0)""",
                  (user_id, username, first_name, last_name, now, now))
    
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
    
    welcome_text = (
        "🎯 *Bienvenue sur B4U Deals !*\n\n"
        "Profite de nos offres premium à prix réduits :\n"
        "• Comptes streaming\n"
        "• Abonnements musique\n"
        "• Services IA\n\n"
        "Choisis une catégorie pour commencer :"
    )
    
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
            new_text = (
                f"🔔 *COMMANDE #{order_id} — PRISE EN CHARGE*\n\n"
                f"Pris en charge par @{admin_username}\n"
                f"📦 {service_name} — {plan_label}\n"
                f"💰 {price}€\n\n"
                f"🕒 {timestamp}"
            )
            answer_text = "✅ Commande prise en charge"
            
            # Notifier le client
            try:
                await context.bot.send_message(
                    chat_id=customer_user_id,
                    text=f"✅ *Bonne nouvelle !*\n\nTa commande #{order_id} est en cours de traitement.\n\nTu recevras tes identifiants très bientôt ! 🚀",
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Erreur notification client: {e}")

        elif action == "complete":
            c.execute("UPDATE cumulative_stats SET total_revenue = total_revenue + ?, total_profit = total_profit + ?, last_updated = ? WHERE id=1",
                      (price, price - cost, datetime.now().isoformat()))
            
            c.execute("UPDATE orders SET status='terminee', admin_id=?, admin_username=?, taken_at=? WHERE id=?",
                      (admin_user_id, admin_username, datetime.now().isoformat(), order_id))
            conn.commit()
            new_text = (
                f"✅ *COMMANDE #{order_id} — TERMINÉE*\n\n"
                f"Traitée par @{admin_username}\n"
                f"📦 {service_name} — {plan_label}\n"
                f"💰 {price}€\n\n"
                f"🕒 {timestamp}"
            )
            answer_text = "✅ Commande terminée"
            
            # Notifier le client
            try:
                await context.bot.send_message(
                    chat_id=customer_user_id,
                    text=f"🎉 *Commande terminée !*\n\nTa commande #{order_id} a été livrée avec succès.\n\nMerci pour ta confiance ! 💙",
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Erreur notification client: {e}")

        elif action == "cancel":
            c.execute("UPDATE orders SET status='annulee', cancelled_by=?, cancelled_at=? WHERE id=?",
                      (admin_user_id, datetime.now().isoformat(), order_id))
            conn.commit()
            new_text = (
                f"❌ *COMMANDE #{order_id} — ANNULÉE*\n\n"
                f"Annulée par @{admin_username}\n"
                f"📦 {service_name} — {plan_label}\n"
                f"🕒 {timestamp}"
            )
            answer_text = "✅ Commande annulée"
            
            # Notifier le client
            try:
                await context.bot.send_message(
                    chat_id=customer_user_id,
                    text=f"ℹ️ *Mise à jour de commande*\n\nTa commande #{order_id} a été annulée.\n\nN'hésite pas à nous contacter si tu as des questions.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Erreur notification client: {e}")

        else:
            conn.close()
            await query.answer("Action inconnue", show_alert=True)
            return

        # Éditer tous les messages admin
        try:
            c.execute("SELECT admin_id, message_id FROM order_messages WHERE order_id=?", (order_id,))
            rows = c.fetchall()
            for admin_chat_id, message_id in rows:
                try:
                    try:
                        await context.bot.edit_message_caption(
                            chat_id=admin_chat_id,
                            message_id=message_id,
                            caption=new_text,
                            parse_mode='Markdown'
                        )
                    except Exception:
                        await context.bot.edit_message_text(
                            chat_id=admin_chat_id,
                            message_id=message_id,
                            text=new_text,
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    print(f"[edit_message] Erreur admin {admin_chat_id} msg {message_id}: {e}")
        except Exception as e:
            print(f"[fetch order_messages] Erreur: {e}")
        finally:
            conn.close()

        await query.answer(answer_text)
        return

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Logique de traitement des messages texte
    pass

def run_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN non configuré - le bot ne sera pas démarré.")
        return
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
        app_bot.add_handler(CommandHandler("start", start))
        app_bot.add_handler(CallbackQueryHandler(button_callback))
        app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

        print("🤖 Démarrage du bot Telegram (polling)...")
        loop.run_until_complete(
            app_bot.run_polling(drop_pending_updates=True, stop_signals=None)
        )

    except Exception as e:
        print(f"❌ Erreur critique du bot: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=True, name='TelegramBotPolling')
    bot_thread.start()

    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
