import os
import threading
import sqlite3
import csv
from datetime import datetime
from io import StringIO
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# ---------------------------
# Flask (pour le port web)
# ---------------------------
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot Telegram actif !"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

# ---------------------------
# Configuration
# ---------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMINS = [6976573567, 6193535472]

# ---------------------------
# Base de données SQLite
# ---------------------------
def init_db():
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prenom TEXT,
            nom TEXT,
            username TEXT,
            prix REAL,
            adresse TEXT,
            paiement TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_commande(user_id, prenom, nom, username, prix, adresse, paiement):
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        INSERT INTO commandes (user_id, prenom, nom, username, prix, adresse, paiement, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, prenom, nom, username, prix, adresse, paiement, date))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    
    # Total commandes
    c.execute('SELECT COUNT(*), SUM(prix) FROM commandes')
    total, ca_total = c.fetchone()
    total = total or 0
    ca_total = ca_total or 0
    
    # Aujourd'hui
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute('SELECT COUNT(*), SUM(prix) FROM commandes WHERE date LIKE ?', (f"{today}%",))
    today_count, today_ca = c.fetchone()
    today_count = today_count or 0
    today_ca = today_ca or 0
    
    # Ce mois
    this_month = datetime.now().strftime("%Y-%m")
    c.execute('SELECT COUNT(*), SUM(prix) FROM commandes WHERE date LIKE ?', (f"{this_month}%",))
    month_count, month_ca = c.fetchone()
    month_count = month_count or 0
    month_ca = month_ca or 0
    
    conn.close()
    
    return {
        'total': total,
        'ca_total': ca_total,
        'today': today_count,
        'today_ca': today_ca,
        'month': month_count,
        'month_ca': month_ca
    }

def get_historique(limit=10):
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute('''
        SELECT prenom, nom, username, prix, adresse, paiement, date 
        FROM commandes 
        ORDER BY id DESC 
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_user_ids():
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute('SELECT DISTINCT user_id FROM commandes')
    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]

def export_commandes():
    conn = sqlite3.connect('commandes.db')
    c = conn.cursor()
    c.execute('SELECT * FROM commandes ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

# ---------------------------
# Commandes
# ---------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛒 Nouvelle commande", callback_data='order')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🍔 *Bienvenue sur Serveur Express !*\n\n"
        "Commandez vos repas à prix réduit. 🔥\n\n"
        "📝 Cliquez sur le bouton ci-dessous pour commander.",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ Commande réservée aux admins.")
        return
    
    stats = get_stats()
    
    benef_total = stats['total'] * 5
    benef_month = stats['month'] * 5
    benef_today = stats['today'] * 5
    
    message = (
        "📊 *STATISTIQUES DU SERVICE*\n\n"
        f"📦 Total commandes : *{stats['total']}*\n"
        f"📅 Aujourd'hui : *{stats['today']}*\n"
        f"📆 Ce mois : *{stats['month']}*\n\n"
        f"💰 Chiffre d'affaires total : *{stats['ca_total']:.2f} €*\n"
        f"💵 Bénéfices totaux : *{benef_total:.2f} €* ({stats['total']} × 5€)\n"
        f"📈 Bénéfices du mois : *{benef_month:.2f} €* ({stats['month']} × 5€)\n"
        f"🎯 Bénéfices aujourd'hui : *{benef_today:.2f} €* ({stats['today']} × 5€)"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def historique_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ Commande réservée aux admins.")
        return
    
    rows = get_historique(10)
    
    if not rows:
        await update.message.reply_text("📜 Aucune commande dans l'historique.")
        return
    
    message = "📜 *HISTORIQUE DES COMMANDES* (10 dernières)\n\n"
    
    for i, row in enumerate(rows, 1):
        prenom, nom, username, prix, adresse, paiement, date = row
        username_str = f"@{username}" if username else "N/A"
        adresse_courte = adresse[:30] + "..." if len(adresse) > 30 else adresse
        
        message += (
            f"*{i}.* {prenom} {nom} ({username_str})\n"
            f"   💰 {prix}€ | 💳 {paiement}\n"
            f"   🏠 {adresse_courte}\n"
            f"   📅 {date}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ Commande réservée aux admins.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ Usage : /broadcast [votre message]\n\n"
            "Exemple : /broadcast Promo -2€ ce weekend ! 🎉"
        )
        return
    
    message_to_send = " ".join(context.args)
    user_ids = get_all_user_ids()
    
    if not user_ids:
        await update.message.reply_text("❌ Aucun client dans la base de données.")
        return
    
    await update.message.reply_text(f"📢 Envoi en cours à {len(user_ids)} clients...")
    
    sent = 0
    failed = 0
    
    for uid in user_ids:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 *Message de Serveur Express*\n\n{message_to_send}",
                parse_mode='Markdown'
            )
            sent += 1
        except Exception as e:
            failed += 1
    
    await update.message.reply_text(
        f"✅ Broadcast terminé !\n\n"
        f"✅ Envoyés : {sent}\n"
        f"❌ Échecs : {failed}"
    )

async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if user_id not in ADMINS:
        await update.message.reply_text("❌ Commande réservée aux admins.")
        return
    
    rows = export_commandes()
    
    if not rows:
        await update.message.reply_text("❌ Aucune commande à exporter.")
        return
    
    # Créer le CSV en mémoire
    output = StringIO()
    writer = csv.writer(output)
    
    # En-têtes
    writer.writerow(['ID', 'User_ID', 'Prénom', 'Nom', 'Username', 'Prix', 'Adresse', 'Paiement', 'Date'])
    
    # Données
    for row in rows:
        writer.writerow(row)
    
    # Récupérer le contenu
    csv_content = output.getvalue()
    output.close()
    
    # Nom du fichier avec date/heure
    filename = f"commandes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    # Envoyer le fichier
    await update.message.reply_document(
        document=csv_content.encode('utf-8'),
        filename=filename,
        caption=f"📊 Export de {len(rows)} commandes"
    )

# ---------------------------
# Gestion des commandes
# ---------------------------
async def bouton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'order':
        context.user_data['step'] = 'photo'
        await query.message.reply_text(
            "📸 *Étape 1/4*\n\n"
            "Envoyez une photo de votre panier.",
            parse_mode='Markdown'
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('step') != 'photo':
        return
    
    photo = update.message.photo[-1]
    context.user_data['photo'] = photo.file_id
    context.user_data['step'] = 'prix'
    
    await update.message.reply_text(
        "💰 *Étape 2/4*\n\n"
        "Quel est le prix de votre commande ?\n"
        "(Entre 20€ et 23€)",
        parse_mode='Markdown'
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('step')
    
    if step == 'prix':
        try:
            prix = float(update.message.text.replace(',', '.'))
            if 20 <= prix <= 23:
                context.user_data['prix'] = prix
                context.user_data['step'] = 'adresse'
                await update.message.reply_text(
                    "🏠 *Étape 3/4*\n\n"
                    "Quelle est votre adresse de livraison ?",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Le prix doit être entre 20€ et 23€.")
        except ValueError:
            await update.message.reply_text("❌ Veuillez entrer un prix valide (ex: 21.5)")
    
    elif step == 'adresse':
        context.user_data['adresse'] = update.message.text
        context.user_data['step'] = 'paiement'
        
        keyboard = [
            [InlineKeyboardButton("💳 PayPal", callback_data='pay_paypal')],
            [InlineKeyboardButton("🏦 Virement", callback_data='pay_virement')],
            [InlineKeyboardButton("💸 Revolut", callback_data='pay_revolut')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💳 *Étape 4/4*\n\n"
            "Choisissez votre mode de paiement :",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

async def handle_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    payment_methods = {
        'pay_paypal': 'PayPal',
        'pay_virement': 'Virement',
        'pay_revolut': 'Revolut'
    }
    
    paiement = payment_methods.get(query.data)
    
    if paiement:
        context.user_data['paiement'] = paiement
        
        user = query.from_user
        user_id = user.id
        prenom = user.first_name or "N/A"
        nom = user.last_name or ""
        username = user.username or "N/A"
        
        info = context.user_data
        
        # Sauvegarder dans la base de données
        save_commande(
            user_id=user_id,
            prenom=prenom,
            nom=nom,
            username=username,
            prix=info['prix'],
            adresse=info['adresse'],
            paiement=paiement
        )
        
        # Message pour le client
        await query.message.reply_text(
            "✅ *Commande envoyée !*\n\n"
            "Nous allons traiter votre demande rapidement. 🚀\n"
            "Vous serez contacté pour le paiement.",
            parse_mode='Markdown'
        )
        
        # Message pour les admins avec infos du client
        caption = (
            "📦 *Nouvelle commande reçue* 🔔\n\n"
            f"👤 *Client :* {prenom} {nom}\n"
            f"📱 *Username :* @{username}\n"
            f"🆔 *ID Telegram :* `{user_id}`\n\n"
            f"💰 *Prix :* {info['prix']} €\n"
            f"🏠 *Adresse :* {info['adresse']}\n"
            f"💳 *Paiement :* {paiement}"
        )
        
        for admin_id in ADMINS:
            try:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=info['photo'],
                    caption=caption,
                    parse_mode='Markdown'
                )
            except Exception as e:
                print(f"Erreur envoi admin {admin_id}: {e}")
        
        context.user_data.clear()

# ---------------------------
# Main
# ---------------------------
def main():
    # Initialiser la base de données
    init_db()
    
    # Démarrer Flask dans un thread séparé
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("🤖 Bot Telegram démarré...")
    
    # Créer l'application Telegram
    app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Commandes
    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("stats", stats_command))
    app_bot.add_handler(CommandHandler("historique", historique_command))
    app_bot.add_handler(CommandHandler("broadcast", broadcast_command))
    app_bot.add_handler(CommandHandler("export", export_command))
    
    # Gestion du flux de commande
    app_bot.add_handler(CallbackQueryHandler(bouton, pattern='^order$'))
    app_bot.add_handler(CallbackQueryHandler(handle_payment, pattern='^pay_'))
    app_bot.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Démarrer le bot
    app_bot.run_polling()

if __name__ == '__main__':
    main()
