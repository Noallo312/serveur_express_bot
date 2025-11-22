import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from functools import wraps
import asyncio

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6976573567, 5174507979]
WEB_PASSWORD = os.getenv('WEB_PASSWORD')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://serveur-express-bot-1.onrender.com')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'votre_secret_key_aleatoire_ici')

# Variable globale pour l'application Telegram
telegram_app = None

SERVICES_CONFIG = {
    'deezer': {
        'name': '🎵 Deezer Premium',
        'active': True,
        'visible': True,
        'plans': {
            'premium': {'label': 'Premium', 'price': 10.00, 'cost': 4.00}
        }
    },
    'basicfit': {
        'name': '🏋️ Basic Fit',
        'active': True,
        'visible': True,
        'plans': {
            'abonnement': {'label': 'Abonnement Basic Fit', 'price': 10.00, 'cost': 1.00}
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

def init_db():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  username TEXT,
                  service TEXT,
                  plan TEXT,
                  photo_id TEXT,
                  price REAL,
                  cost REAL,
                  address TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  payment_method TEXT,
                  timestamp TEXT,
                  status TEXT DEFAULT 'en_attente',
                  admin_id INTEGER,
                  admin_username TEXT,
                  taken_at TEXT,
                  cancelled_by INTEGER,
                  cancelled_at TEXT,
                  cancel_reason TEXT,
                  email TEXT,
                  birth_date TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_messages
                 (order_id INTEGER,
                  admin_id INTEGER,
                  message_id INTEGER,
                  photo_message_id INTEGER)''')
    
    conn.commit()
    conn.close()

init_db()

HTML_LOGIN = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0a2540">
    <title>Connexion - B4U Deals Admin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a2540 0%, #1a4d7a 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #0a2540;
            margin-bottom: 30px;
            font-size: 28px;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            margin-bottom: 20px;
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #00d4ff 0%, #0a2540 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }
        .error {
            background: #fee;
            color: #c33;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🔐 B4U Deals Admin</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <input type="password" name="password" placeholder="Mot de passe" required autofocus>
            <button type="submit">Se connecter</button>
        </form>
    </div>
</body>
</html>
'''

HTML_DASHBOARD = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0a2540">
    <title>Dashboard - B4U Deals</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
        }
        .header {
            background: linear-gradient(135deg, #0a2540 0%, #1a4d7a 100%);
            color: white;
            padding: 15px 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .logout-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
        }
        .container {
            max-width: 1400px;
            margin: 20px auto;
            padding: 0 15px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border-left: 4px solid #00d4ff;
        }
        .stat-card h3 {
            color: #666;
            font-size: 12px;
            margin-bottom: 8px;
        }
        .stat-card .value {
            font-size: 24px;
            font-weight: bold;
            color: #0a2540;
        }
        .orders-section {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .order-card {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 4px solid #ddd;
        }
        .order-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .action-btn {
            padding: 8px 14px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            flex: 1;
            min-width: 100px;
        }
        .btn-take { background: #2196f3; color: white; }
        .btn-complete { background: #4caf50; color: white; }
        .btn-cancel { background: #f44336; color: white; }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #00d4ff;
            color: white;
            border: none;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 B4U Deals Admin</h1>
        <a href="/logout" class="logout-btn">Déconnexion</a>
    </div>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📦 TOTAL</h3>
                <div class="value" id="total-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>⏳ ATTENTE</h3>
                <div class="value" id="pending-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>🔄 COURS</h3>
                <div class="value" id="inprogress-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>✅ TERMINÉES</h3>
                <div class="value" id="completed-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>💰 CA</h3>
                <div class="value" id="revenue">0€</div>
            </div>
            <div class="stat-card">
                <h3>💵 BÉNÉF</h3>
                <div class="value" id="profit">0€</div>
            </div>
        </div>

        <div class="orders-section">
            <h2>📋 Commandes</h2>
            <div id="orders-container"></div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄</button>

    <script>
        async function loadData() {
            try {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                document.getElementById('total-orders').textContent = data.stats.total_orders;
                document.getElementById('pending-orders').textContent = data.stats.pending_orders;
                document.getElementById('inprogress-orders').textContent = data.stats.inprogress_orders;
                document.getElementById('completed-orders').textContent = data.stats.completed_orders;
                document.getElementById('revenue').textContent = data.stats.revenue.toFixed(0) + '€';
                document.getElementById('profit').textContent = data.stats.profit.toFixed(0) + '€';
                displayOrders(data.orders);
            } catch (error) {
                console.error('Erreur:', error);
            }
        }

        function displayOrders(orders) {
            const container = document.getElementById('orders-container');
            if (orders.length === 0) {
                container.innerHTML = '<p style="text-align:center;padding:40px;color:#999">Aucune commande</p>';
                return;
            }
            container.innerHTML = orders.map(order => `
                <div class="order-card">
                    <strong>#${order.id}</strong> - ${order.service} - @${order.username} - ${order.price}€
                    <div class="order-actions">
                        <button class="action-btn btn-take" onclick="takeOrder(${order.id})">✋ Prendre</button>
                        <button class="action-btn btn-complete" onclick="completeOrder(${order.id})">✅ Terminer</button>
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌ Annuler</button>
                    </div>
                </div>
            `).join('');
        }

        async function takeOrder(orderId) {
            await fetch(`/api/order/${orderId}/take`, { method: 'POST' });
            loadData();
        }

        async function completeOrder(orderId) {
            await fetch(`/api/order/${orderId}/complete`, { method: 'POST' });
            loadData();
        }

        async function cancelOrder(orderId) {
            await fetch(`/api/order/${orderId}/cancel`, { method: 'POST' });
            loadData();
        }

        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect('/dashboard')
        return render_template_string(HTML_LOGIN, error="Mot de passe incorrect")
    return render_template_string(HTML_LOGIN)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect('/login')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template_string(HTML_DASHBOARD)

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = []
    for row in c.fetchall():
        orders.append({
            'id': row[0],
            'username': row[2],
            'service': row[3],
            'plan': row[4],
            'price': row[6],
            'cost': row[7],
            'status': row[13]
        })
    
    c.execute("SELECT COUNT(*) FROM orders")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_attente'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_cours'")
    inprogress = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='terminee'")
    completed = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(price), 0) FROM orders WHERE status='terminee'")
    revenue = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(price - cost), 0) FROM orders WHERE status='terminee'")
    profit = c.fetchone()[0]
    
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

@app.route('/api/order/<int:order_id>/take', methods=['POST'])
@login_required
def take_order(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET status='en_cours', taken_at=? WHERE id=?", 
              (datetime.now().isoformat(), order_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET status='terminee' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET status='annulee', cancelled_at=? WHERE id=?",
              (datetime.now().isoformat(), order_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/')
def index():
    return redirect('/dashboard')

# ========== TELEGRAM BOT WEBHOOK ==========

@app.route('/telegram_webhook', methods=['POST'])
async def telegram_webhook():
    """Endpoint pour recevoir les updates de Telegram via webhook"""
    global telegram_app
    if telegram_app is None:
        return jsonify({'error': 'Bot not initialized'}), 500
    
    try:
        update = Update.de_json(request.get_json(), telegram_app.bot)
        await telegram_app.process_update(update)
        return jsonify({'ok': True})
    except Exception as e:
        print(f"❌ Erreur webhook: {e}")
        return jsonify({'error': str(e)}), 500

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[DEBUG] /start appelé par {update.message.from_user.id}")
    keyboard = []
    for service_key, service_data in SERVICES_CONFIG.items():
        if service_data['active'] and service_data.get('visible', True):
            keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🎯 *Bienvenue sur B4U Deals !*\n\nChoisis ton service :", parse_mode='Markdown', reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data.startswith("service_"):
        service_key = data.replace("service_", "")
        service = SERVICES_CONFIG[service_key]
        keyboard = []
        for plan_key, plan_data in service['plans'].items():
            keyboard.append([InlineKeyboardButton(
                f"{plan_data['label']} - {plan_data['price']}€",
                callback_data=f"plan_{service_key}_{plan_key}"
            )])
        keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data="back_to_services")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"*{service['name']}*\n\nChoisis ton plan :", parse_mode='Markdown', reply_markup=reply_markup)
    
    elif data.startswith("plan_"):
        parts = data.replace("plan_", "").split("_")
        service_key = parts[0]
        plan_key = "_".join(parts[1:])
        service = SERVICES_CONFIG[service_key]
        plan = service['plans'][plan_key]
        
        user_states[user_id] = {
            'service': service_key,
            'plan': plan_key,
            'service_name': service['name'],
            'plan_label': plan['label'],
            'price': plan['price'],
            'cost': plan['cost'],
            'step': 'waiting_form'
        }
        
        if service_key == 'deezer':
            await query.edit_message_text(
                f"✅ *Commande confirmée*\n\nService: {service['name']}\nPlan: {plan['label']}\nPrix: {plan['price']}€\n\n📝 Envoie ton nom, prénom et mail (chacun sur une ligne)",
                parse_mode='Markdown'
            )
            user_states[user_id]['step'] = 'waiting_deezer_form'
        
        elif service_key == 'basicfit':
            await query.edit_message_text(
                f"✅ *Commande confirmée*\n\nService: {service['name']}\nPlan: {plan['label']}\nPrix: {plan['price']}€\n\n📝 Envoie ton nom, prénom, mail et date de naissance (chacun sur une ligne)",
                parse_mode='Markdown'
            )
            user_states[user_id]['step'] = 'waiting_basicfit_form'
    
    elif data == "back_to_services":
        keyboard = []
        for service_key, service_data in SERVICES_CONFIG.items():
            if service_data['active'] and service_data.get('visible', True):
                keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎯 *B4U Deals*\n\nChoisis ton service :", parse_mode='Markdown', reply_markup=reply_markup)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Inconnu"
    text = update.message.text
    
    if user_id not in user_states:
        await update.message.reply_text("❌ Commande non trouvée. Utilise /start pour recommencer.")
        return
    
    state = user_states[user_id]
    
    if state.get('step') == 'waiting_deezer_form':
        lines = text.strip().split('\n')
        if len(lines) < 3:
            await update.message.reply_text("❌ Envoie les 3 informations : Nom, Prénom, Mail")
            return
        
        state.update({
            'last_name': lines[0].strip(),
            'first_name': lines[1].strip(),
            'email': lines[2].strip(),
            'step': 'waiting_deezer_payment'
        })
        await update.message.reply_text(f"✅ Infos reçues\n\n💳 Envoie une capture d'écran de ton paiement")
    
    elif state.get('step') == 'waiting_basicfit_form':
        lines = text.strip().split('\n')
        if len(lines) < 4:
            await update.message.reply_text("❌ Envoie les 4 informations : Nom, Prénom, Mail, Date de naissance")
            return
        
        state.update({
            'last_name': lines[0].strip(),
            'first_name': lines[1].strip(),
            'email': lines[2].strip(),
            'birth_date': lines[3].strip(),
            'step': 'waiting_basicfit_payment'
        })
        await update.message.reply_text(f"✅ Infos reçues\n\n💳 Envoie une capture d'écran de ton paiement")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Inconnu"
    
    if user_id not in user_states:
        await update.message.reply_text("❌ Commande non trouvée. Utilise /start pour recommencer.")
        return
    
    state = user_states[user_id]
    
    if state.get('step') not in ['waiting_deezer_payment', 'waiting_basicfit_payment']:
        await update.message.reply_text("❌ Je ne suis pas en attente de paiement.")
        return
    
    photo_id = update.message.photo[-1].file_id
    
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("""INSERT INTO orders 
                 (user_id, username, service, plan, photo_id, price, cost, timestamp, status,
                  first_name, last_name, email, birth_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?, ?, ?)""",
              (user_id, username, state['service_name'], state['plan_label'], 
               photo_id, state['price'], state['cost'], datetime.now().isoformat(),
               state.get('first_name', ''), state.get('last_name', ''), 
               state.get('email', ''), state.get('birth_date', '')))
    
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n👤 @{username}\n📦 {state['service_name']}\n💰 {state['price']}€\n💵 Coût: {state['cost']}€\n📈 Bénéf: {state['price'] - state['cost']}€\n👤 {state.get('first_name', '')} {state.get('last_name', '')}\n📧 {state.get('email', '')}\n🎂 {state.get('birth_date', '')}",
                parse_mode='Markdown'
            )
            await context.bot.send_photo(chat_id=admin_id, photo=photo_id, caption=f"Preuve de paiement - Commande #{order_id}")
        except Exception as e:
            print(f"Erreur: {e}")
    
    await update.message.reply_text(f"✅ *Commande #{order_id} enregistrée !*\n\nMerci ! 🙏", parse_mode='Markdown')
    del user_states[user_id]

async def setup_telegram_bot():
    """Configure et démarre le bot Telegram avec webhook"""
    global telegram_app
    
    print("🤖 Configuration du bot Telegram avec webhook...")
    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button_callback))
    telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    await telegram_app.initialize()
    await telegram_app.start()
    
    # Configure le webhook
    webhook_url = f"{WEBHOOK_URL}/telegram_webhook"
    await telegram_app.bot.set_webhook(webhook_url)
    
    print(f"✅ Bot Telegram configuré avec webhook: {webhook_url}")
    return telegram_app
