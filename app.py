# Full app.py - Dashboard Utilisateurs + Gestion commandes Telegram + Stats cumulatives + Manager React
# Migrated to SQLAlchemy (works with Postgres via DATABASE_URL or with local sqlite if not provided).
# Includes full HTML templates embedded.

import os
import requests
import random
import traceback
import asyncio
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, jsonify, redirect, session
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from functools import wraps
import threading

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
# Replace with your admin Telegram IDs
ADMIN_IDS = [6976573567, 5174507979]
WEB_PASSWORD = os.getenv('WEB_PASSWORD')

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'votre_secret_key_aleatoire_ici')

# Décorateur pour protéger les routes admin
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# Default in-code configuration (used only for initial population)
SERVICES_CONFIG = {
    'netflix': {
        'name': '🎬 Netflix',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Netflix Premium', 'price': 9.00, 'cost': 1.00}
        }
    },
    'primevideo': {
        'name': '🎬 Prime Video',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            '1_mois': {'label': 'Prime Video 1 mois', 'price': 5.00, 'cost': 2.50},
            '6_mois': {'label': 'Prime Video 6 mois', 'price': 15.00, 'cost': 7.50}
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
            '1_mois': {'label': 'Crunchyroll 1 mois', 'price': 5.00, 'cost': 2.50},
            '1_an_fan': {'label': 'Crunchyroll 1 an Fan (profil à vous)', 'price': 10.00, 'cost': 5.00},
            'mega_fan_profil': {'label': 'Crunchyroll Mega Fan (profil à vous)', 'price': 15.00, 'cost': 7.50},
            'mega_fan': {'label': 'Crunchyroll Mega Fan', 'price': 20.00, 'cost': 10.00}
        }
    },
    'canal': {
        'name': '🎬 Canal+',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Canal+', 'price': 9.00, 'cost': 1.00}
        }
    },
    'disney': {
        'name': '🎬 Disney+',
        'active': True,
        'visible': True,
        'category': 'streaming',
        'plans': {
            'standard': {'label': 'Disney+', 'price': 7.00, 'cost': 1.00}
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
            '1_mois': {'label': 'YouTube Premium 1 mois', 'price': 5.00, 'cost': 2.50},
            '1_an': {'label': 'YouTube Premium 1 an', 'price': 30.00, 'cost': 15.00}
        }
    },
    'spotify': {
        'name': '🎧 Spotify Premium',
        'active': True,
        'visible': True,
        'category': 'music',
        'plans': {
            '2_mois': {'label': 'Spotify Premium 2 mois', 'price': 10.00, 'cost': 5.00},
            '1_an': {'label': 'Spotify Premium 1 an', 'price': 20.00, 'cost': 10.00}
        }
    },
    'deezer': {
        'name': '🎵 Deezer Premium',
        'active': True,
        'visible': True,
        'category': 'music',
        'plans': {
            'a_vie': {'label': 'Deezer Premium à vie', 'price': 8.00, 'cost': 4.00}
        }
    },
    'appletv_music': {
        'name': '🍎 Apple TV + Apple Music',
        'active': True,
        'visible': True,
        'category': 'apple',
        'plans': {
            '2_mois': {'label': 'Apple TV + Music 2 mois', 'price': 7.00, 'cost': 3.50},
            '3_mois': {'label': 'Apple TV + Music 3 mois', 'price': 9.00, 'cost': 4.50},
            '6_mois': {'label': 'Apple TV + Music 6 mois', 'price': 16.00, 'cost': 8.00},
            '1_an': {'label': 'Apple TV + Music 1 an', 'price': 30.00, 'cost': 14.00}
        }
    },
    'basicfit': {
        'name': '🏋️ Basic Fit',
        'active': True,
        'visible': True,
        'category': 'basic_fit',
        'plans': {
            'ultimate': {'label': 'Basic Fit Ultimate', 'price': 30.00, 'cost': 5.00}
        }
    }
}

# In-memory cache of services (kept for fast access by bot)
SERVICES_CONFIG_IN_MEMORY = {}
user_states = {}

# DB config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQLITE_PATH = os.path.join(BASE_DIR, 'orders.db')
DATABASE_URL = os.getenv('DATABASE_URL') or f"sqlite:///{os.getenv('DB_PATH', DEFAULT_SQLITE_PATH)}"

connect_args = {}
if DATABASE_URL.startswith('sqlite'):
    connect_args = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))
Base = declarative_base()

# Models
class Service(Base):
    __tablename__ = 'services'
    service_key = Column(String, primary_key=True)
    display_name = Column(String)
    emoji = Column(String)
    category = Column(String)
    active = Column(Boolean, default=True)
    visible = Column(Boolean, default=True)
    plans = relationship("Plan", back_populates="service", cascade="all, delete-orphan")

class Plan(Base):
    __tablename__ = 'plans'
    service_key = Column(String, ForeignKey('services.service_key', ondelete='CASCADE'), primary_key=True)
    plan_key = Column(String, primary_key=True)
    label = Column(String)
    price = Column(Float, default=0.0)
    cost = Column(Float, default=0.0)
    service = relationship("Service", back_populates="plans")

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String, nullable=True)
    service = Column(String)
    plan = Column(String)
    price = Column(Float)
    cost = Column(Float)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    payment_method = Column(String, nullable=True)
    timestamp = Column(String)
    status = Column(String, default='en_attente')
    admin_id = Column(Integer, nullable=True)
    admin_username = Column(String, nullable=True)
    taken_at = Column(String, nullable=True)
    cancelled_by = Column(Integer, nullable=True)
    cancelled_at = Column(String, nullable=True)
    cancel_reason = Column(String, nullable=True)

class OrderMessage(Base):
    __tablename__ = 'order_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, index=True)
    admin_id = Column(Integer)
    message_id = Column(Integer)

class User(Base):
    __tablename__ = 'users'
    user_id = Column(Integer, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    first_seen = Column(String)
    last_activity = Column(String)
    total_orders = Column(Integer, default=0)

class CumulativeStats(Base):
    __tablename__ = 'cumulative_stats'
    id = Column(Integer, primary_key=True)
    total_revenue = Column(Float, default=0.0)
    total_profit = Column(Float, default=0.0)
    last_updated = Column(String, nullable=True)

# DB init & loaders
def init_db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        cs = session.get(CumulativeStats, 1)
        if not cs:
            cs = CumulativeStats(id=1, total_revenue=0.0, total_profit=0.0, last_updated=datetime.now().isoformat())
            session.add(cs)
            session.commit()

        services_count = session.query(Service).count()
        if services_count == 0:
            for sk, sd in SERVICES_CONFIG.items():
                name = sd.get('name', '')
                parts = name.split(' ', 1)
                emoji = parts[0] if len(parts) > 1 else ''
                display_name = parts[1] if len(parts) > 1 else name or sk
                svc = Service(service_key=sk, display_name=display_name, emoji=emoji, category=sd.get('category', ''), active=sd.get('active', True), visible=sd.get('visible', True))
                session.add(svc)
                for pk, pd in sd.get('plans', {}).items():
                    plan = Plan(service_key=sk, plan_key=pk, label=pd.get('label', pk), price=float(pd.get('price', 0.0) or 0.0), cost=float(pd.get('cost', 0.0) or 0.0))
                    svc.plans.append(plan)
            session.commit()

        if os.getenv('OVERWRITE_DB_FROM_CONFIG', 'false').lower() in ('1', 'true', 'yes'):
            session.query(Plan).delete()
            session.query(Service).delete()
            session.commit()
            for sk, sd in SERVICES_CONFIG.items():
                name = sd.get('name', '')
                parts = name.split(' ', 1)
                emoji = parts[0] if len(parts) > 1 else ''
                display_name = parts[1] if len(parts) > 1 else name or sk
                svc = Service(service_key=sk, display_name=display_name, emoji=emoji, category=sd.get('category', ''), active=sd.get('active', True), visible=sd.get('visible', True))
                session.add(svc)
                for pk, pd in sd.get('plans', {}).items():
                    plan = Plan(service_key=sk, plan_key=pk, label=pd.get('label', pk), price=float(pd.get('price', 0.0) or 0.0), cost=float(pd.get('cost', 0.0) or 0.0))
                    svc.plans.append(plan)
            session.commit()
            print("DB overwritten from SERVICES_CONFIG (OVERWRITE_DB_FROM_CONFIG enabled).")

    except Exception as e:
        session.rollback()
        print("init_db error:", e)
        traceback.print_exc()
    finally:
        session.close()
    load_services_from_db()

def load_services_from_db():
    global SERVICES_CONFIG_IN_MEMORY
    session = SessionLocal()
    try:
        services = {}
        svc_rows = session.query(Service).all()
        for s in svc_rows:
            services[s.service_key] = {
                'name': f"{(s.emoji or '').strip()} {s.display_name}".strip(),
                'active': bool(s.active),
                'visible': bool(s.visible),
                'category': s.category or '',
                'plans': {}
            }
        plan_rows = session.query(Plan).all()
        for p in plan_rows:
            if p.service_key not in services:
                continue
            services[p.service_key]['plans'][p.plan_key] = {
                'label': p.label,
                'price': float(p.price or 0.0),
                'cost': float(p.cost or 0.0)
            }
        SERVICES_CONFIG_IN_MEMORY = services

        # Debug log
        print(f"=== Loaded services from DB (url={DATABASE_URL}) ===")
        for sk, sd in SERVICES_CONFIG_IN_MEMORY.items():
            print(f" - {sk}: {sd.get('name')} (active={sd.get('active')}, visible={sd.get('visible')}, category={sd.get('category')})")
            for pk, pd in sd.get('plans', {}).items():
                print(f"    plan {pk}: label='{pd.get('label')}', price={pd.get('price')}, cost={pd.get('cost')}")
        print("=== End loaded services ===")
    except Exception as e:
        print("Erreur load_services_from_db:", e)
        traceback.print_exc()
    finally:
        session.close()

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
        .logout-btn, .simulate-btn, .users-btn, .manager-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.3s;
        }
        .manager-btn {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            font-weight: 600;
        }
        .manager-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(240, 147, 251, 0.4);
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
        .order-card.locked {
            opacity: 0.6;
            border-left-color: #ef4444;
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
        .locked-badge {
            background: #ef4444;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
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
        .action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        .btn-take { background: #3b82f6; color: white; }
        .btn-complete { background: #10b981; color: white; }
        .btn-cancel { background: #ef4444; color: white; }
        .btn-restore { background: #f59e0b; color: white; }
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
            <a href="/manager" class="manager-btn">🎛️ Manager</a>
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
            
            container.innerHTML = filteredOrders.map(order => {
                const isLocked = order.admin_id && order.status !== 'en_attente';
                const lockedClass = isLocked ? 'locked' : '';
                const lockedBadge = isLocked ? `<span class="locked-badge">🔒 Pris par @${order.admin_username || 'Admin'}</span>` : '';
                
                let buttons = '';
                if (order.status === 'en_attente') {
                    buttons = `
                        <button class="action-btn btn-take" onclick="takeOrder(${order.id})">✋ Prendre</button>
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌ Annuler</button>
                    `;
                } else if (order.status === 'en_cours') {
                    buttons = `
                        <button class="action-btn btn-complete" onclick="completeOrder(${order.id})">✅ Terminer</button>
                        <button class="action-btn btn-cancel" onclick="cancelOrder(${order.id})">❌ Annuler</button>
                        <button class="action-btn btn-restore" onclick="restoreOrder(${order.id})">🔄 Remettre</button>
                    `;
                } else if (order.status === 'terminee' || order.status === 'annulee') {
                    buttons = `
                        <button class="action-btn btn-restore" onclick="restoreOrder(${order.id})">🔄 Remettre en ligne</button>
                    `;
                }
                
                return `
                    <div class="order-card ${lockedClass}">
                        <div class="order-header">
                            <div>
                                <strong style="font-size:18px;color:#667eea">#${order.id}</strong>
                                <span class="status-badge status-${order.status}">${getStatusLabel(order.status)}</span>
                                ${lockedBadge}
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
                            ${buttons}
                        </div>
                    </div>
                `;
            }).join('');
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

        async function restoreOrder(orderId) {
            if (confirm('Remettre cette commande en ligne ?')) {
                await fetch(`/api/order/${orderId}/restore`, { method: 'POST' });
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
                        <option value="primevideo">🎬 Prime Video</option>
                        <option value="hbo">🎬 HBO Max</option>
                        <option value="crunchyroll">🎬 Crunchyroll</option>
                        <option value="canal">🎬 Canal+</option>
                        <option value="disney">🎬 Disney+</option>
                        <option value="ufc">🎬 UFC Fight Pass</option>
                        <option value="youtube">▶️ YouTube Premium</option>
                        <option value="spotify">🎧 Spotify Premium</option>
                        <option value="deezer">🎵 Deezer Premium</option>
                        <option value="chatgpt">🤖 ChatGPT+</option>
                        <option value="appletv_music">🍎 Apple TV + Music</option>
                        <option value="basicfit">🏋️ Basic Fit</option>
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
                    headers: { 'Content-Type': 'application/json'},
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

HTML_REACT_MANAGER = '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Bot Manager - B4U Deals</title>
    <style>
        body { font-family: Arial, Helvetica, sans-serif; background:#f5f7fa; margin:0; padding:20px; }
        .top { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; }
        .card { background:white; border-radius:10px; padding:16px; box-shadow:0 6px 18px rgba(0,0,0,0.08); margin-bottom:12px; }
        .service-header { display:flex; align-items:center; gap:12px; }
        .emoji { font-size:28px; }
        .service-actions { margin-left:auto; display:flex; gap:8px; align-items:center; }
        .plans { margin-top:12px; gap:8px; display:flex; flex-direction:column; }
        .plan { display:flex; gap:8px; align-items:center; justify-content:space-between; }
        input[type="text"], input[type="number"], select { padding:8px; border:1px solid #ddd; border-radius:6px; }
        button { background:#667eea; color:white; border:none; padding:8px 12px; border-radius:8px; cursor:pointer; }
        button.secondary { background:#10b981; }
        .small { font-size:13px; color:#666; }
        label { font-size:13px; color:#333; }
        .muted { color:#888; font-size:13px; }
        .save-global { position:fixed; right:20px; bottom:20px; padding:12px 16px; border-radius:12px; background:#f59e0b; color:white; box-shadow:0 8px 30px rgba(0,0,0,0.12); }
        .danger { background:#ef4444; }
    </style>
</head>
<body>
    <div class="top">
        <div>
            <h1>B4U Bot Manager</h1>
            <div class="muted">Éditez la configuration des services et plans</div>
        </div>
        <div>
            <a href="/dashboard"><button>← Dashboard</button></a>
            <button id="addServiceBtn" style="margin-left:8px;">➕ Ajouter service</button>
        </div>
    </div>

    <div id="content"></div>

    <button id="saveAll" class="save-global" style="display:none">Sauvegarder les changements</button>

    <script>
    (function () {
        const content = document.getElementById('content');
        const saveAllBtn = document.getElementById('saveAll');
        const addServiceBtn = document.getElementById('addServiceBtn');
        let servicesState = {};
        let hasChanges = false;

        function setDirty(v) {
            hasChanges = v;
            saveAllBtn.style.display = v ? 'block' : 'none';
        }

        addServiceBtn.addEventListener('click', async () => {
            const key = prompt('Clé du service (ex: myservice) :');
            if (!key) return;
            const display_name = prompt('Nom affiché (ex: My Service) :') || key;
            const emoji = prompt('Emoji (optionnel) :') || '';
            const category = prompt('Catégorie (ex: streaming, music, ai) :') || '';
            try {
                const resp = await fetch('/api/services', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({service_key: key, display_name, emoji, category, active: true, visible: true})
                });
                if (!resp.ok) throw new Error('Erreur création service');
                await loadServices();
                alert('Service créé');
            } catch (e) {
                alert('Erreur: ' + e.message);
            }
        });

        async function loadServices() {
            content.innerHTML = '<div class="card small">Chargement...</div>';
            try {
                const res = await fetch('/api/services');
                const data = await res.json();
                renderServices(data.services || []);
            } catch (e) {
                content.innerHTML = '<div class="card small">Erreur de chargement: ' + e.message + '</div>';
            }
        }

        function renderServices(list) {
            servicesState = {};
            if (!Array.isArray(list) || list.length === 0) {
                content.innerHTML = '<div class="card small">Aucun service trouvé</div>';
                return;
            }
            content.innerHTML = '';
            list.forEach(s => {
                servicesState[s.service_key] = {
                    _original: s,
                    emoji: s.emoji || '',
                    display_name: s.display_name || '',
                    active: !!s.active,
                    visible: !!s.visible,
                    category: s.category || '',
                    plans: {}
                };
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div class="service-header">
                        <div class="emoji">${escapeHtml(s.emoji) || '📦'}</div>
                        <div style="flex:1">
                            <div><strong class="service-title">${escapeHtml(s.emoji)} ${escapeHtml(s.display_name)}</strong></div>
                            <div class="small">Clé: <code>${escapeHtml(s.service_key)}</code> · Catégorie: <span class="muted">${escapeHtml(s.category)}</span></div>
                        </div>
                        <div class="service-actions">
                            <label style="font-size:13px"><input type="checkbox" class="active-checkbox" ${s.active ? 'checked' : ''}> Actif</label>
                            <label style="font-size:13px"><input type="checkbox" class="visible-checkbox" ${s.visible ? 'checked' : ''}> Visible</label>
                            <button class="btn-delete-service danger" title="Supprimer le service">Supprimer</button>
                        </div>
                    </div>
                    <div style="margin-top:10px;">
                        <label>Emoji</label><br>
                        <input type="text" class="input-emoji" value="${escapeHtml(s.emoji)}" style="width:80px;">
                        <label style="margin-left:12px">Nom affiché</label><br>
                        <input type="text" class="input-name" value="${escapeHtml(s.display_name)}" style="width:320px;">
                        <label style="margin-left:12px">Catégorie</label><br>
                        <input type="text" class="input-category" value="${escapeHtml(s.category)}" style="width:160px;">
                    </div>
                    <div class="plans">
                        <h4 style="margin-top:12px; margin-bottom:6px;">Plans</h4>
                        <div class="plans-list"></div>
                        <div style="margin-top:8px;">
                            <button class="btn-add-plan">➕ Ajouter plan</button>
                        </div>
                    </div>
                `;
                const plansList = card.querySelector('.plans-list');

                s.plans.forEach(plan => {
                    servicesState[s.service_key].plans[plan.plan_key] = {
                        label: plan.label,
                        price: plan.price,
                        cost: plan.cost
                    };
                    const planRow = document.createElement('div');
                    planRow.className = 'plan';
                    planRow.innerHTML = `
                        <div style="flex:1">
                            <div><strong>${escapeHtml(plan.plan_key)}</strong> · <span class="small">${escapeHtml(plan.label)}</span></div>
                            <div class="small">Prix: <input type="number" step="0.01" class="input-price" value="${plan.price}" style="width:90px;"> € &nbsp;&nbsp; Coût: <input type="number" step="0.01" class="input-cost" value="${plan.cost}" style="width:90px;"> €</div>
                        </div>
                        <div>
                            <button class="btn-update-plan secondary">Enregistrer plan</button>
                            <button class="btn-delete-plan danger" style="margin-left:6px;">Supprimer</button>
                        </div>
                    `;
                    const inputPrice = planRow.querySelector('.input-price');
                    const inputCost = planRow.querySelector('.input-cost');
                    const btnUpdatePlan = planRow.querySelector('.btn-update-plan');
                    const btnDeletePlan = planRow.querySelector('.btn-delete-plan');

                    inputPrice.addEventListener('change', () => {
                        servicesState[s.service_key].plans[plan.plan_key].price = parseFloat(inputPrice.value) || 0;
                        setDirty(true);
                    });
                    inputCost.addEventListener('change', () => {
                        servicesState[s.service_key].plans[plan.plan_key].cost = parseFloat(inputCost.value) || 0;
                        setDirty(true);
                    });

                    btnUpdatePlan.addEventListener('click', async () => {
                        btnUpdatePlan.disabled = true;
                        btnUpdatePlan.textContent = 'Enregistrement...';
                        try {
                            const payload = {
                                label: servicesState[s.service_key].plans[plan.plan_key].label || plan.label,
                                price: servicesState[s.service_key].plans[plan.plan_key].price,
                                cost: servicesState[s.service_key].plans[plan.plan_key].cost
                            };
                            const resp = await fetch(`/api/services/${encodeURIComponent(s.service_key)}/plans/${encodeURIComponent(plan.plan_key)}`, {
                                method: 'PUT',
                                headers: {'Content-Type': 'application/json'},
                                body: JSON.stringify(payload)
                            });
                            if (!resp.ok) throw new Error('Erreur réseau');
                            btnUpdatePlan.textContent = '✔';
                            setTimeout(() => btnUpdatePlan.textContent = 'Enregistrer plan', 1000);
                            setDirty(false);
                        } catch (e) {
                            alert('Erreur sauvegarde plan: ' + e.message);
                            btnUpdatePlan.disabled = false;
                            btnUpdatePlan.textContent = 'Enregistrer plan';
                        }
                    });

                    btnDeletePlan.addEventListener('click', async () => {
                        if (!confirm('Supprimer ce plan ?')) return;
                        try {
                            const resp = await fetch(`/api/services/${encodeURIComponent(s.service_key)}/plans/${encodeURIComponent(plan.plan_key)}`, {
                                method: 'DELETE'
                            });
                            if (!resp.ok) throw new Error('Erreur suppression');
                            await loadServices();
                        } catch (e) {
                            alert('Erreur suppression plan: ' + e.message);
                        }
                    });

                    plansList.appendChild(planRow);
                });

                const inputEmoji = card.querySelector('.input-emoji');
                const inputName = card.querySelector('.input-name');
                const inputCategory = card.querySelector('.input-category');
                const activeCheckbox = card.querySelector('.active-checkbox');
                const visibleCheckbox = card.querySelector('.visible-checkbox');
                const btnDeleteService = card.querySelector('.btn-delete-service');
                const btnAddPlan = card.querySelector('.btn-add-plan');

                function markAndUpdateHeader() {
                    const titleEl = card.querySelector('.service-title');
                    titleEl.textContent = (inputEmoji.value || '') + ' ' + (inputName.value || s.display_name);
                }

                inputEmoji.addEventListener('input', () => {
                    servicesState[s.service_key].emoji = inputEmoji.value;
                    markAndUpdateHeader();
                    setDirty(true);
                });
                inputName.addEventListener('input', () => {
                    servicesState[s.service_key].display_name = inputName.value;
                    markAndUpdateHeader();
                    setDirty(true);
                });
                inputCategory.addEventListener('input', () => {
                    servicesState[s.service_key].category = inputCategory.value;
                    card.querySelector('.muted').textContent = inputCategory.value;
                    setDirty(true);
                });
                activeCheckbox.addEventListener('change', () => {
                    servicesState[s.service_key].active = activeCheckbox.checked;
                    setDirty(true);
                });
                visibleCheckbox.addEventListener('change', () => {
                    servicesState[s.service_key].visible = visibleCheckbox.checked;
                    setDirty(true);
                });

                btnDeleteService.addEventListener('click', async () => {
                    if (!confirm('Supprimer ce service (toutes ses données) ?')) return;
                    try {
                        const resp = await fetch(`/api/services/${encodeURIComponent(s.service_key)}`, {method: 'DELETE'});
                        if (!resp.ok) throw new Error('Erreur suppression');
                        await loadServices();
                    } catch (e) {
                        alert('Erreur suppression service: ' + e.message);
                    }
                });

                btnAddPlan.addEventListener('click', async () => {
                    const plan_key = prompt('Clé du plan (ex: 1_mois) :');
                    if (!plan_key) return;
                    const label = prompt('Label du plan :') || plan_key;
                    const price = parseFloat(prompt('Prix (ex: 9.99) :') || '0');
                    const cost = parseFloat(prompt('Coût (ex: 2.5) :') || '0');
                    try {
                        const resp = await fetch(`/api/services/${encodeURIComponent(s.service_key)}/plans`, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({plan_key, label, price, cost})
                        });
                        if (!resp.ok) throw new Error('Erreur création plan');
                        await loadServices();
                    } catch (e) {
                        alert('Erreur création plan: ' + e.message);
                    }
                });

                const saveBtn = document.createElement('button');
                saveBtn.textContent = 'Sauvegarder service';
                saveBtn.style.marginLeft = '12px';
                saveBtn.addEventListener('click', async () => {
                    saveBtn.disabled = true;
                    saveBtn.textContent = 'Enregistrement...';
                    try {
                        const payload = {
                            display_name: servicesState[s.service_key].display_name,
                            emoji: servicesState[s.service_key].emoji,
                            category: servicesState[s.service_key].category,
                            active: !!servicesState[s.service_key].active,
                            visible: !!servicesState[s.service_key].visible
                        };
                        const resp = await fetch(`/api/services/${encodeURIComponent(s.service_key)}`, {
                            method: 'PUT',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(payload)
                        });
                        if (!resp.ok) throw new Error('Erreur réseau');
                        saveBtn.textContent = '✔';
                        setTimeout(() => saveBtn.textContent = 'Sauvegarder service', 1000);
                        setDirty(false);
                    } catch (e) {
                        alert('Erreur sauvegarde service: ' + e.message);
                        saveBtn.disabled = false;
                        saveBtn.textContent = 'Sauvegarder service';
                    }
                });

                card.querySelector('.service-actions').appendChild(saveBtn);
                content.appendChild(card);
            });
        }

        saveAllBtn.addEventListener('click', async () => {
            saveAllBtn.disabled = true;
            saveAllBtn.textContent = 'Enregistrement...';
            try {
                for (const [serviceKey, s] of Object.entries(servicesState)) {
                    const payload = {
                        display_name: s.display_name,
                        emoji: s.emoji,
                        category: s.category,
                        active: !!s.active,
                        visible: !!s.visible
                    };
                    await fetch(`/api/services/${encodeURIComponent(serviceKey)}`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    for (const [planKey, p] of Object.entries(s.plans)) {
                        await fetch(`/api/services/${encodeURIComponent(serviceKey)}/plans/${encodeURIComponent(planKey)}`, {
                            method: 'PUT',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify(p)
                        });
                    }
                }
                alert('✅ Configuration sauvegardée');
                setDirty(false);
                await loadServices();
            } catch (e) {
                alert('Erreur lors de la sauvegarde: ' + e.message);
            } finally {
                saveAllBtn.disabled = false;
                saveAllBtn.textContent = 'Sauvegarder les changements';
            }
        });

        function escapeHtml(str) {
            if (!str && str !== 0) return '';
            return String(str).replace(/[&<>"']/g, function(m){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]; });
        }

        loadServices();
    })();
    </script>
</body>
</html>
'''

# ----------------------- Routes & API -----------------------
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

@app.route('/manager')
@login_required
def manager_page():
    return render_template_string(HTML_REACT_MANAGER)

@app.route('/api/reload_services', methods=['POST'])
@login_required
def api_reload_services():
    try:
        load_services_from_db()
        return jsonify({'success': True, 'message': 'Services rechargés depuis la DB', 'db': DATABASE_URL})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/services', methods=['GET'])
@login_required
def api_services_list():
    services = []
    for service_key, service_data in SERVICES_CONFIG_IN_MEMORY.items():
        plans = []
        for plan_key, plan_data in service_data.get('plans', {}).items():
            plans.append({
                'plan_key': plan_key,
                'label': plan_data.get('label', plan_key),
                'price': plan_data.get('price', 0.0),
                'cost': plan_data.get('cost', 0.0)
            })
        name_parts = service_data.get('name', '').split(' ', 1)
        emoji = name_parts[0] if len(name_parts) > 1 else (service_data.get('name') or '')
        display_name = name_parts[1] if len(name_parts) > 1 else (service_data.get('name') or service_key)
        services.append({
            'service_key': service_key,
            'emoji': emoji,
            'display_name': display_name,
            'active': service_data.get('active', True),
            'visible': service_data.get('visible', True),
            'category': service_data.get('category', ''),
            'plans': plans
        })
    return jsonify({'services': services})

@app.route('/api/services', methods=['POST'])
@login_required
def api_create_service():
    data = request.get_json(force=True)
    service_key = data.get('service_key')
    display_name = data.get('display_name') or service_key
    emoji = data.get('emoji') or ''
    category = data.get('category') or ''
    active = bool(data.get('active', True))
    visible = bool(data.get('visible', True))
    if not service_key:
        return jsonify({'error': 'service_key_required'}), 400
    session = SessionLocal()
    try:
        existing = session.get(Service, service_key)
        if existing:
            return jsonify({'error': 'service_exists'}), 409
        svc = Service(service_key=service_key, display_name=display_name, emoji=emoji, category=category, active=active, visible=visible)
        session.add(svc)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500
    finally:
        session.close()
    load_services_from_db()
    return jsonify({'success': True})

@app.route('/api/services/<service_key>', methods=['PUT'])
@login_required
def api_update_service(service_key):
    data = request.get_json(force=True)
    display_name = data.get('display_name') or ''
    emoji = data.get('emoji') or ''
    category = data.get('category') or ''
    active = bool(data.get('active', True))
    visible = bool(data.get('visible', True))
    session = SessionLocal()
    try:
        svc = session.get(Service, service_key)
        if not svc:
            return jsonify({'error': 'Service not found'}), 404
        svc.display_name = display_name
        svc.emoji = emoji
        svc.category = category
        svc.active = active
        svc.visible = visible
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500
    finally:
        session.close()
    load_services_from_db()
    return jsonify({'success': True})

@app.route('/api/services/<service_key>', methods=['DELETE'])
@login_required
def api_delete_service(service_key):
    session = SessionLocal()
    try:
        svc = session.get(Service, service_key)
        if not svc:
            return jsonify({'error': 'Service not found'}), 404
        session.delete(svc)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500
    finally:
        session.close()
    load_services_from_db()
    return jsonify({'success': True})

@app.route('/api/services/<service_key>/plans', methods=['POST'])
@login_required
def api_create_plan(service_key):
    data = request.get_json(force=True)
    plan_key = data.get('plan_key')
    label = data.get('label') or plan_key
    price = float(data.get('price', 0) or 0)
    cost = float(data.get('cost', 0) or 0)
    if not plan_key:
        return jsonify({'error': 'plan_key_required'}), 400
    session = SessionLocal()
    try:
        svc = session.get(Service, service_key)
        if not svc:
            return jsonify({'error': 'Service not found'}), 404
        existing = session.query(Plan).filter_by(service_key=service_key, plan_key=plan_key).first()
        if existing:
            return jsonify({'error': 'plan_exists'}), 409
        plan = Plan(service_key=service_key, plan_key=plan_key, label=label, price=price, cost=cost)
        session.add(plan)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500
    finally:
        session.close()
    load_services_from_db()
    return jsonify({'success': True})

@app.route('/api/services/<service_key>/plans/<plan_key>', methods=['PUT'])
@login_required
def api_update_plan(service_key, plan_key):
    data = request.get_json(force=True)
    label = data.get('label') if 'label' in data else None
    price = float(data.get('price')) if 'price' in data and data.get('price') is not None else None
    cost = float(data.get('cost')) if 'cost' in data and data.get('cost') is not None else None
    session = SessionLocal()
    try:
        plan = session.query(Plan).filter_by(service_key=service_key, plan_key=plan_key).first()
        if not plan:
            return jsonify({'error': 'Plan not found'}), 404
        if label is not None:
            plan.label = label
        if price is not None:
            plan.price = price
        if cost is not None:
            plan.cost = cost
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500
    finally:
        session.close()
    load_services_from_db()
    return jsonify({'success': True})

@app.route('/api/services/<service_key>/plans/<plan_key>', methods=['DELETE'])
@login_required
def api_delete_plan(service_key, plan_key):
    session = SessionLocal()
    try:
        plan = session.query(Plan).filter_by(service_key=service_key, plan_key=plan_key).first()
        if not plan:
            return jsonify({'error': 'Plan not found'}), 404
        session.delete(plan)
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500
    finally:
        session.close()
    load_services_from_db()
    return jsonify({'success': True})

# Users / Dashboard / Orders / Simulate endpoints follow same logic as earlier (using SQLAlchemy sessions)
@app.route('/api/users')
@login_required
def api_users():
    session = SessionLocal()
    try:
        total_users = session.query(func.count(User.user_id)).scalar()
        active_users = session.query(func.count(User.user_id)).filter(User.total_orders > 0).scalar()
        conversion_rate = (active_users / total_users * 100) if total_users and total_users > 0 else 0
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        new_users = session.query(func.count(User.user_id)).filter(User.first_seen >= seven_days_ago).scalar()
        users_q = session.query(User).order_by(User.last_activity.desc()).all()
        users = []
        for u in users_q:
            users.append({
                'user_id': u.user_id,
                'username': u.username or 'N/A',
                'first_name': u.first_name or 'Inconnu',
                'last_name': u.last_name or '',
                'first_seen': u.first_seen,
                'last_activity': u.last_activity,
                'total_orders': u.total_orders
            })
        return jsonify({
            'stats': {
                'total_users': total_users,
                'active_users': active_users,
                'conversion_rate': round(conversion_rate, 1),
                'new_users': new_users
            },
            'users': users
        })
    finally:
        session.close()

@app.route('/api/users/<int:user_id>')
@login_required
def api_user_details(user_id):
    session = SessionLocal()
    try:
        orders_q = session.query(Order).filter(Order.user_id == user_id).order_by(Order.timestamp.desc()).all()
        orders = []
        for o in orders_q:
            orders.append({
                'id': o.id,
                'service': o.service,
                'plan': o.plan,
                'price': o.price,
                'timestamp': o.timestamp,
                'status': o.status
            })
        return jsonify({'orders': orders})
    finally:
        session.close()

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    session = SessionLocal()
    try:
        orders_q = session.query(Order).order_by(Order.id.desc()).all()
        orders = []
        for o in orders_q:
            orders.append({
                'id': o.id,
                'username': o.username,
                'service': o.service,
                'plan': o.plan,
                'price': o.price,
                'cost': o.cost,
                'first_name': o.first_name,
                'last_name': o.last_name,
                'email': o.email,
                'payment_method': o.payment_method,
                'status': o.status,
                'admin_id': o.admin_id,
                'admin_username': o.admin_username
            })
        total = session.query(func.count(Order.id)).scalar()
        pending = session.query(func.count(Order.id)).filter(Order.status == 'en_attente').scalar()
        inprogress = session.query(func.count(Order.id)).filter(Order.status == 'en_cours').scalar()
        completed = session.query(func.count(Order.id)).filter(Order.status == 'terminee').scalar()
        cumul = session.get(CumulativeStats, 1)
        revenue = cumul.total_revenue if cumul else 0
        profit = cumul.total_profit if cumul else 0
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
    finally:
        session.close()

@app.route('/api/order/<int:order_id>/take', methods=['POST'])
@login_required
def take_order(order_id):
    session = SessionLocal()
    try:
        o = session.get(Order, order_id)
        if not o:
            return jsonify({'error': 'Order not found'}), 404
        o.status = 'en_cours'
        o.admin_id = 999999
        o.admin_username = 'web_admin'
        o.taken_at = datetime.now().isoformat()
        session.commit()
    except Exception as e:
        session.rollback()
        print("take_order error:", e)
    finally:
        session.close()
    try:
        delete_other_admin_notifications(order_id, 999999)
        edit_admin_notification(order_id, 999999, f"🔒 *COMMANDE #{order_id} — PRISE EN CHARGE*\n\n✅ Pris en charge via le dashboard\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    except Exception as e:
        print("Erreur notifications:", e)
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/complete', methods=['POST'])
@login_required
def complete_order(order_id):
    session = SessionLocal()
    try:
        o = session.get(Order, order_id)
        if o:
            price = o.price or 0.0
            cost = o.cost or 0.0
            cs = session.get(CumulativeStats, 1)
            if cs:
                cs.total_revenue = (cs.total_revenue or 0.0) + price
                cs.total_profit = (cs.total_profit or 0.0) + (price - cost)
                cs.last_updated = datetime.now().isoformat()
            o.status = 'terminee'
            session.commit()
    except Exception as e:
        session.rollback()
        print("complete_order error:", e)
    finally:
        session.close()
    try:
        edit_all_admin_notifications(order_id, f"✅ *COMMANDE #{order_id} — TERMINÉE*\n\nTerminée via le dashboard\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    except Exception as e:
        print("Erreur notifications:", e)
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    session = SessionLocal()
    try:
        o = session.get(Order, order_id)
        if o:
            o.status = 'annulee'
            o.cancelled_at = datetime.now().isoformat()
            session.commit()
    except Exception as e:
        session.rollback()
        print("cancel_order error:", e)
    finally:
        session.close()
    try:
        edit_all_admin_notifications(order_id, f"❌ *COMMANDE #{order_id} — ANNULÉE*\n\nAnnulée via le dashboard\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    except Exception as e:
        print("Erreur notifications:", e)
    return jsonify({'success': True})

@app.route('/api/order/<int:order_id>/restore', methods=['POST'])
@login_required
def restore_order(order_id):
    session = SessionLocal()
    try:
        o = session.get(Order, order_id)
        if o:
            o.status = 'en_attente'
            o.admin_id = None
            o.admin_username = None
            o.taken_at = None
            o.cancelled_by = None
            o.cancelled_at = None
            session.query(OrderMessage).filter(OrderMessage.order_id == order_id).delete()
            session.commit()
    except Exception as e:
        session.rollback()
        print("restore_order error:", e)
    finally:
        session.close()
    try:
        resend_order_to_all_admins(order_id)
    except Exception as e:
        print("Erreur renvoi notifications:", e)
    return jsonify({'success': True})

@app.route('/')
def index():
    return redirect('/dashboard')

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'bot': 'running'})

@app.route('/api/simulate', methods=['POST'])
@login_required
def api_simulate():
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
    for service_key, service_data in SERVICES_CONFIG_IN_MEMORY.items():
        for plan_key, plan_data in service_data['plans'].items():
            services_list.append({
                'key': service_key,
                'name': service_data['name'],
                'plan_key': plan_key,
                'plan_label': plan_data['label'],
                'price': plan_data['price'],
                'cost': plan_data['cost']
            })
    session = SessionLocal()
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
            user = session.get(User, user_id)
            if not user:
                user = User(user_id=user_id, username=username, first_name=first_name, last_name=last_name, first_seen=timestamp, last_activity=timestamp, total_orders=0)
                session.add(user)
            user.last_activity = timestamp
            user.total_orders = (user.total_orders or 0) + 1
            if service['key'] == 'deezer':
                o = Order(user_id=user_id, username=username, service=service['name'], plan=service['plan_label'], price=service['price'], cost=service['cost'], timestamp=timestamp, status=status, first_name=last_name, last_name=first_name, email=email)
            else:
                o = Order(user_id=user_id, username=username, service=service['name'], plan=service['plan_label'], price=service['price'], cost=service['cost'], timestamp=timestamp, status=status, first_name=first_name, last_name=last_name, email=email, payment_method=payment_method)
            session.add(o)
            session.flush()
            if status == 'terminee':
                cs = session.get(CumulativeStats, 1)
                if cs:
                    cs.total_revenue = (cs.total_revenue or 0.0) + (service['price'] or 0.0)
                    cs.total_profit = (cs.total_profit or 0.0) + ((service['price'] or 0.0) - (service['cost'] or 0.0))
                    cs.last_updated = datetime.now().isoformat()
            created_orders.append({
                'id': o.id,
                'service': service['name'],
                'price': service['price']
            })
        session.commit()
    except Exception as e:
        session.rollback()
        tb = traceback.format_exc()
        print("Erreur génération commandes:", e)
        print(tb)
        return jsonify({'success': False, 'error': 'exception_during_insert', 'detail': str(e)}), 500
    finally:
        session.close()
    return jsonify({'success': True, 'created': len(created_orders), 'orders': created_orders})

# Helper functions (SQLAlchemy-backed)
def update_user_activity(user_id, username, first_name, last_name):
    session = SessionLocal()
    now = datetime.now().isoformat()
    try:
        user = session.get(User, user_id)
        if user:
            user.last_activity = now
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
        else:
            user = User(user_id=user_id, username=username, first_name=first_name, last_name=last_name, first_seen=now, last_activity=now, total_orders=0)
            session.add(user)
        session.commit()
    except Exception as e:
        session.rollback()
        print("update_user_activity error:", e)
    finally:
        session.close()

def delete_other_admin_notifications(order_id: int, keeping_admin_id: int):
    if not BOT_TOKEN:
        return
    session = SessionLocal()
    try:
        rows = session.query(OrderMessage).filter(OrderMessage.order_id == order_id, OrderMessage.admin_id != keeping_admin_id).all()
        for om in rows:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage", json={"chat_id": om.admin_id, "message_id": om.message_id}, timeout=10)
            except Exception as e:
                print(f"[delete_message] Erreur admin {om.admin_id} msg {om.message_id}: {e}")
        session.query(OrderMessage).filter(OrderMessage.order_id == order_id, OrderMessage.admin_id != keeping_admin_id).delete()
        session.commit()
    except Exception as e:
        print("Erreur delete_other_admin_notifications:", e)
    finally:
        session.close()

def edit_admin_notification(order_id: int, admin_id: int, new_text: str):
    if not BOT_TOKEN:
        return
    session = SessionLocal()
    try:
        row = session.query(OrderMessage).filter(OrderMessage.order_id == order_id, OrderMessage.admin_id == admin_id).first()
        if row:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json={"chat_id": admin_id, "message_id": row.message_id, "text": new_text, "parse_mode": "Markdown"}, timeout=10)
            except Exception as e:
                print(f"[edit_message] Erreur admin {admin_id} msg {row.message_id}: {e}")
    except Exception as e:
        print("Erreur edit_admin_notification:", e)
    finally:
        session.close()

def edit_all_admin_notifications(order_id: int, new_text: str):
    if not BOT_TOKEN:
        return
    session = SessionLocal()
    try:
        rows = session.query(OrderMessage).filter(OrderMessage.order_id == order_id).all()
        for om in rows:
            try:
                requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText", json={"chat_id": om.admin_id, "message_id": om.message_id, "text": new_text, "parse_mode": "Markdown"}, timeout=10)
            except Exception as e:
                print(f"[edit_message] Erreur admin {om.admin_id} msg {om.message_id}: {e}")
    except Exception as e:
        print("Erreur edit_all_admin_notifications:", e)
    finally:
        session.close()

def resend_order_to_all_admins(order_id: int):
    if not BOT_TOKEN:
        return
    session = SessionLocal()
    try:
        o = session.get(Order, order_id)
        if not o:
            return
        admin_text = f"🔔 *COMMANDE #{order_id} REMISE EN LIGNE*\n\n"
        if o.username:
            admin_text += f"👤 @{o.username}\n"
        else:
            admin_text += f"👤 ID: {o.user_id}\n"
        admin_text += (f"📦 {o.service}\n" f"📋 {o.plan}\n" f"💰 {o.price}€\n" f"💵 Coût: {o.cost}€\n" f"📈 Bénéf: {(o.price or 0) - (o.cost or 0)}€\n\n" f"👤 {o.first_name} {o.last_name}\n" f"📧 {o.email}\n")
        if o.payment_method:
            admin_text += f"💳 {o.payment_method}\n"
        admin_text += f"\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"

        keyboard = [[{"text": "✋ Prendre", "callback_data": f"admin_take_{order_id}"}, {"text": "❌ Annuler", "callback_data": f"admin_cancel_{order_id}"}]]
        for admin_id in ADMIN_IDS:
            try:
                response = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": admin_id, "text": admin_text, "parse_mode": "Markdown", "reply_markup": {"inline_keyboard": keyboard}}, timeout=10)
                result = response.json()
                if result.get('ok'):
                    message_id = result['result']['message_id']
                    om = OrderMessage(order_id=order_id, admin_id=admin_id, message_id=message_id)
                    session.add(om)
            except Exception as e:
                print(f"Erreur envoi admin {admin_id}: {e}")
        session.commit()
    except Exception as e:
        print("Erreur resend_order_to_all_admins:", e)
    finally:
        session.close()

async def resend_order_to_all_admins_async(context, order_id, service_name, plan_label, price, cost, username, user_id, first_name, last_name, email, payment_method):
    admin_text = f"🔔 *COMMANDE #{order_id} REMISE EN LIGNE*\n\n"
    if username:
        admin_text += f"👤 @{username}\n"
    else:
        admin_text += f"👤 ID: {user_id}\n"
    admin_text += (f"📦 {service_name}\n" f"📋 {plan_label}\n" f"💰 {price}€\n" f"💵 Coût: {cost}€\n" f"📈 Bénéf: {price - cost}€\n\n" f"👤 {first_name} {last_name}\n" f"📧 {email}\n")
    if payment_method:
        admin_text += f"💳 {payment_method}\n"
    admin_text += f"\n🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"), InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}")]])
    session = SessionLocal()
    try:
        for admin_id in ADMIN_IDS:
            try:
                msg = await context.bot.send_message(chat_id=admin_id, text=admin_text, parse_mode='Markdown', reply_markup=keyboard)
                om = OrderMessage(order_id=order_id, admin_id=admin_id, message_id=msg.message_id)
                session.add(om)
            except Exception as e:
                print(f"Erreur envoi admin {admin_id}: {e}")
        session.commit()
    except Exception as e:
        session.rollback()
    finally:
        session.close()

# Telegram handlers use SERVICES_CONFIG_IN_MEMORY
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"User_{user_id}"
    first_name = update.message.from_user.first_name or "Utilisateur"
    last_name = update.message.from_user.last_name or ""
    update_user_activity(user_id, username, first_name, last_name)
    keyboard = [
        [InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],
        [InlineKeyboardButton("🎧 Musique (Spotify, Deezer)", callback_data="cat_music")],
        [InlineKeyboardButton("🤖 IA (ChatGPT+)", callback_data="cat_ai")],
        [InlineKeyboardButton("🍎 Apple (TV + Music)", callback_data="cat_apple")],
        [InlineKeyboardButton("🏋️ Basic Fit", callback_data="cat_basic_fit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    welcome_text = ("🎯 *Bienvenue sur B4U Deals !*\n\nProfite de nos offres premium à prix réduits :\n• Comptes streaming\n• Abonnements musique\n• Services IA\n• Services Apple\n• Abonnements fitness\n\nChoisis une catégorie pour commencer :")
    try:
        image_url = "https://raw.githubusercontent.com/Noallo312/serveur_express_bot/refs/heads/main/514B1CC0-791F-47CA-825C-F82A4100C02E.png"
        await update.message.reply_photo(photo=image_url, caption=welcome_text, parse_mode='Markdown', reply_markup=reply_markup)
    except Exception as e:
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
    update_user_activity(user_id, username, first_name, last_name)

    if data.startswith("cat_"):
        category = data.replace("cat_", "")
        keyboard = []
        for service_key, service_data in SERVICES_CONFIG_IN_MEMORY.items():
            if service_data['active'] and service_data.get('visible', True) and service_data['category'] == category:
                keyboard.append([InlineKeyboardButton(service_data['name'], callback_data=f"service_{service_key}")])
        keyboard.append([InlineKeyboardButton("⬅️ Retour au menu", callback_data="back_to_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        category_labels = {'streaming': '🎬 Streaming', 'music': '🎧 Musique', 'ai': '🤖 Intelligence Artificielle', 'apple': '🍎 Apple', 'basic_fit': '🏋️ Basic Fit'}
        await query.edit_message_caption(caption=f"*{category_labels.get(category, category)}*\n\nChoisis ton service :", parse_mode='Markdown', reply_markup=reply_markup)
        return

    if data.startswith("service_"):
        service_key = data.replace("service_", "")
        service = SERVICES_CONFIG_IN_MEMORY[service_key]
        keyboard = []
        for plan_key, plan_data in service['plans'].items():
            keyboard.append([InlineKeyboardButton(f"{plan_data['label']} - {plan_data['price']}€", callback_data=f"plan_{service_key}_{plan_key}")])
        keyboard.append([InlineKeyboardButton("⬅️ Retour", callback_data=f"cat_{service['category']}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_caption(caption=f"*{service['name']}*\n\nChoisis ton abonnement :", parse_mode='Markdown', reply_markup=reply_markup)
        return

    if data.startswith("plan_"):
        parts = data.replace("plan_", "").split("_")
        service_key = parts[0]
        plan_key = "_".join(parts[1:])
        service = SERVICES_CONFIG_IN_MEMORY[service_key]
        plan = service['plans'][plan_key]
        user_states[user_id] = {'service': service_key, 'plan': plan_key, 'service_name': service['name'], 'plan_label': plan['label'], 'price': plan['price'], 'cost': plan['cost'], 'step': 'waiting_form'}
        if service_key == 'deezer':
            await query.message.reply_text(f"✅ *Commande confirmée*\n\nService: {service['name']}\nPlan: {plan['label']}\nPrix: {plan['price']}€\n\n📝 Envoie ton nom, prénom et mail (chacun sur une ligne)", parse_mode='Markdown')
            user_states[user_id]['step'] = 'waiting_deezer_form'
            return
        else:
            form_text = (f"✅ *{plan['label']} - {plan['price']}€*\n\n📝 *Formulaire de commande*\n\nEnvoie-moi les informations suivantes (une par ligne) :\n\n1️⃣ Nom\n2️⃣ Prénom\n3️⃣ Adresse email\n4️⃣ Moyen de paiement (PayPal / Virement / Revolut)\n\n📌 Exemple :\nDupont\nJean\njean.dupont@email.com\nPayPal")
            await query.message.reply_text(form_text, parse_mode='Markdown')
            return

    if data == "back_to_menu":
        keyboard = [[InlineKeyboardButton("🎬 Streaming (Netflix, HBO, Disney+...)", callback_data="cat_streaming")],[InlineKeyboardButton("🎧 Musique (Spotify, Deezer)", callback_data="cat_music")],[InlineKeyboardButton("🤖 IA (ChatGPT+)", callback_data="cat_ai")],[InlineKeyboardButton("🍎 Apple (TV + Music)", callback_data="cat_apple")],[InlineKeyboardButton("🏋️ Basic Fit", callback_data="cat_basic_fit")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_caption(caption="🎯 *B4U Deals*\n\nChoisis une catégorie :", parse_mode='Markdown', reply_markup=reply_markup)
        return

 # À ajouter dans la fonction button_callback, après les autres conditions

    # Admin prend la commande
    if data.startswith("admin_take_"):
        order_id = int(data.replace("admin_take_", ""))
        admin_id = query.from_user.id
        admin_username = query.from_user.username or f"Admin_{admin_id}"
        
        session = SessionLocal()
        try:
            order = session.get(Order, order_id)
            if not order:
                await query.answer("❌ Commande introuvable", show_alert=True)
                session.close()
                return
            
            if order.status != 'en_attente':
                await query.answer("❌ Commande déjà prise", show_alert=True)
                session.close()
                return
            
            # Mettre à jour la commande
            order.status = 'en_cours'
            order.admin_id = admin_id
            order.admin_username = admin_username
            order.taken_at = datetime.now().isoformat()
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erreur prise commande: {e}")
            await query.answer("❌ Erreur", show_alert=True)
            session.close()
            return
        finally:
            session.close()
        
        # Supprimer les notifications des autres admins
        delete_other_admin_notifications(order_id, admin_id)
        
        # Modifier le message de l'admin qui a pris
        taken_text = (
            f"🔒 *COMMANDE #{order_id} — PRISE EN CHARGE*\n\n"
            f"✅ Pris en charge par @{admin_username}\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Terminer", callback_data=f"admin_complete_{order_id}"),
                InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}")
            ],
            [
                InlineKeyboardButton("🔄 Remettre", callback_data=f"admin_restore_{order_id}")
            ]
        ])
        
        await query.edit_message_text(text=taken_text, parse_mode='Markdown', reply_markup=keyboard)
        await query.answer("✅ Commande prise en charge")
        return
    
    # Admin termine la commande
    if data.startswith("admin_complete_"):
        order_id = int(data.replace("admin_complete_", ""))
        
        session = SessionLocal()
        try:
            order = session.get(Order, order_id)
            if not order:
                await query.answer("❌ Commande introuvable", show_alert=True)
                session.close()
                return
            
            price = order.price or 0.0
            cost = order.cost or 0.0
            
            # Mettre à jour les stats cumulatives
            cs = session.get(CumulativeStats, 1)
            if cs:
                cs.total_revenue = (cs.total_revenue or 0.0) + price
                cs.total_profit = (cs.total_profit or 0.0) + (price - cost)
                cs.last_updated = datetime.now().isoformat()
            
            order.status = 'terminee'
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erreur terminer commande: {e}")
            await query.answer("❌ Erreur", show_alert=True)
            session.close()
            return
        finally:
            session.close()
        
        # Modifier tous les messages admin
        completed_text = (
            f"✅ *COMMANDE #{order_id} — TERMINÉE*\n\n"
            f"Terminée par @{query.from_user.username or 'Admin'}\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        edit_all_admin_notifications(order_id, completed_text)
        await query.answer("✅ Commande terminée")
        return
    
    # Admin annule la commande
    if data.startswith("admin_cancel_"):
        order_id = int(data.replace("admin_cancel_", ""))
        
        session = SessionLocal()
        try:
            order = session.get(Order, order_id)
            if not order:
                await query.answer("❌ Commande introuvable", show_alert=True)
                session.close()
                return
            
            order.status = 'annulee'
            order.cancelled_by = query.from_user.id
            order.cancelled_at = datetime.now().isoformat()
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erreur annulation commande: {e}")
            await query.answer("❌ Erreur", show_alert=True)
            session.close()
            return
        finally:
            session.close()
        
        # Modifier tous les messages admin
        cancelled_text = (
            f"❌ *COMMANDE #{order_id} — ANNULÉE*\n\n"
            f"Annulée par @{query.from_user.username or 'Admin'}\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        edit_all_admin_notifications(order_id, cancelled_text)
        await query.answer("❌ Commande annulée")
        return
    
    # Admin remet la commande en ligne
    if data.startswith("admin_restore_"):
        order_id = int(data.replace("admin_restore_", ""))
        
        session = SessionLocal()
        try:
            order = session.get(Order, order_id)
            if not order:
                await query.answer("❌ Commande introuvable", show_alert=True)
                session.close()
                return
            
            # Récupérer les infos avant de remettre en attente
            service_name = order.service
            plan_label = order.plan
            price = order.price
            cost = order.cost
            username_order = order.username
            user_id_order = order.user_id
            first_name_order = order.first_name
            last_name_order = order.last_name
            email_order = order.email
            payment_method_order = order.payment_method
            
            # Remettre en attente
            order.status = 'en_attente'
            order.admin_id = None
            order.admin_username = None
            order.taken_at = None
            
            # Supprimer les anciens messages admin
            session.query(OrderMessage).filter(OrderMessage.order_id == order_id).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erreur remise en ligne: {e}")
            await query.answer("❌ Erreur", show_alert=True)
            session.close()
            return
        finally:
            session.close()
        
        # Renvoyer aux admins
        await resend_order_to_all_admins_async(
            context, order_id, service_name, plan_label, price, cost,
            username_order, user_id_order, first_name_order, last_name_order,
            email_order, payment_method_order
        )
        
        await query.answer("🔄 Commande remise en ligne")
        return

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or f"User_{user_id}"
    first_name = update.message.from_user.first_name or "Utilisateur"
    last_name = update.message.from_user.last_name or ""
    update_user_activity(user_id, username, first_name, last_name)
    
    if user_id not in user_states:
        await update.message.reply_text("⚠️ Utilise /start pour commencer une commande")
        return
    
    state = user_states[user_id]
    text = update.message.text.strip()
    
    # Traitement formulaire Deezer (3 lignes: nom, prénom, email)
    if state.get('step') == 'waiting_deezer_form':
        lines = text.split('\n')
        if len(lines) < 3:
            await update.message.reply_text("❌ Format incorrect. Envoie 3 lignes:\n1. Nom\n2. Prénom\n3. Email")
            return
        
        last_name_input = lines[0].strip()
        first_name_input = lines[1].strip()
        email = lines[2].strip()
        
        # Créer la commande dans la DB
        session = SessionLocal()
        try:
            order = Order(
                user_id=user_id,
                username=username,
                service=state['service_name'],
                plan=state['plan_label'],
                price=state['price'],
                cost=state['cost'],
                first_name=first_name_input,
                last_name=last_name_input,
                email=email,
                payment_method=None,
                timestamp=datetime.now().isoformat(),
                status='en_attente'
            )
            session.add(order)
            session.flush()
            order_id = order.id
            
            # Mettre à jour le compteur de commandes de l'utilisateur
            user = session.get(User, user_id)
            if user:
                user.total_orders = (user.total_orders or 0) + 1
            
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erreur création commande Deezer: {e}")
            await update.message.reply_text("❌ Erreur lors de la création de la commande")
            session.close()
            return
        finally:
            session.close()
        
        # Confirmation client
        await update.message.reply_text(
            f"✅ *Commande #{order_id} enregistrée !*\n\n"
            f"📦 {state['service_name']}\n"
            f"📋 {state['plan_label']}\n"
            f"💰 {state['price']}€\n\n"
            f"👤 {first_name_input} {last_name_input}\n"
            f"📧 {email}\n\n"
            f"⏳ Un admin va te contacter rapidement !",
            parse_mode='Markdown'
        )
        
        # Notification admins
        admin_text = (
            f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n"
            f"👤 @{username}\n"
            f"📦 {state['service_name']}\n"
            f"📋 {state['plan_label']}\n"
            f"💰 {state['price']}€\n"
            f"💵 Coût: {state['cost']}€\n"
            f"📈 Bénéf: {state['price'] - state['cost']}€\n\n"
            f"👤 {first_name_input} {last_name_input}\n"
            f"📧 {email}\n\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"),
                InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}")
            ]
        ])
        
        session = SessionLocal()
        try:
            for admin_id in ADMIN_IDS:
                try:
                    msg = await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                    om = OrderMessage(order_id=order_id, admin_id=admin_id, message_id=msg.message_id)
                    session.add(om)
                except Exception as e:
                    print(f"Erreur envoi admin {admin_id}: {e}")
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()
        
        del user_states[user_id]
        return
    
    # Traitement formulaire standard (4 lignes: nom, prénom, email, paiement)
    if state.get('step') == 'waiting_form':
        lines = text.split('\n')
        if len(lines) < 4:
            await update.message.reply_text(
                "❌ Format incorrect. Envoie 4 lignes:\n"
                "1. Nom\n"
                "2. Prénom\n"
                "3. Email\n"
                "4. Moyen de paiement (PayPal/Virement/Revolut)"
            )
            return
        
        last_name_input = lines[0].strip()
        first_name_input = lines[1].strip()
        email = lines[2].strip()
        payment_method = lines[3].strip()
        
        # Créer la commande dans la DB
        session = SessionLocal()
        try:
            order = Order(
                user_id=user_id,
                username=username,
                service=state['service_name'],
                plan=state['plan_label'],
                price=state['price'],
                cost=state['cost'],
                first_name=first_name_input,
                last_name=last_name_input,
                email=email,
                payment_method=payment_method,
                timestamp=datetime.now().isoformat(),
                status='en_attente'
            )
            session.add(order)
            session.flush()
            order_id = order.id
            
            # Mettre à jour le compteur de commandes de l'utilisateur
            user = session.get(User, user_id)
            if user:
                user.total_orders = (user.total_orders or 0) + 1
            
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Erreur création commande: {e}")
            await update.message.reply_text("❌ Erreur lors de la création de la commande")
            session.close()
            return
        finally:
            session.close()
        
        # Confirmation client
        await update.message.reply_text(
            f"✅ *Commande #{order_id} enregistrée !*\n\n"
            f"📦 {state['service_name']}\n"
            f"📋 {state['plan_label']}\n"
            f"💰 {state['price']}€\n\n"
            f"👤 {first_name_input} {last_name_input}\n"
            f"📧 {email}\n"
            f"💳 {payment_method}\n\n"
            f"⏳ Un admin va te contacter rapidement !",
            parse_mode='Markdown'
        )
        
        # Notification admins
        admin_text = (
            f"🔔 *NOUVELLE COMMANDE #{order_id}*\n\n"
            f"👤 @{username}\n"
            f"📦 {state['service_name']}\n"
            f"📋 {state['plan_label']}\n"
            f"💰 {state['price']}€\n"
            f"💵 Coût: {state['cost']}€\n"
            f"📈 Bénéf: {state['price'] - state['cost']}€\n\n"
            f"👤 {first_name_input} {last_name_input}\n"
            f"📧 {email}\n"
            f"💳 {payment_method}\n\n"
            f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✋ Prendre", callback_data=f"admin_take_{order_id}"),
                InlineKeyboardButton("❌ Annuler", callback_data=f"admin_cancel_{order_id}")
            ]
        ])
        
        session = SessionLocal()
        try:
            for admin_id in ADMIN_IDS:
                try:
                    msg = await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                    om = OrderMessage(order_id=order_id, admin_id=admin_id, message_id=msg.message_id)
                    session.add(om)
                except Exception as e:
                    print(f"Erreur envoi admin {admin_id}: {e}")
            session.commit()
        except Exception as e:
            session.rollback()
        finally:
            session.close()
        
        del user_states[user_id]
        return

# BOT TELEGRAM MAIN
def run_bot():
    if not BOT_TOKEN:
        print("BOT_TOKEN non défini")
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    print("🤖 Bot Telegram démarré")
    application.run_polling(drop_pending_updates=True, stop_signals=None)

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 Serveur Flask démarré sur le port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
