import os
import threading
import sqlite3
import csv
import time
import asyncio
from datetime import datetime
from io import StringIO
from flask import Flask, render_template_string, request, jsonify, redirect, session, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import requests
from functools import wraps
import json

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
            'premium': {'label': 'Premium', 'price': 6.00, 'cost': 0.00}
        }
    },
    'ubereats': {
        'name': '🍔 Uber Eats',
        'active': False,
        'plans': {}
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

# ============= PWA FILES =============

MANIFEST_JSON = {
    "name": "Serveur Express Admin",
    "short_name": "SE Admin",
    "description": "Dashboard administrateur Serveur Express Bot",
    "start_url": "/dashboard",
    "display": "standalone",
    "background_color": "#667eea",
    "theme_color": "#667eea",
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

# ============= ROUTES PWA =============

@app.route('/manifest.json')
def manifest():
    return jsonify(MANIFEST_JSON)

@app.route('/sw.js')
def service_worker():
    return SERVICE_WORKER_JS, 200, {'Content-Type': 'application/javascript'}

@app.route('/api/subscribe', methods=['POST'])
@login_required
def subscribe_push():
    subscription = request.json
    if subscription not in push_subscriptions:
        push_subscriptions.append(subscription)
    return jsonify({'success': True})

# ============= INTERFACE WEB =============

HTML_LOGIN = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#667eea">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Connexion - Admin Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
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
    
    <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js');
        }
    </script>
</body>
</html>
'''

HTML_DASHBOARD = '''
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#667eea">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <title>Dashboard Admin - Serveur Express Bot</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: #f5f7fa;
            color: #333;
            -webkit-font-smoothing: antialiased;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header h1 { 
            font-size: 20px;
        }
        
        .header-buttons {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        .notif-badge {
            position: relative;
            background: rgba(255,255,255,0.2);
            padding: 8px 12px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
        }
        
        .notif-badge.active::after {
            content: '';
            position: absolute;
            top: 5px;
            right: 5px;
            width: 8px;
            height: 8px;
            background: #4caf50;
            border-radius: 50%;
        }
        
        .logout-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            font-size: 14px;
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
            border-left: 4px solid #667eea;
        }
        
        .stat-card h3 {
            color: #666;
            font-size: 12px;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        
        .stat-card .value {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        
        .orders-section {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        
        .section-title {
            font-size: 18px;
            margin-bottom: 15px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 8px;
        }
        
        .filters {
            display: flex;
            gap: 8px;
            margin-bottom: 15px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            padding-bottom: 5px;
        }
        
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 20px;
            cursor: pointer;
            font-size: 13px;
            white-space: nowrap;
            flex-shrink: 0;
        }
        
        .filter-btn.active {
            background: #667eea;
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
            align-items: center;
            margin-bottom: 12px;
        }
        
        .order-id {
            font-weight: bold;
            font-size: 16px;
            color: #667eea;
        }
        
        .status-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status-badge.en_attente { background: #fff3cd; color: #856404; }
        .status-badge.en_cours { background: #d1ecf1; color: #0c5460; }
        .status-badge.terminee { background: #d4edda; color: #155724; }
        .status-badge.annulee { background: #f8d7da; color: #721c24; }
        
        .order-details {
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
            margin-bottom: 12px;
            font-size: 13px;
        }
        
        .detail-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .detail-item strong {
            color: #667eea;
        }
        
        .order-actions {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
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
        
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #999;
        }
        
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: #667eea;
            color: white;
            border: none;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            z-index: 99;
        }
        
        .install-prompt {
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: #667eea;
            color: white;
            padding: 12px 20px;
            border-radius: 25px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            display: none;
            align-items: center;
            gap: 10px;
            z-index: 99;
        }
        
        .install-prompt button {
            background: white;
            color: #667eea;
            border: none;
            padding: 6px 12px;
            border-radius: 15px;
            font-weight: bold;
            cursor: pointer;
        }
        
        @media (min-width: 768px) {
            .header h1 { font-size: 24px; }
            .stats-grid { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
            .stat-card .value { font-size: 32px; }
            .order-details { grid-template-columns: repeat(2, 1fr); }
            .action-btn { flex: 0; }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>🤖 SE Admin</h1>
            <div class="header-buttons">
                <div class="notif-badge" id="notif-bell" onclick="requestNotificationPermission()">
                    🔔
                </div>
                <a href="/logout" class="logout-btn">Déconnexion</a>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📦 Total</h3>
                <div class="value" id="total-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>⏳ Attente</h3>
                <div class="value" id="pending-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>🔄 Cours</h3>
                <div class="value" id="inprogress-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>✅ Terminées</h3>
                <div class="value" id="completed-orders">0</div>
            </div>
            <div class="stat-card">
                <h3>💰 CA</h3>
                <div class="value" id="revenue">0€</div>
            </div>
            <div class="stat-card">
                <h3>💵 Bénéf</h3>
                <div class="value" id="profit">0€</div>
            </div>
        </div>

        <div class="orders-section">
            <h2 class="section-title">📋 Commandes</h2>
            
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
    
    <div class="install-prompt" id="install-prompt">
        <span>📱 Installer l'app</span>
        <button onclick="installApp()">Installer</button>
        <button onclick="document.getElementById('install-prompt').style.display='none'">✕</button>
    </div>

    <script>
        let currentFilter = 'all';
        let lastOrderCount = 0;
        let deferredPrompt;

        // PWA Installation
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            document.getElementById('install-prompt').style.display = 'flex';
        });

        function installApp() {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choiceResult) => {
                    deferredPrompt = null;
                    document.getElementById('install-prompt').style.display = 'none';
                });
            }
        }

        // Service Worker & Notifications
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').then((registration) => {
                console.log('Service Worker enregistré');
            });
        }

        async function requestNotificationPermission() {
            if ('Notification' in window) {
                const permission = await Notification.requestPermission();
                if (permission === 'granted') {
                    document.getElementById('notif-bell').classList.add('active');
                    alert('✅ Notifications activées !');
                }
            }
        }

        // Check notification permission on load
        if ('Notification' in window && Notification.permission === 'granted') {
            document.getElementById('notif-bell').classList.add('active');
        }

        async function loadData() {
            try {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                
                // Check for new orders
                if (lastOrderCount > 0 && data.stats.total_orders > lastOrderCount) {
                    showNotification('Nouvelle commande !', `${data.stats.total_orders - lastOrderCount} nouvelle(s) commande(s)`);
                    playNotificationSound();
                }
                lastOrderCount = data.stats.total_orders;
                
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

        function showNotification(title, body) {
            if ('Notification' in window && Notification.permission === 'granted') {
                new Notification(title, {
                    body: body,
                    icon: '/static/icon-192.png',
                    badge: '/static/icon-192.png',
                    vibrate: [200, 100, 200]
                });
            }
        }

        function playNotificationSound() {
            const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBTGH0fPTgjMGHm7A7+OZWRQJ');
            audio.play().catch(e => console.log('Erreur son:', e));
        }

        function displayOrders(orders) {
            const container = document.getElementById('orders-container');
            
            const filtered = currentFilter === 'all' 
                ? orders 
                : orders.filter(o => o.status === currentFilter);
            
            if (filtered.length === 0) {
                container.innerHTML = '<div class="empty-state"><h3>Aucune commande</h3></div>';
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
                        <button class="action-btn btn-complete" onclick="completeOrder(${order.id})">✅ OK</button>
                        <button class="action-btn btn-release" onclick="releaseOrder(${order.id})">🔄</button>
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌</button>
                    `;
                }
                
                const details = `
                    <div class="detail-item">📦 <strong>${order.service}</strong></div>
                    ${order.plan ? `<div class="detail-item">📋 <strong>${order.plan}</strong></div>` : ''}
                    <div class="detail-item">👤 <strong>@${order.username}</strong></div>
                    <div class="detail-item">💰 <strong>${order.price}€</strong></div>
                `;
                
                return `
                    <div class="order-card ${order.status}">
                        <div class="order-header">
                            <div class="order-id">#${order.id}</div>
                            <div class="status-badge ${order.status}">${statusText[order.status]}</div>
                        </div>
                        <div class="order-details">
                            ${details}
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

@app.route('/api/order/<int:order_id>/take', methods=['POST'])
@login_required
def api_take_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='en_cours', admin_id=999999, admin_username='web_admin', taken_at=? WHERE id=?",
              (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), order_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

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

# ============= CODE TELEGRAM (reste inchangé) =============

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

# ... (le reste du code Telegram reste identique)

async def run_telegram_bot():
    print("🤖 Initialisation du bot Telegram...")
    
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('stats', stats))
    
    force_kill_all_instances()
    
    print("🤖 Bot Telegram démarré en mode POLLING...")
    
    await application.initialize()
    await application.start()
    
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )
    
    print("✅ Bot Telegram connecté avec succès!")
    
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Arrêt du bot...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def start_telegram_bot():
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
