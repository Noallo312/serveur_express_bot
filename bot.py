import os
import threading
import sqlite3
import time
import asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, session, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import requests
from functools import wraps

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [6976573567, 5174507979]
WEB_PASSWORD = os.getenv('WEB_PASSWORD')

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'votre_secret_key_aleatoire_ici')

# CONFIGURATION DES SERVICES (gardé pour l'historique, masqué sur le bot)
SERVICES_CONFIG = {
    'crunchyroll': {
        'name': '🧡 Crunchyroll',
        'active': False,
        'visible': False,
        'plans': {
            '1_mois': {'label': '1 mois', 'price': 4.00, 'cost': 1.90},
            '1_an_fan': {'label': '1 an Fan', 'price': 12.00, 'cost': 10.00},
            '1_an_mega': {'label': '1 an Méga Fan', 'price': 15.00, 'cost': 11.00},
            '1_an_mega_prive': {'label': '1 an Méga Fan (profils privés)', 'price': 20.00, 'cost': 4.00}
        }
    },
    'youtube': {
        'name': '▶️ YouTube Premium',
        'active': False,
        'visible': False,
        'plans': {
            'solo': {'label': 'Solo (sur ton mail)', 'price': 4.00, 'cost': 0.50},
            'famille': {'label': 'Famille (5 invitations)', 'price': 10.00, 'cost': 1.00}
        }
    },
    'spotify': {
        'name': '🎧 Spotify Premium',
        'active': False,
        'visible': False,
        'plans': {
            '2_mois': {'label': '2 mois', 'price': 10.00, 'cost': 0.75},
            '1_an': {'label': '1 an (garantie complète)', 'price': 20.00, 'cost': 9.50}
        }
    },
    'chatgpt': {
        'name': '🤖 ChatGPT+',
        'active': False,
        'visible': False,
        'plans': {
            '1_mois': {'label': '1 mois (sur ton mail)', 'price': 2.00, 'cost': 0.60},
            'business': {'label': 'Business (+5 invitations)', 'price': 5.00, 'cost': 2.90}
        }
    },
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
push_subscriptions = []

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

# ============= PWA FILES =============

MANIFEST_JSON = {
    "name": "B4U Deals Admin",
    "short_name": "B4U Admin",
    "description": "Dashboard administrateur B4U Deals Bot",
    "start_url": "/dashboard",
    "display": "standalone",
    "background_color": "#0a2540",
    "theme_color": "#0a2540",
    "orientation": "portrait-primary",
    "icons": [
        {
            "src": "/static/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any maskable"
        },
        {
            "src": "/static/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any maskable"
        }
    ]
}

SERVICE_WORKER_JS = '''
self.addEventListener('install', (event) => {
    console.log('Service Worker installé');
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    console.log('Service Worker activé');
    event.waitUntil(clients.claim());
});

self.addEventListener('push', (event) => {
    const data = event.data ? event.data.json() : {};
    const title = data.title || 'Nouvelle commande !';
    const options = {
        body: data.body || 'Une nouvelle commande vient d\\'arriver',
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        vibrate: [200, 100, 200],
        tag: 'order-notification',
        requireInteraction: true,
        data: {
            url: '/dashboard'
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});
'''

HTML_LOGIN = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0a2540">
    <link rel="manifest" href="/manifest.json">
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

HTML_DASHBOARD = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0a2540">
    <link rel="manifest" href="/manifest.json">
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
        .filters {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            overflow-x: auto;
        }
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #00d4ff;
            background: white;
            color: #0a2540;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
        }
        .filter-btn.active {
            background: #00d4ff;
            color: white;
        }
        .order-card {
            background: #f9f9f9;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 12px;
            border-left: 4px solid #ddd;
        }
        .order-card.en_attente { border-left-color: #ffa500; }
        .order-card.en_cours { border-left-color: #2196f3; }
        .order-card.terminee { border-left-color: #4caf50; }
        .order-card.annulee { border-left-color: #f44336; }
        .order-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .status-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }
        .status-badge.en_attente { background: #fff3cd; color: #856404; }
        .status-badge.en_cours { background: #d1ecf1; color: #0c5460; }
        .status-badge.terminee { background: #d4edda; color: #155724; }
        .status-badge.annulee { background: #f8d7da; color: #721c24; }
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
        .btn-release { background: #ff9800; color: white; }
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
            
            <div class="filters">
                <button class="filter-btn active" onclick="filterOrders('all')">Toutes</button>
                <button class="filter-btn" onclick="filterOrders('en_attente')">Attente</button>
                <button class="filter-btn" onclick="filterOrders('en_cours')">Cours</button>
                <button class="filter-btn" onclick="filterOrders('terminee')">Terminées</button>
                <button class="filter-btn" onclick="filterOrders('annulee')">Annulées</button>
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

        function displayOrders(orders) {
            const container = document.getElementById('orders-container');
            
            const filtered = currentFilter === 'all' 
                ? orders 
                : orders.filter(o => o.status === currentFilter);
            
            if (filtered.length === 0) {
                container.innerHTML = '<p style="text-align:center;padding:40px;color:#999">Aucune commande</p>';
                return;
            }
            
            container.innerHTML = filtered.map(order => {
                const statusText = {
                    'en_attente': '⏳ Attente',
                    'en_cours': '🔄 Cours',
                    'terminee': '✅ OK',
                    'annulee': '❌ Annulée'
                };
                
                let actions = '';
                if (order.status === 'en_attente') {
                    actions = `
                        <button class="action-btn btn-take" onclick="takeOrder(${order.id})">✋ Prendre</button>
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌ Annuler</button>
                    `;
                } else if (order.status === 'en_cours') {
                    actions = `
                        <button class="action-btn btn-complete" onclick="completeOrder(${order.id})">✅ Terminer</button>
                        <button class="action-btn btn-release" onclick="releaseOrder(${order.id})">🔄 Remettre</button>
                    `;
                }
                
                return `
                    <div class="order-card ${order.status}">
                        <div class="order-header">
                            <strong>#${order.id}</strong>
                            <span class="status-badge ${order.status}">${statusText[order.status]}</span>
                        </div>
                        <div>
                            <div>📦 ${order.service} ${order.plan ? '- ' + order.plan : ''}</div>
                            <div>👤 @${order.username}</div>
                            <div>💰 ${order.price}€</div>
                        </div>
                        <div class="order-actions">
                            ${actions}
                        </div>
                    </div>
                `;
            }).join('');
        }

        function filterOrders(filter) {
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            loadData();
        }

        async function takeOrder(orderId) {
            if (!confirm('Prendre en charge cette commande ?')) return;
            await fetch(`/api/order/${orderId}/take`, { method: 'POST' });
            loadData();
        }

        async function completeOrder(orderId) {
            if (!confirm('Marquer comme terminée ?')) return;
            await fetch(`/api/order/${orderId}/complete`, { method: 'POST' });
            loadData();
        }

        async function cancelOrder(orderId) {
            if (!confirm('Annuler cette commande ?')) return;
            await fetch(`/api/order/${orderId}/cancel`, { method: 'POST' });
            loadData();
        }

        async function releaseOrder(orderId) {
            if (!confirm('Remettre en ligne ?')) return;
            await fetch(`/api/order/${orderId}/release`, { method: 'POST' });
            loadData();
        }

        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>
'''

# ============= ROUTES WEB =============

@app.route('/manifest.json')
def manifest():
    return jsonify(MANIFEST_JSON)

@app.route('/sw.js')
def service_worker():
    return SERVICE_WORKER_JS, 200, {'Content-Type': 'application/javascript'}

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
            'user_id': row[1],
            'username': row[2],
            'service': row[3],
            'plan': row[4],
            'price': row[6],
            'cost': row[7],
            'status': row[13],
            'timestamp': row[12]
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

@app.route('/api/order/<int:order_id>/release', methods=['POST'])
@login_required
def release_order(order_id):
    conn = sqlite3.connect('orders.db')
    c = conn.cursor()
    c.execute("UPDATE orders SET status='en_attente' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/')
def index():
    return redirect('/dashboard')

# ============= BOT TELEGRAM =============

async def start(update: Update, context):
    print(f"[DEBUG] /start appelé par l'utilisateur {update.message.from_user.id}")
    
    keyboard = []
    for service_key, service_data in SERVICES_CONFIG.items():
        if service_data['active'] and service_data.get('visible', True):
            keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
    
    print(f"[DEBUG] Keyboard créé avec {len(keyboard)} boutons")
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    try:
        await update.message.reply_text(
            "🎯 *Bienvenue sur B4U Deals !*\n\n"
            "Choisis ton service :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        print("[DEBUG] Message envoyé avec succès")
    except Exception as e:
        print(f"[ERROR] Erreur lors de l'envoi du message: {e}")

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    
    print(f"[DEBUG] Callback reçu: {data} de l'utilisateur {user_id}")
    
    if data.startswith("service_"):
        service_key = data.replace("service_", "")
        service = SERVICES_CONFIG[service_key]
        
        keyboard = []
        for plan_key, plan_data in service['plans'].items():
            if plan_data.get('available', True):
                keyboard.append([InlineKeyboardButton(
                    f"{plan_data['label']} - {plan_data['price']}€",
                    callback_data=f"plan_{service_key}_{plan_key}"
                )])
        
        keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data="back_to_services")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"*{service['name']}*\n\nChoisis ton plan :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
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
        
        # Demander le formulaire approprié selon le service
        if service_key == 'deezer':
            await query.edit_message_text(
                f"✅ *Commande confirmée*\n\n"
                f"Service: {service['name']}\n"
                f"Plan: {plan['label']}\n"
                f"Prix: {plan['price']}€\n\n"
                f"📝 Envoie ton nom, prénom et adresse mail (chacun sur une ligne)",
                parse_mode='Markdown'
            )
            user_states[user_id]['step'] = 'waiting_deezer_form'
        
        elif service_key == 'basicfit':
            await query.edit_message_text(
                f"✅ *Commande confirmée*\n\n"
                f"Service: {service['name']}\n"
                f"Plan: {plan['label']}\n"
                f"Prix: {plan['price']}€\n\n"
                f"📝 Envoie ton nom, prénom, mail et date de naissance (chacun sur une ligne)",
                parse_mode='Markdown'
            )
            user_states[user_id]['step'] = 'waiting_basicfit_form'
    
    elif data == "back_to_services":
        keyboard = []
        for service_key, service_data in SERVICES_CONFIG.items():
            if service_data['active'] and service_data.get('visible', True):
                keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎯 *B4U Deals*\n\nChoisis ton service :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_text_message(update: Update, context):
    """Gère les messages texte pour les formulaires"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Inconnu"
    text = update.message.text
    
    if user_id not in user_states:
        await update.message.reply_text("❌ Commande non trouvée. Utilise /start pour recommencer.")
        return
    
    state = user_states[user_id]
    
    # Formulaire Deezer (Nom, Prénom, Mail)
    if state.get('step') == 'waiting_deezer_form':
        lines = text.strip().split('\n')
        if len(lines) < 3:
            await update.message.reply_text("❌ Envoie les 3 informations : Nom, Prénom, Mail (chacun sur une ligne)")
            return
        
        nom = lines[0].strip()
        prenom = lines[1].strip()
        mail = lines[2].strip()
        
        user_states[user_id].update({
            'last_name': nom,
            'first_name': prenom,
            'email': mail,
            'step': 'waiting_deezer_payment'
        })
        
        await update.message.reply_text(
            f"✅ Infos reçues :\n\n"
            f"Nom: {nom}\n"
            f"Prénom: {prenom}\n"
            f"Mail: {mail}\n\n"
            f"💳 Maintenant, envoie une capture d'écran de ton paiement",
            parse_mode='Markdown'
        )
    
    # Formulaire Basic Fit (Nom, Prénom, Mail, Date de naissance)
    elif state.get('step') == 'waiting_basicfit_form':
        lines = text.strip().split('\n')
        if len(lines) < 4:
            await update.message.reply_text("❌ Envoie les 4 informations : Nom, Prénom, Mail, Date de naissance (chacun sur une ligne)")
            return
        
        nom = lines[0].strip()
        prenom = lines[1].strip()
        mail = lines[2].strip()
        birth_date = lines[3].strip()
        
        user_states[user_id].update({
            'last_name': nom,
            'first_name': prenom,
            'email': mail,
            'birth_date': birth_date,
            'step': 'waiting_basicfit_payment'
        })
        
        await update.message.reply_text(
            f"✅ Infos reçues :\n\n"
            f"Nom: {nom}\n"
            f"Prénom: {prenom}\n"
            f"Mail: {mail}\n"
            f"Date de naissance: {birth_date}\n\n"
            f"💳 Maintenant, envoie une capture d'écran de ton paiement",
            parse_mode='Markdown'
        )
    
    else:
        await update.message.reply_text("Utilise /start pour commencer une commande ! 🎯")

async def handle_photo(update: Update, context):
    """Gère les photos de paiement"""
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Inconnu"
    
    if user_id not in user_states:
        await update.message.reply_text("❌ Commande non trouvée. Utilise /start pour recommencer.")
        return
    
    state = user_states[user_id]
    
    # Vérifier si on attend une photo
    if state.get('step') not in ['waiting_deezer_payment', 'waiting_basicfit_payment']:
        await update.message.reply_text("❌ Je ne suis pas en attente de paiement. Utilise /start pour recommencer.")
        return
    
    photo_id = update.message.photo[-1].file_id
    
    # Créer la commande en base de données
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
    
    # Notifier les admins
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n"
                     f"👤 Client: @{username}\n"
                     f"📦 Service: {state['service_name']}\n"
                     f"📋 Plan: {state['plan_label']}\n"
                     f"💰 Prix: {state['price']}€\n"
                     f"💵 Coût: {state['cost']}€\n"
                     f"📈 Bénéfice: {state['price'] - state['cost']}€\n"
                     f"👤 Nom: {state.get('first_name', 'N/A')} {state.get('last_name', 'N/A')}\n"
                     f"📧 Email: {state.get('email', 'N/A')}\n"
                     f"🎂 Date de naissance: {state.get('birth_date', 'N/A')}",
                parse_mode='Markdown'
            )
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo_id,
                caption=f"Preuve de paiement - Commande #{order_id}"
            )
        except Exception as e:
            print(f"Erreur notification admin {admin_id}: {e}")
    
    await update.message.reply_text(
        f"✅ *Commande #{order_id} enregistrée !*\n\n"
        f"Ton paiement est en cours de vérification.\n"
        f"Tu seras notifié dès que ta commande sera traitée.\n\n"
        f"Merci de ta confiance ! 🙏",
        parse_mode='Markdown'
    )
    
    del user_states[user_id]

async def handle_message(update: Update, context):
    """Gère les autres messages"""
    await update.message.reply_text(
        "Utilise /start pour commencer une commande ! 🎯"
    )

application = None

async def setup_bot():
    """Configure le bot Telegram"""
    global application
    print("🤖 Configuration du bot Telegram...")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Ajouter les handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    print("✅ Bot Telegram configuré !")
    await application.initialize()

def run_bot_polling():
    """Lance le polling du bot Telegram"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(setup_bot())
        print("🔄 Démarrage du polling Telegram...")
        loop.run_until_complete(application.start())
        loop.run_until_complete(application.updater.start_polling(drop_pending_updates=False, allowed_updates=Update.ALL_TYPES))
    except Exception as e:
        print(f"❌ Erreur bot: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 B4U DEALS BOT - DÉMARRAGE")
    print("=" * 50)
    
    # Lancer le bot dans un thread séparé
    bot_thread = threading.Thread(target=run_bot_polling, daemon=True)
    bot_thread.start()
    
    # Lancer Flask
    time.sleep(3)
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Démarrage Flask sur le port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
