import os
import threading
import sqlite3
import csv
import time
import asyncio
from datetime import datetime
from io import StringIO
from flask import Flask, render_template_string, request, jsonify, redirect, session
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

# CONFIGURATION DES SERVICES
SERVICES_CONFIG = {
    'crunchyroll': {
        'name': '🧡 Crunchyroll',
        'active': True,
        'plans': {
            '1_mois': {'label': '1 mois', 'price': 4.00, 'cost': 1.90},
            '1_an_fan': {'label': '1 an Fan', 'price': 12.00, 'cost': 10.00},
            '1_an_mega': {'label': '1 an Méga Fan', 'price': 15.00, 'cost': 11.00},
            '1_an_mega_prive': {'label': '1 an Méga Fan (profils privés)', 'price': 20.00, 'cost': 4.00}
        }
    },
    'youtube': {
        'name': '▶️ YouTube Premium',
        'active': True,
        'plans': {
            'solo': {'label': 'Solo (sur ton mail)', 'price': 4.00, 'cost': 0.50},
            'famille': {'label': 'Famille (5 invitations)', 'price': 10.00, 'cost': 1.00}
        }
    },
    'spotify': {
        'name': '🎧 Spotify Premium',
        'active': True,
        'plans': {
            '2_mois': {'label': '2 mois', 'price': 10.00, 'cost': 0.75},
            '1_an': {'label': '1 an (garantie complète)', 'price': 20.00, 'cost': 9.50}
        }
    },
    'chatgpt': {
        'name': '🤖 ChatGPT+',
        'active': True,
        'plans': {
            '1_mois': {'label': '1 mois (sur ton mail)', 'price': 2.00, 'cost': 0.60},
            'business': {'label': 'Business (+5 invitations)', 'price': 5.00, 'cost': 2.90},
            '1_an': {'label': '1 an (nouveau compte)', 'price': 18.00, 'cost': 5.00}
        }
    },
    'deezer': {
        'name': '🎵 Deezer Premium',
        'active': True,
        'plans': {
            'premium': {'label': 'Premium', 'price': 6.00, 'cost': 0.00}  # Bénéfice fixe 6€
        }
    },
    'ubereats': {
        'name': '🍔 Uber Eats',
        'active': False,  # INACTIF
        'plans': {}
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
                  cancel_reason TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS order_messages
                 (order_id INTEGER,
                  admin_id INTEGER,
                  message_id INTEGER,
                  photo_message_id INTEGER)''')
    
    columns_to_add = [
        ("plan", "TEXT"),
        ("cost", "REAL"),
        ("status", "TEXT DEFAULT 'en_attente'"),
        ("admin_id", "INTEGER"),
        ("admin_username", "TEXT"),
        ("taken_at", "TEXT"),
        ("cancelled_by", "INTEGER"),
        ("cancelled_at", "TEXT"),
        ("cancel_reason", "TEXT")
    ]
    
    for column, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE orders ADD COLUMN {column} {col_type}")
        except:
            pass
    
    conn.commit()
    conn.close()

init_db()

def force_kill_all_instances():
    print("🔥 Forçage de la suppression de toutes les instances...")
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        response = requests.get(url, timeout=10)
        print(f"🔧 Webhook supprimé: {response.json()}")
        time.sleep(3)
        
        print("⚡ Vidage des mises à jour en attente...")
        for i in range(10):
            try:
                url2 = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1&timeout=1"
                resp = requests.get(url2, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get('result'):
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

# ============= INTERFACE WEB =============

HTML_LOGIN = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connexion - Admin Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 90%;
            max-width: 400px;
        }
        h1 {
            text-align: center;
            color: #667eea;
            margin-bottom: 30px;
            font-size: 28px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
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
            transition: transform 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
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
        <h1>🔐 Connexion Admin</h1>
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        <form method="POST">
            <div class="form-group">
                <label>Mot de passe</label>
                <input type="password" name="password" required autofocus>
            </div>
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
    <title>Dashboard Admin - Serveur Express Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f7fa;
            color: #333;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 24px; }
        .logout-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }
        .logout-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .container {
            max-width: 1400px;
            margin: 30px auto;
            padding: 0 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border-left: 4px solid #667eea;
        }
        .stat-card h3 {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .orders-section {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        .section-title {
            font-size: 22px;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .filters {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .filter-btn {
            padding: 10px 20px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        .filter-btn.active {
            background: #667eea;
            color: white;
        }
        .filter-btn:hover {
            transform: translateY(-2px);
        }
        .order-card {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 15px;
            border-left: 4px solid #ddd;
            transition: all 0.3s;
        }
        .order-card:hover {
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transform: translateX(5px);
        }
        .order-card.en_attente { border-left-color: #ffa500; }
        .order-card.en_cours { border-left-color: #2196f3; }
        .order-card.terminee { border-left-color: #4caf50; }
        .order-card.annulee { border-left-color: #f44336; }
        .order-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .order-id {
            font-weight: bold;
            font-size: 18px;
            color: #667eea;
        }
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-badge.en_attente { background: #fff3cd; color: #856404; }
        .status-badge.en_cours { background: #d1ecf1; color: #0c5460; }
        .status-badge.terminee { background: #d4edda; color: #155724; }
        .status-badge.annulee { background: #f8d7da; color: #721c24; }
        .order-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }
        .detail-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .detail-item strong {
            color: #667eea;
        }
        .order-actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .action-btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        .action-btn:hover {
            transform: translateY(-2px);
        }
        .btn-take { background: #2196f3; color: white; }
        .btn-complete { background: #4caf50; color: white; }
        .btn-cancel { background: #f44336; color: white; }
        .btn-release { background: #ff9800; color: white; }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: #667eea;
            color: white;
            border: none;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            transition: all 0.3s;
        }
        .refresh-btn:hover {
            transform: scale(1.1) rotate(180deg);
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>🤖 Dashboard Serveur Express Bot</h1>
            <a href="/logout" class="logout-btn">Déconnexion</a>
        </div>
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
                <h3>💵 Bénéfices</h3>
                <div class="value" id="profit">0€</div>
            </div>
        </div>

        <div class="orders-section">
            <h2 class="section-title">📋 Gestion des Commandes</h2>
            
            <div class="filters">
                <button class="filter-btn active" onclick="filterOrders('all')">Toutes</button>
                <button class="filter-btn" onclick="filterOrders('en_attente')">En Attente</button>
                <button class="filter-btn" onclick="filterOrders('en_cours')">En Cours</button>
                <button class="filter-btn" onclick="filterOrders('terminee')">Terminées</button>
                <button class="filter-btn" onclick="filterOrders('annulee')">Annulées</button>
            </div>

            <div id="orders-container"></div>
        </div>
    </div>

    <button class="refresh-btn" onclick="loadData()" title="Rafraîchir">🔄</button>

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
                document.getElementById('revenue').textContent = data.stats.revenue.toFixed(2) + '€';
                document.getElementById('profit').textContent = data.stats.profit.toFixed(2) + '€';
                
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
                container.innerHTML = `
                    <div class="empty-state">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14z"/>
                        </svg>
                        <h3>Aucune commande</h3>
                    </div>
                `;
                return;
            }
            
            container.innerHTML = filtered.map(order => {
                const statusText = {
                    'en_attente': '⏳ En Attente',
                    'en_cours': '🔄 En Cours (OCCUPÉ)',
                    'terminee': '✅ Terminée',
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
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌ Annuler</button>
                    `;
                }
                
                const details = `
                    <div class="detail-item">📦 <strong>Service:</strong> ${order.service}</div>
                    ${order.plan ? `<div class="detail-item">📋 <strong>Plan:</strong> ${order.plan}</div>` : ''}
                    <div class="detail-item">📝 <strong>Nom:</strong> ${order.first_name} ${order.last_name}</div>
                    <div class="detail-item">💰 <strong>Prix:</strong> ${order.price}€</div>
                    ${order.profit !== null ? `<div class="detail-item">💵 <strong>Bénéfice:</strong> ${order.profit.toFixed(2)}€</div>` : ''}
                `;
                
                const adminInfo = order.admin_username ? 
                    `<div class="detail-item">👨‍💼 <strong>Admin:</strong> @${order.admin_username}</div>` : '';
                
                return `
                    <div class="order-card ${order.status}">
                        <div class="order-header">
                            <div class="order-id">#${order.id}</div>
                            <div class="status-badge ${order.status}">${statusText[order.status]}</div>
                        </div>
                        <div class="order-details">
                            ${details}
                            <div class="detail-item">👤 <strong>Client:</strong> @${order.username}</div>
                            <div class="detail-item">💳 <strong>Paiement:</strong> ${order.payment_method}</div>
                            <div class="detail-item">🕐 <strong>Date:</strong> ${order.timestamp}</div>
                            ${adminInfo}
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
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');
            loadData();
        }

        async function takeOrder(orderId) {
            if (!confirm('Prendre en charge cette commande ?')) return;
            try {
                await fetch(`/api/order/${orderId}/take`, { method: 'POST' });
                loadData();
            } catch (error) {
                alert('Erreur: ' + error);
            }
        }

        async function completeOrder(orderId) {
            if (!confirm('Marquer cette commande comme terminée ?')) return;
            try {
                await fetch(`/api/order/${orderId}/complete`, { method: 'POST' });
                loadData();
            } catch (error) {
                alert('Erreur: ' + error);
            }
        }

        async function cancelOrder(orderId) {
            if (!confirm('Annuler cette commande ?')) return;
            try {
                await fetch(`/api/order/${orderId}/cancel`, { method: 'POST' });
                loadData();
            } catch (error) {
                alert('Erreur: ' + error);
            }
        }

        async function releaseOrder(orderId) {
            if (!confirm('Remettre cette commande en ligne ?')) return;
            try {
                await fetch(`/api/order/${orderId}/release`, { method: 'POST' });
                loadData();
            } catch (error) {
                alert('Erreur: ' + error);
            }
        }

        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>
'''

@app.route('/')
def home():
    return "Bot Telegram actif !"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == WEB_PASSWORD:
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
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status != 'annulee'")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_attente'")
    pending_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_cours'")
    inprogress_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='terminee'")
    completed_orders = c.fetchone()[0]
    
    c.execute("SELECT SUM(price) FROM orders WHERE price IS NOT NULL AND status != 'annulee'")
    revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(price - COALESCE(cost, 0)) FROM orders WHERE price IS NOT NULL AND status != 'annulee'")
    profit = c.fetchone()[0] or 0
    
    c.execute("""SELECT id, user_id, username, service, plan, price, cost, first_name, last_name,
                        payment_method, timestamp, status, admin_username
                 FROM orders ORDER BY id DESC LIMIT 50""")
    orders = c.fetchall()
    conn.close()
    
    orders_list = [{
        'id': o[0],
        'user_id': o[1],
        'username': o[2] or 'Unknown',
        'service': o[3],
        'plan': o[4],
        'price': o[5],
        'profit': (o[5] - o[6]) if o[6] is not None else None,
        'first_name': o[7],
        'last_name': o[8],
        'payment_method': o[9],
        'timestamp': o[10],
        'status': o[11],
        'admin_username': o[12]
    } for o in orders]
    
    return jsonify({
        'stats': {
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'inprogress_orders': inprogress_orders,
            'completed_orders': completed_orders,
            'revenue': revenue,
            'profit': profit
        },
        'orders': orders_list
    })

@app.route('/api/order/<int:order_id>/complete', methods=['POST'])
@login_required
def api_complete_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='terminee' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def api_cancel_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='annulee', cancelled_by=999999, cancelled_at=?, cancel_reason='Annulée via web' WHERE id=?",
              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/release', methods=['POST'])
@login_required
def api_release_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='en_attente', admin_id=NULL, admin_username=NULL, taken_at=NULL WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ============= CODE TELEGRAM =============

async def start(update: Update, context):
    keyboard = []
    
    for service_key, service_info in SERVICES_CONFIG.items():
        if service_info['active']:
            keyboard.append([InlineKeyboardButton(service_info['name'], callback_data=f'service_{service_key}')])
        else:
            keyboard.append([InlineKeyboardButton(f"{service_info['name']} (Indisponible)", callback_data=f'inactive_{service_key}')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Bienvenue sur Serveur Express Bot\n\n"
        "🎯 Choisissez le service que vous souhaitez :",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context):
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Cette commande est réservée aux administrateurs.")
        return
    
    message = (
        "📋 **COMMANDES ADMINISTRATEUR**\n\n"
        "/stats - Afficher les statistiques complètes\n"
        "/disponibles - Voir les commandes disponibles\n"
        "/encours - Voir les commandes en cours\n"
        "/historique - Voir les 10 dernières commandes\n"
        "/export - Exporter toutes les commandes en CSV\n"
        "/broadcast [message] - Envoyer un message à tous les clients\n\n"
        "🔔 **Services disponibles :**\n"
        "• Crunchyroll 🧡\n"
        "• YouTube Premium ▶️\n"
        "• Spotify Premium 🎧\n"
        "• ChatGPT+ 🤖\n"
        "• Deezer Premium 🎵\n\n"
        "🌐 **Interface Web :** Accessible sur votre URL/dashboard"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def stats(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(DISTINCT user_id) FROM orders")
    total_clients = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status != 'annulee'")
    total_orders = c.fetchone()[0]
    
    c.execute("SELECT SUM(price) FROM orders WHERE price IS NOT NULL AND status != 'annulee'")
    total_revenue = c.fetchone()[0] or 0
    
    c.execute("SELECT SUM(price - COALESCE(cost, 0)) FROM orders WHERE price IS NOT NULL AND status != 'annulee'")
    total_profit = c.fetchone()[0] or 0
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_attente'")
    pending_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='en_cours'")
    in_progress_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='terminee'")
    completed_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM orders WHERE status='annulee'")
    cancelled_orders = c.fetchone()[0]
    
    conn.close()
    
    await update.message.reply_text(
        f"📊 **Statistiques Serveur Express**\n\n"
        f"👥 Nombre de clients : {total_clients}\n"
        f"📦 Nombre de commandes : {total_orders}\n\n"
        f"📋 Statuts :\n"
        f"⏳ En attente : {pending_orders}\n"
        f"🔄 En cours (OCCUPÉ) : {in_progress_orders}\n"
        f"✅ Terminées : {completed_orders}\n"
        f"❌ Annulées : {cancelled_orders}\n\n"
        f"💰 Chiffre d'affaires : {total_revenue:.2f}€\n"
        f"💵 Bénéfices totaux : {total_profit:.2f}€",
        parse_mode='Markdown'
    )

async def encours(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT id, user_id, username, service, plan, price, first_name, last_name, 
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
        status_emoji = "⏳" if order[10] == "en_attente" else "🔄 OCCUPÉ"
        admin_info = f"\n👨‍💼 Pris par : @{order[11]}" if order[11] else ""
        
        message += (
            f"{status_emoji} **#{order[0]}**\n"
            f"{order[3]}\n"
            f"📦 {order[4] or 'N/A'}\n"
            f"👤 @{order[2]} (ID: {order[1]})\n"
            f"📝 {order[6]} {order[7]}\n"
            f"💰 {order[5]}€\n"
            f"💳 {order[8]}{admin_info}\n"
            f"🕐 {order[9]}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def disponibles(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT id, user_id, username, service, plan, price, first_name, last_name, 
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
        message = (
            f"⏳ **Commande #{order[0]}**\n\n"
            f"📦 Service : {order[3]}\n"
            f"📋 Plan : {order[4] or 'N/A'}\n"
            f"👤 Client : @{order[2]} (ID: {order[1]})\n"
            f"📝 Nom : {order[6]} {order[7]}\n"
            f"💰 Prix : {order[5]}€\n"
            f"💳 Paiement : {order[8]}\n"
            f"🕐 {order[9]}"
        )
        
        keyboard = [
            [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order[0]}')],
            [InlineKeyboardButton("❌ Annuler la commande", callback_data=f'cancel_order_{order[0]}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def historique(update: Update, context):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Accès refusé.")
        return
    
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("""SELECT id, user_id, username, service, plan, price, first_name, last_name, 
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
            "en_cours": "🔄 En cours (OCCUPÉ)",
            "terminee": "✅ Terminée",
            "annulee": "❌ Annulée"
        }
        status_text = status_map.get(order[10], order[10])
        admin_info = f" (@{order[11]})" if order[11] else ""
        
        message += (
            f"🆔 #{order[0]} - {status_text}{admin_info}\n"
            f"{order[3]} - {order[4] or 'N/A'}\n"
            f"👤 @{order[2]} (ID: {order[1]})\n"
            f"📝 {order[6]} {order[7]}\n"
            f"💰 {order[5]}€\n"
            f"💳 {order[8]}\n"
            f"🕐 {order[9]}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

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
    writer.writerow(['ID', 'User ID', 'Username', 'Service', 'Plan', 'Photo ID', 'Prix', 'Coût', 'Adresse', 
                     'Prénom', 'Nom', 'Paiement', 'Date', 'Status', 'Admin ID', 'Admin Username', 
                     'Taken At', 'Cancelled By', 'Cancelled At', 'Cancel Reason'])
    writer.writerows(orders)
    
    output.seek(0)
    await update.message.reply_document(
        document=output.getvalue().encode('utf-8'),
        filename=f'orders_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

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

async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    # Service inactif
    if query.data.startswith('inactive_'):
        await query.message.reply_text(
            "⚠️ Ce service est temporairement indisponible.\n"
            "Nous vous informerons dès sa réouverture !"
        )
        return
    
    # Sélection du service
    if query.data.startswith('service_'):
        service_key = query.data.replace('service_', '')
        
        if service_key == 'deezer':
            user_states[query.from_user.id] = {'state': 'waiting_firstname', 'service': 'deezer'}
            await query.message.reply_text("📝 Entrez votre prénom :")
            return
        
        service_info = SERVICES_CONFIG.get(service_key)
        if not service_info or not service_info['plans']:
            await query.message.reply_text("❌ Service non disponible.")
            return
        
        keyboard = []
        for plan_key, plan_info in service_info['plans'].items():
            keyboard.append([InlineKeyboardButton(
                f"{plan_info['label']} - {plan_info['price']}€",
                callback_data=f'plan_{service_key}_{plan_key}'
            )])
        keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data='back_to_main')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"{service_info['name']}\n\n🎯 Choisissez votre formule :",
            reply_markup=reply_markup
        )
        return
    
    # Retour au menu principal
    if query.data == 'back_to_main':
        keyboard = []
        for service_key, service_info in SERVICES_CONFIG.items():
            if service_info['active']:
                keyboard.append([InlineKeyboardButton(service_info['name'], callback_data=f'service_{service_key}')])
            else:
                keyboard.append([InlineKeyboardButton(f"{service_info['name']} (Indisponible)", callback_data=f'inactive_{service_key}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "👋 Bienvenue sur Serveur Express Bot\n\n"
            "🎯 Choisissez le service que vous souhaitez :",
            reply_markup=reply_markup
        )
        return
    
    # Sélection du plan
    if query.data.startswith('plan_'):
        parts = query.data.split('_')
        service_key = parts[1]
        plan_key = '_'.join(parts[2:])
        
        service_info = SERVICES_CONFIG.get(service_key)
        plan_info = service_info['plans'].get(plan_key)
        
        user_states[query.from_user.id] = {
            'state': 'waiting_firstname',
            'service': service_key,
            'service_name': service_info['name'],
            'plan': plan_key,
            'plan_label': plan_info['label'],
            'price': plan_info['price'],
            'cost': plan_info['cost']
        }
        
        await query.message.reply_text("📝 Entrez votre prénom :")
        return
    
    # Annulation de commande
    if query.data.startswith('cancel_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT user_id, username, status FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        if result[2] == 'terminee':
            await query.answer("⚠️ Impossible d'annuler une commande terminée.", show_alert=True)
            conn.close()
            return
        
        if result[2] == 'annulee':
            await query.answer("⚠️ Cette commande est déjà annulée.", show_alert=True)
            conn.close()
            return
        
        c.execute("""UPDATE orders 
                     SET status='annulee', cancelled_by=?, cancelled_at=?, cancel_reason='Annulée par admin'
                     WHERE id=?""",
                  (query.from_user.id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
        conn.commit()
        
        c.execute("SELECT admin_id, message_id, photo_message_id FROM order_messages WHERE order_id=?", (order_id,))
        messages = c.fetchall()
        conn.close()
        
        try:
            await context.bot.send_message(
                chat_id=result[0],
                text=f"❌ Votre commande #{order_id} a été annulée par l'administration.\n\n"
                     f"Pour plus d'informations, contactez le support."
            )
        except:
            pass
        
        deleted_count = 0
        for msg in messages:
            admin_id = msg[0]
            message_id = msg[1]
            photo_id = msg[2]
            
            try:
                await context.bot.delete_message(chat_id=admin_id, message_id=message_id)
                deleted_count += 1
                print(f"✅ Message {message_id} supprimé pour admin {admin_id}")
            except Exception as e:
                print(f"❌ Erreur suppression message {message_id} admin {admin_id}: {e}")
            
            if photo_id:
                try:
                    await context.bot.delete_message(chat_id=admin_id, message_id=photo_id)
                    deleted_count += 1
                    print(f"✅ Photo {photo_id} supprimée pour admin {admin_id}")
                except Exception as e:
                    print(f"❌ Erreur suppression photo {photo_id} admin {admin_id}: {e}")
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("DELETE FROM order_messages WHERE order_id=?", (order_id,))
        conn.commit()
        conn.close()
        
        print(f"📊 Total messages supprimés: {deleted_count}")
        await query.answer(f"✅ Commande #{order_id} annulée - {deleted_count} messages supprimés.", show_alert=True)
        return
    
    # Prendre en charge
    if query.data.startswith('take_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT status, admin_username, admin_id FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        if result[0] == 'en_cours':
            admin_name = result[1] or f"Admin ID {result[2]}"
            await query.answer(f"⚠️ Commande déjà OCCUPÉE par @{admin_name}", show_alert=True)
            conn.close()
            return
        
        if result[0] == 'annulee':
            await query.answer("⚠️ Cette commande est annulée.", show_alert=True)
            conn.close()
            return
        
        if result[0] == 'terminee':
            await query.answer("⚠️ Cette commande est déjà terminée.", show_alert=True)
            conn.close()
            return
        
        c.execute("""UPDATE orders 
                     SET status='en_cours', admin_id=?, admin_username=?, taken_at=?
                     WHERE id=?""",
                  (query.from_user.id, query.from_user.username or str(query.from_user.id),
                   datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
        conn.commit()
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("✅ Terminer", callback_data=f'complete_order_{order_id}')],
            [InlineKeyboardButton("🔄 Remettre en ligne", callback_data=f'release_order_{order_id}')],
            [InlineKeyboardButton("❌ Annuler", callback_data=f'cancel_order_{order_id}')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(
                query.message.text + f"\n\n🔄 **OCCUPÉ - En cours par @{query.from_user.username or query.from_user.id}**",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except:
            pass
        
        await query.answer(f"✅ Commande #{order_id} prise en charge !", show_alert=True)
        return
    
    # Terminer
    if query.data.startswith('complete_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT admin_id, status, user_id FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        if result[1] == 'annulee':
            await query.answer("⚠️ Impossible de terminer une commande annulée.", show_alert=True)
            conn.close()
            return
        
        if result[0] and result[0] != query.from_user.id and result[1] != 'en_attente':
            await query.answer("⚠️ Seul l'admin en charge peut terminer cette commande.", show_alert=True)
            conn.close()
            return
        
        c.execute("UPDATE orders SET status='terminee' WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
        
        try:
            await context.bot.send_message(
                chat_id=result[2],
                text=f"✅ Votre commande #{order_id} a été livrée avec succès !\n\n"
                     f"Merci d'avoir utilisé Serveur Express Bot 🎉"
            )
        except:
            pass
        
        try:
            await query.edit_message_text(
                query.message.text.split('\n\n🔄')[0] + f"\n\n✅ **Terminée par @{query.from_user.username or query.from_user.id}**",
                parse_mode='Markdown'
            )
        except:
            pass
        
        await query.answer(f"✅ Commande #{order_id} marquée comme terminée !", show_alert=True)
        return
    
    # Remettre en ligne
    if query.data.startswith('release_order_'):
        if query.from_user.id not in ADMIN_IDS:
            await query.answer("⛔ Accès refusé.", show_alert=True)
            return
        
        order_id = int(query.data.split('_')[2])
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT admin_id, status FROM orders WHERE id=?", (order_id,))
        result = c.fetchone()
        
        if not result:
            await query.answer("❌ Commande introuvable.", show_alert=True)
            conn.close()
            return
        
        if result[1] == 'annulee':
            await query.answer("⚠️ Impossible de remettre en ligne une commande annulée.", show_alert=True)
            conn.close()
            return
        
        if result[0] != query.from_user.id:
            await query.answer("⚠️ Seul l'admin en charge peut remettre cette commande en ligne.", show_alert=True)
            conn.close()
            return
        
        c.execute("""UPDATE orders 
                     SET status='en_attente', admin_id=NULL, admin_username=NULL, taken_at=NULL
                     WHERE id=?""", (order_id,))
        conn.commit()
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("✋ Prendre en charge", callback_data=f'take_order_{order_id}')],
            [InlineKeyboardButton("❌ Annuler la commande", callback_data=f'cancel_order_{order_id}')]
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
        return
    
    # Paiement
    if query.data in ['paypal', 'virement', 'revolut']:
        state = user_states.get(query.from_user.id)
        if not state or state['state'] != 'waiting_payment':
            return
        
        payment_methods = {
            'paypal': '💳 PayPal',
            'virement': '🏦 Virement',
            'revolut': '📱 Revolut'
        }
        payment_method = payment_methods[query.data]
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        
        if state['service'] == 'deezer':
            c.execute("""INSERT INTO orders (user_id, username, service, plan, price, cost, first_name, last_name, payment_method, timestamp, status)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'en_attente')""",
                      (query.from_user.id, query.from_user.username or 'Unknown', 'Deezer Premium', 'Premium',
                       6.00, 0.00, state['first_name'], state['last_name'], payment_method,
                       datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        else:
            c.execute("""INSERT INTO orders (user_id, username, service, plan, price, cost, first_name, last_name, payment_method, timestamp, status)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'en_attente')""",
                      (query.from_user.id, query.from_user.username or 'Unknown', state['service_name'],
                       state['plan_label'], state['price'], state['cost'], state['first_name'], state['last_name'],
                       payment_method, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        d>/take', methods=['POST'])
@login_required
def api_take_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='en_cours', admin_id=?, admin_username='WebAdmin', taken_at=? WHERE id=? AND status='en_attente'",
              (999999, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/order/<int:order_i
