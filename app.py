# Full app.py - Dashboard Utilisateurs + Gestion commandes Telegram + Stats cumulatives
# - Système de parrainage RETIRÉ
# - Dashboard utilisateurs avancé avec recherche
# - Gestion complète des commandes depuis Telegram (prendre/annuler/remettre/terminer)
# - Stats cumulatives (CA et bénéfices ne reviennent jamais à 0)
# - Image au lancement du bot
# - Prix Deezer à 10€

import os
import sqlite3
import requests
import random
import traceback
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from functools import wraps
import threading
import time

BOT_TOKEN = os.getenv('BOT_TOKEN')
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
            'premium': {'label': 'Deezer Premium', 'price': 10.00, 'cost': 3.00}
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

# DATABASE avec table users + statistiques cumulatives
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
    
    # Nouvelle table users pour tracking
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  last_name TEXT,
                  first_seen TEXT,
                  last_activity TEXT,
                  total_orders INTEGER DEFAULT 0)''')
    
    # Table pour stats cumulatives (CA et bénéfices ne reviennent jamais à 0)
    c.execute('''CREATE TABLE IF NOT EXISTS cumulative_stats
                 (id INTEGER PRIMARY KEY CHECK (id = 1),
                  total_revenue REAL DEFAULT 0,
                  total_profit REAL DEFAULT 0,
                  last_updated TEXT)''')
    
    # Initialiser les stats cumulatives si pas encore fait
    c.execute("SELECT COUNT(*) FROM cumulative_stats WHERE id=1")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO cumulative_stats (id, total_revenue, total_profit, last_updated) VALUES (1, 0, 0, ?)",
                  (datetime.now().isoformat(),))
    
    conn.commit()
    conn.close()

init_db()

# ----------------------- HTML TEMPLATES -----------------------
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
        .header-actions {
            display: flex;
            gap: 10px;
        }
        .logout-btn, .simulate-btn, .users-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
        }
        .simulate-btn {
            background: rgba(255,255,255,0.3);
        }
        .users-btn {
            background: rgba(100,200,255,0.3);
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
        .stat-card.cumulative {
            border-left-color: #10b981;
        }
        .stat-card.cumulative .value {
            color: #10b981;
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
        <div class="header-actions">
            <a href="/users" class="users-btn">👥 Utilisateurs</a>
            <a href="/simulate" class="simulate-btn">🎲 Simuler</a>
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
            <div class="stat-card cumulative">
                <h3>💰 CA Total (Cumulé)</h3>
                <div class="value" id="revenue">0€</div>
            </div>
            <div class="stat-card cumulative">
                <h3>💵 Bénéfice Total (Cumulé)</h3>
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
                        <div><strong>Paiement:</strong> ${order.payment_method || 'N/A'}</div>
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

HTML_SIMULATE = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#667eea">
    <title>Simuler des ventes - B4U Deals</title>
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
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .back-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
        }
        .container {
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
        }
        .card {
            background: white;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        h2 {
            color: #667eea;
            margin-bottom: 30px;
            text-align: center;
        }
        .form-group {
            margin-bottom: 25px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
        }
        .btn-generate {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        .btn-generate:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102,126,234,0.4);
        }
        .result {
            margin-top: 20px;
            padding: 20px;
            border-radius: 10px;
            display: none;
        }
        .result.success {
            background: #d1e7dd;
            color: #0f5132;
            display: block;
        }
        .result.error {
            background: #f8d7da;
            color: #842029;
            display: block;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎲 Simulateur de Ventes</h1>
        <a href="/dashboard" class="back-btn">← Retour</a>
    </div>

    <div class="container">
        <div class="card">
            <h2>Générer des ventes fictives</h2>
            
            <form id="simulateForm">
                <div class="form-group">
                    <label>Nombre de commandes à générer</label>
                    <input type="number" name="count" min="1" max="100" value="10" required>
                </div>

                <div class="form-group">
                    <label>Service</label>
                    <select name="service">
                        <option value="all">Tous les services (aléatoire)</option>
                        <option value="netflix">🎬 Netflix</option>
                        <option value="hbo">🎬 HBO Max</option>
                        <option value="crunchyroll">🎬 Crunchyroll</option>
                        <option value="canal">🎬 Canal+</option>
                        <option value="disney">🎬 Disney+</option>
                        <option value="ufc">🎬 UFC Fight Pass</option>
                        <option value="youtube">▶️ YouTube Premium</option>
                        <option value="spotify">🎧 Spotify Premium</option>
                        <option value="deezer">🎵 Deezer Premium</option>
                        <option value="chatgpt">🤖 ChatGPT+</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Statut des commandes</label>
                    <select name="status">
                        <option value="terminee">✅ Terminée</option>
                        <option value="en_cours">🔄 En cours</option>
                        <option value="en_attente">⏳ En attente</option>
                        <option value="annulee">❌ Annulée</option>
                    </select>
                </div>

                <button type="submit" class="btn-generate">🚀 Générer les ventes</button>
            </form>

            <div id="result" class="result"></div>
        </div>
    </div>

    <script>
        document.getElementById('simulateForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(e.target);
            const data = {
                count: formData.get('count'),
                service: formData.get('service'),
                status: formData.get('status')
            };

            const resultDiv = document.getElementById('result');
            resultDiv.textContent = '⏳ Génération en cours...';
            resultDiv.className = 'result';
            resultDiv.style.display = 'block';

            try {
                const response = await fetch('/api/simulate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await response.json();

                if (result.success) {
                    resultDiv.className = 'result success';
                    resultDiv.innerHTML = `
                        <strong>✅ Succès !</strong><br>
                        ${result.created} commande(s) générée(s) avec succès !<br>
                        <a href="/dashboard" style="color: #0f5132; text-decoration: underline">Voir dans le dashboard</a>
                    `;
                } else {
                    resultDiv.className = 'result error';
                    resultDiv.textContent = '❌ Erreur lors de la génération : ' + (result.error || JSON.stringify(result));
                }
            } catch (error) {
                resultDiv.className = 'result error';
                resultDiv.textContent = '❌ Erreur: ' + error.message;
            }
        });
    </script>
</body>
</html>
'''

# NOUVELLE PAGE: Dashboard Utilisateurs
HTML_USERS = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Utilisateurs - B4U Deals</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .back-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
        }
        .container {
            max-width: 1400px;
            margin: 20px auto;
            padding: 0 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        .stat-card h3 {
            color: #666;
            font-size: 13px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }
        .users-section {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th {
            background: #f9fafb;
            font-weight: 600;
            color: #333;
        }
        tr:hover {
            background: #f9fafb;
        }
        .search-box {
            margin-bottom: 20px;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            width: 100%;
            max-width: 400px;
        }
        .btn-view {
            padding: 8px 15px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
        }
        .btn-view:hover {
            background: #5568d3;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }
        .modal-content {
            background-color: white;
            margin: 5% auto;
            padding: 30px;
            border-radius: 15px;
            width: 90%;
            max-width: 600px;
            max-height: 70vh;
            overflow-y: auto;
        }
        .close {
            color: #aaa;
            float: right;
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
        }
        .close:hover {
            color: #000;
        }
        .order-item {
            padding: 12px;
            background: #f9fafb;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }
        .badge-active {
            background: #d1e7dd;
            color: #0f5132;
        }
        .badge-inactive {
            background: #f8d7da;
            color: #842029;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>👥 Gestion des Utilisateurs</h1>
        <a href="/dashboard" class="back-btn">← Dashboard</a>
    </div>

    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>👥 Total Utilisateurs</h3>
                <div class="value" id="total-users">0</div>
            </div>
            <div class="stat-card">
                <h3>🛒 Clients Actifs</h3>
                <div class="value" id="active-users">0</div>
            </div>
            <div class="stat-card">
                <h3>📈 Taux Conversion</h3>
                <div class="value" id="conversion-rate">0%</div>
            </div>
            <div class="stat-card">
                <h3>🆕 Nouveaux (7j)</h3>
                <div class="value" id="new-users">0</div>
            </div>
        </div>

        <div class="users-section">
            <h2 style="margin-bottom:20px">📊 Liste des Utilisateurs</h2>
            <input type="text" class="search-box" id="searchBox" placeholder="🔍 Rechercher un utilisateur..." onkeyup="filterTable()">
            <table id="usersTable">
                <thead>
                    <tr>
                        <th>👤 Utilisateur</th>
                        <th>📞 Telegram</th>
                        <th>📊 Statut</th>
                        <th>🛒 Commandes</th>
                        <th>📅 Première visite</th>
                        <th>🕐 Dernière activité</th>
                        <th>📋 Actions</th>
                    </tr>
                </thead>
                <tbody id="users-body"></tbody>
            </table>
        </div>
    </div>

    <div id="detailsModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="closeModal()">&times;</span>
            <h2 id="modal-title">Détails</h2>
            <div id="modal-body"></div>
        </div>
    </div>

    <script>
        async function loadUsers() {
            const response = await fetch('/api/users');
            const data = await response.json();
            
            document.getElementById('total-users').textContent = data.stats.total_users;
            document.getElementById('active-users').textContent = data.stats.active_users;
            document.getElementById('conversion-rate').textContent = data.stats.conversion_rate + '%';
            document.getElementById('new-users').textContent = data.stats.new_users;
            
            const tbody = document.getElementById('users-body');
            tbody.innerHTML = data.users.map(u => {
                const isActive = u.total_orders > 0;
                const badge = isActive ? 
                    '<span class="badge badge-active">✅ Client</span>' : 
                    '<span class="badge badge-inactive">❌ Inactif</span>';
                
                return `
                    <tr>
                        <td><strong>${u.first_name || 'Inconnu'} ${u.last_name || ''}</strong></td>
                        <td>@${u.username || 'N/A'} <br><small style="color:#999">ID: ${u.user_id}</small></td>
                        <td>${badge}</td>
                        <td><strong style="color:#667eea;font-size:18px">${u.total_orders}</strong></td>
                        <td>${new Date(u.first_seen).toLocaleDateString('fr-FR')}</td>
                        <td>${new Date(u.last_activity).toLocaleDateString('fr-FR')}</td>
                        <td><button class="btn-view" onclick="showDetails(${u.user_id}, '${u.first_name}', '@${u.username}')">👁️ Voir</button></td>
                    </tr>
                `;
            }).join('');
        }

        async function showDetails(userId, name, username) {
            const response = await fetch(`/api/users/${userId}`);
            const data = await response.json();
            
            document.getElementById('modal-title').textContent = `📋 Commandes de ${name} (${username})`;
            
            if (data.orders.length === 0) {
                document.getElementById('modal-body').innerHTML = '<p style="text-align:center;color:#999;padding:40px">Aucune commande</p>';
            } else {
                document.getElementById('modal-body').innerHTML = data.orders.map(o => `
                    <div class="order-item">
                        <strong>#${o.id} - ${o.service}</strong><br>
                        <small style="color:#666">📦 ${o.plan} - ${o.price}€</small><br>
                        <small style="color:#666">📅 ${new Date(o.timestamp).toLocaleString('fr-FR')}</small><br>
                        <small style="color:#999">Statut: ${o.status}</small>
                    </div>
                `).join('');
            }
            
            document.getElementById('detailsModal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('detailsModal').style.display = 'none';
        }

        function filterTable() {
            const input = document.getElementById('searchBox');
            const filter = input.value.toUpperCase();
            const table = document.getElementById('usersTable');
            const tr = table.getElementsByTagName('tr');
            
            for (let i = 1; i < tr.length; i++) {
                const td = tr[i].getElementsByTagName('td');
                let found = false;
                for (let j = 0; j < td.length; j++) {
                    if (td[j].innerHTML.toUpperCase().indexOf(filter) > -1) {
                        found = true;
                        break;
                    }
                }
                tr[i].style.display = found ? '' : 'none';
            }
        }

        window.onclick = function(event) {
            const modal = document.getElementById('detailsModal');
            if (event.target == modal) {
                closeModal();
            }
        }

        loadUsers();
        setInterval(loadUsers, 30000);
    </script>
</body>
</html>
'''

# ----------------------- FLASK ROUTES -----------------------

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

@app.route('/simulate')
@login_required
def simulate():
    return render_template_string(HTML_SIMULATE)

@app.route('/users')
@login_required
def users_page():
    return render_template_string(HTML_USERS)

# API USERS
@app.route('/api/users')
@login_required
def api_users():
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE total_orders > 0")
    active_users = c.fetchone()[0]
    
    conversion_rate = (active_users / total_users * 100) if total_users > 0 else 0
    
    from datetime import timedelta
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    c.execute("SELECT COUNT(*) FROM users WHERE first_seen >= ?", (seven_days_ago,))
    new_users = c.fetchone()[0]
    
    c.execute("""SELECT user_id, username, first_name, last_name, first_seen, last_activity, total_orders
                 FROM users
                 ORDER BY last_activity DESC""")
    
    users = []
    for row in c.fetchall():
        users.append({
            'user_id': row[0],
            'username': row[1] or 'N/A',
            'first_name': row[2] or 'Inconnu',
            'last_name': row[3] or '',
            'first_seen': row[4],
            'last_activity': row[5],
            'total_orders': row[6]
        })
    
    conn.close()
    
    return jsonify({
        'stats': {
            'total_users': total_users,
            'active_users': active_users,
            'conversion_rate': round(conversion_rate, 1),
            'new_users': new_users
        },
        'users': users
    })

@app.route('/api/users/<int:user_id>')
@login_required
def api_user_details(user_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    c.execute("""SELECT id, service, plan, price, timestamp, status
                 FROM orders
                 WHERE user_id=?
                 ORDER BY timestamp DESC""", (user_id,))
    
    orders = []
    for row in c.fetchall():
        orders.append({
            'id': row[0],
            'service': row[1],
            'plan': row[2],
            'price': row[3],
            'timestamp': row[4],
            'status': row[5]
        })
    
    conn.close()
    
    return jsonify({'orders': orders})

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
    
    # Récupérer les stats cumulatives
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

@app.route('/api/order/<int:order_id>/take', methods=['POST'])
@login_required
def take_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='en_cours', admin_username=?, taken_at=? WHERE id=?", 
              ('web_admin', datetime.now().isoformat(), order_id))
    conn.commit()
    conn.close()
    try:
        edit_notifications_for_order(order_id, f"🔔 *COMMANDE #{order_id} — PRISE EN CHARGE*\n\nPris en charge via le dashboard\n🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    except Exception as e:
        print("Erreur edit notifications:", e)
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    
    # Récupérer prix et coût
    c.execute("SELECT price, cost FROM orders WHERE id=?", (order_id,))
    row = c.fetchone()
    if row:
        price, cost = row
        # Mettre à jour stats cumulatives
        c.execute("UPDATE cumulative_stats SET total_revenue = total_revenue + ?, total_profit = total_profit + ?, last_updated = ? WHERE id=1",
                  (price, price - cost, datetime.now().isoformat()))
    
    c.execute("UPDATE orders SET status='terminee' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    try:
        edit_notifications_for_order(order_id, f"✅ *COMMANDE #{order_id} — TERMINÉE*\n\nTerminée via le dashboard\n🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    except Exception as e:
        print("Erreur edit notifications:", e)
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='annulee', cancelled_at=? WHERE id=?",
              (datetime.now().isoformat(), order_id))
    conn.commit()
    conn.close()
    try:
        edit_notifications_for_order(order_id, f"❌ *COMMANDE #{order_id} — ANNULÉE*\n\nAnnulée via le dashboard\n🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    except Exception as e:
        print("Erreur edit notifications:", e)
    return jsonify({'success': True})

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'bot': 'running'})

# ----------------------- SIMULATE SALES -----------------------
@app.route('/api/simulate', methods=['POST'])
@login_required
def api_simulate():
    from datetime import timedelta

    try:
        data = request.get_json(force=True)
        if data is None:
            raise ValueError("Corps JSON vide")
    except Exception as e:
        return jsonify({'success': False, 'error': 'invalid_json', 'detail': str(e)}), 400

    try:
        count = int(data.get('count', 1))
    except Exception as e:
        return jsonify({'success': False, 'error': 'invalid_count'}), 400

    service_filter = data.get('service', 'all')
    status = data.get('status', 'terminee')

    first_names = ['Lucas', 'Emma', 'Louis', 'Léa', 'Hugo', 'Chloé', 'Arthur', 'Manon', 'Jules', 'Camille']
    last_names = ['Martin', 'Bernard', 'Dubois', 'Thomas', 'Robert', 'Richard', 'Petit', 'Durand']
    payment_methods = ['PayPal', 'Virement', 'Revolut']

    services_list = []
    for service_key, service_data in SERVICES_CONFIG.items():
        for plan_key, plan_data in service_data['plans'].items():
            services_list.append({
                'key': service_key,
                'name': service_data['name'],
                'plan_key': plan_key,
                'plan_label': plan_data['label'],
                'price': plan_data['price'],
                'cost': plan_data['cost']
            })

    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()

    created_orders = []
    try:
        for i in range(count):
            if service_filter == 'all':
                service = random.choice(services_list)
            else:
                filtered = [s for s in services_list if s['key'] == service_filter]
                service = random.choice(filtered) if filtered else random.choice(services_list)

            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@email.com"
            user_id = random.randint(100000000, 999999999)
            username = f"user_{random.randint(1000, 9999)}"
            payment_method = random.choice(payment_methods)

            days_ago = random.randint(0, 30)
            timestamp = (datetime.now() - timedelta(days=days_ago)).isoformat()

            # Enregistrer l'utilisateur
            c.execute("""INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, first_seen, last_activity, total_orders)
                         VALUES (?, ?, ?, ?, ?, ?, 0)""", 
                      (user_id, username, first_name, last_name, timestamp, timestamp))
            
            c.execute("UPDATE users SET last_activity = ?, total_orders = total_orders + 1 WHERE user_id = ?",
                      (timestamp, user_id))

            if service['key'] == 'deezer':
                c.execute("""INSERT INTO orders 
                             (user_id, username, service, plan, price, cost, timestamp, status,
                              first_name, last_name, email)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (user_id, username, service['name'], service['plan_label'],
                           service['price'], service['cost'], timestamp, status,
                           first_name, last_name, email))
            else:
                c.execute("""INSERT INTO orders 
                             (user_id, username, service, plan, price, cost, timestamp, status,
                              first_name, last_name, email, payment_method)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (user_id, username, service['name'], service['plan_label'],
                           service['price'], service['cost'], timestamp, status,
                           first_name, last_name, email, payment_method))

            order_id = c.lastrowid
            
            # Si terminée, mettre à jour stats cumulatives
            if status == 'terminee':
                c.execute("UPDATE cumulative_stats SET total_revenue = total_revenue + ?, total_profit = total_profit + ?, last_updated = ? WHERE id=1",
                          (service['price'], service['price'] - service['cost'], datetime.now().isoformat()))

            created_orders.append({
                'id': order_id,
                'service': service['name'],
                'price': service['price']
            })

        conn.commit()

    except Exception as e:
        conn.rollback()
        tb = traceback.format_exc()
        print("Erreur génération commandes:", e)
        print(tb)
        return jsonify({'success': False, 'error': 'exception_during_insert', 'detail': str(e)}), 500

    finally:
        conn.close()

    return jsonify({'success': True, 'created': len(created_orders), 'orders': created_orders})

# ----------------------- TELEGRAM BOT HANDLERS -----------------------

# Helper pour enregistrer/update user
def update_user_activity(user_id, username, first_name, last_name):
    """Enregistre ou met à jour l'activité d'un utilisateur"""
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
    
    # Enregistrer l'activité
    update_user_activity(user_id, username, first_name, last_name)
    
    # Menu principal
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
    
    # Envoyer l'image avec le message
    try:
        # URL de l'image B4U Deals
        image_url = "https://raw.githubusercontent.com/Noallo312/serveur_express_bot/refs/heads/main/514B1CC0-791F-47CA-825C-F82A4100C02E.png"
        await update.message.reply_photo(
            photo=image_url,
            caption=welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    except Exception as e:
        # Si l'image ne charge pas, envoyer juste le texte
        print(f"Erreur chargement image: {e}")
        await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    username = query.from_user.username or f"User_{user_id}"
    first_name = query.from_user.first_name or "Utilisateur"
    last_name = query.from_user.last_name or ""
    
    # Update activité
    update_user_activity(user_id, username, first_name, last_name)
    
    # Catégories
    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        keyboard = []
        
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
        
        await query.edit_message_caption(
            caption=f"*{category_labels.get(category, category)}*\n\nChoisis ton service :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Services
    if data.startswith("service_"):
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
        
        await query.edit_message_caption(
            caption=f"*{service['name']}*\n\nChoisis ton abonnement :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return
    
    # Plans
    if data.startswith("plan_"):
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
        
        # Formulaire Deezer
        if service_key == 'deezer':
            await query.message.reply_text(
                f"✅ *Commande confirmée*\n\nService: {service['name']}\nPlan: {plan['label']}\nPrix: {plan['price']}€\n\n📝 Envoie ton nom, prénom et mail (chacun sur une ligne)",
                parse_mode='Markdown'
            )
            user_states[user_id]['step'] = 'waiting_deezer_form'
            return
        
        # Formulaire standard
        else:
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
            await query.message.reply_text(form_text, parse_mode='Markdown')
            return
    
    # Retour au menu principal
    if data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],
            [InlineKeyboardButton("🎧 Musique (Spotify, Deezer)", callback_data="cat_music")],
            [InlineKeyboardButton("🤖 IA (ChatGPT+)", callback_data="cat_ai")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_caption(
            caption="🎯 *B4U Deals*\n\nChoisis une catégorie :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        return

    # Actions admin depuis Telegram
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
        c.execute("SELECT service, plan, price, cost FROM orders WHERE id=?", (order_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            await query.answer("Commande introuvable", show_alert=True)
            return
        service_name, plan_label, price, cost = row

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

        elif action == "complete":
            # Mettre à jour stats cumulatives
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

        elif action == "restore":
            c.execute("UPDATE orders SET status='en_attente', admin_id=NULL, admin_username=NULL, taken_at=NULL, cancelled_by=NULL, cancelled_at=NULL WHERE id=?",
                      (order_id,))
            conn.commit()
            new_text = (
                f"🔄 *COMMANDE #{order_id} — REMISE EN LIGNE*\n\n"
                f"Remise en attente par @{admin_username}\n"
                f"📦 {service_name} — {plan_label}\n"
                f"💰 {price}€\n"
                f"💵 Coût: {cost}€\n"
                f"📈 Bénéf: {price - cost}€\n\n"
                f"🕒 {timestamp}"
            )
            answer_text = "✅ Commande remise en ligne"

        else:
            conn.close()
            await query.answer("Action inconnue", show_alert=True)
            return

        try:
            c.execute("SELECT admin_id, message_id FROM order_messages WHERE order_id=?", (order_id,))
            rows = c.fetchall()
            for admin_chat_id, message_id in rows:
                try:
                    await context.bot.edit_message_text(
                        chat_id=admin_chat_id,
                        message_id=message_id,
                        text=new_text,
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"),
                            InlineKeyboardButton("✅ Terminer", callback_data=f"admin_complete_{order_id}"),
                            InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}"),
                            InlineKeyboardButton("🔄 Remettre", callback_data=f"admin_restore_{order_id}")
                        ]])
                    )
                except Exception as e:
                    print(f"[edit_message] Erreur admin {admin_chat_id} msg {message_id}: {e}")
        except Exception as e:
            print(f"[fetch order_messages] Erreur: {e}")
        finally:
            conn.close()

        await query.answer(answer_text)
        return

# ----------------------- TEXT MESSAGE HANDLER -----------------------
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"User_{user_id}"
    first_name_tg = update.message.from_user.first_name or ""
    last_name_tg = update.message.from_user.last_name or ""
    full_name_tg = f"{first_name_tg} {last_name_tg}".strip() or f"User_{user_id}"
    text = update.message.text
    
    # Update activité
    update_user_activity(user_id, username, first_name_tg, last_name_tg)
    
    if user_id not in user_states:
        await update.message.reply_text(
            "❌ Aucune commande en cours.\n\nUtilise /start pour commencer."
        )
        return
    
    state = user_states[user_id]
    
    # Formulaire Deezer
    if state.get('step') == 'waiting_deezer_form':
        lines = text.strip().split('\n')
        if len(lines) < 3:
            await update.message.reply_text("❌ Envoie les 3 informations : Nom, Prénom, Mail")
            return
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("""INSERT INTO orders 
                     (user_id, username, service, plan, price, cost, timestamp, status,
                      first_name, last_name, email)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?, ?)""",
                  (user_id, username, state['service_name'], state['plan_label'], 
                   state['price'], state['cost'], datetime.now().isoformat(),
                   lines[1].strip(), lines[0].strip(), lines[2].strip()))
        
        order_id = c.lastrowid
        
        # Update total_orders de l'utilisateur
        c.execute("UPDATE users SET total_orders = total_orders + 1, last_activity = ? WHERE user_id = ?",
                  (datetime.now().isoformat(), user_id))
        
        conn.commit()

        for admin_id in ADMIN_IDS:
            try:
                admin_text = f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n"
                if update.message.from_user.username:
                    admin_text += f"👤 @{username}\n"
                else:
                    admin_text += f"👤 {full_name_tg} (ID: {user_id})\n"
                admin_text += (
                    f"📦 {state['service_name']}\n"
                    f"💰 {state['price']}€\n"
                    f"💵 Coût: {state['cost']}€\n"
                    f"📈 Bénéf: {state['price'] - state['cost']}€\n\n"
                    f"👤 {lines[1].strip()} {lines[0].strip()}\n"
                    f"📧 {lines[2].strip()}\n"
                    f"🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                )

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"),
                    InlineKeyboardButton("✅ Terminer", callback_data=f"admin_complete_{order_id}"),
                    InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}"),
                    InlineKeyboardButton("🔄 Remettre", callback_data=f"admin_restore_{order_id}")
                ]])

                msg = await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )

                try:
                    conn2 = sqlite3.connect('orders.db', check_same_thread=False)
                    c2 = conn2.cursor()
                    c2.execute("""INSERT INTO order_messages (order_id, admin_id, message_id)
                                  VALUES (?, ?, ?)""", (order_id, admin_id, msg.message_id))
                    conn2.commit()
                    conn2.close()
                except Exception as e:
                    print(f"[order_messages insert] Erreur: {e}")

            except Exception as e:
                print(f"Erreur envoi admin: {e}")
        
        conn.close()
        
        await update.message.reply_text(f"✅ *Commande #{order_id} enregistrée !*\n\nMerci ! 🙏", parse_mode='Markdown')
        del user_states[user_id]
        return
    
    # Formulaire standard
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
        
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("""INSERT INTO orders 
                     (user_id, username, service, plan, price, cost, timestamp, status,
                      first_name, last_name, email, payment_method)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 'en_attente', ?, ?, ?, ?)""",
                  (user_id, username, state['service_name'], state['plan_label'], 
                   state['price'], state['cost'], datetime.now().isoformat(),
                   first_name, last_name, email, payment_method))
        
        order_id = c.lastrowid
        
        # Update total_orders de l'utilisateur
        c.execute("UPDATE users SET total_orders = total_orders + 1, last_activity = ? WHERE user_id = ?",
                  (datetime.now().isoformat(), user_id))
        
        conn.commit()

        admin_message = (
            f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n"
            f"👤 Client: @{username}\n"
            f"📦 Service: {state['service_name']}\n"
            f"📋 Plan: {state['plan_label']}\n"
            f"💰 Prix: {state['price']}€\n"
            f"💵 Coût: {state['cost']}€\n"
            f"📈 Bénéf: {state['price'] - state['cost']}€\n\n"
            f"*Informations client:*\n"
            f"👤 {first_name} {last_name}\n"
            f"📧 {email}\n"
            f"💳 Paiement: {payment_method}\n\n"
            f"🕒 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"),
            InlineKeyboardButton("✅ Terminer", callback_data=f"admin_complete_{order_id}"),
            InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}"),
            InlineKeyboardButton("🔄 Remettre", callback_data=f"admin_restore_{order_id}")
        ]])
        
        for admin_id in ADMIN_IDS:
            try:
                msg = await context.bot.send_message(
                    chat_id=admin_id,
                    text=admin_message,
                    parse_mode='Markdown',
                    reply_markup=keyboard
                )
                try:
                    conn2 = sqlite3.connect('orders.db', check_same_thread=False)
                    c2 = conn2.cursor()
                    c2.execute("""INSERT INTO order_messages (order_id, admin_id, message_id)
                                  VALUES (?, ?, ?)""", (order_id, admin_id, msg.message_id))
                    conn2.commit()
                    conn2.close()
                except Exception as e:
                    print(f"[order_messages insert] Erreur: {e}")
            except Exception as e:
                print(f"[ERREUR] Notification admin {admin_id}: {e}")
        
        conn.close()
        
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
        
        del user_states[user_id]
        return

# ----------------------- Helper edit notifications -----------------------
def edit_notifications_for_order(order_id: int, new_text: str):
    """Édite toutes les notifications pour une commande (HTTP API sync)"""
    if not BOT_TOKEN:
        return

    conn = sqlite3.connect('orders.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute("SELECT admin_id, message_id FROM order_messages WHERE order_id=?", (order_id,))
        rows = c.fetchall()
        for admin_chat_id, message_id in rows:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                    json={
                        "chat_id": admin_chat_id,
                        "message_id": message_id,
                        "text": new_text,
                        "parse_mode": "Markdown"
                    },
                    timeout=10
                )
            except Exception as e:
                print(f"[edit_notifications] Erreur admin {admin_chat_id} msg {message_id}: {e}")
    except Exception as e:
        print("Erreur récupérer order_messages:", e)
    finally:
        conn.close()

# ----------------------- Bot runner -----------------------
def run_bot():
    """Démarre le bot Telegram dans un thread séparé avec event loop dédié"""
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
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass

if __name__ == '__main__':
    # Lancer le bot dans un thread séparé
    bot_thread = threading.Thread(target=run_bot, daemon=True, name='TelegramBotPolling')
    bot_thread.start()

    # Lancer Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
