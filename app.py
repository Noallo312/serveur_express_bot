import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from functools import wraps

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6976573567, 5174507979]
WEB_PASSWORD = os.getenv('WEB_PASSWORD')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'votre_secret_key_aleatoire_ici')

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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
            color: #667eea;
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
        <h1>🎯 B4U Deals Admin</h1>
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
    <meta name="theme-color" content="#667eea">
    <title>Dashboard - B4U Deals</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
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
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
        }
        .container {
            max-width: 1400px;
            margin: 20px auto;
            padding: 0 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            border-left: 5px solid #667eea;
        }
        .stat-card h3 {
            color: #666;
            font-size: 13px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .orders-section {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        .orders-section h2 {
            margin-bottom: 20px;
            color: #333;
        }
        .order-card {
            background: #f9fafb;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            border-left: 5px solid #ddd;
            transition: all 0.3s;
        }
        .order-card:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .order-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .order-info {
            font-size: 14px;
            color: #666;
            line-height: 1.6;
        }
        .order-info strong {
            color: #333;
        }
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }
        .status-en_attente {
            background: #fff3cd;
            color: #856404;
        }
        .status-en_cours {
            background: #cfe2ff;
            color: #084298;
        }
        .status-terminee {
            background: #d1e7dd;
            color: #0f5132;
        }
        .status-annulee {
            background: #f8d7da;
            color: #842029;
        }
        .order-actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 15px;
        }
        .action-btn {
            padding: 10px 18px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.3s;
            flex: 1;
            min-width: 120px;
        }
        .action-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .btn-take { background: #3b82f6; color: white; }
        .btn-complete { background: #10b981; color: white; }
        .btn-cancel { background: #ef4444; color: white; }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 6px 20px rgba(102,126,234,0.4);
            transition: all 0.3s;
        }
        .refresh-btn:hover {
            transform: scale(1.1);
        }
        .filter-tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-tab {
            padding: 10px 20px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            transition: all 0.3s;
        }
        .filter-tab.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 B4U Deals - Dashboard Admin</h1>
        <a href="/logout" class="logout-btn">Déconnexion</a>
    </div>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📦 Total Commandes</h3>
                <div class="value" id="total-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>⏳ En Attente</h3>
                <div class="value" id="pending-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>🔄 En Cours</h3>
                <div class="value" id="inprogress-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>✅ Terminées</h3>
                <div class="value" id="completed-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>💰 Chiffre d'Affaires</h3>
                <div class="value" id="revenue">0€</div>
            </div>
            <div class="stat-card">
                <h3>💵 Bénéfice</h3>
                <div class="value" id="profit">0€</div>
            </div>
        </div>

        <div class="orders-section">
            <h2>📋 Gestion des Commandes</h2>
            <div class="filter-tabs">
                <button class="filter-tab active" onclick="filterOrders('all')">Toutes</button>
                <button class="filter-tab" onclick="filterOrders('en_attente')">En Attente</button>
                <button class="filter-tab" onclick="filterOrders('en_cours')">En Cours</button>
                <button class="filter-tab" onclick="filterOrders('terminee')">Terminées</button>
            </div>
            <div id="orders-container"></div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadData()">🔄</button>

    <script>
        let currentFilter = 'all';

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

        function filterOrders(status) {
            currentFilter = status;
            document.querySelectorAll('.filter-tab').forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            loadData();
        }

        function displayOrders(orders) {
            const container = document.getElementById('orders-container');
            
            let filteredOrders = orders;
            if (currentFilter !== 'all') {
                filteredOrders = orders.filter(o => o.status === currentFilter);
            }
            
            if (filteredOrders.length === 0) {
                container.innerHTML = '<p style="text-align:center;padding:60px;color:#999;font-size:16px">Aucune commande</p>';
                return;
            }
            
            container.innerHTML = filteredOrders.map(order => `
                <div class="order-card">
                    <div class="order-header">
                        <div>
                            <strong style="font-size:18px;color:#667eea">#${order.id}</strong>
                            <span class="status-badge status-${order.status}">${getStatusLabel(order.status)}</span>
                        </div>
                        <div style="font-weight:bold;font-size:18px;color:#10b981">${order.price}€</div>
                    </div>
                    <div class="order-info">
                        <div><strong>Service:</strong> ${order.service}</div>
                        <div><strong>Plan:</strong> ${order.plan}</div>
                        <div><strong>Client:</strong> @${order.username}</div>
                        <div><strong>Nom:</strong> ${order.first_name} ${order.last_name}</div>
                        <div><strong>Email:</strong> ${order.email}</div>
                        <div><strong>Paiement:</strong> ${order.payment_method}</div>
                        <div><strong>Coût:</strong> ${order.cost}€ | <strong>Bénéfice:</strong> ${(order.price - order.cost).toFixed(2)}€</div>
                    </div>
                    <div class="order-actions">
                        <button class="action-btn btn-take" onclick="takeOrder(${order.id})">✋ Prendre en charge</button>
                        <button class="action-btn btn-complete" onclick="completeOrder(${order.id})">✅ Marquer terminée</button>
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌ Annuler</button>
                    </div>
                </div>
            `).join('');
        }

        function getStatusLabel(status) {
            const labels = {
                'en_attente': '⏳ En Attente',
                'en_cours': '🔄 En Cours',
                'terminee': '✅ Terminée',
                'annulee': '❌ Annulée'
            };
            return labels[status] || status;
        }

        async function takeOrder(orderId) {
            if (confirm('Prendre en charge cette commande ?')) {
                await fetch(`/api/order/${orderId}/take`, { method: 'POST' });
                loadData();
            }
        }

        async function completeOrder(orderId) {
            if (confirm('Marquer cette commande comme terminée ?')) {
                await fetch(`/api/order/${orderId}/complete`, { method: 'POST' });
                loadData();
            }
        }

        async function cancelOrder(orderId) {
            if (confirm('Annuler cette commande ?')) {
                await fetch(`/api/order/${orderId}/cancel`, { method: 'POST' });
                loadData();
            }
        }

        loadData();
        setInterval(loadData, 15000);
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
            'price': row[5],
            'cost': row[6],
            'first_name': row[7],
            'last_name': row[8],
            'email': row[9],
            'payment_method': row[11],
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

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'bot': 'running'})

# ========== TELEGRAM BOT ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    print(f"[BOT] /start appelé par {user_id}")
    
    # Organiser les services par catégories
    keyboard = [
        [InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],
        [InlineKeyboardButton("🎧 Musique (Spotify)", callback_data="cat_music")],
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
    
    # Catégories
    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        keyboard = []
        
        for service_key, service_data in SERVICES_CONFIG.items():
            if service_data['active'] and service_data.get('visible', True) and service_data['category'] == category:
                keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
        
        keyboard.append([InlineKeyboardButton("⬅️ Retour au menu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        category_labels = {
            'streaming': '🎬 Streaming',
            'music': '🎧 Musique',
            'ai': '🤖 Intelligence Artificielle'
        }
        
        await query.edit_message_text(
            f"*{category_labels.get(category, category)}*\n\nChoisis ton service :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    # Services
    elif data.startswith("service_"):
        service_key = data.replace("service_", "")
        service = SERVICES_CONFIG[service_key]
        keyboard = []
        
        for plan_key, plan_data in service['plans'].items():
            keyboard.append([InlineKeyboardButton(
                f"{plan_data['label']} - {plan_data['price']}€",
                callback_data=f"plan_{service_key}_{plan_key}"
            )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data=f"cat_{service['category']}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"*{service['name']}*\n\nChoisis ton abonnement :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    # Plans
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
        
        form_text = (
            f"✅ *{plan['label']} - {plan['price']}€*\n\n"
            "📝 *Formulaire de commande*\n\n"
            "Envoie-moi les informations suivantes (une par ligne) :\n\n"
            "1️⃣ Nom\n"
            "2️⃣ Prénom\n"
            "3️⃣ Adresse email\n"
            "4️⃣ Moyen de paiement (PayPal / Virement / Revolut)\n\n"
            "📌 Exemple :\n"
            "Dupont\n"
            "Jean\n"
            "jean.dupont@email.com\n"
            "PayPal"
        )
        
        await query.edit_message_text(form_text, parse_mode='Markdown')
    
    # Retour au menu principal
    elif data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],
            [InlineKeyboardButton("🎧 Musique (Spotify)", callback_data="cat_music")],
            [InlineKeyboardButton("🤖 IA (ChatGPT+)", callback_data="cat_ai")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 *B4U Deals*\n\nChoisis une catégorie :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Inconnu"
    text = update.message.text
    
    if user_id not in user_states:
        await update.message.reply_text(
            "❌ Aucune commande en cours.\n\nUtilise /start pour commencer."
        )
        return
    
    state = user_states[user_id]
    
    if state.get('step') == 'waiting_form':
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        
        if len(lines) < 4:
            await update.message.reply_text(
                "❌ *Informations incomplètes*\n\n"
                "Il me faut les 4 informations :\n"
                "1️⃣ Nom\n"
                "2️⃣ Prénom\n"
                "3️⃣ Email\n"
                "4️⃣ Moyen de paiement",
                parse_mode='Markdown'
            )
            return
        
        last_name = lines[0]
        first_name = lines[1]
        email = lines[2]
        payment_method = lines[3]
        
        # Validation basique
        if '@' not in email:
            await update.message.reply_text("❌ Email invalide. Recommence avec un email valide.")
            return
        
        payment_methods = ['paypal', 'virement', 'revolut']
        if payment_method.lower() not in payment_methods:
            await update.message.reply_text(
                "❌ Moyen de paiement invalide.\n\n"
                "Choisis parmi : PayPal, Virement, Revolut"
            )
            return
        
        # Enregistrer la commande
        conn = sqlite3.connect('orders.db')
        c = conn.cursor()
        c.execute("""INSERT INTO orders 
                     (user_id, username, service, plan, price, cost, timestamp, status,
                      first_name, last_name, email, payment_method)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?, ?, ?)""",
                  (user_id, username, state['service_name'], state['plan_label'], 
                   state['price'], state['cost'], datetime.now().isoformat(),
                   first_name, last_name, email, payment_method))
        
        order_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Notification admins
        admin_message = (
            f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n"
            f"👤 Client: @{username}\n"
            f"📦 Service: {state['service_name']}\n"
            f"📋 Plan: {state['plan_label']}\n"
            f"💰 Prix: {state['price']}€\n"
            f"💵 Coût: {state['cost']}€\n"
            f"📈 Bénéfice: {state['price'] - state['cost']}€\n\n"
            f"*Informations client:*\n"
            f"👤 {first_name} {last_name}\n"
            f"📧 {email}\n"
            f"💳 Paiement: {payment_method}\n\n"
            f"🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"[ERREUR] Notification admin {admin_id}: {e}")
        
        # Confirmation client
        confirmation_message = (
            f"✅ *Commande #{order_id} enregistrée !*\n\n"
            f"📦 {state['plan_label']}\n"
            f"💰 Montant: {state['price']}€\n"
            f"💳 Paiement: {payment_method}\n\n"
            f"Nous traitons ta commande rapidement.\n"
            f"Tu seras notifié dès qu'elle sera prête ! 🚀\n\n"
            f"Merci de ta confiance ! 🙏"
        )
        
        await update.message.reply_text(confirmation_message, parse_mode='Markdown')
        
        # Nettoyer l'état
        del user_states[user_id]

def run_bot():
    """Démarrage du bot Telegram en mode polling"""
    import asyncio
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        print("🤖 Démarrage du bot Telegram...")
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        
        print("✅ Bot Telegram configuré avec succès !")
        
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(application.start())
        loop.run_until_complete(application.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,
            timeout=30
        ))
        
        print("🔄 Bot en écoute des messages...")
        loop.run_forever()
        
    except Exception as e:
        print(f"❌ Erreur critique du bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    import threading
    
    # Lancer le bot dans un thread séparé
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Lancer Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
